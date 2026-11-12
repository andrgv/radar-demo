import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from radar.protocol import Frame
from radar.storage import Recorder
from radar_min.__main__ import main
from radar_min.core import Config
from radar_min.cfar_2d import cluster_cells
from radar_min.rd_association import AssociationConfig, CandidateAssociator
from tests_min.test_range_doppler import tone


C = Config()


def frame(seq, **kwargs):
    return Frame(seq,kwargs.pop('timestamp_us',seq*100000),C.profile_id,
                 np.full((17,64,3),32768,dtype=np.uint16),**kwargs)


def step(associator, seq, cells=(), **kwargs):
    p = np.ones((16,33)); threshold = np.full_like(p,2)
    for d,r,value in cells:p[d,r] = value
    accepted = p>threshold
    groups = cluster_cells(p,accepted,associator.doppler_edge)
    return associator.update(frame(seq,**kwargs),p,threshold,accepted,groups)


class AssociationTests(unittest.TestCase):
    def test_quadratic_cost_resolves_native_tie_using_only_current_peak(self):
        native=CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        refined=CandidateAssociator(C,AssociationConfig(confirmation_frames=1,range_metric='quadratic'))
        for a in (native,refined):step(a,1,[(8,3,100),(8,5,100)])
        points=[(8,3,100),(8,4,200),(8,5,4)]
        old=step(native,2,points);new=step(refined,2,points)
        self.assertTrue(all(t['measurement'] is None for t in old['tracks']))
        left=next(t for t in new['tracks'] if t['track_id']==1)
        self.assertTrue(left['measurement_valid'])
        self.assertEqual(left['measurement']['range_bin'],4)
        self.assertLess(left['measurement']['range_coordinate'],4)
        self.assertEqual(left['last_peak_sequence'],2)
        # The same native gate rejects a peak two bins away despite a refined cost.
        a=CandidateAssociator(C,AssociationConfig(confirmation_frames=1,range_metric='quadratic'))
        step(a,1,[(8,3,100)])
        result=step(a,2,[(8,5,200)])
        first=next(t for t in result['tracks'] if t['track_id']==1)
        self.assertIsNone(first['measurement'])

    def test_quadratic_exact_tie_stays_ambiguous(self):
        a=CandidateAssociator(C,AssociationConfig(confirmation_frames=1,range_metric='quadratic'))
        step(a,1,[(8,3,100),(8,5,100)])
        result=step(a,2,[(8,4,200)])
        self.assertTrue(all(t['measurement'] is None for t in result['tracks']))

    def test_startup_stationary_confirmation_needs_no_empty_reference(self):
        a = CandidateAssociator(C)
        for seq in (1,2):
            r = step(a,seq,[(8,5,100)])
            self.assertEqual(r['tracks'][0]['state'],'tentative')
            self.assertIsNone(r['tracks'][0]['measurement'])
        r = step(a,3,[(8,5,100)])
        t = r['tracks'][0]
        self.assertTrue(t['measurement_valid'])
        self.assertEqual(t['measurement']['range_bin'],5)
        self.assertEqual(t['doppler_evidence'],'zero_doppler')

    def test_motion_into_stop_keeps_id_and_current_measurement(self):
        a = CandidateAssociator(C)
        for seq in (1,2,3):r = step(a,seq,[(10,5,100)])
        track_id = r['tracks'][0]['track_id']
        for seq,d,rng in ((4,9,4),(5,8,4),(6,8,4)):
            t = step(a,seq,[(d,rng,100)])['tracks'][0]
            self.assertEqual(t['track_id'],track_id)
            self.assertEqual(t['state'],'measured')
            self.assertEqual(t['measurement']['range_bin'],rng)
            self.assertEqual(t['last_peak_sequence'],seq)
        self.assertTrue(t['has_nonzero_peak_history'])
        self.assertEqual(t['doppler_evidence'],'zero_doppler')

    def test_merged_ridge_is_bounded_ambiguity_not_a_fresh_range(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1,max_ambiguous_frames=2))
        first = step(a,1,[(8,4,100),(8,7,200)])
        target = next(t['track_id']for t in first['tracks']if t['measurement']['range_bin']==4)
        ridge = [(8,4,20),(8,5,40),(8,6,60),(8,7,200)]
        for seq in (2,3):
            result = step(a,seq,ridge)
            t = next(t for t in result['tracks']if t['track_id']==target)
            self.assertEqual(t['state'],'ambiguous')
            self.assertEqual(t['reason'],'accepted_cells_without_isolated_peak')
            self.assertIsNone(t['measurement'])
            self.assertIsNone(t['current_peak'])
            self.assertFalse(t['measurement_valid'])
            self.assertIn([8,4],t['current_support_cells'])
            self.assertEqual(t['last_peak_sequence'],1)
            self.assertEqual(next(t for t in a.tracks if t.track_id==target).anchor,(8,4))
        result = step(a,4,ridge)
        self.assertFalse(any(t['track_id']==target for t in result['tracks']))
        self.assertEqual(result['ended_tracks'][0]['reason'],'ambiguous_support_expired')

    def test_missing_measurement_clears_immediately_then_loses_and_reseeds(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1,max_missed_frames=2))
        first = step(a,1,[(8,5,100)])['tracks'][0]['track_id']
        for seq in (2,3):
            t = step(a,seq)['tracks'][0]
            self.assertEqual(t['state'],'missed')
            self.assertIsNone(t['measurement'])
            self.assertEqual(t['current_support_cells'],[])
        lost = step(a,4)
        self.assertEqual(lost['tracks'],[])
        self.assertEqual(lost['ended_tracks'][0]['track_id'],first)
        new = step(a,5,[(8,5,100)])['tracks'][0]['track_id']
        self.assertNotEqual(first,new)

    def test_competing_tracks_do_not_silently_take_the_same_peak(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        step(a,1,[(8,4,100),(8,6,100)])
        result = step(a,2,[(8,5,100)])
        self.assertEqual(len(result['tracks']),2)
        self.assertTrue(all(t['state']=='ambiguous'for t in result['tracks']))
        self.assertTrue(all(t['measurement']is None for t in result['tracks']))
        self.assertEqual(result['observations'][0]['disposition'],'unresolved_track_gate')

    def test_distinct_new_peak_can_seed_next_to_a_measured_peak(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        step(a,1,[(8,5,100)])
        result = step(a,2,[(8,5,100),(6,5,100)])
        self.assertEqual(len(result['tracks']),2)
        self.assertEqual({t['measurement']['doppler_bin']for t in result['tracks']},{6,8})

    def test_birth_quality_and_confirmation_reject_transients(self):
        a = CandidateAssociator(C)
        weak = step(a,1,[(8,20,3)])
        self.assertEqual(weak['tracks'],[])
        self.assertEqual(weak['observations'][0]['disposition'],'below_birth_margin')
        step(a,2,[(8,20,100)])
        transient = step(a,3)
        self.assertEqual(transient['tracks'],[])
        self.assertEqual(transient['ended_tracks'][0]['reason'],'confirmation_interrupted')
        step(a,4,[(8,20,100)])
        weak = step(a,5,[(8,20,3)])
        self.assertEqual(weak['tracks'],[])
        self.assertEqual(weak['ended_tracks'][0]['reason'],'confirmation_quality_interrupted')
        for seq in (6,7,8):r = step(a,seq,[(8,20,100)])
        self.assertTrue(r['tracks'][0]['confirmed'])
        self.assertTrue(step(a,9,[(8,20,3)])['tracks'][0]['measurement_valid'])

    def test_support_alone_cannot_seed_a_second_object(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        result = step(a,1,[(8,4,20),(8,5,40),(8,6,60),(8,7,200)])
        self.assertEqual(len(result['tracks']),1)
        self.assertEqual(result['tracks'][0]['measurement']['range_bin'],7)

    def test_cell_support_cannot_finish_confirmation(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=2))
        first = step(a,1,[(8,4,100)])['tracks'][0]['track_id']
        result = step(a,2,[(8,4,20),(8,5,40),(8,6,60),(8,7,200)])
        self.assertFalse(any(t['track_id']==first for t in result['tracks']))
        self.assertTrue(any(t['track_id']==first and t['reason']=='confirmation_interrupted'for t in result['ended_tracks']))

    def test_two_distinct_maxima_in_one_component_remain_measured(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        first = step(a,1,[(8,4,100),(8,7,100)])
        ids = {t['track_id']for t in first['tracks']}
        result = step(a,2,[(8,4,100),(8,5,10),(8,6,5),(8,7,100)])
        self.assertEqual({t['track_id']for t in result['tracks']},ids)
        self.assertTrue(all(t['measurement_valid']for t in result['tracks']))
        self.assertEqual({t['measurement']['cluster_id']for t in result['tracks']},{0})
        self.assertTrue(all(t['measurement']['cluster_local_maxima']==2 for t in result['tracks']))

    def test_wrap_policy_and_no_range_wrap(self):
        for policy in ('wrap','truncate'):
            a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1),policy)
            first = step(a,1,[(15,5,100)])['tracks'][0]['track_id']
            result = step(a,2,[(0,5,100)])
            measured = [t for t in result['tracks']if t['measurement_valid']]
            self.assertEqual(measured[0]['track_id']==first,policy=='wrap')
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        first = step(a,1,[(8,1,100)])['tracks'][0]['track_id']
        result = step(a,2,[(8,31,100)])
        self.assertFalse(any(t['measurement_valid']and t['track_id']==first for t in result['tracks']))

    def test_gap_invalid_frame_and_counters_reset_without_id_reuse(self):
        for kind in ('gap','flags','counter','invalid'):
            a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
            first = step(a,1,[(8,5,100)])['tracks'][0]['track_id']
            if kind=='gap':result = step(a,3,[(8,5,100)]); next_seq=4
            elif kind=='flags':result = step(a,2,[(8,5,100)],flags=0); next_seq=3
            elif kind=='counter':result = step(a,2,[(8,5,100)],errors=1); next_seq=3
            else:result = a.update(frame(2),None,None,None,[],valid=False,reason='invalid_adc'); next_seq=3
            self.assertFalse(result['valid'])
            self.assertEqual(result['tracks'],[])
            self.assertEqual(result['ended_tracks'][0]['track_id'],first)
            kwargs = {'errors':1}if kind=='counter'else{}
            new = step(a,next_seq,[(8,5,100)],**kwargs)['tracks'][0]
            self.assertNotEqual(new['track_id'],first)

    def test_timestamp_wrap_is_continuous(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        first = step(a,1,[(8,5,100)],timestamp_us=0xffff0000)['tracks'][0]['track_id']
        t = step(a,2,[(8,5,100)],timestamp_us=(0xffff0000+100000)&0xffffffff)['tracks'][0]
        self.assertEqual(t['track_id'],first)

    def test_bad_maps_and_stale_candidates_fail_closed(self):
        a = CandidateAssociator(C,AssociationConfig(confirmation_frames=1))
        step(a,1,[(8,5,100)])
        bad = a.update(frame(2),np.full((16,33),np.nan),np.ones((16,33)),np.zeros((16,33),bool),[])
        self.assertFalse(bad['valid'])
        self.assertEqual(bad['tracks'],[])
        p=np.ones((16,33));mask=np.zeros_like(p,dtype=bool)
        groups=[dict(cluster_id=0,local_maxima=[dict(doppler_bin=8,range_bin=5)])]
        bad = a.update(frame(3),p,np.full_like(p,2),mask,groups)
        self.assertEqual(bad['reason'],'invalid_association_candidates')

    def test_config_validation(self):
        for kw in ({'confirmation_frames':0},{'range_gate':-1},{'max_missed_frames':1.5},
                   {'birth_margin_db':-1},{'ambiguity_gap':float('nan')}):
            with self.assertRaises(ValueError):AssociationConfig(**kw)
        with self.assertRaises(ValueError):CandidateAssociator(C,AssociationConfig(doppler_gate=8))

    def test_cli_tracks_exports_reset_and_do_not_change_cfar(self):
        import matplotlib
        matplotlib.use('Agg')
        with tempfile.TemporaryDirectory()as folder:
            recording=Path(folder)/'recording';output=Path(folder)/'associated';baseline=Path(folder)/'cfar'
            with Recorder(recording,C)as recorder:
                for seq in range(1,6):
                    f=tone([(6,0,2000),(15,-.25,1000)],seq)
                    if seq==3:f.flags=0
                    recorder.write(f)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['range-doppler',str(recording),'--detector','cfar2d',
                    '--associate','--track-confirmation','2','--output',str(output)]),0)
                self.assertEqual(main(['range-doppler',str(recording),'--detector','cfar2d',
                    '--output',str(baseline)]),0)
            rows=[json.loads(x)for x in(output/'tracks.jsonl').read_text().splitlines()]
            self.assertFalse(any(t['measurement_valid']for t in rows[0]['tracks']))
            self.assertTrue(any(t['measurement_valid']for t in rows[1]['tracks']))
            old_ids={t['track_id']for t in rows[1]['tracks']}
            self.assertFalse(rows[2]['valid'])
            self.assertEqual(rows[2]['tracks'],[])
            self.assertTrue(all(t['measurement']is None for t in rows[2]['ended_tracks']))
            self.assertTrue(old_ids.isdisjoint({t['track_id']for t in rows[3]['tracks']}))
            self.assertTrue(any(t['measurement_valid']for t in rows[4]['tracks']))
            meta=json.loads((output/'metadata.json').read_text())
            self.assertEqual(meta['association']['confirmation_frames'],2)
            self.assertFalse(meta['calibrated'])
            self.assertTrue((output/'preview.png').is_file())
            with np.load(output/'cfar.npz')as a,np.load(baseline/'cfar.npz')as b:
                np.testing.assert_array_equal(a['accepted'],b['accepted'])
                np.testing.assert_allclose(a['threshold_power'],b['threshold_power'],equal_nan=True)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main(['range-doppler',str(recording),'--associate']),2)


if __name__=='__main__':unittest.main()
