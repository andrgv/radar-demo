import unittest
import numpy as np
from radar_min.core import Config
from tools.multi_component_fit import MultiComponentFit

class MultiComponentTests(unittest.TestCase):
    def test_known_three_components_and_input_preserved(self):
        c=Config();model=MultiComponentFit(c);rng=np.random.default_rng(19)
        data=[]
        for _ in range(48):
            row=np.full(c.samples,20000.)
            for distance,amplitude in [(.3,200),(.9,700),(2.2,400)]:
                row+=amplitude*np.cos(2*np.pi*2*c.slope_hz_s*distance*model.t/299792458+rng.uniform(0,2*np.pi))
            data.append(row)
        data=np.array(data);original=data.copy();r=model.fit_associated(data,1,[1])
        np.testing.assert_array_equal(data,original)
        self.assertIsNotNone(r['range_m'])
        self.assertLess(abs(r['range_m']-.3),.0051)
        self.assertTrue(np.all(np.diff(r['objective_history'])>=-1e-8))
        self.assertLess(r['residual_fraction'],1e-4)
