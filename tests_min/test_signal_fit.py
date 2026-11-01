import unittest
import numpy as np
from radar_min.core import Config
from tools.fit_range_signal import ToneFit


class SignalFitTests(unittest.TestCase):
    def setUp(self):
        self.c=Config();self.fit=ToneFit(self.c)

    def tone(self,distance,phases):
        f=2*self.c.slope_hz_s*distance/299792458
        return np.cos(2*np.pi*f*self.fit.t[None,:]+np.asarray(phases)[:,None])

    def test_known_frequency_across_phase_and_range(self):
        for distance in [.15,.1837,.3,.4,.5,.8732,1.5]:
            for phase in np.arange(12)*2*np.pi/12:
                result=self.fit.fit(17000+730*self.tone(distance,[phase]))
                self.assertAlmostEqual(result['range_m'],distance,places=5)
                self.assertLess(result['residual_fraction'],1e-10)

    def test_independent_trace_offsets_amplitudes_and_phases(self):
        x=self.tone(.4173,[0,.4,1.7,3.1])*np.array([10,300,700,40])[:,None]
        result=self.fit.fit(x+np.array([50,2000,-40,0])[:,None])
        self.assertAlmostEqual(result['range_m'],.4173,places=5)

    def test_constant_has_no_frequency(self):
        result=self.fit.fit(np.full((3,64),32000.))
        self.assertIsNone(result['range_m'])
        self.assertEqual(result['reason'],'no_ac_energy')

    def test_invalid_samples_rejected(self):
        with self.assertRaises(ValueError): self.fit.fit(np.full((1,64),np.nan))

    def test_noisy_known_tone(self):
        rng=np.random.default_rng(4)
        x=5000+500*self.tone(.4173,np.arange(48)) + rng.normal(0,5,(48,64))
        self.assertLess(abs(self.fit.fit(x)['range_m']-.4173),.001)


if __name__=='__main__': unittest.main()
