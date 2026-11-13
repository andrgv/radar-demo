import copy
from dataclasses import asdict
import tempfile
from pathlib import Path
import unittest
import json
import io
import contextlib
from unittest.mock import patch

import numpy as np

from radar.config import Config
from radar.obstacle import fit_profiles, classify_profile, ObstacleDetector, load_model, _write_new, fit_experiment, replay_obstacle, live_obstacle, _hash
from radar.protocol import Frame


class ObstacleTests(unittest.TestCase):
    def model(self):
        config = Config()
        opened = np.full((2, config.samples//2+1), 40.)
        closed = opened.copy()
        closed[:, [4, 5, 10, 11]] += [10, 10, -10, -10]
        model = fit_profiles(opened, closed, np.zeros_like(opened))
        model.update(schema=1, method='fixed_scene_signed_template_v1', config=asdict(config), window_frames=10,
                     training_raw_sha256=[])
        return model

    def test_opposite_signs_combine_and_one_bin_drift_does_not_trigger(self):
        model = self.model()
        p = np.array(model['baseline_db'])
        p[4] += 4.2  # Old one-bin 3 dB rule would falsely trigger.
        self.assertEqual(classify_profile(p, model)['state'], 'clear')
        blocked = np.array(model['baseline_db']) + np.array(model['signature_db'])
        self.assertEqual(classify_profile(blocked, model)['state'], 'obstacle')
        midpoint = np.array(model['baseline_db']) + .5*np.array(model['signature_db'])
        self.assertEqual(classify_profile(midpoint, model)['state'], 'uncertain')
        self.assertIsNone(classify_profile(blocked, model)['range_m'])

    def test_single_bin_and_inconsistent_examples_refused(self):
        opened = np.full((2, 33), 40.)
        closed = opened.copy()
        closed[:, 7] += 12
        with self.assertRaises(ValueError):
            fit_profiles(opened, closed, np.zeros_like(opened))
        closed[1, 7] -= 24
        with self.assertRaises(ValueError):
            fit_profiles(opened, closed, np.zeros_like(opened))

    def test_gap_clears_window_and_restart_invalidates_model(self):
        detector = ObstacleDetector(self.model())
        cfg = detector.config
        adc = np.full((cfg.chirps, cfg.samples, 3), 20000, dtype='uint16')
        for i in range(1, 10):
            self.assertIsNone(detector.update(Frame(i, i*100000, cfg.profile_id, adc)))
        result = detector.update(Frame(11, 1100000, cfg.profile_id, adc))
        self.assertEqual(result['reason'], 'sequence_gap')
        self.assertEqual(len(detector.window), 0)
        result = detector.update(Frame(1, 100000, cfg.profile_id, adc))
        self.assertEqual(result['reason'], 'device_restart_requires_new_calibration')
        result = detector.update(Frame(2, 200000, cfg.profile_id, adc))
        self.assertEqual(result['state'], 'uncertain')

    def test_model_validation_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'model.json'
            model = self.model()
            _write_new(path, model)
            self.assertEqual(load_model(path)[0]['selected_bins'], [4, 5, 10, 11])
            with self.assertRaises(FileExistsError):
                _write_new(path, model)
            bad = copy.deepcopy(model)
            bad['signature_db'] = [0]*33
            badpath = Path(tmp)/'bad.json'
            _write_new(badpath, bad)
            with self.assertRaises(ValueError):
                load_model(badpath)

    def test_fitting_never_reads_final_pair(self):
        model = self.model()
        opened = model['baseline_db']
        closed = (np.array(opened)+np.array(model['signature_db'])).tolist()
        seen = []

        def summary(path, config):
            seen.append(path.name)
            return dict(median_db=opened if path.name.startswith('open') else closed,
                        within_recording_mad_db=[0]*33, sensor_span_s=30.)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Config().save(root/'config.json')
            (root/'door-check.json').write_text(json.dumps(dict(complete=True, repeats=3, seconds_per_state=30)))
            with patch('radar.obstacle._session', side_effect=summary), \
                 patch('radar.obstacle._hash', side_effect=lambda p: str(p)):
                fitted = fit_experiment(root, root/'model.json')
            self.assertEqual(set(seen), {'open-01','closed-01','open-02','closed-02'})
            self.assertEqual(fitted['reserved_pair'], 3)

    def test_copied_training_raw_file_is_refused_before_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recording = root/'renamed'
            recording.mkdir()
            (recording/'frames.grd').write_bytes(b'same raw calibration bytes')
            model = self.model()
            model['training_raw_sha256'] = [_hash(recording/'frames.grd')]
            _write_new(root/'model.json', model)
            with self.assertRaisesRegex(ValueError, 'overlap'):
                replay_obstacle(recording, root/'model.json', root/'result.json')
            self.assertFalse((root/'result.json').exists())

    def test_live_mismatch_preserves_raw_closes_and_reports_uncertain(self):
        class FakeSource:
            closed = False

            def __init__(self, config, port):
                from radar.protocol import Parser
                self.parser = Parser()

            def read(self):
                return Frame(1, 100000, 0x33514802, np.full((17,64,3),20000,dtype='uint16'))

            def close(self):
                FakeSource.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_new(root/'model.json', self.model())
            console = io.StringIO()
            with patch('radar.acquisition.Source', FakeSource), contextlib.redirect_stdout(console):
                with self.assertRaisesRegex(ValueError, 'Frame/config mismatch'):
                    live_obstacle('FAKE', root/'model.json', root/'capture')
            self.assertTrue(FakeSource.closed)
            self.assertIn('uncertain', console.getvalue())
            self.assertGreater((root/'capture'/'frames.grd').stat().st_size, 0)


if __name__ == '__main__':
    unittest.main()
