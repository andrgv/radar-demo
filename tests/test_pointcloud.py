import unittest
import numpy as np
from radar.config import Config
from radar.pointcloud import CloudProcessor


class CloudTests(unittest.TestCase):
    def test_cloud_mode_records_replayable_raw_data_and_quality_fields(self):
        import tempfile,json
        from pathlib import Path
        from radar.processing import Processor
        from radar.storage import Recorder,replay
        from radar.synthetic import generate,Target
        config=Config()
        frame=generate(config,targets=[Target(config.ranges[8])],seed=1)
        result=Processor(config,point_cloud=True).process(frame)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene'
            with Recorder(path,config) as recorder:
                recorder.write(frame,result)
            cloud=json.loads((path/'pointcloud.jsonl').read_text())
            self.assertTrue(cloud['xyz'])
            self.assertEqual(len(cloud['xyz']),len(cloud['model_fit']))
            self.assertEqual(len(cloud['xyz']),len(cloud['angular_width_deg']))
            self.assertFalse(cloud['angular_calibration_verified'])
            self.assertEqual(len(list(replay(path))),1)

    def test_same_range_different_dopplers_and_stationary_scene_return(self):
        config=Config()
        spectrum=np.zeros((16,33,3),complex)
        targets=[(8,-0.25,-30,10,100),(8,0.25,25,-10,90),(15,0,0,20,70)]
        for r,d,az,el,amplitude in targets:
            direction=[np.sin(np.radians(az))*np.cos(np.radians(el)),np.sin(np.radians(el))]
            spatial=np.exp(2j*np.pi*config.array_geometry@direction)
            spectrum[:,r]+=amplitude*np.exp(2j*np.pi*d*np.arange(16))[:,None]*spatial
        cloud=CloudProcessor(config).process(spectrum)
        for r,d,az,el,_ in targets:
            indices=np.flatnonzero((cloud.range_bins==r)&np.isclose(cloud.doppler_cycles_per_chirp,d))
            self.assertEqual(len(indices),1)
            point=cloud.xyz[indices[0]]
            estimated_az=np.degrees(np.arctan2(point[0],point[1]))
            estimated_el=np.degrees(np.arcsin(point[2]/np.linalg.norm(point)))
            self.assertAlmostEqual(estimated_az,az,delta=5)
            self.assertAlmostEqual(estimated_el,el,delta=5)
            self.assertGreater(cloud.model_fit[indices[0]],0.95)

    def test_empty_data_does_not_make_surface_points(self):
        cloud=CloudProcessor(Config()).process(np.zeros((16,33,3),complex))
        self.assertEqual(cloud.xyz.shape,(0,3))
        self.assertEqual(cloud.angular_width_deg.shape,(0,2))

    def test_multiple_range_returns_preserved_when_weak_return_is_20db_lower(self):
        spectrum=np.zeros((16,33,3),complex)
        spectrum[:,5]=100
        spectrum[:,16]=10
        cloud=CloudProcessor(Config()).process(spectrum)
        self.assertIn(5,cloud.range_bins)
        self.assertIn(16,cloud.range_bins)
