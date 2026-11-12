import unittest
import numpy as np

from radar_min.phase_range import CandidatePhaseRange,PhaseRangeConfig
from tests_min.test_range_doppler import C,tone


class PhaseRangeTests(unittest.TestCase):
    def test_clean_real_tone_range_is_phase_invariant(self):
        fitter=CandidatePhaseRange(C)
        for distance in (.3,.5,.8,1.2):
            coordinate=distance/C.spacing_m
            center=int(np.floor(coordinate+.5))
            bins=list(range(max(1,center-1),center+2))
            for phase in np.linspace(0,2*np.pi,13):
                frame=tone([],1)
                samples=np.arange(C.samples)[None,:,None]
                chirp=np.arange(C.chirps)[:,None,None]
                phases=phase+np.array([0,.8,-1.2])[None,None,:]+.4*chirp
                frame.adc=32768+3*chirp+1200*np.cos(2*np.pi*coordinate*samples/C.samples+phases)
                result=fitter.fit(frame,bins)
                self.assertIsNotNone(result['range_m'],result)
                self.assertAlmostEqual(result['range_m'],distance,delta=1e-6)
                self.assertLess(result['residual_fraction'],1e-10)

    def test_dominant_single_rx_is_not_multi_rx_agreement(self):
        frame=tone([])
        samples=np.arange(C.samples)[None,:,None]
        coordinates=np.array([2,2.6,3])[None,None,:]
        amplitudes=np.array([2000,400,400])[None,None,:]
        frame.adc=32768+np.broadcast_to(amplitudes*np.cos(2*np.pi*coordinates*samples/C.samples),frame.adc.shape)
        result=CandidatePhaseRange(C).fit(frame,[1,2,3,4])
        self.assertIsNone(result['range_m'])
        self.assertEqual(result['reason'],'insufficient_consistent_rx')
        self.assertEqual(result['supported_rx'],1)
        self.assertLess(result['residual_fraction'],.5)

    def test_outside_support_never_forces_a_boundary_distance(self):
        result=CandidatePhaseRange(C).fit(tone([(4,0,2000)]),[1])
        self.assertIsNone(result['range_m'])
        self.assertEqual(result['reason'],'phase_fit_at_support_boundary')

    def test_noise_or_multiple_reflectors_not_forced_into_a_tone(self):
        fitter=CandidatePhaseRange(C)
        frame=tone([],1);rng=np.random.default_rng(42)
        frame.adc=32768+rng.normal(0,1000,frame.adc.shape)
        result=fitter.fit(frame,[2,3,4])
        self.assertIsNone(result['range_m'])
        self.assertIn(result['reason'],('poor_single_tone_model','broad_phase_fit','phase_fit_at_support_boundary','competing_phase_fits'))
        # Two widely separated equal tones have comparable fit optima.
        result=fitter.fit(tone([(2,0,1000),(6,0,1000)]),[1,2,3,4,5,6,7])
        self.assertIsNone(result['range_m'])
        self.assertIn(result['reason'],('competing_phase_fits','broad_phase_fit','insufficient_consistent_rx','poor_single_tone_model'))

    def test_empty_invalid_rails_and_noncontiguous_support(self):
        fitter=CandidatePhaseRange(C)
        self.assertEqual(fitter.fit(tone([]),[1])['reason'],'no_ac_energy')
        for bins in ([],[0],[1,3]):
            with self.assertRaises(ValueError):fitter.fit(tone([]),bins)
        frame=tone([(2,0,1000)]);frame.adc[0,0,0]=0
        # Discarded startup chirp is irrelevant; retained rails are rejected.
        fitter.fit(frame,[2])
        frame.adc[1,0,0]=0
        with self.assertRaises(ValueError):fitter.fit(frame,[2])
        with self.assertRaises(ValueError):PhaseRangeConfig(max_residual_fraction=1)


if __name__=='__main__':unittest.main()
