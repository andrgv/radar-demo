from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import numpy as np
from radar.background import SpectralBackground
from radar.config import Config
from radar.processing import Processor, range_fft
from radar.synthetic import Target, generate


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.clutter = Target(self.config.ranges[7], amplitude=2000)
        self.frames = [generate(self.config, index + 1, targets=[self.clutter], seed=index) for index in range(20)]
        self.background = SpectralBackground.fit(self.frames[:10], self.config)

    def test_background_removes_heldout_static_clutter(self):
        frame = self.frames[-1]
        raw = range_fft(frame.adc, self.config)
        residual = self.background.subtract(raw, self.config)
        self.assertLess(np.mean(abs(residual[:, 7])**2), np.mean(abs(raw[:, 7])**2) / 1000)

    def test_added_target_survives_and_no_background_target_is_detected(self):
        added = Target(self.config.ranges[17], azimuth_deg=20, amplitude=1500)
        frame = generate(self.config, targets=[self.clutter, added], seed=100)
        result = Processor(self.config, background=self.background).process(frame)
        self.assertTrue(result.background_subtracted)
        bins = [int(np.argmin(abs(self.config.ranges - item.range_m))) for item in result.detections]
        self.assertIn(17, bins)
        self.assertNotIn(7, bins)

    def test_reference_is_independent_of_channel_gain_corrections(self):
        config = replace(self.config, gains_real=[1, 0.5, -0.4], gains_imag=[0, 0.2, 0.7])
        other = SpectralBackground.fit(self.frames[:10], config)
        np.testing.assert_allclose(other.reference, self.background.reference)
        raw = range_fft(self.frames[-1].adc, config)
        expected = self.background.subtract(range_fft(self.frames[-1].adc, self.config), self.config) * config.gains
        np.testing.assert_allclose(self.background.subtract(raw, config), expected, atol=1e-10)

    def test_snapshot_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spectral-background.npz"
            self.background.save(path)
            loaded = SpectralBackground.from_path(path, self.config)
            np.testing.assert_array_equal(loaded.reference, self.background.reference)
            self.assertEqual(loaded.frame_count, 10)

    def test_mismatch_and_short_recording_rejected(self):
        with self.assertRaises(ValueError):
            self.background.validate(replace(self.config, samples=128))
        with self.assertRaises(ValueError):
            SpectralBackground.fit(self.frames[:1], self.config)
