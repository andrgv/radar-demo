"""Positive controls for offline experiments; not physical validation."""
import unittest
import numpy as np
from radar_min.core import Config
from tools.evaluate_weighted_fit import WeightedFit
from tools.evaluate_far_component import FarComponentFit

class CloseModelTests(unittest.TestCase):
    def test_weighted_basis_matches_weighted_data_across_phase(self):
        c=Config();fit=WeightedFit(c)
        for distance in [.3,.4,.5]:
            for phase in np.arange(8)*np.pi/4:
                x=20000+500*np.cos(2*np.pi*(2*c.slope_hz_s*distance/299792458)*fit.t[None,:]+phase)
                result=fit.fit_associated(x,1,[1,2])
                self.assertIsNotNone(result['range_m'])
                self.assertLess(abs(result['range_m']-distance),.001)
    def test_near_target_with_stronger_far_component(self):
        c=Config();fit=FarComponentFit(c)
        for distance in [.3,.4,.5]:
            for phase in [0,1,2]:
                t=fit.t;near=200*np.cos(2*np.pi*(2*c.slope_hz_s*distance/299792458)*t+.7)
                far=700*np.cos(2*np.pi*(2*c.slope_hz_s*2.2/299792458)*t+phase)
                x=np.tile(near+far+20000,(48,1))
                result=fit.fit_associated(x,1,[1,2])
                self.assertIsNotNone(result['range_m'])
                self.assertLess(abs(result['range_m']-distance),.04)
