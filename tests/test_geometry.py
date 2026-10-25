from dataclasses import replace
import unittest
import numpy as np
from radar.config import C, Config
from radar.processing import estimate_angle, Processor
from radar.synthetic import Target, generate


class PhysicalGeometryTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]],
                             geometry_label="BGT60CUTR13AIP portrait antenna-face view")

    def test_documented_spacing_converts_with_carrier(self):
        distance = 0.00235 * self.config.carrier_hz / C
        np.testing.assert_allclose(self.config.array_geometry,
            [[0, 0], [0, distance], [-distance, 0]], atol=1e-12)
        changed = replace(self.config, carrier_hz=64e9)
        self.assertAlmostEqual(abs(changed.array_geometry[2, 0]), 0.00235 * 64e9 / C)

    def test_azimuth_uses_rx3_relative_to_rx1(self):
        phase = -2 * np.pi * 0.00235 * self.config.carrier_hz / C * np.sin(np.radians(15))
        azimuth, elevation, direction, valid = estimate_angle(np.array([1, 1, np.exp(1j * phase)]), self.config)
        self.assertTrue(valid)
        self.assertAlmostEqual(azimuth, 15)
        self.assertAlmostEqual(elevation, 0)

    def test_elevation_uses_rx2_relative_to_rx1(self):
        phase = 2 * np.pi * 0.00235 * self.config.carrier_hz / C * np.sin(np.radians(12))
        azimuth, elevation, direction, valid = estimate_angle(np.array([1, np.exp(1j * phase), 1]), self.config)
        self.assertTrue(valid)
        self.assertAlmostEqual(azimuth, 0)
        self.assertAlmostEqual(elevation, 12)

    def test_mount_rotation_does_not_reorder_receivers(self):
        config = replace(self.config, mount_roll_deg=-90)
        distance = 0.00235 * config.carrier_hz / C
        np.testing.assert_allclose(config.array_geometry,
            [[0, 0], [distance, 0], [0, distance]], atol=1e-12)

    def test_physical_geometry_full_processing(self):
        target = Target(self.config.ranges[10], azimuth_deg=-20, elevation_deg=8)
        result = Processor(self.config).process(generate(self.config, targets=[target], seed=1))
        detection = max(result.detections, key=lambda item: item.power_db)
        self.assertLess(abs(detection.azimuth_deg + 20), 1)
        self.assertLess(abs(detection.elevation_deg - 8), 1)

    def test_invalid_physical_geometry_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.config, geometry_mm=[[0, 0], [0, 1], [0, 2]]).validate()
        with self.assertRaises(ValueError):
            replace(self.config, mount_roll_deg=float("nan")).validate()
