"""Viam point-cloud camera backed by the existing sensor's buffered raw ADC."""
import asyncio
import copy
import time
from typing import ClassVar

from google.protobuf.timestamp_pb2 import Timestamp
from viam.components.camera import Camera
from viam.components.sensor import Sensor
from viam.media.video import CameraMimeType, NamedImage, ViamImage
from viam.proto.common import ResponseMetadata
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import struct_to_dict

from .cloud import PCD_MIME, camera_settings, reconstruct
from .raw_frame import decode_raw


class MmwavePointCloud(Camera, EasyResource):
    MODEL: ClassVar[Model] = Model(ModelFamily('carlyworkspace','upenn-mmwave'),'mmwave-pointcloud')

    @classmethod
    def validate_config(cls,config):
        settings=camera_settings(struct_to_dict(config.attributes))
        if settings['sensor']==config.name:
            raise ValueError('Camera and sensor must have different resource names')
        return [settings['sensor']],[]

    @classmethod
    def new(cls,config,dependencies):
        cls.validate_config(config)
        self=super().new(config,dependencies)
        self.settings=camera_settings(struct_to_dict(config.attributes))
        resource_name=Sensor.get_resource_name(self.settings['sensor'])
        if resource_name not in dependencies:
            raise ValueError(f'Missing sensor dependency: {self.settings["sensor"]}')
        self.source=dependencies[resource_name]
        if not isinstance(self.source,Sensor):
            raise ValueError('The camera dependency must implement the Sensor API')
        self._lock=asyncio.Lock()
        self._cached=None
        self._closed=False
        return self

    async def _snapshot(self,timeout=None):
        started=time.monotonic()
        async with self._lock:
            if self._closed:
                raise RuntimeError('Radar camera is closed')
            remaining=None if timeout is None else timeout-(time.monotonic()-started)
            if remaining is not None and remaining<=0:
                raise TimeoutError('Radar camera request timed out waiting for processing')
            fetched=time.monotonic()
            try:
                request=self.source.do_command({'command':'raw_frame'},timeout=remaining)
                packet=await request if remaining is None else await asyncio.wait_for(request,remaining)
                _,_,metadata=decode_raw(packet,self.settings['max_frame_age_s'])
                key=(metadata['frame_id'],metadata['config_sha256'])
                if self._cached is None or self._cached['key']!=key:
                    result=await asyncio.to_thread(reconstruct,packet,self.settings)
                    result['key']=key
                    self._cached=result
                result=self._cached
                age=metadata['source_age_s']+(time.monotonic()-fetched)
                if age>metadata['maximum_age_s']:
                    raise RuntimeError('Radar frame became stale during point-cloud processing')
                if timeout is not None and time.monotonic()-started>timeout:
                    raise TimeoutError('Radar point-cloud processing exceeded the requested timeout')
                if self._closed:
                    raise RuntimeError('Radar camera is closed')
                result['status'].update(healthy=True,frame_age_s=age)
                return result
            except BaseException:
                self._cached=None
                raise

    async def get_point_cloud(self,*,extra=None,timeout=None,**kwargs):
        result=await self._snapshot(timeout)
        return result['pcd'],PCD_MIME

    async def get_images(self,*,filter_source_names=None,extra=None,timeout=None,**kwargs):
        result=await self._snapshot(timeout)
        stamp=Timestamp();stamp.FromNanoseconds(round(result['metadata']['captured_at_unix']*1e9))
        images=[]
        if not filter_source_names or 'radar-topdown' in filter_source_names:
            images=[NamedImage('radar-topdown',result['png'],CameraMimeType.PNG)]
        return images,ResponseMetadata(captured_at=stamp)

    async def get_image(self,mime_type='',*,extra=None,timeout=None,**kwargs):
        if mime_type not in ('','image/png'):
            raise ValueError('Radar preview supports image/png only')
        result=await self._snapshot(timeout)
        return ViamImage(result['png'],CameraMimeType.PNG)

    async def get_properties(self,*,timeout=None,**kwargs):
        # Opt out of the hosted viewer's empty-cloud crash by default.
        # Direct GetPointCloud calls still return measured XYZ, including empty frames.
        return Camera.Properties(
            supports_pcd=self.settings['native_pointcloud_viewer'],
            mime_types=['image/png'])

    async def do_command(self,command,*,timeout=None,**kwargs):
        name=command.get('command')
        if name not in ('status','points','diagnostics'):
            raise ValueError('Supported camera commands: status, points, diagnostics')
        result=await self._snapshot(timeout)
        output=copy.deepcopy(result['status'])
        if name=='points':output['points']=copy.deepcopy(result['points'])
        if name=='diagnostics':output['reconstruction']=copy.deepcopy(result['diagnostics'])
        return output

    async def get_status(self,*,timeout=None,**kwargs):
        try:
            return await self.do_command({'command':'status'},timeout=timeout)
        except Exception as error:
            return {'healthy':False,'error':str(error),'point_count':0}

    async def get_geometries(self,*,extra=None,timeout=None):
        return []

    async def close(self):
        self._closed=True
        self._cached=None
        # The sensor owns acquisition. Closing a camera never closes its dependency.
