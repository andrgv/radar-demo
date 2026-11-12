import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from radar.cfar_map import MultiObstacleMap, demo_frame, main
from radar.angle_lab import raw_model_phase
from radar.config import Config
from radar.protocol import Frame
from radar.scene_map import FixedSceneMap, MapArchive, SceneMapSettings, reference_fingerprint
from radar.storage import Recorder


def reading(sequence, points=(), state='OBSTACLES'):
    return dict(sequence=sequence, timestamp_us=sequence*100000, state=state, reason='test',
        obstacles=[dict(state='LOCALIZED', confirmed=True, x_m=x, y_m=y) for x, y in points])


class SceneMapTests(unittest.TestCase):
    def scene(self, **kwargs):
        return FixedSceneMap('same-sensor-and-reference', wall_clock=lambda: 1000., **kwargs)

    def confirmed(self, scene):
        for i in range(3):
            result = scene.update(reading(i, [(-.3, 2), (.5, 4)]), now=i*.1)
        return result

    def test_two_regions_have_stable_ids_and_average_jitter(self):
        scene = self.scene()
        for i, jitter in enumerate([-.04, .02, .02, 0.]):
            result = scene.update(reading(i, [(-.3+jitter, 2), (.5-jitter, 4)]), now=i*.1)
        self.assertEqual(len(result['objects']), 2)
        for obj, x in zip(result['objects'], [-.3, .5]):
            self.assertEqual(obj['state'], 'CURRENT')
            self.assertEqual(obj['observations'], 4)
            self.assertAlmostEqual(obj['x_m'], x)
            self.assertGreater(obj['spread_x_m'], 0)
        self.assertEqual([v['object_id'] for v in result['objects']], [1, 2])

    def test_dropout_and_fault_preserve_regions_and_reacquire_same_ids(self):
        scene = self.scene()
        self.confirmed(scene)
        result = scene.update(reading(3, [], state='NO_DETECTION'), now=.3)
        self.assertEqual([v['state'] for v in result['objects']], ['REMEMBERED']*2)
        self.assertTrue(all(v['confirmed'] for v in result['objects']))
        result = scene.update(reading(4, [(-.3, 2)], state='UNCERTAIN'), now=.4)
        self.assertEqual([v['observations'] for v in result['objects']], [3, 3])
        result = scene.update(reading(5, [(-.28, 2.01), (.48, 4.01)]), now=.5)
        self.assertEqual([v['object_id'] for v in result['objects']], [1, 2])
        self.assertEqual([v['state'] for v in result['objects']], ['CURRENT']*2)

    def test_old_regions_fade_and_become_stale_without_claiming_removal(self):
        scene = self.scene()
        initial = self.confirmed(scene)
        remembered = scene.update(reading(3), now=10.)
        stale = scene.update(reading(4), now=40.)
        self.assertEqual(len(stale['objects']), 2)
        self.assertTrue(all(v['state'] == 'STALE' for v in stale['objects']))
        self.assertGreater(initial['objects'][0]['support_score'], remembered['objects'][0]['support_score'])
        self.assertGreater(remembered['objects'][0]['support_score'], stale['objects'][0]['support_score'])
        self.assertFalse(stale['objects'][0]['currently_observed'])

    def test_one_frame_cannot_confirm_region_by_many_nearby_returns(self):
        scene = self.scene()
        result = scene.update(reading(1, [(0, 2), (.05, 2), (-.05, 2.01)]), now=0.)
        self.assertEqual(len(result['objects']), 1)
        obj = result['objects'][0]
        self.assertEqual(obj['observations'], 1)
        self.assertEqual(obj['raw_return_count'], 3)
        self.assertEqual(obj['state'], 'TENTATIVE')
        repeated = scene.update(reading(1, [(0, 2)]), now=.1)
        self.assertEqual(repeated['objects'][0]['observations'], 1)
        expired = scene.update(reading(2), now=3.)
        self.assertEqual(expired['objects'], [])

    def test_unresolved_and_malformed_positions_cannot_enter_map(self):
        scene = self.scene()
        row = reading(1)
        row['obstacles'] = [dict(state='UNRESOLVED', confirmed=True, x_m=None, y_m=None),
            dict(state='LOCALIZED', confirmed=True, x_m=float('nan'), y_m=2),
            dict(state='LOCALIZED', confirmed=True, x_m=0, y_m=-1)]
        self.assertFalse(scene.update(row, now=0.)['objects'])

    def test_missing_frames_age_current_regions_into_memory(self):
        scene = self.scene()
        self.confirmed(scene)
        result = scene.update(None, now=1.)
        self.assertEqual([v['state'] for v in result['objects']], ['REMEMBERED']*2)

    def test_clear_map_preserves_id_uniqueness_and_resets_evidence(self):
        scene = self.scene()
        self.confirmed(scene)
        scene.clear()
        result = scene.update(reading(4, [(0, 2)]), now=.4)
        self.assertEqual(result['generation'], 1)
        self.assertEqual(result['objects'][0]['object_id'], 3)
        self.assertEqual(result['objects'][0]['observations'], 1)

    def test_stop_retains_positions_as_memory(self):
        scene = self.scene()
        self.confirmed(scene)
        saved = scene.snapshot(now=.3, stopped=True)
        self.assertEqual(saved['sensor_state'], 'STOPPED')
        self.assertEqual([v['state'] for v in saved['objects']], ['REMEMBERED']*2)
        json.dumps(saved, allow_nan=False)

    def test_save_load_rebases_time_and_never_restores_live_status(self):
        scene = self.scene()
        self.confirmed(scene)
        with tempfile.TemporaryDirectory() as tmp:
            archive = MapArchive(tmp)
            archive.activate()
            archive.write(scene.snapshot(now=.3, stopped=True))
            archive.close()
            restored = FixedSceneMap('same-sensor-and-reference', wall_clock=lambda: 1005.)
            loaded = restored.restore(Path(tmp)/'map.json', now=90.)
            self.assertEqual([v['object_id'] for v in loaded['objects']], [1, 2])
            self.assertAlmostEqual(loaded['objects'][0]['age_s'], 5.1)
            self.assertFalse(any(v['currently_observed'] for v in loaded['objects']))
            self.assertEqual(len((Path(tmp)/'map_history.jsonl').read_text().splitlines()), 1)
            self.assertFalse((Path(tmp)/'map.json.tmp').exists())
            with self.assertRaisesRegex(ValueError, 'does not match'):
                FixedSceneMap('other-radar').restore(Path(tmp)/'map.json')

    def test_unowned_output_is_never_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'map.json'
            path.write_text('user data')
            MapArchive(tmp).write(self.scene().snapshot(now=0.))
            self.assertEqual(path.read_text(), 'user data')

    def test_malformed_saved_regions_are_rejected_cleanly(self):
        scene = self.scene()
        saved = self.confirmed(scene)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'bad.json'
            for change in (dict(objects=[{}]), dict(objects=[dict(saved['objects'][0], x_m='bad')]),
                           dict(updated_s='bad'), dict(next_id=1), dict(generation=-1)):
                path.write_text(json.dumps(dict(saved, **change)))
                with self.subTest(change=change), self.assertRaises(ValueError):
                    self.scene().restore(path, now=1.)

    def test_demo_and_measured_maps_have_different_compatibility_keys(self):
        cfg = Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
                     geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]], mount_roll_deg=90)
        xyz = [0, 2, 0]
        detector = MultiObstacleMap(cfg, raw_model_phase(cfg, xyz)[0], xyz,
                                    min_range=.7, max_range=10)
        detector.metadata['source'] = 'live'
        measured = reference_fingerprint(detector)
        detector.metadata['source'] = 'replay'
        self.assertEqual(measured, reference_fingerprint(detector))
        detector.metadata['source'] = 'synthetic'
        self.assertNotEqual(measured, reference_fingerprint(detector))

    def test_capacity_and_invalid_settings(self):
        scene = self.scene(settings=SceneMapSettings(max_objects=1))
        result = scene.update(reading(0, [(0, 2), (1, 3)]), now=0.)
        self.assertEqual(len(result['objects']), 1)
        self.assertTrue(result['capacity_reached'])
        for kwargs in (dict(merge_radius_m=0), dict(min_observations=0), dict(max_objects=-1),
                       dict(remember_seconds=float('nan'))):
            with self.assertRaises(ValueError):
                SceneMapSettings(**kwargs)
        with self.assertRaisesRegex(ValueError, 'backwards'):
            scene.update(reading(1), now=-1.)


