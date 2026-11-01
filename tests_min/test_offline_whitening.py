"""Checks for offline experiments, not claims of hardware accuracy."""
import unittest
import numpy as np
from test_range_min import C, frame
from tools.evaluate_whitened_range import WhitenedRange
from tools.evaluate_joint_presence import JointPresence


class OfflineWhiteningTests(unittest.TestCase):
    def test_split_does_not_train_on_calibration_or_later_frames(self):
        empty = [frame(i) for i in range(1, 31)]
        model = WhitenedRange(C, empty)
        changed = empty[:20] + [frame(i, amplitude=1000) for i in range(21, 31)]
        alternate = WhitenedRange(C, changed)
        np.testing.assert_array_equal(model.reference, alternate.reference)
        np.testing.assert_array_equal(model.transforms, alternate.transforms)
        self.assertGreater(alternate.threshold, model.threshold)
        extra = WhitenedRange(C, empty + [frame(31, amplitude=2000)])
        self.assertEqual(extra.threshold, model.threshold)
        np.testing.assert_array_equal(extra.reference, model.reference)

    def test_ideal_tone_recovered_without_distance_labels(self):
        model = WhitenedRange(C, [frame(i) for i in range(1, 31)])
        for i in range(31, 34):
            result = model.update(frame(i, k=2, amplitude=1000))
        self.assertTrue(result['presence'])
        self.assertAlmostEqual(result['range_m'], 2*C.spacing_m, delta=.005)
        self.assertIsNone(model.update(frame(34))['range_m'])
        self.assertIsNone(model.update(frame(34, amplitude=1000))['range_m'])
        self.assertIsNone(model.update(frame(35, amplitude=1000))['range_m'])

    def test_joint_gate_rejects_restart_and_clears_disappearance(self):
        for receivers in (False, True):
            model = JointPresence(C, [frame(i) for i in range(1, 31)], receivers)
            for i in range(31, 34):
                detected, _ = model.update(frame(i, amplitude=1000))
            self.assertTrue(detected)
            self.assertFalse(model.update(frame(34))[0])
            self.assertFalse(model.update(frame(34, amplitude=1000))[0])
            self.assertFalse(model.update(frame(35, amplitude=1000))[0])

    def test_insufficient_calibration_rejected(self):
        with self.assertRaises(ValueError):
            WhitenedRange(C, [frame(i) for i in range(1, 30)])
