from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from radar.config import C, Config
from radar.pointcloud import CloudProcessor
from radar.processing import Processor, range_fft
from radar.reconstruction import ReconstructionSettings, SceneReconstructor
from radar.storage import Recorder, replay
from radar.synthetic import Target, generate


class ReconstructionTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000.,
                             geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]])
        self.spacing = self.config.ranges[1]

    def assert_target(self, cloud, target, range_tolerance=.01, angle_tolerance=5.1):
        ranges = np.linalg.norm(cloud.xyz, axis=1)
        self.assertTrue(len(ranges))
        point = cloud.xyz[int(np.argmin(abs(ranges - target.range_m)))]
        self.assertAlmostEqual(np.linalg.norm(point), target.range_m, delta=range_tolerance)
        az = np.degrees(np.arctan2(point[0], point[1]))
        el = np.degrees(np.arcsin(point[2] / np.linalg.norm(point)))
        self.assertAlmostEqual(az, target.azimuth_deg, delta=angle_tolerance)
        self.assertAlmostEqual(el, target.elevation_deg, delta=angle_tolerance)

    def test_two_offgrid_reflectors_merged_by_fft_are_separated_from_raw_data(self):
        targets = [Target(3.2*self.spacing, azimuth_deg=-25, elevation_deg=10),
                   Target(3.9*self.spacing, azimuth_deg=30, elevation_deg=-15, amplitude=1400)]
        frame = generate(self.config, targets=targets, noise=5, seed=1)
        old = CloudProcessor(self.config).process(range_fft(frame.adc, self.config))
        new = SceneReconstructor(self.config).process(frame.adc)
        self.assertEqual(len(old.xyz), 1)
        self.assertEqual(len(new.xyz), 2)
        for target in targets:
            self.assert_target(new, target)

    def test_stationary_scene_keeps_multiple_distinct_reflections(self):
        targets = [Target(f*self.spacing, azimuth_deg=az, elevation_deg=el, amplitude=a)
                   for f, az, el, a in [(2.3,-30,-15,1500), (4.5,20,10,1800),
                                        (6.2,45,0,900), (8.7,-10,35,1200), (11.4,15,-25,750)]]
        frame = generate(self.config, targets=targets, noise=5, seed=1)
        new = SceneReconstructor(self.config).process(frame.adc)
        self.assertEqual(len(new.xyz), len(targets))
        for target in targets:
            self.assert_target(new, target)

    def test_opposite_dopplers_sharing_a_range_keep_both_directions(self):
        speed = C * .25 / (2 * self.config.carrier_hz * self.config.chirp_interval_s)
        targets = [Target(8*self.spacing, -speed, -30, 10),
                   Target(8*self.spacing, speed, 25, -10, 1400)]
        frame = generate(self.config, targets=targets, noise=5, seed=1)
        cloud = SceneReconstructor(self.config).process(frame.adc)
        self.assertEqual(len(cloud.xyz), 2)
        for target in targets:
            index = int(np.argmin(abs(cloud.doppler_cycles_per_chirp - np.sign(target.velocity_mps)*.25)))
            point = cloud.xyz[index]
            self.assertAlmostEqual(np.degrees(np.arctan2(point[0], point[1])), target.azimuth_deg, delta=5.1)

    def test_no_previous_points_are_held_and_noise_does_not_become_a_scene(self):
        mapper = SceneReconstructor(self.config)
        target = Target(5.4*self.spacing, azimuth_deg=10, elevation_deg=5)
        self.assertEqual(len(mapper.process(generate(self.config, targets=[target], seed=1).adc).xyz), 1)
        for seed in (1, 2, 3):
            noise = generate(self.config, targets=[], noise=5, seed=seed)
            self.assertEqual(len(mapper.process(noise.adc).xyz), 0)
        constant = np.full((self.config.chirps, self.config.samples, 3), 32768, dtype='<u2')
        self.assertEqual(len(mapper.process(constant).xyz), 0)
        self.assertEqual(mapper.last_report['reason'], 'no_ac_energy')

    def test_boundary_direction_is_unresolved_instead_of_a_clipped_point(self):
        frame = generate(self.config, targets=[Target(5.4*self.spacing, azimuth_deg=75)], noise=5, seed=1)
        mapper = SceneReconstructor(self.config)
        self.assertEqual(len(mapper.process(frame.adc).xyz), 0)
        self.assertTrue(any('direction_at_search_boundary' in c['reasons'] for c in mapper.last_report['components']))

    def test_nonunitary_array_correction_and_complex_channel_gains(self):
        matrix = np.array([[1,0,0],[.15+.1j, .8+.3j,0],[.1,0,.6-.2j]])
        gains = np.array([1, .9+.2j, 1.2-.15j])
        config = replace(self.config, angle_matrix_real=matrix.real.tolist(), angle_matrix_imag=matrix.imag.tolist(),
                         gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist())
        az, el, f = 20., -15., 5.3
        direction = [np.sin(np.radians(az))*np.cos(np.radians(el)), np.sin(np.radians(el))]
        raw_response = np.linalg.solve(matrix, np.exp(2j*np.pi*config.array_geometry @ direction)) / gains
        phase = np.exp(2j*np.pi*np.arange(config.samples)*f/config.samples)
        adc = 32768 + 1500 * np.real(phase[None, :, None]*raw_response[None, None, :])
        adc = np.broadcast_to(adc, (config.chirps, config.samples, 3)).copy().astype('<u2')
        cloud = SceneReconstructor(config).process(adc)
        self.assertEqual(len(cloud.xyz), 1)
        self.assert_target(cloud, Target(f*self.spacing, azimuth_deg=az, elevation_deg=el))

    def test_real_samples_are_unchanged_and_actual_processor_exports_replayable_cloud(self):
        frame = generate(self.config, targets=[Target(3.2*self.spacing, azimuth_deg=10)], noise=5, seed=1)
        original = frame.adc.copy()
        result = Processor(self.config, point_cloud=True).process(frame)
        self.assertEqual(result.features['cloud_method'], 'raw_multitone_range_angle')
        np.testing.assert_array_equal(frame.adc, original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'capture'
            with Recorder(path, self.config) as recorder:
                recorder.write(frame, result)
            np.testing.assert_array_equal(next(replay(path)).adc, original)
            cloud = json.loads((path/'pointcloud.jsonl').read_text())
            self.assertTrue(cloud['xyz'])
            self.assertFalse(cloud['angular_calibration_verified'])

    def test_invalid_adc_or_settings_are_rejected(self):
        mapper = SceneReconstructor(self.config)
        for value in (np.zeros((17,64,3)), np.ones((17,64,3))*65535, np.ones((2,3))):
            with self.assertRaises(ValueError):
                mapper.process(value)
        with self.assertRaises(ValueError):
            SceneReconstructor(self.config, ReconstructionSettings(max_components=100))


if __name__ == '__main__':
    unittest.main()
