import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from radar.angle_lab import raw_model_phase
from radar.cfar_map import MultiObstacleMap, demo_frame, iter_results, main
from radar.config import Config
from radar.protocol import Frame, Parser, encode
from radar.storage import Recorder
from radar_min.cfar import CfarConfig


class CfarMapTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
            geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]], mount_roll_deg=90)
        self.xyz = [0, 2, 0]

    def detector(self, **kwargs):
        return MultiObstacleMap(self.cfg, raw_model_phase(self.cfg, self.xyz)[0], self.xyz,
                                min_range=.7, max_range=10, **kwargs)

    def frame(self, seq, targets=((6.2, -8, 1500), (21.1, 12, 1000)), incoherent=False):
        x = np.full((self.cfg.chirps, self.cfg.samples, 3), 32768., dtype=float)
        for bin_position, az, amplitude in targets:
            distance = bin_position*self.cfg.ranges[1]
            z = self.xyz[2]
            h = np.sqrt(distance**2-z**2)
            xyz = np.array([h*np.sin(np.radians(az)), h*np.cos(np.radians(az)), z])
            raw = np.linalg.solve(self.cfg.angle_matrix,
                np.exp(2j*np.pi*(self.cfg.array_geometry@xyz[[0, 2]]/distance)))
            raw /= max(abs(raw))
            phase = np.exp(2j*np.pi*bin_position*np.arange(self.cfg.samples)/self.cfg.samples)
            term = np.broadcast_to(phase[None, :, None]*raw[None, None, :], x.shape).copy()
            if incoherent:
                term[:, :, 1] *= np.exp(2j*np.pi*np.arange(self.cfg.chirps)/self.cfg.chirps)[:, None]
            x += amplitude*np.real(term)
        x += np.random.default_rng(seq).normal(0, .5, x.shape)
        return Frame(seq, seq*100000, self.cfg.profile_id, x.astype('uint16'))

    def confirm(self, detector, **kwargs):
        return [detector.update(self.frame(i, **kwargs)) for i in range(1, 4)][-1]

    def test_two_obstacles_real_adc_independent_range_and_angle(self):
        d = self.detector()
        first = d.update(self.frame(1))
        self.assertFalse(first['obstacles'])
        d.update(self.frame(2))
        result = d.update(self.frame(3))
        self.assertEqual(len(result['obstacles']), 2)
        for item, (bin_position, angle) in zip(result['obstacles'], [(6.2, -8), (21.1, 12)]):
            self.assertEqual(item['state'], 'LOCALIZED')
            self.assertAlmostEqual(item['range_m'], bin_position*self.cfg.ranges[1], delta=.003)
            self.assertAlmostEqual(item['azimuth_deg'], angle, delta=.1)
            self.assertAlmostEqual(np.hypot(item['x_m'], item['y_m']), item['range_m'], places=6)
            self.assertEqual(item['confirmation_hits'], 3)
        self.assertFalse(result['calibrated'])
        json.dumps(result, allow_nan=False)

    def test_production_demo_has_three_independent_targets(self):
        self.cfg = Config.load('configs/exploratory-roll90-phase.json')
        d = self.detector()
        for seq in range(1, 5):
            result = d.update(demo_frame(self.cfg, seq))
        self.assertEqual(len(result['obstacles']), 3)
        for item, angle in zip(result['obstacles'], [-12, 8, 18]):
            self.assertEqual(item['state'], 'LOCALIZED')
            self.assertAlmostEqual(item['azimuth_deg'], angle, delta=.1)

    def test_gain_and_nondiagonal_matrix_are_applied_only_to_angle(self):
        self.cfg.angle_matrix_real = [[.5, 0, 0], [.05, -.44, 0], [-.06, 0, -.16]]
        self.cfg.angle_matrix_imag = [[0, 0, 0], [.10, .16, 0], [.02, 0, -.46]]
        baseline = self.confirm(self.detector())
        self.cfg.gains_real = [1, .7, 1.2]
        self.cfg.gains_imag = [0, .3, -.2]
        corrected = self.confirm(self.detector())
        np.testing.assert_allclose(baseline['power_db'], corrected['power_db'])
        for a, b in zip(baseline['obstacles'], corrected['obstacles']):
            self.assertEqual(a['azimuth_deg'], b['azimuth_deg'])

    def test_miss_removes_only_missing_track_other_id_survives(self):
        d = self.detector()
        result = self.confirm(d)
        near_id, far_id = [v['track_id'] for v in result['obstacles']]
        result = d.update(self.frame(4, targets=((21.1, 12, 1000),)))
        self.assertEqual([v['track_id'] for v in result['obstacles']], [far_id])
        result = d.update(self.frame(5))
        near, far = result['observations']
        self.assertNotEqual(near['track_id'], near_id)
        self.assertFalse(near['confirmed'])
        self.assertEqual(far['track_id'], far_id)
        result = d.update(self.frame(6, targets=()))
        self.assertEqual(result['observations'], [])
        self.assertFalse(d.tracks)

    def test_gap_bad_flags_rails_and_counter_changes_clear_all_tracks(self):
        for fault in ('gap', 'flags', 'rails', 'errors', 'drops', 'profile'):
            with self.subTest(fault=fault):
                d = self.detector()
                self.confirm(d)
                frame = self.frame(5 if fault == 'gap' else 4)
                if fault == 'flags': frame.flags = 0
                if fault == 'rails': frame.adc[self.cfg.discard_chirps, 0, 0] = 0
                if fault == 'errors': frame.errors = 1
                if fault == 'drops': frame.dropped = 1
                if fault == 'profile': frame.profile_id += 1
                result = d.update(frame)
                self.assertEqual(result['state'], 'UNCERTAIN')
                self.assertEqual(result['obstacles'], [])
                self.assertFalse(d.tracks)

    def test_incoherent_reflector_keeps_presence_without_fake_location(self):
        result = self.confirm(self.detector(), incoherent=True)
        self.assertEqual(len(result['obstacles']), 2)
        for item in result['obstacles']:
            self.assertEqual(item['state'], 'UNRESOLVED')
            self.assertIsNone(item['azimuth_deg'])
            self.assertIsNone(item['x_m'])
            self.assertLess(item['coherence_rx2'], .9)

    def test_unresolved_fine_range_does_not_emit_position(self):
        with patch('radar.cfar_map.refine_group', return_value={
                'range_m': None, 'reason': 'multiple_fine_peaks', 'support_m': [1, 3]}):
            result = self.confirm(self.detector())
        self.assertTrue(result['obstacles'])
        for item in result['obstacles']:
            self.assertEqual(item['state'], 'UNRESOLVED')
            self.assertIsNone(item['range_m'])
            self.assertIsNone(item['x_m'])

    def test_height_is_used_and_bounds_reject_unusable_angles(self):
        self.xyz = [0, 2, -.3]
        result = self.confirm(self.detector())
        for item in result['obstacles']:
            self.assertAlmostEqual(item['x_m']**2+item['y_m']**2+.3**2,
                                   item['range_m']**2, places=6)
        result = self.confirm(self.detector(), targets=((6.2, 35, 1500),))
        self.assertEqual(result['obstacles'][0]['state'], 'UNRESOLVED')

    def test_bearing_jump_restarts_independent_confirmation(self):
        d = self.detector()
        initial = self.confirm(d, targets=((6.2, -10, 1500),))
        old_id = initial['obstacles'][0]['track_id']
        result = d.update(self.frame(4, targets=((6.2, 10, 1500),)))
        self.assertFalse(result['obstacles'])
        self.assertNotEqual(result['observations'][0]['track_id'], old_id)

    def test_same_range_reflectors_are_not_claimed_as_two_resolved_objects(self):
        result = self.confirm(self.detector(), targets=((6.2, -8, 1000), (6.2, 12, 1000)))
        self.assertLessEqual(len(result['obstacles']), 1)

    def test_replay_exports_raw_frames_terminal_state_and_same_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            recording, output = Path(tmp)/'input', Path(tmp)/'output'
            with Recorder(recording, self.cfg) as recorder:
                for i in range(1, 5): recorder.write(self.frame(i))
            rows = list(iter_results(self.detector(), recording=recording, output=output))
            self.assertEqual(len(rows[-1]['obstacles']), 2)
            self.assertEqual((recording/'frames.grd').read_bytes(), (output/'frames.grd').read_bytes())
            exported = [json.loads(v) for v in (output/'obstacles2d.jsonl').read_text().splitlines()]
            self.assertEqual(exported[:-1], rows)
            self.assertEqual(exported[-1]['state'], 'UNCERTAIN')
            self.assertEqual(exported[-1]['obstacles'], [])
            with self.assertRaises(FileExistsError):
                list(iter_results(self.detector(), recording=recording, output=output))

    def test_truncated_replay_fails_and_withdraws_tracks(self):
        with tempfile.TemporaryDirectory() as tmp:
            recording, output = Path(tmp)/'input', Path(tmp)/'output'
            with Recorder(recording, self.cfg) as recorder:
                recorder.write(self.frame(1))
            with (recording/'frames.grd').open('ab') as f:
                f.write(encode(self.frame(2))[:100])
            d = self.detector()
            with self.assertRaisesRegex(ValueError, 'Truncated'):
                list(iter_results(d, recording=recording, output=output))
            self.assertFalse(d.tracks)
            self.assertEqual(json.loads((output/'obstacles2d.jsonl').read_text().splitlines()[-1])['state'],
                             'UNCERTAIN')

    def test_empty_replay_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            recording = Path(tmp)/'empty'
            with Recorder(recording, self.cfg):
                pass
            with self.assertRaisesRegex(ValueError, 'No complete'):
                list(iter_results(self.detector(), recording=recording))

    def test_corrupt_recording_withdraws_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            recording = Path(tmp)/'corrupt'
            with Recorder(recording, self.cfg) as recorder:
                for i in range(1, 5): recorder.write(self.frame(i))
            packet = bytearray(encode(self.frame(1)))
            packet[-1] ^= 1
            # Insert a bad packet before valid data; preserve the original
            # bytes so replay must encounter a real parser CRC rejection.
            raw = (recording/'frames.grd').read_bytes()
            (recording/'frames.grd').write_bytes(packet+raw)
            rows = list(iter_results(self.detector(), recording=recording))
            self.assertEqual(rows[0]['reason'], 'transport_corruption')
            self.assertFalse(rows[0]['obstacles'])
            self.assertFalse(rows[2]['obstacles'])
            self.assertEqual(len(rows[3]['obstacles']), 2)

    def test_live_handshake_recording_and_stop_on_generator_close(self):
        packets = [encode(self.frame(i)) for i in range(1, 4)]
        class Serial:
            in_waiting = 0
            def __init__(self): self.commands = []; self.closed = False
            def reset_input_buffer(self): pass
            def flush(self): pass
            def write(self, value): self.commands.append(value)
            def read(self, n): return packets.pop(0) if packets else b''
            def close(self): self.closed = True
        serial = Serial()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'live'
            with patch('serial.Serial', return_value=serial), patch('radar.acquisition.time.sleep'):
                results = iter_results(self.detector(), port='test', output=output)
                rows = [next(results) for _ in range(3)]
                results.close()
            self.assertTrue(serial.closed)
            self.assertEqual(serial.commands, [b'c', b'B', b'c'])
            self.assertEqual(len(rows[-1]['obstacles']), 2)
            self.assertEqual((output/'serial-wire.bin').read_bytes(),
                             b''.join(encode(self.frame(i)) for i in range(1, 4)))
            self.assertEqual(json.loads((output/'obstacles2d.jsonl').read_text().splitlines()[-1])['state'],
                             'UNCERTAIN')

    def test_live_timeout_withdraws_tracks_and_closes_port(self):
        detector = self.detector()
        self.confirm(detector)
        source = SimpleNamespace(read=lambda: None, close=Mock(), parser=Parser(), pending=[],
                                 serial=SimpleNamespace(in_waiting=0))
        with patch('radar.acquisition.Source', return_value=source), \
                patch('radar.cfar_map.time.monotonic', side_effect=[0, 2]):
            with self.assertRaises(TimeoutError):
                list(iter_results(detector, port='test'))
        source.close.assert_called_once()
        self.assertFalse(detector.tracks)

    def test_live_backlog_withdraws_all_current_obstacles(self):
        detector = self.detector()
        self.confirm(detector)
        source = SimpleNamespace(read=lambda: self.frame(4), close=Mock(), parser=Parser(),
            pending=[object(), object()], serial=SimpleNamespace(in_waiting=0))
        with patch('radar.acquisition.Source', return_value=source):
            results = iter_results(detector, port='test')
            result = next(results)
            results.close()
        self.assertEqual(result['reason'], 'serial_backlog')
        self.assertEqual(result['obstacles'], [])
        self.assertFalse(detector.tracks)
        source.close.assert_called_once()

    def test_settings_and_missing_reference_are_rejected_before_acquisition(self):
        for kwargs in (dict(window=0), dict(confirmation_frames=0), dict(limit_deg=0),
                       dict(settings=CfarConfig(guard_cells=40)), dict(target_z=float('nan'))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.detector(**kwargs)
        self.cfg.range_scale = 1.1
        with self.assertRaisesRegex(ValueError, 'range_scale'):
            self.detector()
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            main(['--port', 'unused'])

    def test_cli_demo_snapshot_has_all_three_points_and_table(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MPLBACKEND': 'Agg'}):
            path = Path(tmp)/'map.png'
            # Deterministic generator length without waiting on a wall-clock limit.
            def frames(detector, **kwargs):
                for i in range(1, 5):
                    yield detector.update(demo_frame(detector.config, i))
            with patch('radar.cfar_map.iter_results', side_effect=frames), contextlib.redirect_stdout(io.StringIO()) as stdout:
                code = main(['--demo', '--snapshot', str(path)])
            self.assertEqual(code, 0)
            self.assertGreater(path.stat().st_size, 10000)
            result = json.loads(stdout.getvalue().splitlines()[-1])
            self.assertEqual(len(result['obstacles']), 3)


if __name__ == '__main__':
    unittest.main()
