import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from radar.storage import Recorder
from radar_min.__main__ import main
from radar_min.cfar_2d import CaCfar2D, Cfar2DConfig, cluster_cells
from radar_min.range_doppler import RangeDoppler
from tests_min.test_range_doppler import C, tone


class Cfar2DTests(unittest.TestCase):
    def test_explicit_ring_mean_range_edges_and_dc_exclusion(self):
        settings = Cfar2DConfig(guard_range=1, guard_doppler=1,
                                training_range=1, training_doppler=1, min_training=1)
        detector = CaCfar2D((8, 9), settings)
        p = np.arange(72, dtype=float).reshape(8, 9)+1
        p[:, 0] = 1e12
        p[:, -1] = 1e12
        noise, threshold, _, _ = detector.detect(p)
        for d, r in ((4, 4), (0, 1), (7, 7)):
            expected = [p[(d+dd) % 8, r+dr]
                        for dd in range(-2, 3) for dr in range(-2, 3)
                        if 1 <= r+dr <= 7 and not (abs(dd) <= 1 and abs(dr) <= 1)]
            self.assertEqual(detector.counts[d, r], len(expected))
            self.assertAlmostEqual(noise[d, r], np.mean(expected))
            self.assertAlmostEqual(threshold[d, r], np.mean(expected)*settings.factor)
        self.assertTrue(np.isnan(threshold[:, (0, 8)]).all())
        self.assertEqual(detector.counts[4, 4], 16)
        self.assertLess(detector.counts[4, 1], 16)

    def test_flat_maps_and_untestable_cells(self):
        detector = CaCfar2D((16, 33))
        self.assertFalse(detector.detect(np.ones((16, 33)))[2].any())
        self.assertFalse(detector.detect(np.zeros((16, 33)))[2].any())
        p = np.ones((16, 33)); p[8, 12] = detector.settings.factor
        self.assertFalse(detector.detect(p)[2][8, 12])  # equality does not pass
        limited = CaCfar2D((16, 33), Cfar2DConfig(min_training=54))
        p = np.ones((16, 33)); p[8, 1] = 1e6
        _, threshold, accepted, _ = limited.detect(p)
        self.assertTrue(np.isnan(threshold[8, 1]))
        self.assertFalse(accepted[8, 1])

    def test_multiple_signed_and_stationary_cells(self):
        p = np.ones((16, 33))
        for d, r in ((8, 5), (4, 13), (12, 22)):
            p[d, r] = 100
        _, _, accepted, groups = CaCfar2D(p.shape).detect(p)
        self.assertEqual(set(map(tuple, np.argwhere(accepted))), {(8, 5), (4, 13), (12, 22)})
        self.assertEqual(len(groups), 3)
        self.assertEqual({g['peak']['cycles_per_saved_block'] for g in groups}, {0, -.25, .25})
        self.assertEqual(sum(g['touches_zero_doppler'] for g in groups), 1)

    def test_doppler_wrap_and_truncation_and_no_range_wrap(self):
        p = np.ones((16, 33)); p[0, 6] = p[15, 6] = 100
        wrap = CaCfar2D(p.shape)
        trunc = CaCfar2D(p.shape, Cfar2DConfig(doppler_edge='truncate'))
        self.assertLess(trunc.counts[0, 6], wrap.counts[0, 6])
        self.assertEqual(len(wrap.detect(p)[3]), 1)
        self.assertEqual(len(trunc.detect(p)[3]), 2)
        self.assertTrue(wrap.detect(p)[3][0]['crosses_doppler_seam'])
        p = np.ones((16, 33)); p[8, 1] = p[8, 31] = 100
        self.assertEqual(len(wrap.detect(p)[3]), 2)

    def test_merged_group_keeps_multiple_local_maxima_and_plateaus(self):
        p = np.ones((16, 12)); mask = np.zeros_like(p, dtype=bool)
        p[8, 3:8] = [10, 5, 4, 6, 12]; mask[8, 3:8] = True
        groups = cluster_cells(p, mask)
        self.assertEqual(len(groups), 1)
        self.assertEqual([x['range_bin'] for x in groups[0]['local_maxima']], [3, 7])
        p[8, 3:8] = 10
        self.assertEqual(len(cluster_cells(p, mask)[0]['local_maxima']), 1)

    def test_invalid_settings_geometry_and_power(self):
        for kw in ({'factor': 1}, {'factor': float('nan')}, {'guard_range': -1},
                   {'training_doppler': 0}, {'min_training': 1.5}, {'doppler_edge': 'silent'}):
            with self.assertRaises(ValueError): Cfar2DConfig(**kw)
        with self.assertRaises(ValueError): CaCfar2D((6, 33))
        with self.assertRaises(ValueError): CaCfar2D((16, 33), Cfar2DConfig(min_training=100))
        detector = CaCfar2D((16, 33))
        for p in (np.ones((8, 33)), np.full((16, 33), np.nan), -np.ones((16, 33))):
            with self.assertRaises(ValueError): detector.detect(p)

    def test_hann_processed_stationary_and_moving_tones(self):
        full, _, _ = RangeDoppler(C).update(tone([(5, 0, 2000), (13, -4/16, 1000), (23, 3/16, 800)]))
        _, _, accepted, groups = CaCfar2D(full.shape).detect(full)
        for cell in ((8, 5), (4, 13), (11, 23)):
            self.assertTrue(accepted[cell])
        peaks = {(x['doppler_bin'], x['range_bin']) for g in groups for x in g['local_maxima']}
        self.assertTrue({(8, 5), (4, 13), (11, 23)} <= peaks)

    def test_near_zero_hann_return_is_preserved(self):
        full, _, _ = RangeDoppler(C).update(tone([(6, .02, 1000)]))
        self.assertTrue(CaCfar2D(full.shape).detect(full)[2][8, 6])

    def test_cli_exports_and_invalid_frame_does_not_reuse_candidates(self):
        import matplotlib
        matplotlib.use('Agg')
        with tempfile.TemporaryDirectory() as folder:
            recording, output = Path(folder)/'recording', Path(folder)/'result'
            with Recorder(recording, C) as recorder:
                recorder.write(tone([(6, 0, 2000), (15, -.25, 1000)], seq=1))
                recorder.write(replace(tone([(6, 0, 2000)], seq=2), flags=0))
                recorder.write(tone([(6, 0, 2000)], seq=3))
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(['range-doppler', str(recording), '--detector', 'cfar2d', '--output', str(output)])
            self.assertEqual(code, 0)
            reports = [json.loads(line) for line in (output/'candidates.jsonl').read_text().splitlines()]
            self.assertGreater(len(reports[0]['clusters']), 0)
            self.assertFalse(reports[1]['valid'])
            self.assertEqual(reports[1]['clusters'], [])
            self.assertTrue(reports[2]['valid'])
            with np.load(output/'cfar.npz') as arrays:
                self.assertFalse(arrays['accepted'][1].any())
                self.assertTrue(np.isnan(arrays['threshold_power'][1]).all())
            meta = json.loads((output/'metadata.json').read_text())
            self.assertFalse(meta['calibrated'])
            self.assertEqual(meta['cfar_doppler_policy'], 'wrap')
            self.assertTrue((output/'preview.png').is_file())


if __name__ == '__main__':
    unittest.main()
