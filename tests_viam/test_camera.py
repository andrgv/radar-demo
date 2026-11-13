import asyncio
import base64
import copy
import io
import json
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
from PIL import Image
from google.protobuf.struct_pb2 import Struct
from viam.components.sensor import Sensor
from viam.components.camera import Camera
from viam.proto.app.robot import ComponentConfig
from viam.proto.component.camera import GetPointCloudResponse
from viam.resource.registry import Registry
from viam.utils import dict_to_struct, struct_to_dict
from radar.config import Config
from radar.synthetic import Target, generate
from viam_module.camera import MmwavePointCloud
from viam_module.cloud import camera_settings, encode_pcd, reconstruct, PCD_MIME
from viam_module.raw_frame import encode_raw, decode_raw

CFG=Config(sample_rate_hz=5e6,slope_hz_s=33691406250000,
           geometry_mm=[[0,0],[0,2.35],[-2.35,0]])


def packet(targets=None,frame_id='test:1'):
    frame=generate(CFG,targets=targets if targets is not None else [Target(1.4,azimuth_deg=20,elevation_deg=10)],seed=1,noise=5)
    return encode_raw(frame,CFG,frame_id=frame_id,captured_at_unix=time.time(),age=.01,stale_after=1)


def pcd_points(data):
    header,body=data.split(b'DATA ascii\n',1)
    n=int(next(line.split()[1] for line in header.splitlines() if line.startswith(b'POINTS ')))
    assert b'FIELDS x y z\n' in header
    assert b'SIZE 4 4 4\nTYPE F F F\nCOUNT 1 1 1\n' in header
    assert f'WIDTH {n}\n'.encode() in header
    rows=[tuple(map(float,line.split())) for line in body.splitlines()]
    assert len(rows)==n
    assert all(len(row)==3 for row in rows)
    return np.array(rows,dtype=[('x','<f4'),('y','<f4'),('z','<f4')])



class RawAndCloudTests(unittest.TestCase):
    def test_protobuf_roundtrip_preserves_adc_config_and_integers(self):
        original=packet()
        transported=struct_to_dict(dict_to_struct(original))
        frame,cfg,metadata=decode_raw(transported,1)
        self.assertEqual(cfg.samples,64);self.assertIsInstance(cfg.samples,int)
        np.testing.assert_array_equal(frame.adc,np.frombuffer(base64.b64decode(original['adc_base64']),dtype='<u2').reshape(17,64,3))
        self.assertEqual(metadata['frame_id'],'test:1')

    def test_pcd_meters_and_optical_orientation(self):
        points=pcd_points(encode_pcd([[.1,2,.3]],[20]))
        self.assertAlmostEqual(points['x'][0],.1,places=6)
        self.assertAlmostEqual(points['y'][0],-.3,places=6)
        self.assertAlmostEqual(points['z'][0],2,places=6)
        self.assertEqual(len(pcd_points(encode_pcd([],[]))),0)

    def test_invalid_raw_packets_and_staleness(self):
        for changes in [dict(schema='bad'),dict(adc_base64='invalid!!'),dict(frame_age_s=2),
                        dict(flags=9),dict(errors=1),dict(profile_id=0),
                        dict(radar_config_sha256='incorrect'),dict(captured_at_unix=float('nan'))]:
            with self.subTest(changes=changes),self.assertRaises((ValueError,RuntimeError)):
                decode_raw(dict(packet(),**changes),1)

    def test_reconstruction_separates_stationary_subbin_returns(self):
        step=CFG.ranges[1]
        targets=[Target(3.2*step,azimuth_deg=-25,elevation_deg=10),
                 Target(3.9*step,azimuth_deg=30,elevation_deg=-15,amplitude=1400)]
        result=reconstruct(packet(targets),camera_settings({'sensor':'radar'}))
        points=pcd_points(result['pcd'])
        self.assertEqual(len(points),2)
        for point,target in zip(points,targets):
            xyz=np.array([point['x'],point['z'],-point['y']])
            self.assertAlmostEqual(np.linalg.norm(xyz),target.range_m,delta=.02)
            self.assertAlmostEqual(np.degrees(np.arctan2(xyz[0],xyz[1])),target.azimuth_deg,delta=5.1)
        self.assertFalse(result['status']['temporal_accumulation'])
        self.assertFalse(result['status']['angle_calibrated'])
        json.dumps(result['status'],allow_nan=False)
        json.dumps(result['diagnostics'],allow_nan=False)

    def test_empty_frame_does_not_hold_previous_points(self):
        settings=camera_settings({'sensor':'radar'})
        self.assertGreater(reconstruct(packet(),settings)['status']['point_count'],0)
        result=reconstruct(packet([],'test:2'),settings)
        self.assertEqual(len(pcd_points(result['pcd'])),0)
        self.assertEqual(result['points'],[])

    def test_range_filter_and_point_cap(self):
        p=packet([Target(1.1),Target(2.7,azimuth_deg=20)])
        settings=camera_settings({'sensor':'radar','max_range_m':2,'max_points':1})
        result=reconstruct(p,settings)
        self.assertEqual(result['status']['point_count'],1)
        self.assertLess(result['points'][0]['distance_m'],2)

    def test_fft_mode_keeps_static_points_and_png_is_valid(self):
        result=reconstruct(packet(),camera_settings({'sensor':'radar','method':'fft'}))
        self.assertGreater(result['status']['point_count'],0)
        image=Image.open(io.BytesIO(result['png']))
        self.assertEqual(image.size,(640,480));self.assertEqual(image.format,'PNG')

    def test_bad_camera_settings(self):
        for attrs in [{},{'sensor':'s','serial_port':'/dev/x'},{'sensor':'s','min_model_fit':2},
                      {'sensor':'s','method':'fake'},{'sensor':'s','max_components':1.5},
                      {'sensor':'s','max_frame_age_s':float('nan')}]:
            with self.subTest(attrs=attrs),self.assertRaises(ValueError):camera_settings(attrs)


class CameraTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.source=MagicMock(spec=Sensor)
        self.source.do_command=AsyncMock(return_value=packet())
        attributes=Struct();attributes.update({'sensor':'upenn-radar'})
        self.config=ComponentConfig(name='radar-cloud',attributes=attributes)
        self.camera=MmwavePointCloud.new(self.config,{Sensor.get_resource_name('upenn-radar'):self.source})

    async def test_dependency_registration_and_camera_api(self):
        self.assertEqual(MmwavePointCloud.validate_config(self.config),(['upenn-radar'],[]))
        self.assertIsNotNone(Registry.lookup_resource_creator(Camera.API,MmwavePointCloud.MODEL))
        props=await self.camera.get_properties()
        self.assertFalse(props.supports_pcd)
        data,mime=await self.camera.get_point_cloud()
        self.assertEqual(mime,PCD_MIME)
        response=GetPointCloudResponse(mime_type=mime,point_cloud=data)
        self.assertEqual(GetPointCloudResponse.FromString(response.SerializeToString()).point_cloud,data)
        self.assertGreater(len(pcd_points(data)),0)
        images,metadata=await self.camera.get_images()
        self.assertEqual(len(images),1);self.assertGreater(metadata.captured_at.seconds,0)
        self.assertTrue(images[0].data.startswith(b'\x89PNG'))
        filtered,_=await self.camera.get_images(filter_source_names=['not-a-source'])
        self.assertEqual(filtered,[])
        details=await self.camera.do_command({'command':'points'})
        self.assertEqual(details['point_count'],len(details['points']))
        self.source.do_command.assert_awaited_with({'command':'raw_frame'},timeout=None)

    async def test_mapping_commands_use_exact_snapshot_and_do_not_fetch_for_export(self):
        frame=await self.camera.do_command({'command':'mapping_frame'})
        self.assertEqual(frame['schema'],'upenn-mmwave/mapping-frame/v1')
        await self.camera.do_command({'command':'map_add','frame_id':frame['frame_id'],
            'map_id':'test','pose_timestamp_unix':frame['captured_at_unix'],
            'map_from_radar_optical':np.eye(4).tolist()})
        self.source.do_command.side_effect=RuntimeError('disconnected')
        result=await self.camera.do_command({'command':'map_points'})
        self.assertEqual(result['keyframe_count'],1)
        await self.camera.do_command({'command':'map_reset'})
        self.assertEqual((await self.camera.do_command({'command':'map_points'}))['point_count'],0)

    async def test_native_viewer_is_explicitly_opt_in(self):
        self.camera.settings['native_pointcloud_viewer']=True
        self.assertTrue((await self.camera.get_properties()).supports_pcd)

    async def test_empty_frame_keeps_image_preview_available(self):
        result={'status':{'healthy':True,'point_count':0},'points':[],
                'pcd':encode_pcd([],[]),
                'png':b'\x89PNG\r\n\x1a\n',
                'metadata':{'captured_at_unix':time.time()}}
        with patch.object(self.camera,'_snapshot',AsyncMock(return_value=result)):
            images,_=await self.camera.get_images()
            self.assertEqual(len(images),1)
            data,_=await self.camera.get_point_cloud()
            self.assertEqual(len(pcd_points(data)),0)

    async def test_empty_cloud_reports_no_points_without_fabricating_data(self):
        result={'status':{'healthy':True,'point_count':0},'points':[],
                'pcd':encode_pcd([],[])}
        with patch.object(self.camera,'_snapshot',AsyncMock(return_value=result)):
            data,mime=await self.camera.get_point_cloud()
            self.assertEqual(mime,PCD_MIME)
            self.assertEqual(len(pcd_points(data)),0)
            status=await self.camera.do_command({'command':'points'})
            self.assertTrue(status['healthy'])
            self.assertEqual(status['points'],[])

    async def test_cached_frame_reused_but_new_frames_processed(self):
        import viam_module.camera as module
        with patch.object(module,'reconstruct',wraps=module.reconstruct) as spy:
            await self.camera.get_point_cloud();await self.camera.get_images()
            self.assertEqual(spy.call_count,1)
            self.source.do_command.return_value=packet(frame_id='test:2')
            await self.camera.get_point_cloud()
            self.assertEqual(spy.call_count,2)

    async def test_dependency_failure_invalidates_cached_cloud(self):
        await self.camera.get_point_cloud()
        self.source.do_command.side_effect=RuntimeError('Sensor disconnected')
        with self.assertRaisesRegex(RuntimeError,'disconnected'):await self.camera.get_point_cloud()
        self.assertIsNone(self.camera._cached)
        status=await self.camera.get_status()
        self.assertFalse(status['healthy'])

    async def test_stale_packet_rejected_even_when_cached(self):
        await self.camera.get_point_cloud()
        self.source.do_command.return_value['frame_age_s']=2
        with self.assertRaisesRegex(RuntimeError,'stale'):await self.camera.get_point_cloud()

    async def test_close_camera_does_not_close_sensor(self):
        await self.camera.close()
        self.source.close.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,'closed'):await self.camera.get_point_cloud()

    async def test_deadline_is_not_ignored(self):
        with self.assertRaises(TimeoutError):await self.camera.get_point_cloud(timeout=0)

    async def test_missing_sensor_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing sensor'):MmwavePointCloud.new(self.config,{})

if __name__=='__main__':unittest.main()
