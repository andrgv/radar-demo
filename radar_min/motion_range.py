"""Experimental measured-only distance policy for a unique moving RD feature."""


class MotionRangePolicy:
    def __init__(self, motion_confirmation_frames=2, stationary_support_required=True):
        if type(motion_confirmation_frames) is not int or motion_confirmation_frames<1:
            raise ValueError('Motion confirmation must be a positive frame count')
        self.motion_confirmation_frames=motion_confirmation_frames
        self.stationary_support_required=stationary_support_required
        self.clear()

    def clear(self):
        self.track_id = None
        self.pending_id=None
        self.pending_sequence=None
        self.pending_sign=None
        self.pending_count=0

    def update(self, reading):
        result = dict(frame_sequence=reading.get('frame_sequence'), experimental_range_m=None,
                      source=None, track_id=self.track_id, state='unresolved', reason=None,
                      predicted=False)
        if not reading.get('valid',False):
            self.clear()
            result.update(state='invalid',reason=reading.get('reason','invalid_frame'),track_id=None)
            return result
        sequence = reading['frame_sequence']
        if reading.get('results',{}).get('frame_sequence')!=sequence:
            self.clear();result.update(state='invalid',reason='mismatched_result_sequence',track_id=None)
            return result
        tracks = reading['association']['tracks']
        def current(t):
            return (t['state']=='measured' and t.get('confirmed',False) and t['measurement_valid'] and
                    t.get('measurement') is not None and t['last_peak_sequence']==sequence)
        moving = [t for t in tracks if current(t) and t['measurement']['cycles_per_saved_block']!=0]
        result['current_moving_track_ids'] = [t['track_id'] for t in moving]
        if self.track_id is None:
            if len(moving)>1:
                self.pending_count=0
                result.update(state='ambiguous',reason='multiple_current_moving_features')
                return result
            if len(moving)==1:
                candidate=moving[0]
                sign=1 if candidate['measurement']['cycles_per_saved_block']>0 else -1
                continuing=(self.pending_id==candidate['track_id'] and self.pending_sequence==sequence-1 and self.pending_sign==sign)
                self.pending_count=self.pending_count+1 if continuing else 1
                self.pending_id=candidate['track_id'];self.pending_sequence=sequence;self.pending_sign=sign
                result['motion_confirmation_hits']=self.pending_count
                if self.pending_count<self.motion_confirmation_frames:
                    result.update(state='confirming',reason='confirming_same_feature_nonzero_doppler')
                    return result
                self.track_id=moving[0]['track_id']
            else:
                self.pending_count=0
                self.pending_id=None
                primary=reading.get('results',{}).get('primary')
                result.update(state='baseline' if primary else 'unresolved',
                              reason='no_motion_episode_baseline' if primary else 'no_motion_episode_no_baseline')
                if primary:
                    result.update(experimental_range_m=primary['experimental_range_m'],source='frozen 1D baseline')
                return result
        result['track_id']=self.track_id
        track=next((t for t in tracks if t['track_id']==self.track_id),None)
        if track is None:
            ended=self.track_id;self.clear()
            result.update(state='lost',track_id=ended,reason='motion_feature_lost_no_substitution')
            return result
        if any(t['track_id']!=self.track_id for t in moving):
            result.update(state='ambiguous',reason='competing_current_moving_feature')
            return result
        if not current(track):
            result.update(state=track['state'] if track['state']!='measured' else 'unresolved',
                          reason='motion_feature_'+track['state'] if track['state']!='measured' else 'no_current_confirmed_measurement')
            return result
        candidate=next((r for r in reading['results']['candidates'] if r.get('rd_track_id')==self.track_id),None)
        fine=candidate.get('rd_fine_range') if candidate else None
        if not fine or fine.get('range_m') is None:
            result.update(reason=fine['reason'] if fine else 'no_current_rd_refinement')
            return result
        stopped=track['measurement']['cycles_per_saved_block']==0
        if stopped and self.stationary_support_required:
            baseline=reading.get('one_d',{})
            power=baseline.get('power',[]);threshold=baseline.get('threshold_power',[])
            k=track['measurement']['range_bin']
            # Use full current CA profile, even outside the scalar search mask.
            # No persistence/held baseline or new distance-specific exclusion.
            supported=(1<=k<len(power)-1 and k<len(threshold) and threshold[k] is not None
                       and power[k]>threshold[k] and
                       power[k]>=max(power[max(1,k-1):min(len(power)-1,k+2)]))
            if not supported:
                result.update(state='unverified_stationary',reason='stopped_rd_without_current_range_support',
                              inspection_range_m=fine['range_m'])
                return result
        result.update(state='measured',source='RD stopped' if stopped else 'RD motion',
                      experimental_range_m=fine['range_m'],
                      reason='same_feature_current_zero_doppler' if stopped else 'unique_current_motion_measurement')
        return result
