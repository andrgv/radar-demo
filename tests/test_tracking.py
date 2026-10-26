from dataclasses import replace
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from radar.background import SpectralBackground
from radar.cli import main
from radar.config import Config
from radar.processing import Detection, Processor
from radar.storage import Recorder
from radar.synthetic import Target, generate
from radar.tracking import RangeTracker


def detection(distance=1.0, valid=True):
    return Detection(distance, None, 0., 0., (0., distance, 0.) if valid else (float('nan'),) * 3,
                     15., 50., False, valid)


class RangeTrackingTests(unittest.TestCase):
    def setUp(self):
        self.config = Config().validate()
        self.tracker = RangeTracker(self.config)

    def confirm(self):
        for i in range(3):
            tracks = self.tracker.update([detection()], [], i * 100000)
        return tracks[0]

    def test_confirmation_allows_misses_and_preserves_id(self):
        first = self.tracker.update([detection()], [], 0)[0]
        self.assertEqual(first.state, 'tentative')
        self.tracker.update([], [], 100000)
        self.tracker.update([detection(1.02)], [], 200000)
        self.tracker.update([], [], 300000)
        track = self.tracker.update([detection(1.03)], [], 400000)[0]
        self.assertEqual(track.state, 'confirmed')
        self.assertEqual(track.track_id, first.track_id)
        self.assertLess(track.range_m, 1.03)

    def test_coasting_expiry_and_reacquisition(self):
        confirmed = self.confirm()
        coast = self.tracker.update([], [], 400000)[0]
        self.assertEqual(coast.state, 'coasting')
        self.assertFalse(coast.measured)
        self.assertAlmostEqual(coast.measurement_age_s, .2)
        self.assertLess(coast.confidence, confirmed.confidence)
        recovered = self.tracker.update([detection()], [], 500000)[0]
        self.assertEqual(recovered.track_id, confirmed.track_id)
        self.assertTrue(recovered.measured)
        self.assertEqual(self.tracker.update([], [], 1000000), [])
        new = self.tracker.update([detection()], [], 1100000)[0]
        self.assertNotEqual(new.track_id, confirmed.track_id)
        self.assertEqual(new.state, 'tentative')

    def test_weak_returns_only_maintain_confirmed_tracks(self):
        self.assertEqual(self.tracker.update([], [detection()], 0), [])
        self.tracker.update([detection()], [], 100000)
        track = self.tracker.update([], [detection()], 200000)[0]
        self.assertFalse(track.measured)
        self.tracker.reset()
        confirmed = self.confirm()
        weak = self.tracker.update([], [detection(1.01)], 300000)[0]
        self.assertEqual(weak.track_id, confirmed.track_id)
        self.assertEqual(weak.state, 'confirmed')
        self.assertTrue(weak.measured)
        self.assertEqual(weak.measurement_kind, 'supporting')

    def test_unconfirmed_track_expires_and_distant_return_gets_new_id(self):
        first = self.tracker.update([detection()], [], 0)[0]
        for i in range(1, 5):
            tracks = self.tracker.update([], [], i * 100000)
        self.assertEqual(tracks, [])
        self.tracker.reset()
        first = self.confirm()
        tracks = self.tracker.update([detection(3.)], [], 300000)
        self.assertEqual(len(tracks), 2)
        self.assertNotEqual(tracks[1].track_id, first.track_id)

    def test_invalid_angle_keeps_range_without_stale_direction(self):
        self.confirm()
        track = self.tracker.update([detection(valid=False)], [], 300000)[0]
        self.assertEqual(track.state, 'confirmed')
        self.assertFalse(track.angle_valid)
        self.assertIsNone(track.xyz)

    def test_two_tracks_one_to_one_and_same_bin_static_moving_deduplicated(self):
        tracks = self.tracker.update([detection(), detection(3.)], [], 0)
        self.assertEqual(len(tracks), 2)
        tracks = self.tracker.update([detection(3.01), detection(1.01)], [], 100000)
        self.assertLess(tracks[0].range_m, tracks[1].range_m)
        self.tracker.reset()
        self.assertEqual(len(self.tracker.update([detection(), detection(1.01)], [], 0)), 1)

    def test_timestamp_wrap_and_restart(self):
        self.tracker.update([detection()], [], 0xffff0000)
        tracks = self.tracker.update([detection()], [], 0x000086a0)
        self.assertEqual(len(tracks), 1)
        old_id = tracks[0].track_id
        tracks = self.tracker.update([detection()], [], 1)
        self.assertNotEqual(tracks[0].track_id, old_id)


