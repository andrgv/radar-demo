import unittest
import numpy as np
from tools.audit_direct_obstacles import candidates
from tools.audit_subspace_returns import estimate
from tools.audit_stable_returns import stable_components
from tools.track_transition_returns import track_peaks


class DirectAuditTests(unittest.TestCase):
    def test_noise_floor_has_no_candidates(self):
        self.assertEqual(candidates(np.ones((33,3)),6)[0], [])

    def test_two_receiver_support_and_no_measured_distance_input(self):
        power = np.ones((33,3))
        power[7,:2] = 100
        power[19,:2] = 20
        self.assertEqual(candidates(power,6)[0], [7,19])
        power[7,1] = 1
        self.assertEqual(candidates(power,6)[0], [19])

    def test_dc_and_nyquist_not_candidates(self):
        power = np.ones((33,3))
        power[[0,32]] = 10000
        self.assertEqual(candidates(power,6)[0], [])

    def test_subspace_recovers_overlapping_known_tones_without_range_labels(self):
        rng=np.random.default_rng(42)
        axis=np.arange(64)
        frequencies=[3.2,4.7,13.4]
        traces=sum(rng.uniform(300,1000,(3,1))*np.cos(2*np.pi*f*axis/64+rng.uniform(-3,3,(3,1)))
                   for f in frequencies)
        traces+=rng.normal(0,.1,traces.shape)
        fitted=estimate(traces)['best']['frequencies_native_bins']
        self.assertEqual(len(fitted),3)
        np.testing.assert_allclose(fitted,frequencies,atol=.01)

    def test_subspace_does_not_fit_empty_signal(self):
        with self.assertRaises(ValueError):
            estimate(np.ones((3,64)))

    def test_known_components_agree_across_fast_time_subsets(self):
        rng=np.random.default_rng(42)
        axis=np.arange(64)
        traces=sum(rng.uniform(300,1000,(3,1))*np.cos(2*np.pi*f*axis/64+rng.uniform(-3,3,(3,1)))
                   for f in (3.2,4.7,13.4))
        traces+=rng.normal(0,.1,traces.shape)
        found=[v['native_bin'] for v in stable_components(traces)['components']]
        np.testing.assert_allclose(found,[3.2,4.7,13.4],atol=.01)

    def test_track_follows_continuous_return_but_does_not_bridge_time_gap(self):
        power=np.ones((20,33,3))
        for i in range(20):
            power[i,5,:]=100
        times=np.r_[np.arange(10)*.1,3+np.arange(10)*.1]
        tracks=track_peaks(power,times)
        self.assertEqual(len(tracks),6)
        self.assertTrue(all(len(track['points'])==10 for track in tracks))


if __name__ == '__main__':
    unittest.main()
