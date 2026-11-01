"""Math checks for the offline joint fit, not physical accuracy qualification."""
import unittest
import numpy as np
from radar_min.core import Config
from tools.joint_component_fit import JointComponentFit

class JointComponentTests(unittest.TestCase):
    def setUp(self):self.c=Config();self.model=JointComponentFit(self.c)
    def make_signal(self,near,seed=4):
        rng=np.random.default_rng(seed);t=self.model.t
        x=np.empty((16,3,64))
        for rx,far in enumerate([1.93,2.2,2.67]):
            for chirp in range(16):
                pn,pf=rng.uniform(0,2*np.pi,2)
                x[chirp,rx]=20000+200*np.cos(2*np.pi*(2*self.c.slope_hz_s*near/299792458)*t+pn)+700*np.cos(2*np.pi*(2*self.c.slope_hz_s*far/299792458)*t+pf)
        return x.reshape(-1,64)
    def test_known_components_and_monotonic_objective(self):
        for near in [.3,.4,.5]:
            result=self.model.fit_associated(self.make_signal(near),1,[1,2])
            self.assertIsNotNone(result['range_m'])
            self.assertLessEqual(abs(result['range_m']-near),.0051)
            self.assertTrue(np.all(np.diff(result['objective_history'])>=-1e-9))
            self.assertLess(result['residual_fraction'],1e-4)
    def test_constant_and_invalid(self):
        self.assertIsNone(self.model.fit_associated(np.ones((48,64)),1)['range_m'])
        for x in [np.ones((4,64)),np.full((48,64),np.nan)]:
            with self.assertRaises(ValueError):self.model.fit_associated(x,1)
