from dataclasses import replace
import unittest
from radar.config import Config
from radar.gui import range_readout, track_readout, diagnostic_readout
from radar.tracking import RangeTrack
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

    def test_coasting_track_is_distinct_from_current_detections(self):
        result = Processor(Config()).process(generate(Config(), seed=1))
        track = RangeTrack(7, 1.2, 'coasting', False, .2, .5, False, None, False, 'none')
        result = replace(result, detections=[], tracks=[track])
        self.assertIn('No detections', range_readout(result))
        self.assertIn('#7', track_readout(result))
        self.assertIn('retained estimate', track_readout(result))
        self.assertIn('direction unavailable', track_readout(result))
        self.assertIn('Track #7 nearby bin', diagnostic_readout(result))

    def test_tentative_tracks_are_not_reported_as_confirmed(self):
        result = Processor(Config()).process(generate(Config(), seed=1))
        self.assertIn('No confirmed range tracks', track_readout(result))
