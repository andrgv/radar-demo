from dataclasses import replace
import unittest

import numpy as np

from radar.background import SpectralBackground
from radar.config import Config
from radar.processing import Detection, Processor
from radar.synthetic import Target, generate
from radar.tracking import RangeTracker, ShortRangeAmplitudeTracker


class RangeTrackerTests(unittest.TestCase):
    def setUp(self):
        self.ranges = np.arange(33, dtype=float) * 0.35

    def detection(self, index, snr_db=20):
        return Detection(float(self.ranges[index]), None, 0, 0, (0, 0, 0),
                         snr_db, 50, False, False)

    def test_requires_repeated_hits_and_does_not_hold_a_missing_dot(self):
        tracker = RangeTracker()
        self.assertEqual(tracker.update([self.detection(10)], self.ranges).state, "checking")
        self.assertEqual(tracker.update([self.detection(11)], self.ranges).state, "checking")
        confirmed = tracker.update([self.detection(11)], self.ranges)
        self.assertEqual(confirmed.state, "confirmed")
        self.assertEqual(confirmed.observed_range_m, self.ranges[11])
        missing = tracker.update([], self.ranges)
        self.assertEqual(missing.state, "missing")
        self.assertEqual(missing.bin_index, 11)
        self.assertIsNone(missing.observed_range_m)
        self.assertEqual(tracker.update([], self.ranges).state, "missing")
        self.assertEqual(tracker.update([], self.ranges).state, "lost")
        self.assertEqual(tracker.update([], self.ranges).state, "no change")

    def test_large_jump_is_not_reported_as_continuous_motion(self):
        tracker = RangeTracker()
        for _ in range(3):
            tracker.update([self.detection(10)], self.ranges)
        for expected in ("missing", "missing", "lost", "checking", "checking", "confirmed"):
            state = tracker.update([self.detection(22)], self.ranges)
            self.assertEqual(state.state, expected)

    def test_tentative_hits_must_be_consecutive(self):
        tracker = RangeTracker()
        tracker.update([self.detection(10)], self.ranges)
        tracker.update([], self.ranges)
        self.assertEqual(tracker.update([self.detection(10)], self.ranges).hits, 1)

    def test_current_observation_is_not_the_smoothed_track_value(self):
        tracker = RangeTracker()
        for _ in range(3):
            tracker.update([self.detection(10)], self.ranges)
        shifted = replace(self.detection(10), range_m=float(self.ranges[10] + 0.08))
        state = tracker.update([shifted], self.ranges)
        self.assertEqual(state.observed_range_m, shifted.range_m)
        self.assertLess(state.range_m, state.observed_range_m)

    def test_empty_scene_reference_removes_static_clutter(self):
        config = Config()
        clutter = Target(float(config.ranges[10]), amplitude=2000)
        frames = [generate(config, sequence=i + 1, targets=[clutter], seed=i) for i in range(30)]
        background = SpectralBackground.fit(frames, config)
        processor = Processor(config, background=background)
        empty = processor.process(generate(config, sequence=31, targets=[clutter], seed=31))
        self.assertFalse(any(abs(item.range_m - config.ranges[10]) < config.ranges[1]
                             for item in empty.detections))
        added = Target(float(config.ranges[17]), amplitude=1800)
        tracker = RangeTracker()
        for i in range(32, 35):
            result = processor.process(generate(config, sequence=i, targets=[clutter, added], seed=i))
            state = tracker.update(result.detections, result.ranges)
        self.assertEqual(state.state, "confirmed")
        self.assertEqual(state.bin_index, 17)

    def test_short_range_amplitude_tracks_near_then_far_without_distant_clutter(self):
        config = Config()
        clutter = Target(float(config.ranges[10]), amplitude=2000)
        tracker = ShortRangeAmplitudeTracker(config)
        empty = [generate(config, sequence=i + 1, targets=[clutter], seed=i) for i in range(30)]
        tracker.fit(empty)
        for index in range(30, 33):
            frame = generate(config, sequence=index + 1,
                             targets=[clutter, Target(float(config.ranges[2]), amplitude=1800)], seed=index)
            near, _ = tracker.update(frame)
        self.assertEqual((near.state, near.bin_index), ("confirmed", 2))
        for index in range(33, 36):
            frame = generate(config, sequence=index + 1,
                             targets=[clutter, Target(float(config.ranges[3]), amplitude=1800)], seed=index)
            far, _ = tracker.update(frame)
        self.assertEqual((far.state, far.bin_index), ("confirmed", 3))
        absent, _ = tracker.update(generate(config, sequence=37, targets=[clutter], seed=37))
        self.assertEqual(absent.state, "missing")
        self.assertIsNone(absent.observed_range_m)

    def test_short_range_accepts_close_in_broad_change_but_not_weak_noise(self):
        config = Config()
        tracker = ShortRangeAmplitudeTracker(config)
        tracker.reference_power = np.ones(len(config.ranges))
        excess_db = np.zeros(len(config.ranges))
        excess_db[1] = 4.0
        excess_db[2] = 3.5  # Neighboring energy is the same broad return.
        tracker.power = lambda frame: 10 ** (excess_db / 10)
        for _ in range(3):
            status, _ = tracker.update(None)
        self.assertEqual((status.state, status.bin_index), ("confirmed", 1))

        excess_db[1] = 2.5
        excess_db[2] = 2.0
        status, _ = tracker.update(None)
        self.assertEqual(status.state, "missing")
        self.assertIsNone(status.observed_range_m)


if __name__ == "__main__":
    unittest.main()
