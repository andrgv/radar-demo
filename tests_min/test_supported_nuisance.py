"""Synthetic identifiability check for the offline expanded nuisance search."""
import unittest
import numpy as np
from radar_min.core import Config
from tools.supported_nuisance_fit import SupportedNuisanceFit

class SupportedNuisanceTests(unittest.TestCase):
    def test_near_target_and_interference_below_previous_cutoff(self):
        c=Config();model=SupportedNuisanceFit(c);rng=np.random.default_rng(8)
        for distance in [.3,.5]:
            x=np.empty((16,3,64))
            for rx,nuisance in enumerate([.9,1.2,2.2]):
                for chirp in range(16):
                    pn,pf=rng.uniform(0,2*np.pi,2);t=model.t
                    x[chirp,rx]=20000+200*np.cos(2*np.pi*2*c.slope_hz_s*distance*t/299792458+pn)+700*np.cos(2*np.pi*2*c.slope_hz_s*nuisance*t/299792458+pf)
            result=model.fit_associated(x.reshape(-1,64),1,[1])
            self.assertIsNotNone(result['range_m'])
            self.assertLess(abs(result['range_m']-distance),.0051)
            lo,hi=result['target_support_m']
            self.assertTrue(all(r<lo or r>hi for r in result['far_m']))
            self.assertTrue(np.all(np.diff(result['objective_history'])>=-1e-8))
