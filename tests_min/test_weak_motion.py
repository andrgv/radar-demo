from copy import deepcopy
import unittest

from radar_min.motion_range import MotionRangePolicy
from radar_min.weak_motion import WeakMotionLink
from tests_min.test_motion_range import reading
from tests_min.test_range_doppler import C


def frame(seq,frequency=0,track_id=7,weak=True):
    r=reading(seq,[(track_id,frequency,.8)])
    for c in r['results']['candidates']:c['rd_confirmed']=True
    if frequency==0:r['one_d']['power']=[1.]*33
    r['clutter_comparison']=dict(os=dict(frame_sequence=seq,target_detected=True,selected_group_bins=[2]),
        weak_phase_fit=dict(frame_sequence=seq),weak_selection=dict(shape_supported=weak,
            experimental_range_m=.81 if weak else None,rd_range_bin=2,rd_cycles_per_saved_block=frequency,
            phase_model_accepted=False,phase_model_reason='poor_single_tone_model'))
    return r


class WeakMotionTests(unittest.TestCase):
    def setUp(self):
        self.reference=MotionRangePolicy();self.policy=WeakMotionLink(C)

    def update(self,r):
        r['motion_result']=self.reference.update(r);before=deepcopy(r)
        result=self.policy.update(r);self.assertEqual(r,before);return result

    def seed(self):
        self.assertIsNone(self.update(frame(1,-.0625))['experimental_range_m'])
        self.assertEqual(self.update(frame(2,-.0625))['state'],'armed')

    def test_same_current_weak_stop_retains_model_rejection_and_only_current_rd_range(self):
        self.seed();r=self.update(frame(3))
        self.assertEqual(r['experimental_range_m'],.8)
        self.assertEqual(r['source'],'RD weak stopped')
        self.assertFalse(r['phase_model_accepted']);self.assertFalse(r['primary_eligible'])
        self.assertFalse(r['predicted']);self.assertTrue(r['inspection_only'])

    def test_stationary_candidate_never_seeds_and_unsupported_stop_revokes_motion_proof(self):
        for seq in range(1,10):self.assertIsNone(self.update(frame(seq))['experimental_range_m'])
        self.setUp();self.seed()
        self.assertEqual(self.update(frame(3,weak=False))['state'],'cleared')
        self.assertIsNone(self.update(frame(4))['experimental_range_m'])

    def test_miss_gap_or_identity_switch_requires_new_motion(self):
        self.seed();missing=frame(3)
        missing['association']['tracks'][0].update(state='missed',measurement_valid=False)
        self.assertEqual(self.update(missing)['state'],'cleared')
        self.assertIsNone(self.update(frame(4))['experimental_range_m'])
        self.setUp();self.seed()
        self.assertIsNone(self.update(frame(5))['experimental_range_m'])
        self.assertIsNone(self.update(frame(6,track_id=8))['experimental_range_m'])

    def test_different_weak_peak_stale_support_and_range_disagreement_revoke(self):
        for key in('peak','stale','range','fine','competitor'):
            self.setUp();self.seed();r=frame(3)
            if key=='peak':r['clutter_comparison']['weak_selection']['rd_range_bin']=1
            elif key=='stale':r['clutter_comparison']['weak_phase_fit']['frame_sequence']=2
            elif key=='range':r['clutter_comparison']['weak_selection']['experimental_range_m']=.3
            elif key=='fine':r['results']['candidates'][0]['rd_fine_range']['range_m']=None
            else:
                competitor=frame(3,.0625,8)['association']['tracks'][0]
                r['association']['tracks'].append(competitor)
            self.assertEqual(self.update(r)['state'],'cleared',key)
            self.assertIsNone(self.update(frame(4))['experimental_range_m'],key)

    def test_invalid_and_strong_stop_do_not_publish_a_weak_replacement(self):
        self.seed();r=frame(3);r['one_d']['power'][2]=100
        self.assertEqual(self.update(r)['state'],'strong_stop')
        self.assertIsNone(self.policy.update(dict(valid=False,frame_sequence=4))['experimental_range_m'])
        self.assertIsNone(self.policy.track_id)

    def test_new_motion_can_reseed_after_unsupported_stop_but_static_reappearance_cannot(self):
        self.seed();self.update(frame(3,weak=False))
        for seq in(4,5):self.assertIsNone(self.update(frame(seq))['experimental_range_m'])
        self.assertEqual(self.update(frame(6,-.0625))['state'],'confirming')
        self.assertEqual(self.update(frame(7,-.0625))['state'],'armed')
        self.assertEqual(self.update(frame(8))['experimental_range_m'],.8)
