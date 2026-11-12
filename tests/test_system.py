from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
import numpy as np
from radar.config import Config, C
from radar.protocol import HEADER, EDGE_TIMING, EDGE_TIMING_FULL, EDGE_TIMING_AVG16, Parser, encode
from radar.synthetic import Target, generate
from radar.processing import Processor, estimate_angle
from radar.calibration import calibrate_channels, fit_range
from radar.storage import Recorder, replay


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.frame = generate(self.config, seed=1)

    def test_wire_layout_and_fragmentation(self):
        self.assertEqual(HEADER.size, 48)
        packet = encode(self.frame)
        self.assertEqual(len(packet), 6580)
        parser = Parser()
        frames = []
        for start in range(0, len(packet), 7):
            frames.extend(parser.feed(packet[start:start + 7]))
        self.assertEqual(len(frames), 1)
        np.testing.assert_array_equal(frames[0].adc, self.frame.adc)

    def test_edge_timing_roundtrip_and_recording(self):
        frame = replace(self.frame, profile_id=0x33515401, capture_elapsed_us=3464,
                        edge_times_us=(31, 131, 231), edge_count=3)
        packet = encode(frame)
        self.assertEqual(len(packet), 6580 + EDGE_TIMING.size)
        parser = Parser()
        frames = parser.feed(packet[:37]) + parser.feed(packet[37:])
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].edge_times_us, (31, 131, 231))
        self.assertEqual(frames[0].capture_elapsed_us, 3464)
        self.assertEqual(frames[0].edge_count, 3)
        self.assertFalse(frames[0].edge_overflow)
        self.assertEqual(encode(frames[0]), packet)
        with tempfile.TemporaryDirectory() as folder:
            recording = Path(folder)/'capture'
            with Recorder(recording, self.config) as recorder:
                recorder.write(frames[0])
            saved = list(replay(recording))
            self.assertEqual(saved[0].edge_times_us, (31, 131, 231))
            from tools.analyze_mcu_edges import analyze_recording
            summary = analyze_recording(recording, Path(folder)/'edges.csv')
            self.assertEqual(summary['median_interval_us'], 100)
            self.assertEqual(summary['edge_counts'], {3: 1})
            self.assertEqual(summary['complete_edge_bursts'], 1)

    def test_edge_timing_overflow(self):
        frame = replace(self.frame, edge_times_us=tuple(range(64)), edge_count=65,
                        edge_overflow=True)
        decoded = Parser().feed(encode(frame))[0]
        self.assertEqual(decoded.edge_count, 65)
        self.assertTrue(decoded.edge_overflow)
        self.assertEqual(decoded.edge_times_us, tuple(range(64)))

    def test_full_edge_timing_roundtrip(self):
        frame = replace(self.frame, profile_id=0x33515402,
                        edge_times_us=tuple(range(112)), edge_count=112,
                        edge_capacity=128)
        packet = encode(frame)
        self.assertEqual(len(packet), 6580 + EDGE_TIMING_FULL.size)
        decoded = Parser().feed(packet)[0]
        self.assertEqual(decoded.edge_count, 112)
        self.assertEqual(decoded.edge_capacity, 128)
        self.assertFalse(decoded.edge_overflow)
        self.assertEqual(decoded.edge_times_us, tuple(range(112)))
        self.assertEqual(encode(decoded), packet)

    def test_avg16_edge_timing_roundtrip(self):
        frame = replace(self.frame, profile_id=0x33515403,
                        edge_times_us=tuple(range(272)), edge_count=272,
                        edge_capacity=320, flags=27)
        packet = encode(frame)
        self.assertEqual(len(packet), 6580 + EDGE_TIMING_AVG16.size)
        decoded = Parser().feed(packet)[0]
        self.assertEqual(decoded.edge_count, 272)
        self.assertEqual(decoded.edge_capacity, 320)
        self.assertFalse(decoded.edge_overflow)
        self.assertEqual(decoded.edge_times_us, tuple(range(272)))
        self.assertEqual(encode(decoded), packet)

    def test_crc_garbage_and_header_recovery(self):
        bad_payload = bytearray(encode(self.frame))
        bad_payload[120] ^= 0x80
        bad_header = bytearray(encode(self.frame))
        bad_header[8] ^= 0x40
        parser = Parser()
        frames = parser.feed(b"garbage" + bad_payload + bad_header + encode(self.frame))
        self.assertEqual(len(frames), 1)
        self.assertEqual(parser.bad_crc, 1)
        self.assertGreater(parser.bad_headers, 0)

    def test_loss_wrap_restart(self):
        parser = Parser()
        for sequence in [0xfffffffe, 0xffffffff, 0, 3, 1]:
            parser.feed(encode(replace(self.frame, sequence=sequence)))
        self.assertEqual(parser.gaps, 2)
        self.assertEqual(parser.restarts, 1)

    def test_truncation(self):
        parser = Parser()
        packet = encode(self.frame)
        self.assertEqual(parser.feed(packet[:-1]), [])
        self.assertEqual(len(parser.feed(packet[-1:])), 1)

    def test_random_chunk_boundaries_and_dropped_bytes(self):
        rng = np.random.default_rng(18)
        packet1 = encode(replace(self.frame, sequence=1))
        packet2 = encode(replace(self.frame, sequence=2))
        packet3 = encode(replace(self.frame, sequence=3))
        stream = packet1 + packet2[:200] + packet2[203:] + packet3
        parser = Parser()
        frames = []
        offset = 0
        while offset < len(stream):
            count = int(rng.integers(1, 512))
            frames.extend(parser.feed(stream[offset:offset + count]))
            offset += count
        self.assertEqual([frame.sequence for frame in frames], [1, 3])
        self.assertEqual(parser.gaps, 1)
        self.assertEqual(parser.bad_crc, 1)


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(discard_chirps=1,chirp_timing_verified=True,carrier_frequency_verified=True)

    def test_stationary_and_moving(self):
        config = self.config
        result = Processor(config).process(generate(config, seed=7))
        stationary = [item for item in result.detections if not item.moving]
        moving = [item for item in result.detections if item.moving]
        self.assertTrue(stationary)
        self.assertTrue(moving)
        self.assertEqual(len(stationary), 1)
        static = min(stationary, key=lambda item: abs(item.range_m - config.ranges[7]))
        dynamic = min(moving, key=lambda item: abs(item.range_m - config.ranges[17]))
        self.assertLess(abs(static.range_m - config.ranges[7]), (config.ranges[1] - config.ranges[0]) * 0.01)
        self.assertLess(abs(static.azimuth_deg + 20), 1)
        self.assertLess(abs(static.elevation_deg - 10), 1)
        self.assertLess(abs(dynamic.azimuth_deg - 30), 1)
        velocity_resolution = C / (2 * config.carrier_hz * 16 * config.chirp_interval_s)
        self.assertLess(abs(dynamic.velocity_mps - 0.35), velocity_resolution)

    def test_negative_velocity(self):
        target = Target(self.config.ranges[10], -0.45, -25, -15)
        result = Processor(self.config).process(generate(self.config, targets=[target], seed=3))
        detection = max([item for item in result.detections if item.moving], key=lambda item: item.power_db)
        self.assertLess(detection.velocity_mps, 0)
        self.assertLess(abs(detection.elevation_deg + 15), 1)

    def test_noise_does_not_become_material_classification(self):
        result = Processor(self.config).process(generate(self.config, targets=[], seed=8))
        self.assertLess(len(result.detections), 3)
        self.assertNotIn("glass_probability", result.features)
        self.assertTrue(all(np.isfinite(value) for value in result.features.values()))

    def test_configuration_mismatch(self):
        frame = generate(self.config)
        with self.assertRaises(ValueError):
            Processor(replace(self.config, profile_id=2)).process(frame)

    def test_gap_resets_temporal_features(self):
        processor = Processor(self.config)
        processor.process(generate(self.config, 1))
        processor.process(generate(self.config, 2))
        result = processor.process(generate(self.config, 4))
        self.assertEqual(result.features["temporal_frames"], 1)

    def test_invalid_direction(self):
        channels = np.exp(1j * np.array([0, 3, 3]))
        self.assertFalse(estimate_angle(channels, self.config)[-1])

    def test_channel_calibration(self):
        response = np.array([1, 0.7 * np.exp(0.6j), 1.3 * np.exp(-0.4j)])
        target = Target(self.config.ranges[10])
        frames = [generate(self.config, index + 1, [target], seed=index, channel_response=response) for index in range(10)]
        calibrated = calibrate_channels(frames, self.config, target.range_m)
        np.testing.assert_allclose(calibrated.gains, 1 / response, atol=0.01)
        result = Processor(calibrated).process(frames[0])
        detection = max(result.detections, key=lambda item: item.power_db)
        self.assertLess(abs(detection.azimuth_deg), 0.5)
        self.assertFalse(calibrated.verified)

    def test_coherent_broadband_clutter_is_not_a_calibration_target(self):
        config = self.config
        common = np.random.default_rng(20).normal(0, 1000, (1, config.samples, 1))
        adc = np.clip(32768 + np.broadcast_to(common, (config.chirps, config.samples, 3)), 0, 65535).astype("<u2")
        frame = replace(generate(config), adc=adc)
        with self.assertRaisesRegex(ValueError, "not sufficiently isolated"):
            calibrate_channels([frame], config, config.ranges[10])

    def test_range_fit(self):
        fit = fit_range([1, 2, 3], [1.1, 2.2, 3.3])
        self.assertAlmostEqual(fit["scale"], 1.1)
        self.assertLess(fit["rms_m"], 1e-10)

    def test_fractional_bin_with_empirical_range_scale(self):
        config = replace(self.config, range_scale=4.45, range_offset_m=0.008)
        spacing = config.ranges[1] - config.ranges[0]
        target = Target(float(config.ranges[10] + 0.25 * spacing))
        result = Processor(config).process(generate(config, targets=[target], noise=1, seed=1))
        detection = max(result.detections, key=lambda item: item.power_db)
        self.assertLess(abs(detection.range_m - target.range_m), 0.03 * spacing)
        self.assertFalse(result.calibrated)

    def test_nonpositive_range_scale_rejected(self):
        with self.assertRaises(ValueError):
            replace(self.config, range_scale=0).validate()

    def test_bad_geometry(self):
        with self.assertRaises(ValueError):
            replace(self.config, geometry_wavelengths=[[0, 0], [1, 0], [2, 0]]).validate()

    def test_recording_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "session"
            frame = generate(self.config, seed=7)
            result = Processor(self.config).process(frame)
            with Recorder(directory, self.config, {"label": "glass"}) as recorder:
                recorder.write(frame, result)
            frames = list(replay(directory))
            self.assertEqual(len(frames), 1)
            np.testing.assert_array_equal(frames[0].adc, frame.adc)
            self.assertEqual(Config.load(directory / "config.json"), self.config)
            with self.assertRaises(FileExistsError):
                Recorder(directory, self.config)


if __name__ == "__main__":
    unittest.main()
