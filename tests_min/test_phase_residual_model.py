import unittest
import numpy as np

from tools.phase_residual_model import ResidualRangeModel
from tests_min.test_range_doppler import C,tone


class ResidualModelTests(unittest.TestCase):
    def test_separated_strong_nuisance_does_not_move_candidate_tone(self):
        model=ResidualRangeModel(C)
        for phase in (0,.8,2):
            f=tone([(7,0,4000)])
            n=np.arange(C.samples)[None,:,None]
            f.adc+=700*np.cos(2*np.pi*1.43*n/C.samples+phase)
            r=model.fit(f,[1,2])
            self.assertEqual(r['single']['reason'],'poor_single_tone_model')
            self.assertAlmostEqual(r['diagnostic_range_m']/C.spacing_m,1.43,delta=.002)
            self.assertLess(r['residual_fraction'],1e-6)
            self.assertGreater(r['nuisance_unique_energy_fraction'],.9)
            self.assertLess(r['candidate_unique_energy_fraction'],.1)

    def test_no_energy_and_outside_candidate_remain_explicit(self):
        model=ResidualRangeModel(C)
        self.assertEqual(model.fit(tone([]),[1])['reason'],'no_ac_energy')
        r=model.fit(tone([(4,0,1000),(8,0,2000)]),[1])
        # Two outside returns can leave a small interior leakage optimum. A good
        # global residual must not be interpreted as presence in this candidate.
        self.assertIsNone(r['single']['range_m'])
        self.assertNotIn('range_m',r)
        self.assertLess(r['candidate_unique_energy_fraction'],.01)
        self.assertGreaterEqual(r['diagnostic_range_m'],.5*C.spacing_m)
        self.assertLessEqual(r['diagnostic_range_m'],1.5*C.spacing_m)
        with self.assertRaises(ValueError):model.fit(tone([]),[1,3])


if __name__=='__main__':unittest.main()