class PersistentPipelineTests(unittest.TestCase):
    def config(self):
        return Config(sample_rate_hz=5e6, slope_hz_s=33691406250000,
            geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]], mount_roll_deg=90)

    def recordings(self, root):
        cfg = self.config()
        config_path = root/'config.json'
        cfg.save(config_path)
        reference, recording = root/'reference', root/'scene'
        # Known on-axis isolated reference, then the production three-return
        # ADC scene followed by two missed frames. No mocked DSP.
        adc = 32768+1500*np.cos(2*np.pi*6*np.arange(cfg.samples)/cfg.samples)
        adc = np.broadcast_to(adc[None, :, None], (cfg.chirps, cfg.samples, 3)).astype('uint16')
        with Recorder(reference, cfg) as recorder:
            for i in range(1, 12):
                recorder.write(Frame(i, i*100000, cfg.profile_id, adc))
        with Recorder(recording, cfg) as recorder:
            for i in range(1, 9):
                recorder.write(demo_frame(cfg, i))
            for i in range(9, 11):
                recorder.write(Frame(i, i*100000, cfg.profile_id, np.full_like(adc, 32768)))
        return ['--replay', str(recording), '--reference', str(reference), '--reference-xyz',
                '0', str(cfg.ranges[6]), '0', '--config', str(config_path)]

    def test_real_replay_saves_persistent_map_and_resumes_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = self.recordings(root)
            output, resumed = root/'out', root/'resumed'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args+['--output', str(output)]), 0)
                saved = json.loads((output/'map.json').read_text())
                self.assertEqual(len(saved['objects']), 3)
                self.assertEqual([v['state'] for v in saved['objects']], ['REMEMBERED']*3)
                self.assertTrue(all(v['confirmed'] for v in saved['objects']))
                original_ids = [v['object_id'] for v in saved['objects']]
                rows = [json.loads(line) for line in (output/'map_history.jsonl').read_text().splitlines()]
                self.assertTrue(any(v['state'] == 'CURRENT' for row in rows for v in row['objects']))
                self.assertEqual(main(args+['--output', str(resumed), '--load-map', str(output/'map.json')]), 0)
                loaded = json.loads((resumed/'map.json').read_text())
                self.assertEqual([v['object_id'] for v in loaded['objects']], original_ids)
                before = (output/'map.json').read_bytes()
                self.assertEqual(main(args+['--output', str(output)]), 2)
                self.assertEqual((output/'map.json').read_bytes(), before)

    def test_headless_snapshot_includes_persistent_regions(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'MPLBACKEND': 'Agg'}):
            root = Path(tmp)
            args = self.recordings(root)
            image, output = root/'persistent.png', root/'out'
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(args+['--output', str(output), '--snapshot', str(image)]), 0)
            self.assertGreater(image.stat().st_size, 10000)
            self.assertEqual(len(json.loads((output/'map.json').read_text())['objects']), 3)

    def test_map_save_and_clear_controls(self):
        from radar.cfar_map_gui import MapPlot
        cfg = self.config()
        xyz = [0, 2, 0]
        detector = MultiObstacleMap(cfg, raw_model_phase(cfg, xyz)[0], xyz,
                                   min_range=.7, max_range=10)
        scene = FixedSceneMap('test')
        for i in range(1, 7):
            result = detector.update(demo_frame(cfg, i))
            result['scene_map'] = scene.update(result, now=float(i))
        saves = []
        def save():
            value = scene.snapshot(now=scene.last_time)
            saves.append(value)
            return value
        plot = MapPlot(detector, interactive=False, scene_map=scene, save_callback=save)
        try:
            plot.update(result)
            plot.save_map()
            self.assertEqual(len(saves[-1]['objects']), 3)
            plot.clear_map()
            self.assertEqual(saves[-1]['objects'], [])
            self.assertEqual(plot.last['scene_map']['objects'], [])
        finally:
            plot.close()


if __name__ == '__main__':
    unittest.main()
