import contextlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
from radar.protocol import Frame, encode
from radar.storage import Recorder
from radar_min.core import Config
from radar_min.cfar import CfarConfig, CfarDetector, ca_thresholds
from radar_min.__main__ import main, stream


C = Config()


def frame(seq, k=2, amplitude=1000):
    rng = np.random.default_rng(seq)
    x = 32768 + amplitude*np.cos(2*np.pi*k*np.arange(C.samples)/C.samples)
    adc = x[None, :, None] + rng.normal(0, 2, (C.chirps, C.samples, 3))
    return Frame(seq, seq*100000, C.profile_id, adc.astype('uint16'))


class CfarTests(unittest.TestCase):
    def test_guard_cells_dc_nyquist_and_edges(self):
        p = np.ones(33)
        p[0] = p[32] = 1e9
        p[1:4] = 100  # CUT and guard cells must not contaminate bin 1
        noise, threshold, counts = ca_thresholds(p, CfarConfig())
        self.assertEqual(counts[1], 8)
        self.assertEqual(noise[1], 1)
        self.assertEqual(threshold[1], 6)
        self.assertTrue(np.isnan(threshold[0]))
        self.assertTrue(np.isnan(threshold[32]))
        _, threshold, _ = ca_thresholds(p, CfarConfig(min_training_cells=9))
        self.assertTrue(np.isnan(threshold[1]))

    def test_power_scale_invariance(self):
        p = np.linspace(1, 5, 33)
        p[10] = 100
        _, a, _ = ca_thresholds(p, CfarConfig())
        _, b, _ = ca_thresholds(20*p, CfarConfig())
        np.testing.assert_allclose(b, 20*a)
        np.testing.assert_equal(p > a, 20*p > b)

    def test_real_fft_target_present_at_start_and_noise_only(self):
        for k in (1, 2, 4):
            d = CfarDetector(C)
            results = [d.update(frame(i, k)) for i in range(1, 4)]
            self.assertEqual([r['target_detected'] for r in results], [False, False, True])
            self.assertEqual(results[-1]['range_bin'], k)
            self.assertIsNone(results[-1]['range_m'])
            self.assertFalse(results[-1]['calibrated'])
            self.assertFalse(d.update(frame(4, amplitude=0))['target_detected'])
        d = CfarDetector(C)
        self.assertFalse(any(d.update(frame(i, amplitude=0))['target_detected'] for i in range(1, 101)))

    def test_grouping_nearest_selection_and_outside_peak(self):
        p = np.ones(33)
        p[1:3] = [160, 120]
        p[4] = 200
        with patch('radar_min.cfar.power', return_value=p):
            r = CfarDetector(C).update(frame(1))
        self.assertEqual([v['range_bin'] for v in r['candidates']], [1, 4])
        self.assertEqual(r['candidates'][0]['bins'], [1, 2])
        self.assertEqual(r['candidate_bin'], 1)
        p = np.ones(33);p[4:6] = [100, 200]
        with patch('radar_min.cfar.power', return_value=p):
            self.assertEqual(CfarDetector(C).update(frame(1))['candidates'], [])

    def test_gaps_restart_and_invalid_adc_clear_persistence(self):
        d = CfarDetector(C)
        for i in range(1, 4):d.update(frame(i))
        self.assertEqual(d.update(frame(5))['reason'], 'sequence_gap')
        self.assertFalse(d.update(frame(6))['target_detected'])
        self.assertEqual(d.update(frame(6))['reason'], 'restart_or_duplicate')
        self.assertFalse(d.update(frame(7))['target_detected'])
        f = frame(8);f.adc[:] = 0
        self.assertEqual(d.update(f)['reason'], 'adc_container_rail')
        self.assertFalse(d.update(frame(9))['target_detected'])

    def test_config_validation_and_no_testable_bins(self):
        for kw in (dict(factor=1), dict(factor=float('nan')), dict(guard_cells=-1),
                   dict(training_cells=0), dict(min_training_cells=17), dict(guard_cells=1.5)):
            with self.assertRaises(ValueError):CfarConfig(**kw)
        with self.assertRaises(ValueError):CfarDetector(C, CfarConfig(guard_cells=32))

    def test_replay_cli_without_baseline_and_bad_combinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'r'
            with Recorder(path, C) as recorder:
                for i in range(1, 5):recorder.write(frame(i))
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(main(['replay', str(path), '--detector', 'cfar']), 0)
            rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
            self.assertTrue(rows[-1]['target_detected'])
            self.assertEqual(json.loads(stderr.getvalue())['detected_frames'], 2)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['replay', str(path)]), 2)
                self.assertEqual(main(['replay', str(path), '--detector', 'cfar', '--cfar-factor', '0']), 2)

    def test_live_records_settings_without_baseline(self):
        packet = encode(frame(1));stop = threading.Event()
        class Serial:
            in_waiting = 0
            closed = False
            def reset_input_buffer(self):pass
            def write(self, value):pass
            def read(self, n):return packet
            def close(self):self.closed = True
        ser = Serial()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'live'
            stream('fake', C, path, 5, CfarDetector(C), serial_factory=lambda *a, **kw:ser,
                   observer=lambda f, r:stop.set(), stop_event=stop, quiet=True)
            metadata = json.loads((path/'metadata.json').read_text())
            self.assertIsNone(metadata['baseline_provenance'])
            self.assertEqual(metadata['detector']['cfar']['factor'], 6)
            self.assertEqual((path/'serial-wire.bin').read_bytes(), packet)
            reading = json.loads((path/'readings.jsonl').read_text())
            self.assertEqual(len(reading['threshold_power']), 33)
            self.assertIsNone(reading['threshold_power'][0])
        self.assertTrue(ser.closed)


if __name__ == '__main__':unittest.main()
