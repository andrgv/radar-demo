from copy import deepcopy
import unittest

from radar_min.motion_range import MotionRangePolicy


def reading(sequence, observations=(), baseline=None):
    tracks=[];candidates=[]
    for track_id,frequency,value in observations:
        peak=dict(cycles_per_saved_block=frequency,range_bin=2)
        tracks.append(dict(track_id=track_id,state='measured',confirmed=True,measurement_valid=True,
                           measurement=peak,last_peak_sequence=sequence))
        candidates.append(dict(rd_track_id=track_id,rd_fine_range=dict(range_m=value,reason='fine_peak_at_group_boundary' if value is None else 'fine_peak_uncalibrated')))
    power=[1.]*33;power[2]=100.
    return dict(frame_sequence=sequence,valid=True,association=dict(tracks=tracks),
                one_d=dict(power=power,threshold_power=[2.]*33),
                results=dict(frame_sequence=sequence,candidates=candidates,
                             primary=dict(experimental_range_m=baseline) if baseline is not None else None))


class MotionRangeTests(unittest.TestCase):
    def test_motion_stop_and_miss_never_hold_or_substitute(self):
        p=MotionRangePolicy(motion_confirmation_frames=1)
        a=p.update(reading(1,[(7,-.0625,.8)],baseline=2))
        self.assertEqual(a['experimental_range_m'],.8)
        b=p.update(reading(2,[(7,0,.9)],baseline=2))
        self.assertEqual(b['source'],'RD stopped');self.assertEqual(b['experimental_range_m'],.9)
        missed=reading(3,[(7,0,.9)],baseline=2)
        missed['association']['tracks'][0].update(state='missed',measurement_valid=False)
        self.assertIsNone(p.update(missed)['experimental_range_m'])
        self.assertIsNone(p.update(reading(4,[],baseline=2))['experimental_range_m'])
        self.assertEqual(p.update(reading(5,[(8,0,.3)],baseline=2))['source'],'frozen 1D baseline')

    def test_multiple_movers_and_competitor_to_locked_feature_withhold(self):
        p=MotionRangePolicy(motion_confirmation_frames=1)
        self.assertEqual(p.update(reading(1,[(1,.1,.8),(2,-.1,1.2)]))['state'],'ambiguous')
        p.update(reading(2,[(1,.1,.8)]))
        r=p.update(reading(3,[(1,0,.8),(2,.1,1.2)]))
        self.assertEqual(r['track_id'],1);self.assertIsNone(r['experimental_range_m'])

    def test_stationary_nuisance_cannot_seed_motion_episode(self):
        p=MotionRangePolicy()
        for seq in range(1,20):
            r=p.update(reading(seq,[(1,0,.3)]))
            self.assertIsNone(r['experimental_range_m']);self.assertIsNone(p.track_id)

    def test_invalid_stale_and_unresolved_refinement(self):
        p=MotionRangePolicy(motion_confirmation_frames=1)
        r=p.update(reading(1,[(1,.1,None)]))
        self.assertEqual(r['reason'],'fine_peak_at_group_boundary')
        stale=reading(2,[(1,.1,.8)]);stale['association']['tracks'][0]['last_peak_sequence']=1
        self.assertIsNone(p.update(stale)['experimental_range_m'])
        r=p.update(dict(valid=False,reason='serial_backlog',frame_sequence=3))
        self.assertEqual(r['state'],'invalid');self.assertIsNone(p.track_id)
        mismatch=reading(4,[(1,.1,.8)]);mismatch['results']['frame_sequence']=3
        self.assertEqual(p.update(mismatch)['reason'],'mismatched_result_sequence')
        self.assertIsNone(p.update(reading(5,[(1,0,.8)]))['experimental_range_m'])

    def test_default_requires_two_consecutive_same_sign_motion_measurements(self):
        p=MotionRangePolicy()
        self.assertEqual(p.update(reading(1,[(1,.1,.8)]))['state'],'confirming')
        self.assertIsNone(p.update(reading(2,[(1,0,.8)]))['experimental_range_m'])
        self.assertEqual(p.update(reading(3,[(1,.1,.8)]))['state'],'confirming')
        self.assertEqual(p.update(reading(4,[(1,-.1,.8)]))['state'],'confirming')
        self.assertEqual(p.update(reading(5,[(1,-.1,.8)]))['source'],'RD motion')

    def test_stopped_scene_handoff_without_range_support_is_inspection_only(self):
        p=MotionRangePolicy(motion_confirmation_frames=1)
        p.update(reading(1,[(1,.1,.8)]))
        empty=reading(2,[(1,0,.3)])
        empty['one_d']['power']=[1.]*33
        result=p.update(empty)
        self.assertIsNone(result['experimental_range_m'])
        self.assertEqual(result['inspection_range_m'],.3)
        self.assertEqual(result['reason'],'stopped_rd_without_current_range_support')
        self.assertEqual(p.update(reading(3,[(1,0,.8)]))['source'],'RD stopped')

    def test_stopped_support_rejects_flank_even_when_above_threshold(self):
        p=MotionRangePolicy(motion_confirmation_frames=1)
        p.update(reading(1,[(1,.1,.8)]))
        flank=reading(2,[(1,0,.8)])
        flank['one_d']['power'][3]=200
        self.assertIsNone(p.update(flank)['experimental_range_m'])


if __name__=='__main__':unittest.main()
