import unittest
import numpy as np
from radar_min.core import Config
from radar_min.associated_fit import AssociatedFit

class AssociatedFitTests(unittest.TestCase):
    def setUp(self):self.c=Config();self.fit=AssociatedFit(self.c)
    def tone(self,r):
        return 500*np.cos(2*np.pi*(2*self.c.slope_hz_s*r/299792458)*self.fit.t[None,:]+np.arange(12)[:,None])
    def test_known_tone_and_subbin_refinement(self):
        for r in [.3,.4,.5]:
            result=self.fit.fit_associated(self.tone(r),1,[1])
            self.assertLess(abs(result['range_m']-r),.001)
    def test_connected_bins_preserve_low_side_component(self):
        result=self.fit.fit_associated(self.tone(.32),2,[1,2])
        self.assertLess(abs(result['range_m']-.32),.001)
    def test_search_limit_cannot_promote_secondary_peak(self):
        self.assertIsNone(self.fit.fit_associated(self.tone(.1),1,[1,2])['range_m'])
    def test_constant_and_nonfinite(self):
        self.assertIsNone(self.fit.fit_associated(np.ones((3,64)),1)['range_m'])
        with self.assertRaises(ValueError):self.fit.fit_associated(np.full((3,64),np.nan),1)
    def test_disconnected_qualified_bin_does_not_expand_support(self):
        result=self.fit.fit_associated(self.tone(.32),2,[2,4])
        self.assertTrue(result['range_m'] is None or result['range_m']>=self.c.spacing_m)
