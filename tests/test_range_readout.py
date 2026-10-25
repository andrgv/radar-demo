from dataclasses import replace
import unittest
from radar.config import Config
from radar.gui import range_readout
from radar.processing import Processor
from radar.synthetic import generate


class RangeReadoutTests(unittest.TestCase):
    def test_numeric_distances_with_provisional_scale(self):
        config = Config()
        result = Processor(config).process(generate(config, seed=1))
        text = range_readout(result)
        self.assertIn("provisional scale", text)
        for detection in result.detections:
            self.assertIn(f"{detection.range_m:.3f} m", text)

    def test_no_detection_does_not_report_strongest_noise_bin(self):
        result = Processor(Config()).process(generate(Config(), seed=1))
        text = range_readout(replace(result, detections=[]))
        self.assertIn("No detections", text)

    def test_verified_configuration_label(self):
        result = Processor(Config()).process(generate(Config(), seed=1))
        self.assertNotIn("provisional", range_readout(replace(result, calibrated=True)))
