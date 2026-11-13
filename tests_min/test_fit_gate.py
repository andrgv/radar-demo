import unittest
import numpy as np
from test_range_min import C, frame
from tools.evaluate_fit_gate import FitEvidence, gate, select


def feature(value=.5, **changes):
    return dict(candidate=value,gain=10.,purity=.9,rx_spread=.01,**changes)


class FitGateTests(unittest.TestCase):
    def test_rejection_clears_median_and_requires_new_confirmation(self):
        rows=[feature(.3) for _ in range(5)]+[feature(None)]+[feature(.5) for _ in range(3)]
        result=gate(rows,(2.,.5,.1),5)
        self.assertEqual(result[:2],[None,None])
        self.assertEqual(result[4],.3)
        self.assertEqual(result[5:8],[None,None,None])
        self.assertEqual(result[8],.5)

    def test_future_samples_do_not_change_past_and_invalid_clears(self):
        rows=[feature(.3+i*.01) for i in range(10)]
        self.assertEqual(gate(rows,(2.,.5,.1),5)[:6],gate(rows[:6],(2.,.5,.1),5))
        rows[5]['valid']=False
        self.assertEqual(gate(rows,(2.,.5,.1),5)[5:8],[None,None,None])

    def test_stable_empty_cannot_win_selection(self):
        records=[dict(label=None,features=[feature() for _ in range(100)]),
                 dict(label=.5,features=[feature() for _ in range(100)])]
        self.assertIsNone(select(records,[(2.,.5,.1),(100.,.5,.1)]))

    def test_stability_requires_history_but_does_not_prove_presence(self):
        rows=[feature(.5) for _ in range(7)]
        result=gate(rows,(2.,.5,.1,.02),5)
        self.assertEqual(result[:6],[None]*6)
        self.assertEqual(result[6],.5)
        rows.append(feature(.7))
        self.assertIsNone(gate(rows,(2.,.5,.1,.02),5)[-1])
        # A perfectly stable empty candidate must still fail the empty audit.
        records=[dict(label=None,features=[feature() for _ in range(100)]),
                 dict(label=.5,features=[feature() for _ in range(100)])]
        self.assertIsNone(select(records,[(2.,.5,.1,.02)]))

    def test_calibration_does_not_fit_reference(self):
        empty=[frame(i) for i in range(1,31)]
        a=FitEvidence(C,empty)
        b=FitEvidence(C,empty[:20]+[frame(i,amplitude=1000) for i in range(21,31)])
        np.testing.assert_array_equal(a.reference,b.reference)
        self.assertGreater(b.noise,a.noise)
        extra=FitEvidence(C,empty+[frame(31,amplitude=2000)])
        self.assertEqual(extra.noise,a.noise)
