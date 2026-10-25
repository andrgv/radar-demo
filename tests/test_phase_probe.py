from dataclasses import replace
import unittest
import numpy as np
from radar.config import Config
from radar.processing import Processor
from radar.synthetic import Target, generate


class PhaseProbeTests(unittest.TestCase):
    def test_gate_follows_neighboring_peak_without_temporal_smoothing(self):
        config = replace(Config(), probe_search_bins=1)
        processor = Processor(config, phase_probe_range=config.ranges[7])
        for sequence, index in enumerate([7, 8, 6, 7], 1):
            target = Target(config.ranges[index], azimuth_deg=15)
            result = processor.process(generate(config, sequence, targets=[target], seed=sequence))
            self.assertEqual(result.phase_probe.range_bin, index)
            self.assertTrue(result.phase_probe.usable)
            self.assertAlmostEqual(result.phase_probe.azimuth_deg, 15, delta=1)

    def test_gate_does_not_chase_distant_target(self):
        config = replace(Config(), probe_search_bins=1)
        result = Processor(config, phase_probe_range=config.ranges[7]).process(
            generate(config, targets=[Target(config.ranges[15])], seed=3))
        self.assertIn(result.phase_probe.range_bin, [6, 7, 8])
        self.assertFalse(result.phase_probe.usable)

    def test_disabled_by_default(self):
        config = Config()
        result = Processor(config).process(generate(config, seed=1))
        self.assertIsNone(result.phase_probe)

    def test_probe_does_not_bypass_detection_threshold(self):
        config = replace(Config(), snr_db=100)
        target = Target(config.ranges[7], azimuth_deg=20, elevation_deg=-10)
        result = Processor(config, phase_probe_range=target.range_m).process(
            generate(config, targets=[target], seed=1))
        self.assertEqual(result.detections, [])
        self.assertTrue(result.phase_probe.angle_valid)
        self.assertGreater(result.phase_probe.min_coherence, 0.99)
        self.assertLess(abs(result.phase_probe.azimuth_deg - 20), 1)
        self.assertLess(abs(result.phase_probe.elevation_deg + 10), 1)
        self.assertLess(result.phase_probe.snr_db, result.phase_probe.threshold_db)
        self.assertFalse(result.phase_probe.usable)
        self.assertIn("weak/unisolated", result.phase_probe.rejection_reason)

    def test_common_chirp_phase_cancellation(self):
        config = Config()
        target = Target(config.ranges[7], velocity_mps=0.45, azimuth_deg=-15, elevation_deg=12)
        result = Processor(config, phase_probe_range=target.range_m).process(
            generate(config, targets=[target], seed=2))
        self.assertGreater(result.phase_probe.min_coherence, 0.99)
        self.assertLess(abs(result.phase_probe.azimuth_deg + 15), 1)
        self.assertLess(abs(result.phase_probe.elevation_deg - 12), 1)
        self.assertTrue(result.phase_probe.usable)

    def test_noise_probe_not_coherent(self):
        config = Config()
        result = Processor(config, phase_probe_range=config.ranges[7]).process(
            generate(config, targets=[], noise=100, seed=9))
        self.assertLess(result.phase_probe.min_coherence, 0.9)

    def test_outside_range_rejected(self):
        for value in [0, -1, np.nan, 1000]:
            with self.assertRaises(ValueError):
                Processor(Config(), phase_probe_range=value)
