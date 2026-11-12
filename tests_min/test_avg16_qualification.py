"""Qualification metrics must expose missing output and interrupted episodes."""
from types import SimpleNamespace
import unittest

import numpy as np

from radar_min.core import Config
from tools.qualify_avg16_cfar import aligned_times, summarize


class QualificationTests(unittest.TestCase):
    def test_sequence_alignment_and_host_clock(self):
        frames = [SimpleNamespace(sequence=1), SimpleNamespace(sequence=2)]
        arrivals = [dict(sequence=1, host_unix_ns=100), dict(sequence=3, host_unix_ns=200)]
        with self.assertRaisesRegex(ValueError, 'sequence'):
            aligned_times(frames, arrivals)
        arrivals[1].update(sequence=2, host_unix_ns=99)
        with self.assertRaisesRegex(ValueError, 'increase'):
            aligned_times(frames, arrivals)

    def test_coverage_unresolved_and_sequence_gap(self):
        frames = [SimpleNamespace(sequence=s, timestamp_us=t)
                  for s, t in [(1, 0), (2, 100000), (4, 300000), (5, 400000)]]
        rows = [dict(target_detected=True, experimental_range_m=v, range_bin=2,
                     reason='present', fine_range=dict(reason='resolved' if v else 'boundary'))
                for v in [.5, .6, .7, None]]
        result = summarize(rows, frames, Config(), np.array([0, .1, .3, .4]),
                           dict(label='hold', window_host_s=[0, .5], nominal_target_m=.5))
        self.assertEqual(result['numeric_frames'], 3)
        self.assertEqual(result['unresolved_presence_frames'], 1)
        self.assertEqual(result['numeric_coverage'], .75)
        self.assertAlmostEqual(result['conditional_placement_mae_cm'], 10)
        self.assertEqual([r['frames'] for r in result['numeric_episodes']], [2, 1])
        # Half-open windows exclude the boundary frame; absent outputs have no error statistic.
        result = summarize(rows, frames, Config(), np.array([0, .1, .3, .4]),
                           dict(label='absent', window_host_s=[.4, .5]))
        self.assertEqual(result['frames'], 1)
        self.assertIsNone(result['range_cm_p05_p50_p95'])
        self.assertIsNone(result['conditional_placement_mae_cm'])


if __name__ == '__main__':
    unittest.main()