class TrackingIntegrationTests(unittest.TestCase):
    def test_processing_diagnostics_and_sequence_gap_reset(self):
        config = Config()
        processor = Processor(config)
        for i in range(1, 4):
            result = processor.process(generate(config, i, seed=i))
        self.assertTrue(any(t.state == 'confirmed' for t in result.tracks))
        self.assertTrue(result.detection_diagnostics)
        json.dumps(result.detection_diagnostics, allow_nan=False)
        result = processor.process(generate(config, 9, seed=9))
        self.assertTrue(all(t.state == 'tentative' for t in result.tracks))
        disabled = Processor(replace(config, tracking_enabled=False)).process(generate(config, seed=1))
        self.assertEqual(disabled.tracks, [])

    def test_weaker_local_threshold_supports_track_but_does_not_create_detection(self):
        config = Config()
        target = Target(config.ranges[12])
        processor = Processor(config)
        for i in range(1, 4):
            result = processor.process(generate(config, i, targets=[target], seed=i))
        track_id = next(t.track_id for t in result.tracks if t.state == 'confirmed')
        power_target = 1800. ** 2 * 1.1  # just below strong gate; above -3 dB support
        calls = 0
        def thresholds(power, factor):
            nonlocal calls
            calls += 1
            return np.full_like(power, power_target if calls == 1 else 1e30)
        with patch('radar.processing.noise_threshold', side_effect=thresholds):
            result = processor.process(generate(config, 4, targets=[target], seed=4))
        self.assertFalse(result.detections)
        track = next(t for t in result.tracks if t.track_id == track_id)
        self.assertTrue(track.measured)
        self.assertEqual(track.measurement_kind, 'supporting')
        self.assertTrue(result.detection_diagnostics[10]['supporting_only'])  # bin 12

    def test_background_rejection_is_recorded_and_cannot_support_track(self):
        config = Config()
        background = SpectralBackground.fit([generate(config, i, targets=[], seed=i) for i in range(10)], config)
        processor = Processor(config, background=background)
        for i in range(1, 4):
            result = processor.process(generate(config, i, seed=i))
        with patch.object(background, 'target_supported', return_value=np.zeros(len(config.ranges), dtype=bool)):
            result = processor.process(generate(config, 4, seed=4))
        self.assertFalse(result.detections)
        self.assertTrue(all(not t.measured for t in result.tracks))
        self.assertTrue(all('background_gate' in d['static_rejection_reasons'] for d in result.detection_diagnostics))

    def test_strict_json_recording_and_replay_export(self):
        config = Config()
        processor = Processor(config)
        with tempfile.TemporaryDirectory() as temporary:
            recording = Path(temporary) / 'recording'
            with Recorder(recording, config) as recorder:
                for i in range(1, 5):
                    frame = generate(config, i, seed=i)
                    recorder.write(frame, processor.process(frame))
            lines = [json.loads(line) for line in (recording / 'tracking.jsonl').read_text().splitlines()]
            self.assertEqual(len(lines), 4)
            self.assertTrue(lines[-1]['tracks'])
            output = Path(temporary) / 'diagnostics.jsonl'
            with contextlib.redirect_stdout(io.StringIO()):
                main(['analyze', str(recording), '--diagnostics-output', str(output)])
            replayed = [json.loads(line) for line in output.read_text().splitlines()]
            self.assertEqual(replayed[-1]['tracks'], lines[-1]['tracks'])
            self.assertEqual(replayed[-1]['detection_diagnostics'], lines[-1]['detection_diagnostics'])

    def test_config_rejects_invalid_tracking_values(self):
        for values in (dict(track_confirm_hits=6), dict(track_hold_s=0),
                       dict(track_smoothing=1.1), dict(track_match_bins=float('nan')),
                       dict(tracking_enabled=1), dict(track_hysteresis_db=-1)):
            with self.subTest(values=values), self.assertRaises(ValueError):
                replace(Config(), **values).validate()
