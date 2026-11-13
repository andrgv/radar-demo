import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np
from radar.config import Config
from radar.protocol import Frame
from radar.synthetic import Target, generate
from radar.angle_lab import raw_model_phase
from viam_module.processing import EchoProcessor, json_safe, radar_config


class EchoTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
                          geometry_mm=[[0,0],[0,2.35],[-2.35,0]])

    def test_repository_configuration_is_unchanged(self):
        from dataclasses import asdict
        for file in ['qualification-hpf350.json', 'exploratory-roll90-phase.json']:
            path = 'configs/'+file
            self.assertEqual(asdict(radar_config({'config_path':path})), asdict(Config.load(path)))

    def test_stationary_echo_and_stronger_mover(self):
        cfg=self.cfg
        frame=generate(cfg, targets=[Target(cfg.ranges[3], amplitude=1500),
            Target(cfg.ranges[8], velocity_mps=.5, amplitude=4000)], seed=1)
        result=EchoProcessor(cfg).process(frame)
        self.assertEqual(result['echo_count'],2)
        self.assertAlmostEqual(result['distance_m'],cfg.ranges[3],delta=.04)
        self.assertFalse(result['echoes'][0]['moving'])
        self.assertIsNone(result['radial_velocity_mps'])
        json.dumps(result,allow_nan=False)

    def test_noise_and_invalid_angle_do_not_fabricate_or_remove_range(self):
        proc=EchoProcessor(self.cfg, angles=True)
        self.assertEqual(proc.process(generate(self.cfg, targets=[],seed=1))['echo_count'],0)
        frame=generate(self.cfg,targets=[Target(self.cfg.ranges[4])],seed=2)
        with patch('viam_module.processing.estimate_angle', return_value=(float('nan'),float('nan'),(),False)):
            result=proc.process(frame)
        self.assertEqual(result['echo_count'],1)
        self.assertIsNone(result['azimuth_deg'])
        json.dumps(result,allow_nan=False)

    def test_static_echo_persists_and_disappears_without_motion_gate(self):
        proc=EchoProcessor(self.cfg)
        for i in range(1,20):
            r=proc.process(generate(self.cfg,i,targets=[Target(self.cfg.ranges[4])],seed=i))
            self.assertEqual(r['echo_count'],1)
        self.assertEqual(proc.process(generate(self.cfg,20,targets=[],seed=20))['echo_count'],0)

    def test_background_is_explicit_and_clearable(self):
        proc=EchoProcessor(self.cfg)
        targets=[Target(self.cfg.ranges[4])]
        proc.capture_background(10)
        for i in range(10):
            result=proc.process(generate(self.cfg,i,targets=targets,seed=i))
        self.assertTrue(result['background_subtracted'])
        self.assertEqual(result['echo_count'],0)
        proc.clear_background()
        self.assertEqual(proc.process(generate(self.cfg,11,targets=targets,seed=11))['echo_count'],1)

    def test_matrix_angle_synthetic(self):
        result=EchoProcessor(self.cfg,angles=True).process(generate(self.cfg,
            targets=[Target(self.cfg.ranges[4],azimuth_deg=15,elevation_deg=5)],seed=2))
        self.assertAlmostEqual(result['azimuth_deg'],15,delta=1)
        self.assertAlmostEqual(result['elevation_deg'],5,delta=1)
        self.assertFalse(result['angle_calibrated'])

    def test_reference_angle_uses_repository_rx2_algorithm(self):
        cfg=replace(self.cfg,mount_roll_deg=90)
        xyz=[0,2,-.1125]
        phase=raw_model_phase(cfg,xyz)[0]
        proc=EchoProcessor(cfg,angles=True,reference=(phase,xyz,xyz[2]))
        r=cfg.ranges[6]; el=np.degrees(np.arcsin(xyz[2]/r))
        result=proc.process(generate(cfg,targets=[Target(r,azimuth_deg=4,elevation_deg=el)],seed=2))
        self.assertAlmostEqual(result['azimuth_deg'],4,delta=.2)
        self.assertIsNone(result['elevation_deg'])
        self.assertEqual(result['angle_method'],'rx2_reference')

    def test_physical_velocity_only_when_verified(self):
        cfg=replace(self.cfg,chirp_timing_verified=True,carrier_frequency_verified=True)
        result=EchoProcessor(cfg).process(generate(cfg,targets=[Target(cfg.ranges[4],velocity_mps=.5)],seed=1))
        self.assertIsNotNone(result['radial_velocity_mps'])

    def test_bad_frames_fail(self):
        proc=EchoProcessor(self.cfg)
        for field,value in [('profile_id',0),('flags',9),('errors',1)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                proc.process(replace(generate(self.cfg),**{field:value}))

    def test_json_safe(self):
        self.assertEqual(json_safe({'x':np.array([1,np.nan,np.inf]),'b':np.bool_(True)}),
                         {'x':[1,None,None],'b':True})

if __name__=='__main__': unittest.main()
