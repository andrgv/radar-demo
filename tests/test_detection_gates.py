import unittest
from unittest.mock import patch
import numpy as np
from radar.config import Config
from radar.processing import Processor, coherent_channels, estimate_angle
from radar.synthetic import Target, generate


class DetectionGateTests(unittest.TestCase):
    def test_channel_mixing_recovers_known_direction(self):
        from pathlib import Path
        config = Config.load(Path(__file__).resolve().parents[1] / 'configs/range-vendor-matrix-experimental.json')
        target = Target(config.ranges[4], azimuth_deg=12, elevation_deg=-8)
        ideal = generate(config, targets=[target], noise=0, seed=1)
        # Invert the non-diagonal hardware response in complex range space.
        from radar.processing import range_fft
        spectrum = range_fft(ideal.adc, config)
        raw = spectrum @ np.linalg.inv(config.angle_matrix).T
        calibrated = raw @ config.angle_matrix.T
        azimuth, elevation, _, valid = estimate_angle(coherent_channels(calibrated[:, 4]), config)
        self.assertTrue(valid)
        self.assertAlmostEqual(azimuth, 12, delta=0.02)
        self.assertAlmostEqual(elevation, -8, delta=0.02)

    def test_common_phase_cancellation_does_not_destroy_direction(self):
        config = Config()
        expected = np.array([0.2, -0.1])
        spatial = np.exp(2j * np.pi * (config.array_geometry @ expected))
        chirps = np.exp(2j * np.pi * np.arange(16) / 16)[:, None] * spatial
        self.assertLess(np.max(abs(chirps.mean(axis=0))), 1e-12)
        _, _, direction, valid = estimate_angle(coherent_channels(chirps), config)
        self.assertTrue(valid)
        np.testing.assert_allclose(np.array(direction)[[0, 2]], expected, atol=1e-12)

    def test_moving_detection_has_independent_gate(self):
        config = Config()
        frame = generate(config, targets=[Target(config.ranges[12], velocity_mps=0.4)], seed=3)
        # Simulate strong static clutter raising only the total-power gate.
        from radar.processing import noise_threshold
        calls = 0
        def thresholds(power, factor):
            nonlocal calls
            calls += 1
            return np.full_like(power, 1e30) if calls == 1 else noise_threshold(power, factor)
        with patch('radar.processing.noise_threshold', side_effect=thresholds):
            result = Processor(config).process(frame)
        moving = [item for item in result.detections if item.moving]
        self.assertTrue(any(abs(item.range_m - config.ranges[12]) < 0.03 for item in moving))
        self.assertFalse(any(not item.moving for item in result.detections))
