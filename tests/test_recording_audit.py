import hashlib
from pathlib import Path
import tempfile
import unittest
import numpy as np
from radar.config import Config
from radar.recording_audit import decode_q15_pair, factory_matrices, nominal_waveform, read_register_profile, write_audit
from radar.storage import Recorder
from radar.synthetic import Target, generate


class RecordingAuditTests(unittest.TestCase):
    def setUp(self):
        self.profile = Path(__file__).resolve().parents[1] / "firmware/vendor/presence_detection_tracking.h"
        self.registers, self.clock = read_register_profile(self.profile)

    def test_nominal_range_model_reproduces_independent_metadata(self):
        result = nominal_waveform(self.registers, self.clock)
        self.assertEqual(result["sample_rate_hz_nominal"], 5_000_000)
        self.assertEqual(result["slope_hz_s_nominal"], 33_691_406_250_000)
        self.assertAlmostEqual(result["fft_bin_spacing_m_nominal"], 0.34758545855072465)
        for crosscheck in result["independent_official_metadata_crosschecks"]:
            self.assertLess(crosscheck["absolute_difference_m"], 1e-12)
        self.assertIsNone(result["chirp_interval_s"])
        self.assertIsNone(result["carrier_hz"])

    def test_q15_signed_packing_and_matrix_shapes(self):
        self.assertEqual(decode_q15_pair(0x40000000), 0.5 + 0j)
        self.assertEqual(decode_q15_pair(0x80008000), -1 - 1j)
        matrices = factory_matrices(self.registers)
        self.assertEqual(matrices["H"].shape, (2, 3))
        self.assertEqual(matrices["E"].shape, (2, 3))
        self.assertNotEqual(matrices["H"][1, 0], 0)
        self.assertNotEqual(matrices["E"][1, 0], 0)

    def test_source_derived_config_matches_loaded_firmware(self):
        config = Config.load(self.profile.parents[2] / "configs/range-source-derived.json")
        waveform = nominal_waveform(self.registers, self.clock)
        self.assertEqual(config.sample_rate_hz, waveform["sample_rate_hz_nominal"])
        self.assertEqual(config.slope_hz_s, waveform["slope_hz_s_nominal"])
        self.assertAlmostEqual(config.ranges[1], waveform["fft_bin_spacing_m_nominal"])
        self.assertEqual(config.range_scale, 1)
        self.assertEqual(config.range_offset_m, 0)
        self.assertFalse(config.verified)

    def test_audit_preserves_raw_files_and_detects_format_alternatives(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "recordings"
            root.mkdir()
            config = Config(sample_rate_hz=5e6, slope_hz_s=33_691_406_250_000)
            directory = root / "plate_1_3m"
            with Recorder(directory, config) as recorder:
                for sequence in range(1, 11):
                    recorder.write(generate(config, sequence, targets=[Target(1.3)], seed=sequence))
            raw_path = directory / "frames.grd"
            before = hashlib.sha256(raw_path.read_bytes()).hexdigest()
            result = write_audit(root, Path(temporary) / "audit", self.profile)
            self.assertEqual(before, hashlib.sha256(raw_path.read_bytes()).hexdigest())
            self.assertEqual(result["total_frames"], 10)
            self.assertEqual(result["total_adc_containers"], 10 * 17 * 64 * 3)
            session = result["sessions"][0]
            scores = session["packing_hypotheses"]
            self.assertLess(scores["unsigned16_sample_interleaved"]["difference_rms_over_signal_rms"],
                            scores["byte_swapped_unsigned16"]["difference_rms_over_signal_rms"])
            self.assertLess(abs(result["plate_nominal_range_checks"][0]["error_m"]), 0.02)
            self.assertGreater(session["consecutive_chirp_correlation_p05_median_p95"][1], 0.99)
            self.assertFalse(session["physical_rx_order_verified"])
