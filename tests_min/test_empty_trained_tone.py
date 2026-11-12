"""Synthetic controls for the empty-trained, variable-coefficient nuisance probe."""
from types import SimpleNamespace
import unittest
import numpy as np
from radar_min.core import Config
from tools.investigate_empty_trained_tone import EmptyTrainedTone


class EmptyTrainedToneTests(unittest.TestCase):
    def setUp(self):
        self.c=Config()

    def frame(self,nuisance,phase=0,amplitude=300,target=None):
        c=self.c;n=np.arange(c.samples)
        x=np.empty((c.chirps,c.samples,3))
        for rx,r in enumerate(nuisance):
            for chirp in range(c.chirps):
                p=phase+.11*chirp+.2*rx
                x[chirp,:,rx]=20000+amplitude*np.cos(2*np.pi*r/c.spacing_m*n/c.samples+p)
                if target is not None:
                    x[chirp,:,rx]+=90*np.cos(2*np.pi*target/c.spacing_m*n/c.samples-.17*chirp+.3*rx)
        return SimpleNamespace(adc=x,profile_id=c.profile_id)

    def test_added_target_survives_background_phase_and_amplitude_changes(self):
        ranges=[2.1,2.3,2.5]
        model=EmptyTrainedTone(self.c,[self.frame(ranges,phase=p) for p in [0,.8,1.6]])
        frozen=model.q.copy();frequencies=[r[:] for r in model.background.frequencies]
        for distance in [.5,1.2]:
            for phase,amplitude in [(0,150),(1.1,800),(2.8,400)]:
                result=model.fit(self.frame(ranges,phase,amplitude,target=distance))
                self.assertIsNotNone(result['quality_range_m'],result)
                self.assertLess(abs(result['quality_range_m']-distance),.006)
                self.assertEqual(result['supported_rx'],3)
        np.testing.assert_array_equal(model.q,frozen)
        self.assertEqual(model.background.frequencies,frequencies)

    def test_background_only_phase_change_is_not_a_unique_target(self):
        ranges=[.5,.5,.5]
        model=EmptyTrainedTone(self.c,[self.frame(ranges)])
        result=model.fit(self.frame(ranges,phase=2.3,amplitude=700))
        self.assertIsNone(result['quality_range_m'])
        self.assertIn('no_unique_energy',result['failures'])
        self.assertLess(result['background_residual_fraction'],1e-20)

    def test_outside_scan_target_cannot_be_published_at_boundary(self):
        ranges=[2.1,2.3,2.5]
        model=EmptyTrainedTone(self.c,[self.frame(ranges)])
        result=model.fit(self.frame(ranges,target=1.7))
        self.assertIsNone(result['quality_range_m'])
        self.assertIn('scan_boundary',result['failures'])

    def test_orthogonal_scores_match_independent_joint_least_squares(self):
        ranges=[2.1,2.3,2.5]
        model=EmptyTrainedTone(self.c,[self.frame(ranges)])
        frame=self.frame(ranges,phase=1.7,amplitude=550,target=.5)
        result=model.fit(frame)
        raw=frame.adc[self.c.discard_chirps:].transpose(0,2,1)
        candidate=model.background.target.basis(result['diagnostic_range_m'])
        residual_energy=0.
        for rx,u in enumerate(model.background.nuisance):
            design=np.column_stack((np.ones(self.c.samples),u,candidate))
            data=raw[:,rx].T
            coefficients=np.linalg.lstsq(design,data,rcond=None)[0]
            residual_energy+=float(np.sum((data-design@coefficients)**2))
        centered=raw-raw.mean(axis=2,keepdims=True)
        expected=residual_energy/np.sum(centered**2)
        self.assertAlmostEqual(result['joint_raw_residual_fraction'],expected,places=12)


if __name__=='__main__':unittest.main()
