import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from radar.config import Config
from radar.material import (FeatureSpec, FeatureWindows, _xgboost, capture_material,
                            load_material, predict_material, recording_features, train_material)
from radar.protocol import Frame, Parser
from radar.storage import Recorder, replay

try:
    _xgboost()
    HAS_XGBOOST = True
except ValueError:
    HAS_XGBOOST = False


def frame(config, n, glass=False, seed=0, phase=0):
    rng = np.random.default_rng(seed + n)
    x = np.arange(config.samples)[None, :, None]
    amplitude = 3000 if glass else 600
    signal = 32768 + amplitude * np.cos(2 * np.pi * 3 * x / config.samples + phase)
    signal = np.broadcast_to(signal, (config.chirps, config.samples, 3)).copy()
    signal += rng.normal(0, 30, signal.shape)
    return Frame(n, n * 100000, config.profile_id, np.asarray(signal, dtype='<u2'))


def write_capture(path, config, glass, seed=0, count=90):
    with Recorder(path, config, dict(label='glass' if glass else 'drywall')) as rec:
        for n in range(1, count + 1):
            rec.write(frame(config, n, glass, seed))
    (path / 'arrivals.jsonl').write_text(''.join(json.dumps(dict(
        sequence=n, host_unix_ns=n * 100000000)) + '\n' for n in range(1, count + 1)))


def study(root, mode='surface_holdout'):
    config = Config()
    rows = []
    for i in range(6):
        label = 'glass' if i % 2 else 'drywall'
        path = root / f'capture-{i}'
        write_capture(path, config, label == 'glass', seed=i * 1000)
        split = 'test' if i >= 4 else 'train'
        rows.append(dict(path=path.name, label=label, specimen_id=f'surface-{i}',
                         scene_id='test-room' if split == 'test' else 'train-room',
                         distance_m=1., split=split))
    manifest = root / 'study.json'
    manifest.write_text(json.dumps(dict(schema=1, evaluation=mode, recordings=rows)))
    return config, manifest


