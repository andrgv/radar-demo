import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from radar.angle_lab import raw_model_phase
from radar.cfar_map import MultiObstacleMap, iter_results, main
from radar.config import Config
from radar.protocol import Frame
from radar.selected_target import SelectedTargetTracker, TargetSettings
from radar.storage import Recorder


def observation(distance, bearing=0, source_id=1):
    return dict(range_m=distance, azimuth_deg=bearing, coherence_rx2=.99,
                track_id=source_id, range_bin=6, signal_to_reference_db=15.)


def row(seq, *observations, state='OBSTACLES'):
    return dict(sequence=seq, timestamp_us=seq*100000, state=state,
                reason='test', observations=list(observations))


class SelectedTargetTests(unittest.TestCase):
    def tracker(self):
        return SelectedTargetTracker(TargetSettings(2., max_misses=5))

    def lock(self, tracker):
        for seq in range(1, 4):
            result = tracker.update(row(seq, observation(2.02), observation(3., source_id=2)))
        self.assertEqual(result['state'], 'TRACKING')
        return result

    def test_locks_only_selected_start_position(self):
        tracker = self.tracker()
        result = self.lock(tracker)
        self.assertEqual(result['measurement']['range_m'], 2.02)
        self.assertEqual(result['rejected_candidates'], 1)
        self.assertEqual(result['target_id'], 1)

    def test_follows_twenty_cm_motion_without_switching_to_three_meters(self):
        tracker = self.tracker()
        self.lock(tracker)
        for seq, distance in enumerate([2.07, 2.12, 2.16, 2.2], 4):
            result = tracker.update(row(seq, observation(distance, source_id=seq), observation(3.)))
            self.assertEqual(result['state'], 'TRACKING')
            self.assertEqual(result['target_id'], 1)
            self.assertEqual(result['measurement']['range_m'], distance)

    def test_jump_to_three_meters_reports_missing_then_lost_and_stays_lost(self):
        tracker = self.tracker()
        self.lock(tracker)
        for seq in range(4, 9):
            result = tracker.update(row(seq, observation(3.)))
            self.assertIsNone(result['measurement'])
        self.assertEqual(result['state'], 'LOST')
        result = tracker.update(row(9, observation(2.02)))
        self.assertEqual(result['state'], 'LOST')
        self.assertIsNone(result['measurement'])
        tracker.request_relock()
        for seq in range(10, 13):
            result = tracker.update(row(seq, observation(2.02)))
        self.assertEqual(result['state'], 'TRACKING')
        self.assertEqual(result['target_id'], 2)

    def test_short_miss_reacquires_same_target_without_growing_gate(self):
        tracker = self.tracker()
        self.lock(tracker)
        self.assertEqual(tracker.update(row(4))['state'], 'MISSING')
        self.assertEqual(tracker.update(row(5, observation(3.)))['state'], 'MISSING')
        result = tracker.update(row(6, observation(2.2)))
        self.assertEqual(result['state'], 'TRACKING')
        self.assertEqual(result['target_id'], 1)
        self.assertEqual(result['measurement']['range_m'], 2.2)

    def test_never_invents_selected_range_when_only_wrong_return_exists(self):
        tracker = self.tracker()
        for seq in range(1, 10):
            result = tracker.update(row(seq, observation(3.)))
            self.assertEqual(result['state'], 'SEARCHING')
            self.assertIsNone(result['measurement'])
        self.assertFalse(result['history'])

    def test_competing_nearby_returns_are_ambiguous(self):
        result = self.tracker().update(row(1, observation(1.9), observation(2.1)))
        self.assertEqual(result['reason'], 'ambiguous_returns_within_selected_target_gate')
        self.assertIsNone(result['measurement'])

    def test_sensor_fault_and_stop_cannot_carry_current_measurement(self):
        tracker = self.tracker()
        self.lock(tracker)
        result = tracker.update(row(4, observation(2.02), state='UNCERTAIN'))
        self.assertEqual(result['state'], 'LOST')
        self.assertIsNone(result['measurement'])
        self.assertIsNotNone(result['last_measurement'])
        self.assertIsNone(tracker.stop()['measurement'])

    def test_duplicate_frame_cannot_complete_confirmation(self):
        tracker = self.tracker()
        for _ in range(5):
            result = tracker.update(row(1, observation(2.02)))
        self.assertEqual(result['state'], 'ACQUIRING')
        self.assertEqual(result['confirmation_hits'], 1)

    def test_invalid_settings(self):
        for kwargs in (dict(start_range_m=0), dict(start_range_m=float('nan')),
                       dict(start_range_m=2, max_step_m=0), dict(start_range_m=2, max_misses=0)):
            with self.assertRaises(ValueError):
                TargetSettings(**kwargs)


class SelectedTargetPipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
                          geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]], mount_roll_deg=90)
        self.xyz = [0, 2, 0]

    def frame(self, seq, distance=2., background=True):
        c = self.cfg
        x = np.full((c.chirps, c.samples, 3), 32768., dtype=float)
        targets = [] if distance is None else [(distance, 1600.)]
        if background:
            targets.append((3., 500.))
        for r, amplitude in targets:
            k = r/(c.ranges[1]-c.ranges[0])
            signal = amplitude*np.cos(2*np.pi*k*np.arange(c.samples)/c.samples)
            x += signal[None, :, None]
        x += np.random.default_rng(seq).normal(0, .5, x.shape)
        return Frame(seq, seq*100000, c.profile_id, x.astype('uint16'))

    def detector(self):
        return MultiObstacleMap(self.cfg, raw_model_phase(self.cfg, self.xyz)[0], self.xyz,
                                min_range=1.5, max_range=3.5, window=1)

    def test_real_adc_small_motion_and_target_loss(self):
        detector, tracker = self.detector(), SelectedTargetTracker(TargetSettings(2.))
        for seq, distance in enumerate([2., 2., 2., 2.05, 2.1, 2.15, 2.2], 1):
            result = tracker.update(detector.update(self.frame(seq, distance)))
        self.assertEqual(result['state'], 'TRACKING')
        self.assertAlmostEqual(result['measurement']['range_m'], 2.2, delta=.03)
        for seq in range(8, 25):
            result = tracker.update(detector.update(self.frame(seq, None)))
            self.assertIsNone(result['measurement'])
        self.assertEqual(result['state'], 'LOST')

    def test_replay_logs_target_each_frame_and_exports_no_current_value_after_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root/'source', root/'output'
            with Recorder(source, self.cfg) as recorder:
                for seq in range(1, 8): recorder.write(self.frame(seq, 2.+max(0, seq-3)*.05))
            tracker = SelectedTargetTracker(TargetSettings(2.))
            results = list(iter_results(self.detector(), recording=source, output=output, target_tracker=tracker))
            saved = [json.loads(line) for line in (output/'target_track.jsonl').read_text().splitlines()]
            self.assertEqual(len(saved), len(results)+1)
            self.assertEqual(saved[-2]['state'], 'TRACKING')
            self.assertEqual(saved[-1]['state'], 'STOPPED')
            self.assertIsNone(saved[-1]['measurement'])

    def test_tracking_cli_and_display_use_one_target_without_persistent_regions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MPLBACKEND': 'Agg'}):
            root = Path(tmp)
            reference, source, output = root/'reference', root/'source', root/'output'
            config_path, image = root/'config.json', root/'tracking.png'
            self.cfg.save(config_path)
            with Recorder(reference, self.cfg) as recorder:
                for seq in range(1, 12): recorder.write(self.frame(seq, 2., background=False))
            with Recorder(source, self.cfg) as recorder:
                for seq in range(1, 9): recorder.write(self.frame(seq, 2.+max(0, seq-3)*.04))
            args = ['--replay', str(source), '--reference', str(reference), '--reference-xyz', '0', '2', '0',
                    '--config', str(config_path), '--min-range', '1.5', '--max-range', '3.5',
                    '--track-target', '--target-range', '2', '--window', '1',
                    '--output', str(output), '--snapshot', str(image)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args), 0)
            self.assertGreater(image.stat().st_size, 10000)
            self.assertFalse((output/'map.json').exists())
            rows = [json.loads(line) for line in (output/'target_track.jsonl').read_text().splitlines()]
            self.assertTrue(any(r['state'] == 'TRACKING' for r in rows))


if __name__ == '__main__':
    unittest.main()
