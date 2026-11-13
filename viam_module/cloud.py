"""Sparse raw-radar reconstruction, Viam PCD encoding and a top-down preview."""
import io
import math
import time

import numpy as np
from PIL import Image, ImageDraw
from radar.processing import range_fft
from radar.pointcloud import CloudProcessor
from radar.reconstruction import ReconstructionSettings, SceneReconstructor
from .processing import json_safe
from .raw_frame import decode_raw

PCD_MIME = 'pointcloud/pcd'


def camera_settings(attributes):
    sensor = attributes.get('sensor')
    if not isinstance(sensor, str) or not sensor.strip():
        raise ValueError('sensor must name the existing upenn-mmwave sensor resource')
    if 'serial_port' in attributes or 'config_path' in attributes:
        raise ValueError('Configure serial_port/config_path on the sensor, not the camera')
    method = attributes.get('method','deblend')
    if method not in ('deblend','fft'):
        raise ValueError('method must be deblend or fft')
    result = dict(sensor=sensor, method=method)
    for key, default, lo, hi, integer in [
        ('min_range_m',.5,0,100,False), ('max_range_m',3,.01,100,False),
        ('min_snr_db',12,.01,80,False), ('min_model_fit',.8,.01,1,False),
        ('max_components',8,1,12,True), ('max_points',64,1,512,True),
        ('max_angular_width_deg',120,5,120,False), ('max_frame_age_s',1,.05,10,False),
    ]:
        value=attributes.get(key,default)
        if (isinstance(value,bool) or not isinstance(value,(float,int))
                or not math.isfinite(value) or not lo<=value<=hi
                or (integer and value != int(value))):
            raise ValueError(f'{key} must be {"an integer" if integer else "finite"} in [{lo}, {hi}]')
        result[key] = int(value) if integer else float(value)
    if result['min_range_m'] >= result['max_range_m']:
        raise ValueError('min_range_m must be less than max_range_m')
    return result


def encode_pcd(xyz_m, snr_db):
    """PCD uses meters. Viam's parser converts those to its internal millimeters.

    Repository axes: X right, Y forward, Z up.
    Camera optical axes: X right, Y down, Z forward.
    """
    xyz=np.asarray(xyz_m,dtype=float).reshape(-1,3)
    if not np.isfinite(xyz).all():
        raise ValueError('Cannot encode nonfinite radar points')
    snr=np.asarray(snr_db,dtype=float)
    if snr.shape != (len(xyz),) or not np.isfinite(snr).all():
        raise ValueError('Point and quality counts do not match')
    points=np.empty(len(xyz),dtype=[('x','<f4'),('y','<f4'),('z','<f4'),('rgb','<u4')])
    points['x']=xyz[:,0];points['y']=-xyz[:,2];points['z']=xyz[:,1]
    quality=np.clip((snr-8)/32,0,1)
    red=(255*(1-quality)).astype(np.uint32)
    green=(100+155*quality).astype(np.uint32)
    points['rgb']=(red<<16)|(green<<8)|np.uint32(80)
    header=(f'VERSION .7\nFIELDS x y z rgb\nSIZE 4 4 4 4\nTYPE F F F I\n'
            f'COUNT 1 1 1 1\nWIDTH {len(points)}\nHEIGHT 1\nVIEWPOINT 0 0 0 1 0 0 0\n'
            f'POINTS {len(points)}\nDATA binary\n')
    return header.encode('ascii')+points.tobytes()


