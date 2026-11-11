from dataclasses import replace
import tempfile
from pathlib import Path
import unittest
import numpy as np

from radar.config import C, Config
from radar.processing import Processor, range_doppler_peaks
from radar.synthetic import Target, generate


class RangeDopplerDetectionTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(moving_detector="range_doppler", chirp_timing_verified=True,
                             carrier_frequency_verified=True)
        self.velocity_scale = C / (2 * self.config.carrier_hz * self.config.chirp_interval_s)
        self.spacing = self.config.ranges[1] - self.config.ranges[0]

    def test_two_movers_at_same_range_have_separate_angles_and_velocities(self):
        config = self.config
        targets = [Target(config.ranges[12], -0.25 * self.velocity_scale, -25, 5, 1800),
                   Target(config.ranges[12], 0.25 * self.velocity_scale, 30, -10, 900)]
        frame = generate(config, targets=targets, seed=3)
        original = Processor(replace(config, moving_detector="range_profile")).process(frame)
        self.assertEqual(len([d for d in original.detections if d.moving]), 1)
        moving = [d for d in Processor(config).process(frame).detections if d.moving]
        self.assertEqual(len(moving), 2)
        for target in targets:
            detection = min(moving, key=lambda d: abs(d.velocity_mps - target.velocity_mps))
            self.assertAlmostEqual(detection.velocity_mps, target.velocity_mps)
            self.assertAlmostEqual(detection.range_m, target.range_m, delta=0.03 * self.spacing)
            self.assertAlmostEqual(detection.azimuth_deg, target.azimuth_deg, delta=1)
            self.assertAlmostEqual(detection.elevation_deg, target.elevation_deg, delta=1)
            self.assertGreaterEqual(detection.snr_db, config.snr_db)

    def test_adjacent_ranges_are_interpolated_in_their_own_doppler_rows(self):
        config = self.config
        targets = [Target(config.ranges[12] + 0.2 * self.spacing,
                          -0.25 * self.velocity_scale, -25, 5, 1800),
                   Target(config.ranges[13] - 0.2 * self.spacing,
                          0.25 * self.velocity_scale, 30, -10, 900)]
        moving = [d for d in Processor(config).process(generate(config, targets=targets, seed=3)).detections
                  if d.moving]
        self.assertEqual(len(moving), 2)
        for target in targets:
            detection = min(moving, key=lambda d: abs(d.velocity_mps - target.velocity_mps))
            self.assertAlmostEqual(detection.range_m, target.range_m, delta=0.03 * self.spacing)

    def test_static_angle_is_not_mixed_with_a_mover_at_the_same_range(self):
        for mode in ("range_profile", "range_doppler"):
            with self.subTest(mode=mode):
                config = replace(self.config, moving_detector=mode)
                targets = [Target(config.ranges[12], azimuth_deg=-20, elevation_deg=5),
                           Target(config.ranges[12], 0.25 * self.velocity_scale, 30, -10, 900)]
                result = Processor(config).process(generate(config, targets=targets, seed=3))
                stationary = [d for d in result.detections if not d.moving]
                self.assertEqual(len(stationary), 1)
                self.assertAlmostEqual(stationary[0].azimuth_deg, -20, delta=1)
                self.assertAlmostEqual(stationary[0].elevation_deg, 5, delta=1)
                self.assertTrue(any(d.moving for d in result.detections))

    def test_single_off_bin_mover_does_not_make_notch_or_sidelobe_peaks(self):
        config = self.config
        for frequency in (0.18, 0.22, -0.18, -0.22):
            with self.subTest(frequency=frequency):
                target = Target(config.ranges[12] + 0.3 * self.spacing,
                                frequency * self.velocity_scale, 30, -10)
                moving = [d for d in Processor(config).process(generate(config, targets=[target], seed=3)).detections
                          if d.moving]
                self.assertEqual(len(moving), 1)
                self.assertAlmostEqual(moving[0].velocity_mps, target.velocity_mps,
                                       delta=self.velocity_scale / 32)

    def test_slow_return_in_the_notch_does_not_create_edge_detection(self):
        target = Target(self.config.ranges[12], 0.06 * self.velocity_scale)
        result = Processor(self.config).process(generate(self.config, targets=[target], noise=1, seed=3))
        self.assertFalse(any(d.moving for d in result.detections))

    def test_nyquist_seam_has_one_peak(self):
        for frequency in (-0.49, 0.49):
            with self.subTest(frequency=frequency):
                target = Target(self.config.ranges[12], frequency * self.velocity_scale)
                result = Processor(self.config).process(generate(self.config, targets=[target], seed=3))
                moving = [d for d in result.detections if d.moving]
                self.assertEqual(len(moving), 1)
                self.assertAlmostEqual(abs(moving[0].velocity_mps), 0.5 * self.velocity_scale)

    def test_peak_ties_wrap_doppler_but_range_edges_are_excluded(self):
        power = np.zeros((16, 33))
        power[0, 10:12] = power[-1, 10:12] = 10
        power[:, :2] = power[:, -1:] = 100
        self.assertEqual(range_doppler_peaks(power, np.ones_like(power)), [(0, 10)])

    def test_white_noise_does_not_produce_a_flood_of_detections(self):
        counts = [len(Processor(self.config).process(generate(self.config, targets=[], seed=seed)).detections)
                  for seed in range(50)]
        self.assertLessEqual(sum(counts), 2)  # Regression envelope, not a hardware Pfa claim.

    def test_unverified_timing_stays_unverified_in_new_mode(self):
        config = replace(self.config, chirp_timing_verified=False, carrier_frequency_verified=False)
        result = Processor(config).process(generate(config, seed=3))
        self.assertTrue(result.detections)
        self.assertTrue(all(d.velocity_mps is None for d in result.detections))
        self.assertIn("unverified", result.doppler_unit)

    def test_short_burst_without_doppler_training_cells_is_handled(self):
        config = replace(self.config, chirps=8, discard_chirps=3)
        result = Processor(config).process(generate(config, seed=3))
        self.assertFalse(any(d.moving for d in result.detections))

    def test_old_configs_keep_baseline_and_new_mode_roundtrips(self):
        self.assertEqual(Config().moving_detector, "range_profile")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            self.config.save(path)
            self.assertEqual(Config.load(path), self.config)
        with self.assertRaisesRegex(ValueError, "Moving detector"):
            replace(self.config, moving_detector="unknown").validate()