class MaterialSignalTests(unittest.TestCase):
    def test_waveform_uses_three_receivers_and_skips_startup_chirp(self):
        config = Config()
        f = frame(config, 1)
        spec = FeatureSpec(kind='waveform')
        expected = f.adc[config.discard_chirps].astype(float)
        expected -= expected.mean(axis=0, keepdims=True)
        np.testing.assert_allclose(spec.frame(f, config), (expected.T / 32768).reshape(-1))
        self.assertEqual(len(spec.names(config)), 192)

    def test_power_features_preserve_stationary_material_return_and_rx_order(self):
        config = Config()
        spec = FeatureSpec(bins=[3])
        f = frame(config, 1, glass=True)
        a = spec.frame(f, config)
        b = spec.frame(frame(config, 1, glass=True, phase=1.5), config)
        np.testing.assert_allclose(a, b, atol=.1)
        x = f.adc.astype(float)
        x[:, :, 1] = 32768 + 2 * (x[:, :, 1] - 32768)
        doubled = replace(f, adc=x.astype('<u2'))
        delta = spec.frame(doubled, config) - a
        self.assertAlmostEqual(delta[1], 20 * np.log10(2), places=2)
        self.assertAlmostEqual(delta[0], 0)
        self.assertAlmostEqual(delta[2], 0)

    def test_streaming_and_saved_features_use_identical_nonoverlapping_windows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture'
            config = Config()
            write_capture(path, config, True, count=24)
            spec = FeatureSpec(window_frames=4, skip_frames=3, bins=[2, 3, 4])
            capture = recording_features(path, config, spec)
            live = FeatureWindows(config, spec)
            streamed = [r[0] for f in replay(path) if (r := live.push(f)) is not None]
            np.testing.assert_allclose(capture['x'], streamed, rtol=1e-6)
            self.assertEqual(capture['discarded_tail_frames'], 1)
            self.assertEqual([(r['first_sequence'], r['last_sequence']) for r in capture['sequence_windows']],
                             [(4, 7), (8, 11), (12, 15), (16, 19), (20, 23)])

    def test_corrupt_truncated_stale_and_wrong_profile_captures_are_rejected(self):
        for failure in ('corrupt', 'truncated', 'stale', 'profile', 'incomplete'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'capture'
                config = Config()
                write_capture(path, config, True)
                raw = path / 'frames.grd'
                if failure == 'corrupt':
                    content = bytearray(raw.read_bytes())
                    content[100] ^= 1
                    raw.write_bytes(content)
                elif failure == 'truncated':
                    raw.write_bytes(raw.read_bytes()[:-1])
                elif failure == 'stale':
                    (path / 'arrivals.jsonl').write_text((json.dumps(dict(host_unix_ns=1)) + '\n') * 90)
                elif failure == 'profile':
                    config = replace(config, profile_id=999)
                else:
                    (path / 'metadata.json').write_text('{"material_experiment": true}')
                with self.assertRaises(ValueError):
                    recording_features(path, config, FeatureSpec())

    def test_invalid_features_fail_before_output(self):
        config = Config()
        for spec in (FeatureSpec(window_frames=0), FeatureSpec(skip_frames=-1),
                     FeatureSpec(bins=[0]), FeatureSpec(bins=[3, 3]),
                     FeatureSpec(kind='waveform', bins=[3])):
            with self.assertRaises(ValueError):
                spec.validate(config)


@unittest.skipUnless(HAS_XGBOOST, 'Install the optional material dependencies')
class MaterialModelTests(unittest.TestCase):
    def test_train_save_replay_and_training_overlap_indicator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, manifest = study(root)
            output = root / 'model'
            report = train_material(manifest, output, FeatureSpec(bins=[2, 3, 4]))
            self.assertEqual(report['heldout_recording_metrics']['correct'], 2)
            self.assertEqual(report['heldout_recording_metrics']['recordings'], 2)
            test = predict_material(root / 'capture-5', output)
            self.assertEqual(test['prediction'], 'glass')
            self.assertFalse(test['overlaps_training_frames'])
            training = predict_material(root / 'capture-1', output)
            self.assertTrue(training['overlaps_training_frames'])
            # Live uses inplace_predict, so check it agrees with the saved replay path.
            model, _, spec, booster = load_material(output)
            capture = recording_features(root / 'capture-5', config, spec)
            np.testing.assert_allclose(booster.inplace_predict(capture['x']),
                [r['glass_score'] for r in test['window_predictions']])
            with self.assertRaises(FileExistsError):
                train_material(manifest, output)
            with self.assertRaisesRegex(ValueError, 'configuration differs'):
                replace(config, slope_hz_s=2e13).save(root / 'capture-5/config.json')
                predict_material(root / 'capture-5', output)
            with (output / 'booster.ubj').open('ab') as handle:
                handle.write(b'altered')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_material(output)

    def test_heldout_labels_do_not_affect_trained_booster(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manifest = study(root)
            train_material(manifest, root / 'first')
            data = json.loads(manifest.read_text())
            for row in data['recordings']:
                if row['split'] == 'test':
                    row['label'] = 'glass' if row['label'] == 'drywall' else 'drywall'
            manifest.write_text(json.dumps(data))
            report = train_material(manifest, root / 'second')
            self.assertEqual((root / 'first/booster.ubj').read_bytes(), (root / 'second/booster.ubj').read_bytes())
            self.assertEqual(report['heldout_recording_metrics']['correct'], 0)

    def test_no_cross_partition_surface_or_scene_overlap_and_no_duplicate_raw(self):
        for failure in ('surface', 'scene', 'duplicate', 'subset'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, manifest = study(root)
                data = json.loads(manifest.read_text())
                if failure == 'surface':
                    data['recordings'][4]['specimen_id'] = data['recordings'][0]['specimen_id']
                elif failure == 'scene':
                    data['recordings'][4]['scene_id'] = data['recordings'][0]['scene_id']
                else:
                    frames = list(replay(root / 'capture-0'))
                    if failure == 'subset':
                        frames = frames[30:]
                    # Even re-encoding with changed counters cannot conceal shared ADCs.
                    raw = root / 'capture-4/frames.grd'
                    from radar.protocol import encode
                    raw.write_bytes(b''.join(encode(replace(f, sequence=i+1, timestamp_us=(i+1)*100000))
                                             for i, f in enumerate(frames)))
                    (root / 'capture-4/arrivals.jsonl').write_text(''.join(json.dumps(dict(
                        host_unix_ns=(i+1)*100000000)) + '\n' for i in range(len(frames))))
                manifest.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    train_material(manifest, root / 'model')
                self.assertFalse((root / 'model').exists())

    def test_repeated_surfaces_require_explicit_repeat_evaluation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, manifest = study(root, mode='repeat_holdout')
            data = json.loads(manifest.read_text())
            for row in data['recordings']:
                row['scene_id'] = 'same-room'
                row['specimen_id'] = row['label'] + '-surface'
            manifest.write_text(json.dumps(data))
            report = train_material(manifest, root / 'model')
            self.assertEqual(report['status'], 'experimental_repeat_comparison')
            self.assertIn('Same-surface repeat test only', report['limitations'][0])

    def test_live_scores_match_replay_of_the_same_saved_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config, manifest = study(root)
            train_material(manifest, root / 'model', FeatureSpec(bins=[2, 3, 4]))
            clock = [0.]
            sources = []

            class FakeSource:
                def __init__(self, config, port):
                    self.parser = Parser()
                    self.sequence = 0
                    self.closed = False
                    sources.append(self)

                def read(self):
                    self.sequence += 1
                    clock[0] += .1
                    return frame(config, self.sequence, glass=True, seed=9000)

                def close(self):
                    self.closed = True

            with patch('radar.acquisition.Source', FakeSource), \
                 patch('radar.material.time.monotonic', side_effect=lambda: clock[0]), \
                 patch('radar.storage.time.time_ns', side_effect=lambda: int(clock[0]*1e9)), \
                 contextlib.redirect_stdout(io.StringIO()):
                live = capture_material(root / 'live', config, 'FAKE', seconds=3, settle=3,
                                        model_path=root / 'model')
            saved = predict_material(root / 'live', root / 'model')
            self.assertEqual(live['prediction'], 'glass')
            self.assertAlmostEqual(live['glass_score'], saved['glass_score'])
            self.assertTrue(sources[0].closed)
            self.assertEqual(json.loads((root / 'live/metadata.json').read_text())['label'], 'unknown')


class MaterialCaptureTests(unittest.TestCase):
    def test_interruption_preserves_raw_closes_source_and_prevents_training_use(self):
        clock = [0.]
        config = Config()
        sources = []

        class FakeSource:
            def __init__(self, config, port):
                self.parser = Parser()
                self.sequence = 0
                self.closed = False
                sources.append(self)

            def read(self):
                self.sequence += 1
                clock[0] += .1
                if self.sequence == 35:
                    raise KeyboardInterrupt
                return frame(config, self.sequence)

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'partial'
            with patch('radar.acquisition.Source', FakeSource), \
                 patch('radar.material.time.monotonic', side_effect=lambda: clock[0]), \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
                capture_material(path, config, 'FAKE', seconds=3, settle=3, metadata=dict(
                    label='drywall', specimen_id='wall-2', scene_id='room-2', distance_m=1.))
            self.assertTrue(sources[0].closed)
            self.assertGreater((path / 'frames.grd').stat().st_size, 0)
            with self.assertRaisesRegex(ValueError, 'capture incomplete'):
                recording_features(path, config, FeatureSpec())

    def test_labeled_capture_drains_setup_validates_and_closes_connection(self):
        clock = [0.]
        config = Config()
        sources = []

        class FakeSource:
            def __init__(self, config, port):
                self.parser = Parser()
                self.closed = False
                self.sequence = 0
                sources.append(self)

            def read(self):
                self.sequence += 1
                clock[0] += .1
                return frame(config, self.sequence, glass=True)

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture'
            with patch('radar.acquisition.Source', FakeSource), \
                 patch('radar.material.time.monotonic', side_effect=lambda: clock[0]), \
                 patch('radar.storage.time.time_ns', side_effect=lambda: int(clock[0]*1e9)), \
                 contextlib.redirect_stdout(io.StringIO()):
                result = capture_material(path, config, 'FAKE', seconds=3, settle=3,
                    metadata=dict(label='glass', specimen_id='window-2', scene_id='room-2', distance_m=1.))
            self.assertTrue(result['complete'])
            self.assertTrue(sources[0].closed)
            self.assertEqual(len(sources), 1)
            self.assertGreater(next(replay(path)).sequence, 29)
            self.assertEqual(json.loads((path / 'metadata.json').read_text())['specimen_id'], 'window-2')
            self.assertGreaterEqual(len(recording_features(path, config, FeatureSpec())['x']), 1)

    def test_invalid_distance_does_not_open_hardware(self):
        with patch('radar.acquisition.Source') as source, self.assertRaises(ValueError):
            capture_material('unused', Config(), 'FAKE', metadata=dict(
                label='glass', specimen_id='window-2', scene_id='room-2', distance_m=float('nan')))
        source.assert_not_called()


if __name__ == '__main__':
    unittest.main()
