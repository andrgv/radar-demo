from pathlib import Path
import tempfile
import unittest
from radar.config import Config
from radar.diagnostics import diagnose
from radar.storage import Recorder
from radar.synthetic import generate


class DiagnosticTests(unittest.TestCase):
    def test_known_spectral_bin_and_repeated_adc(self):
        config = Config()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "session"
            with Recorder(directory, config) as recorder:
                recorder.write(generate(config, 1, seed=4))
                recorder.write(generate(config, 2, seed=4))
            result = diagnose(directory)
        self.assertEqual(result["frames"], 2)
        self.assertFalse(result["physical_scale_verified"])
        self.assertEqual(result["consecutive_identical_adc_frames"], 1)
        self.assertEqual(result["sequence_gaps"], 0)
        for channel in result["channels"]:
            self.assertEqual(channel["dominant_bin"], 7)
            self.assertGreater(channel["mean_fast_time_std_counts"], 0)
