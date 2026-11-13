"""Safety properties of the offline averaging comparison, not live DSP changes."""
import unittest
import numpy as np
from tools.evaluate_range_average import rolling_average

class AverageTests(unittest.TestCase):
    def test_rejected_frame_clears_previous_distance(self):
        values=np.array([.3]*5+[99]+[.5]*5)
        accepted=np.array([True]*5+[False]+[True]*5)
        result=rolling_average(values,accepted)
        self.assertTrue(np.isnan(result[:4]).all())
        self.assertAlmostEqual(result[4],.3)
        self.assertTrue(np.isnan(result[5:10]).all())
        self.assertAlmostEqual(result[10],.5)

    def test_future_samples_cannot_change_previous_output(self):
        values=np.array([.2,.3,.4,.5,.6,.7,np.nan,.9,1.,1.1,1.2,1.3])
        full=rolling_average(values,np.ones(len(values),dtype=bool))
        prefix=rolling_average(values[:6],np.ones(6,dtype=bool))
        np.testing.assert_equal(full[:6],prefix)
        self.assertTrue(np.isnan(full[6:11]).all())
        self.assertAlmostEqual(full[11],1.1)

if __name__=='__main__':unittest.main()