def preview_png(xyz, max_range):
    image=Image.new('RGB',(640,480),(18,24,32));draw=ImageDraw.Draw(image)
    left,right,top,bottom=52,612,48,416
    cx=(left+right)/2;scale=min((right-left)/(2*max_range),(bottom-top)/max_range)
    def pixel(x,y):return (cx+x*scale,bottom-y*scale)
    draw.text((16,12),'mmWave: top-down scattering points (uncalibrated)',fill=(230,235,240))
    for frac in (.25,.5,.75,1):
        r=max_range*frac;y=pixel(0,r)[1]
        draw.line((left,y,right,y),fill=(48,60,72))
        draw.text((5,y-5),f'{r:.2g}m',fill=(160,170,180))
    for frac in (-1,-.5,0,.5,1):
        x=pixel(frac*max_range,0)[0]
        draw.line((x,top,x,bottom),fill=(48,60,72))
        draw.text((x-12,bottom+7),f'{frac*max_range:.2g}',fill=(160,170,180))
    draw.text((260,444),'Right X (meters)',fill=(190,200,210))
    draw.text((16,462),f'{len(xyz)} points | Forward is up | Current frame only',fill=(190,200,210))
    for x,y,_ in xyz:
        px,py=pixel(x,y)
        draw.ellipse((px-4,py-4,px+4,py+4),fill=(70,235,150))
    draw.polygon([(cx,bottom-7),(cx-5,bottom+2),(cx+5,bottom+2)],fill=(245,190,70))
    output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()


def reconstruct(packet, settings):
    """Stateless per-call engine: no old points, poses, surfaces or artificial fill."""
    started=time.monotonic()
    frame,cfg,metadata=decode_raw(packet,settings['max_frame_age_s'])
    if settings['method']=='deblend':
        processor=SceneReconstructor(cfg,ReconstructionSettings(
            max_components=settings['max_components'],
            minimum_model_fit=settings['min_model_fit'],minimum_snr_db=settings['min_snr_db']))
        cloud=processor.process(frame.adc)
        diagnostics=processor.last_report
    else:
        processor=CloudProcessor(cfg,snr_db=settings['min_snr_db'],minimum_fit=settings['min_model_fit'])
        cloud=processor.process(range_fft(frame.adc,cfg))
        diagnostics={'method':'range_doppler_fft_array_fit'}
    ranges=np.linalg.norm(cloud.xyz,axis=1)
    mask=(np.isfinite(cloud.xyz).all(axis=1)&np.isfinite(cloud.snr_db)&np.isfinite(cloud.model_fit)
          &np.isfinite(cloud.angular_width_deg).all(axis=1)
          &(ranges>=settings['min_range_m'])&(ranges<=settings['max_range_m'])
          &(cloud.xyz[:,1]>0)&(cloud.snr_db>=settings['min_snr_db'])
          &(cloud.model_fit>=settings['min_model_fit'])
          &(np.max(cloud.angular_width_deg,axis=1,initial=0)<=settings['max_angular_width_deg']))
    selected=np.flatnonzero(mask)
    # Bound the response by quality, then sort by range for stable output ordering.
    selected=selected[np.argsort(-cloud.snr_db[selected],kind='stable')[:settings['max_points']]]
    selected=selected[np.argsort(ranges[selected],kind='stable')]
    xyz=cloud.xyz[selected]
    points=[dict(x_m=float(p[0]),y_m=float(-p[2]),z_m=float(p[1]),
                 distance_m=float(ranges[i]),snr_db=float(cloud.snr_db[i]),
                 model_fit=float(cloud.model_fit[i]),
                 angular_width_deg=cloud.angular_width_deg[i].tolist(),
                 doppler_cycles_per_chirp=float(cloud.doppler_cycles_per_chirp[i]))
            for p,i in zip(xyz,selected)]
    pcd=encode_pcd(xyz,cloud.snr_db[selected])
    png=preview_png(xyz,settings['max_range_m'])
    status=json_safe(dict(
        point_count=len(xyz), candidate_count=len(cloud.xyz), method=settings['method'],
        frame_id=metadata['frame_id'], sequence=int(frame.sequence),
        device_timestamp_us=int(frame.timestamp_us), config_sha256=metadata['config_sha256'],
        calibration_id=cfg.calibration_id, range_calibrated=cfg.verified,angle_calibrated=False,
        coordinate_frame='camera_optical_x_right_y_down_z_forward',pcd_units='meters',
        background_subtracted=False,temporal_accumulation=False,
        doppler_unit='cycles/output_chirp',capture_time_basis='host_frame_receipt',
        device_dropped=int(frame.dropped),processing_ms=(time.monotonic()-started)*1000,
    ))
    return dict(pcd=pcd,png=png,status=status,points=json_safe(points),
                diagnostics=json_safe(diagnostics),metadata=metadata)
