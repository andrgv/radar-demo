from copy import deepcopy
import unittest

from radar_min.weak_candidate import select_weak_candidate
from radar_min.rd_live import LiveRangeDoppler
from tests_min.test_range_doppler import C,tone


class WeakCandidateTests(unittest.TestCase):
    def inputs(self):
        reading=dict(frame_sequence=5,target_detected=True,reason='cfar_peak_uncalibrated',candidates=[{}],
            selected_group_bins=[2,3],fine_range=dict(range_m=.8))
        clusters=[dict(local_maxima=[dict(range_bin=2,cycles_per_saved_block=0)])]
        phase=dict(frame_sequence=5,range_m=None,provisional_range_m=.8,reason='poor_single_tone_model',
            support_m=[1.5*C.spacing_m,3.5*C.spacing_m],comparable_optima=1,
            near_optimal_width_m=.02,per_rx_range_m=[.79,.81,.95],residual_fraction=.8)
        return reading,clusters,phase

    def test_shape_support_does_not_accept_the_rejected_model_or_promote_primary(self):
        r,c,p=self.inputs();before=deepcopy(p)
        result=select_weak_candidate(r,c,p,C)
        self.assertEqual(result['experimental_range_m'],.8)
        self.assertFalse(result['primary_eligible'])
        self.assertFalse(result['phase_model_accepted'])
        self.assertEqual(result['phase_model_reason'],'poor_single_tone_model')
        self.assertEqual(result['raw_model_residual_fraction'],.8)
        self.assertEqual(result['interior_rx'],2)
        self.assertEqual(p,before)

    def test_boundary_broad_competing_and_inconsistent_rx_remain_withheld(self):
        changes=[dict(provisional_range_m=1.5*C.spacing_m),dict(near_optimal_width_m=C.spacing_m),
            dict(comparable_optima=2),dict(per_rx_range_m=[.6,.8,1.1]),dict(frame_sequence=4),
            dict(support_m=[.1,1.5])]
        for change in changes:
            r,c,p=self.inputs();p.update(change)
            self.assertIsNone(select_weak_candidate(r,c,p,C)['experimental_range_m'],change)

    def test_original_os_rd_and_confirmation_requirements_cannot_be_bypassed(self):
        r,c,p=self.inputs();r['target_detected']=False
        self.assertIsNone(select_weak_candidate(r,c,p,C)['experimental_range_m'])
        r['target_detected']=True;r['candidates']=[{},{}]
        self.assertEqual(select_weak_candidate(r,c,p,C)['reason'],'multiple_os_groups')
        r['candidates']=[{}];c[0]['local_maxima']*=2
        self.assertEqual(select_weak_candidate(r,c,p,C)['reason'],'multiple_current_rd_peaks')

    def test_optional_live_branch_preserves_primary_motion_and_rd_and_clears_on_fault(self):
        baseline=LiveRangeDoppler(C);weak=LiveRangeDoppler(C,experimental_weak=True)
        self.assertIsNotNone(weak.metadata['experimental_weak_candidate'])
        self.assertIsNone(baseline.metadata['experimental_weak_candidate'])
        for seq in(1,2,3,4,5):
            f=tone([(2.2,0,2000)],seq);a=baseline.update(f);b=weak.update(f)
            self.assertEqual(a['results'],b['results'])
            self.assertEqual(a['association'],b['association'])
            self.assertEqual(a['motion_result'],b['motion_result'])
            self.assertNotIn('weak_motion_result',a)
            self.assertEqual(b['weak_motion_result']['frame_sequence'],seq)
            self.assertNotIn('weak_feature_result',a)
            self.assertEqual(b['weak_feature_result']['frame_sequence'],seq)
            self.assertEqual(b['weak_feature_result']['confirmed'],seq==5)
        self.assertIsNotNone(b['clutter_comparison']['weak_selection']['experimental_range_m'])
        self.assertEqual(b['clutter_comparison']['weak_phase_fit']['frame_sequence'],5)
        self.assertTrue(b['weak_feature_result']['confirmed'])
        rejected=weak.reject_frame(tone([(2.2,0,2000)],6),'clock_fit_unstable')
        self.assertNotIn('clutter_comparison',rejected)
        self.assertEqual(rejected['weak_motion_result']['state'],'invalid')
        self.assertIsNone(rejected['weak_motion_result']['experimental_range_m'])
        self.assertIsNone(rejected['weak_feature_result']['experimental_range_m'])
        recovered=weak.update(tone([(2.2,0,2000)],7))
        self.assertIsNone(recovered['clutter_comparison']['weak_selection']['experimental_range_m'])
        weak.clear();self.assertIsNone(weak.weak_motion.track_id)
        self.assertIsNone(weak.weak_features.feature_id)
