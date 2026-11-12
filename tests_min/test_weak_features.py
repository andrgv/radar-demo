from copy import deepcopy
import unittest

from radar_min.weak_features import WeakFeatureConfirmer
from radar_min.rd_association import AssociationConfig
from tests_min.test_range_doppler import C


def frame(seq,r=2,d=8,value=.8):
    frequency=(d-8)/16
    peak=dict(doppler_bin=d,range_bin=r,cycles_per_saved_block=frequency)
    observation=dict(**peak,power=10.,threshold_power=8.,disposition='below_birth_margin')
    return dict(frame_sequence=seq,valid=True,results=dict(frame_sequence=seq,candidates=[],primary=None),
        association=dict(sequence=seq,valid=True,observations=[observation],tracks=[]),
        cfar_clusters=[dict(local_maxima=[peak])],
        clutter_comparison=dict(os=dict(frame_sequence=seq,target_detected=True,selected_group_bins=[r]),
            weak_phase_fit=dict(frame_sequence=seq),weak_selection=dict(shape_supported=True,
                experimental_range_m=value,rd_range_bin=r,rd_cycles_per_saved_block=frequency,
                phase_model_accepted=False,phase_model_reason='poor_single_tone_model')))


class WeakFeaturesTests(unittest.TestCase):
    def test_consecutive_low_margin_scene_feature_confirms_without_motion_or_model_acceptance(self):
        p=WeakFeatureConfirmer(C)
        for seq in(1,2,3):
            r=frame(seq);before=deepcopy(r);out=p.update(r);self.assertEqual(r,before)
            self.assertEqual(out['confirmation_hits'],seq)
            self.assertEqual(out['confirmed'],seq==3)
        self.assertEqual(out['experimental_range_m'],.8)
        self.assertEqual(out['measurement_sequence'],3)
        self.assertFalse(out['primary_eligible']);self.assertFalse(out['predicted'])
        self.assertFalse(out['phase_model_accepted']);self.assertEqual(out['physical_identity'],'unverified')

    def test_gap_loss_ambiguity_and_rejection_never_hold_or_recycle_feature_ids(self):
        for kind in('gap','loss','ambiguity','strong_ambiguity','invalid','stale'):
            p=WeakFeatureConfirmer(C)
            for seq in(1,2,3):old=p.update(frame(seq))['feature_id']
            r=frame(4)
            if kind=='gap':r=frame(5)
            elif kind=='loss':r['clutter_comparison']['weak_selection']['experimental_range_m']=None
            elif kind=='ambiguity':r['cfar_clusters'][0]['local_maxima'].append(dict(doppler_bin=8,range_bin=3))
            elif kind=='strong_ambiguity':r['association']['observations'][0]['disposition']='unresolved_track_gate'
            elif kind=='invalid':r['valid']=False
            else:r['clutter_comparison']['weak_phase_fit']['frame_sequence']=3
            out=p.update(r);self.assertIsNone(out['experimental_range_m'],kind)
            out=p.update(frame(6));self.assertNotEqual(out['feature_id'],old,kind)
            self.assertFalse(out['confirmed'],kind)

    def test_native_gates_and_doppler_wrap_are_inherited_without_point_prediction(self):
        p=WeakFeatureConfirmer(C)
        first=p.update(frame(1,d=15))
        second=p.update(frame(2,d=0))
        self.assertEqual(first['feature_id'],second['feature_id'])
        third=p.update(frame(3,d=1));self.assertTrue(third['confirmed'])
        jumped=p.update(frame(4,r=4,d=1,value=1.3))
        self.assertNotEqual(jumped['feature_id'],third['feature_id']);self.assertFalse(jumped['confirmed'])
        p=WeakFeatureConfirmer(C,doppler_edge='truncate')
        first=p.update(frame(1,d=15));second=p.update(frame(2,d=0))
        self.assertNotEqual(first['feature_id'],second['feature_id'])

    def test_current_cfar_and_matching_support_cannot_be_bypassed(self):
        for kind in('cfar','support','rd_sequence','result_sequence'):
            p=WeakFeatureConfirmer(C,AssociationConfig(confirmation_frames=1));r=frame(1)
            if kind=='cfar':r['association']['observations'][0]['power']=8.
            elif kind=='support':r['clutter_comparison']['os']['selected_group_bins']=[4]
            elif kind=='rd_sequence':r['association']['sequence']=0
            else:r['results']['frame_sequence']=0
            self.assertIsNone(p.update(r)['experimental_range_m'],kind)
