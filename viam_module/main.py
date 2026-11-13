import asyncio
import json
import sys
from viam.module.module import Module
from viam_module.sensor import UpennMmwave
from viam_module.camera import MmwavePointCloud

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from viam_module.processing import EchoProcessor, radar_config
        from radar.synthetic import Target, generate
        cfg = radar_config({'config_path': 'configs/exploratory-roll90-phase.json'})
        result = EchoProcessor(cfg).process(generate(
            cfg, targets=[Target(float(cfg.ranges[4]))], seed=1))
        assert result['echo_count'] >= 1
        assert str(UpennMmwave.MODEL) == 'carlyworkspace:upenn-mmwave:infineon-mmwave'
        import time
        import numpy as np
        from viam_module.raw_frame import encode_raw
        from viam_module.cloud import camera_settings, reconstruct
        from viam.components.camera import Camera
        from viam.resource.registry import Registry
        response = np.linalg.solve(cfg.angle_matrix, np.ones(3)) / cfg.gains
        frame = generate(cfg, targets=[Target(float(cfg.ranges[4]))],
                         channel_response=response, seed=1)
        packet = encode_raw(frame,cfg,frame_id='self-test',captured_at_unix=time.time(),age=0,stale_after=1)
        cloud = reconstruct(packet,camera_settings({'sensor':'self-test'}))
        assert cloud['status']['point_count'] > 0
        assert cloud['pcd'].startswith(b'VERSION .7')
        assert cloud['png'].startswith(b'\x89PNG')
        assert Registry.lookup_resource_creator(Camera.API,MmwavePointCloud.MODEL)
        print(json.dumps({'sensor':result,'camera':cloud['status']}, allow_nan=False))
    else:
        asyncio.run(Module.run_from_registry())
