import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

import numpy as np

from radar.config import Config
from radar.obstacle3d import Obstacle3DDetector, Settings, iter_results, load_config
from radar.protocol import encode
from radar.storage import Recorder
from radar.synthetic import Target, generate


class Obstacle3DTests(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.settings = Settings(window_seconds=.1, persistence_windows=3)

    def frames(self, count=6, **kwargs):
        return [generate(self.config, i, seed=i, **kwargs) for i in range(1, count + 1)]

    def test_multiple_stationary_and_moving_xyz_without_reference(self):
        targets = [Target(self.config.ranges[7], azimuth_deg=-20, elevation_deg=10),
                   Target(self.config.ranges[17], velocity_mps=.35, azimuth_deg=30, elevation_deg=-10, amplitude=500)]
        detector = Obstacle3DDetector(self.config, self.settings)
        results = [detector.push(f) for f in self.frames(targets=targets)]
        self.assertFalse(any(r['persistent'] for r in results[1]['returns']))
        for target in targets:
            result = min(results[-1]['returns'], key=lambda r: abs(r['provisional_range_m'] - target.range_m))
            self.assertTrue(result['persistent'])
            self.assertEqual(result['direction_status'], 'provisional_3d')
            self.assertAlmostEqual(result['azimuth_deg'], target.azimuth_deg, delta=5)
            self.assertAlmostEqual(result['elevation_deg'], target.elevation_deg, delta=5)
            self.assertAlmostEqual(np.linalg.norm(result['xyz']), target.range_m, delta=.01)
        self.assertFalse(results[-1]['angular_calibration_verified'])
        self.assertEqual(results[-1]['material'], 'unknown')

    def test_single_rx_return_kept_without_fabricating_angles(self):
        frames = self.frames(targets=[Target(self.config.ranges[8])], channel_response=[0, 1, 0], noise=0)
        detector = Obstacle3DDetector(self.config, self.settings)
        for frame in frames:
            result = detector.push(frame)
        item = min(result['returns'], key=lambda r: abs(r['native_bin'] - 8))
        self.assertTrue(item['persistent'])
        self.assertEqual(item['peak_receivers'], [2])
        self.assertIsNone(item['xyz'])
        self.assertIsNone(item['azimuth_deg'])
        self.assertEqual(result['state'], 'obstacle_candidates')

    def test_independent_rx_peaks_survive_average_power_masking(self):
        frames = self.frames(noise=0, targets=[])
        sample = np.arange(self.config.samples)
        # RX2 has an isolated tone absent from the other two receivers. Their
        # much stronger nearby tone would dominate receiver-averaged selection.
        for frame in frames:
            x = np.full(frame.adc.shape, 32768.)
            for rx, frequency, amplitude in ((0, 10, 10000), (1, 8, 500), (2, 10, 10000)):
                x[:, :, rx] += amplitude * np.cos(2 * np.pi * frequency * sample / self.config.samples)
            frame.adc = x.astype(np.uint16)
        detector = Obstacle3DDetector(self.config, self.settings)
        for frame in frames:
            result = detector.push(frame)
        self.assertTrue(any(abs(r['native_bin'] - 8) <= .25 and 2 in r['peak_receivers']
                            and r['persistent'] and r['xyz'] is None for r in result['returns']))

    def test_empty_and_missing_returns_never_report_clear_or_hold_old_point(self):
        detector = Obstacle3DDetector(self.config, self.settings)
        for frame in self.frames():
            result = detector.push(frame)
        self.assertTrue(any(r['persistent'] for r in result['returns']))
        frame = generate(self.config, 7, targets=[], noise=0)
        result = detector.push(frame)
        self.assertEqual(result['state'], 'uncertain')
        self.assertEqual(result['returns'], [])

    def test_gap_rails_restart_and_config_mismatch_clear_persistence(self):
        detector = Obstacle3DDetector(self.config, self.settings)
        frames = self.frames(count=12)
        for frame in frames[:3]:
            detector.push(frame)
        result = detector.push(frames[5])
        self.assertEqual(result['reason'], 'frame_discontinuity')
        for frame in frames[6:8]:
            result = detector.push(frame)
            self.assertFalse(any(r['persistent'] for r in result['returns']))
        bad = replace(frames[8], profile_id=123)
        self.assertEqual(detector.push(bad)['returns'], [])
        bad = replace(frames[9], adc=np.zeros_like(frames[9].adc))
        self.assertEqual(detector.push(bad)['reason'], 'invalid_adc_or_container_rails')
        detector.push(frames[10])
        result = detector.push(frames[0])
        self.assertIn('restart', result['reason'])
        self.assertIn('restart', detector.push(frames[11])['reason'])

    def test_covariance_rejects_incoherent_joint_direction(self):
        detector = Obstacle3DDetector(self.config, self.settings)
        rng = np.random.default_rng(1)
        frames = self.frames(noise=0, targets=[])
        for frame in frames:
            phase = rng.uniform(-np.pi, np.pi, (self.config.chirps, 1, 3))
            wave = 2 * np.pi * 8 * np.arange(self.config.samples)[None, :, None] / self.config.samples
            frame.adc = np.rint(32768 + 1000 * np.cos(wave + phase)).astype(np.uint16)
            result = detector.push(frame)
        item = min(result['returns'], key=lambda r: abs(r['native_bin'] - 8))
        self.assertTrue(item['persistent'])
        self.assertIsNone(item['xyz'])
        self.assertIn('incoherent_or_mixed_returns', item['direction_reasons'])

    def test_window_tail_not_promoted_and_sequence_timestamp_wrap_allowed(self):
        settings = replace(self.settings, window_seconds=.2)
        detector = Obstacle3DDetector(self.config, settings)
        frames = self.frames(count=4)
        frames = [replace(f, sequence=(0xfffffffe + i) & 0xffffffff,
                          timestamp_us=(0xffff0000 + i * 100000) & 0xffffffff) for i, f in enumerate(frames)]
        self.assertIsNone(detector.push(frames[0]))
        self.assertTrue(detector.push(frames[1])['complete_window'])
        self.assertIsNone(detector.push(frames[2]))
        self.assertTrue(detector.push(frames[3])['complete_window'])
        self.assertFalse(detector.latched)

    def test_replay_live_parity_raw_recording_and_terminal_invalidation(self):
        frames = self.frames()
        wire = b''.join(encode(f) for f in frames)
        from radar.protocol import Parser
        clock = [0.]

        class FakeSource:
            def __init__(self, *args, **kwargs):
                self.parser = Parser()
                self.pending = []
                self.frames = iter([self.parser.feed(encode(f))[0] for f in frames])
                self.transport_recorder = None
            def read(self):
                frame = next(self.frames)
                clock[0] = frame.timestamp_us / 1e6
                return frame
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with Recorder(path / 'raw', self.config) as recorder:
                for frame in frames:
                    recorder.write(frame)
            replayed = list(iter_results(self.config, recording=path / 'raw', output=path / 'replay', settings=self.settings))
            # Deterministic host clock matches simulated device increments.
            with patch('radar.acquisition.Source', FakeSource), patch('radar.obstacle3d.time.monotonic', side_effect=lambda: clock[0]):
                live = list(iter_results(self.config, port='fake', output=path / 'live', settings=self.settings))
            self.assertEqual(replayed[:-1], live[:-1])
            self.assertEqual((path / 'live/frames.grd').read_bytes(), wire)
            self.assertEqual(replayed[-1]['returns'], [])
            self.assertEqual(live[-1]['state'], 'uncertain')
            with self.assertRaises(FileExistsError):
                list(iter_results(self.config, recording=path / 'raw', output=path / 'replay'))
            with (path / 'raw/frames.grd').open('ab') as handle:
                handle.write(b'GRD3')
            bad = list(iter_results(self.config, recording=path / 'raw', output=path / 'truncated'))
            self.assertEqual(bad[-1]['reason'], 'recording_integrity_failure')
            self.assertFalse(json.loads((path / 'truncated/report.json').read_text())['complete'])

    def test_reject_changed_acquisition_axes_and_load_legacy_without_claiming_calibration(self):
        from radar_min.core import Config as MinimalConfig
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / 'legacy.json'
            legacy.write_text(json.dumps(asdict(MinimalConfig())))
            c = load_config(legacy)
            self.assertFalse(c.verified)
            self.assertIsNotNone(c.geometry_mm)
            path = Path(directory) / 'raw'
            with Recorder(path, self.config) as recorder:
                recorder.write(self.frames(count=1)[0])
            with self.assertRaisesRegex(ValueError, 'sample_rate_hz'):
                list(iter_results(replace(self.config, sample_rate_hz=2e6), recording=path))

    def test_configured_complex_channel_gains_and_array_matrix_are_used(self):
        matrix = np.array([[1, 0, 0], [.1j, 1, 0], [0, .1, 1]], complex)
        gains = np.array([1, .8 * np.exp(.3j), 1.2 * np.exp(-.4j)])
        config = replace(self.config, gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                         angle_matrix_real=matrix.real.tolist(), angle_matrix_imag=matrix.imag.tolist())
        target = Target(config.ranges[8], azimuth_deg=20, elevation_deg=-10)
        az, el = np.radians([20, -10])
        ideal = np.exp(2j * np.pi * config.array_geometry @ [np.sin(az) * np.cos(el), np.sin(el)])
        response = np.linalg.solve(matrix, ideal) / gains / ideal
        detector = Obstacle3DDetector(config, self.settings)
        for i in range(1, 5):
            result = detector.push(generate(config, i, targets=[target], channel_response=response, noise=1, seed=i))
        item = min(result['returns'], key=lambda r: abs(r['native_bin'] - 8))
        self.assertAlmostEqual(item['azimuth_deg'], 20, delta=5)
        self.assertAlmostEqual(item['elevation_deg'], -10, delta=5)
        self.assertGreater(item['model_fit'], .95)

    def test_empty_recording_is_not_reported_as_complete_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with Recorder(path / 'raw', self.config):
                pass
            results = list(iter_results(self.config, recording=path / 'raw', output=path / 'out'))
            self.assertEqual(results[-1]['state'], 'uncertain')
            self.assertFalse(json.loads((path / 'out/report.json').read_text())['complete'])

    def test_usb_timeout_and_close_failure_preserve_raw_and_withdraw_returns(self):
        from radar.protocol import Parser
        frames = self.frames(count=3)
        clock = [0.]

        class TimeoutSource:
            def __init__(self, *args, **kwargs):
                self.parser = Parser()
                self.frames = iter(frames)
                self.pending = []
                self.transport_recorder = None
            def read(self):
                frame = next(self.frames, None)
                if frame is None:
                    clock[0] += 2
                    return None
                clock[0] = frame.timestamp_us / 1e6
                return self.parser.feed(encode(frame))[0]
            def close(self):
                raise OSError('simulated unplug during close')

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'live'
            with patch('radar.acquisition.Source', TimeoutSource), patch('radar.obstacle3d.time.monotonic', side_effect=lambda: clock[0]):
                results = list(iter_results(self.config, port='fake', output=output, settings=self.settings))
            self.assertTrue(any(r['persistent'] for r in results[-2]['returns']))
            self.assertEqual(results[-1]['reason'], 'serial_timeout')
            self.assertEqual(results[-1]['returns'], [])
            self.assertEqual((output / 'frames.grd').read_bytes(), b''.join(encode(f) for f in frames))
            report = json.loads((output / 'report.json').read_text())
            self.assertFalse(report['complete'])
            self.assertEqual(report['cleanup_errors'], ['simulated unplug during close'])


if __name__ == '__main__':
    unittest.main()
