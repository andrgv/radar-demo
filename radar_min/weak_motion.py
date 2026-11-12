"""Inspection-only continuation of an unbroken motion-seeded weak scene feature."""


METADATA=dict(method='motion-seeded-weak-stop-link-v1',motion_confirmation_frames=2,
    max_range_difference_bins=.5,
    scope='Supplement only: same current confirmed RD feature after two same-sign measured motion frames; stopped OS/raw-peak support must identify its current peak',
    clearing='Invalid input, sequence gaps, missing/ambiguous/lost measurements, competitors or unsupported stops revoke the seed; stationary support cannot reseed',
    interpretation='Current RD fine inspection, no held/predicted range, primary eligibility or certified physical identity')


def weak_candidate_stage(reading):
    """Describe current association disposition without changing its decision."""
    weak=reading.get('clutter_comparison',{}).get('weak_selection')or{}
    if weak.get('experimental_range_m')is None:return None
    observations=[o for o in reading.get('association',{}).get('observations',[])if o['range_bin']==weak['rd_range_bin']and
                  o['cycles_per_saved_block']==weak['rd_cycles_per_saved_block']]
    if len(observations)!=1:return 'no_unique_current_rd_observation'
    observation=observations[0]
    if observation.get('disposition')=='below_birth_margin':return 'below_rd_birth_margin'
    track=next((t for t in reading['association']['tracks']if t['track_id']==observation.get('track_id')),None)
    if not track or not track['confirmed']or not track['measurement_valid']:return 'no_confirmed_current_track'
    rows=[r for r in reading['results']['candidates']if r.get('rd_track_id')==track['track_id']]
    fine=rows[0].get('rd_fine_range')if len(rows)==1 else None
    if not fine or fine.get('range_m')is None:return 'rd_refinement_'+(fine['reason']if fine else'absent')
    if not track['has_nonzero_peak_history']:return 'refined_static_feature_without_motion_history'
    return 'refined_feature_with_nonzero_peak_history'


class WeakMotionLink:
    def __init__(self,config):
        self.config=config;self.clear()

    def clear(self):
        self.track_id=None;self.pending_id=None;self.pending_sign=None
        self.pending_count=0;self.last_sequence=None

    def update(self,reading):
        seq=reading.get('frame_sequence')
        out=dict(frame_sequence=seq,experimental_range_m=None,source=None,track_id=self.track_id,
            state='unseeded',reason='no_current_motion_seed',weak_rd_stage=None,
            inspection_only=True,primary_eligible=False,predicted=False)
        reference=reading.get('motion_result',{})
        if not reading.get('valid')or reading.get('results',{}).get('frame_sequence')!=seq or reference.get('frame_sequence')!=seq:
            self.clear();out.update(track_id=None,state='invalid',reason='invalid_or_mismatched_current_results');return out
        out['weak_rd_stage']=weak_candidate_stage(reading)
        gap=self.last_sequence is not None and seq!=self.last_sequence+1
        if gap:self.clear()
        self.last_sequence=seq
        def current(t):
            return (t['state']=='measured'and t.get('confirmed',False)and t['measurement_valid']and
                    t.get('measurement')is not None and t.get('last_peak_sequence')==seq)
        tracks=reading.get('association',{}).get('tracks',[])
        moving=[t for t in tracks if current(t)and t['measurement']['cycles_per_saved_block']!=0]
        def fine_for(t):
            rows=[r for r in reading['results']['candidates']if r.get('rd_track_id')==t['track_id']and r.get('rd_confirmed')]
            return rows[0].get('rd_fine_range')if len(rows)==1 else None
        if self.track_id is None:
            if len(moving)!=1:
                self.pending_id=None;self.pending_count=0;self.pending_sign=None
                out.update(track_id=None,reason='motion_reseed_required_after_gap'if gap else
                    'multiple_current_movers'if len(moving)>1 else'no_current_motion_seed')
                return out
            track=moving[0];fine=fine_for(track)
            if not fine or fine.get('range_m')is None:
                self.pending_id=None;self.pending_count=0
                out.update(track_id=None,reason='motion_seed_has_no_current_refinement');return out
            sign=1 if track['measurement']['cycles_per_saved_block']>0 else-1
            self.pending_count=self.pending_count+1 if self.pending_id==track['track_id']and self.pending_sign==sign else 1
            self.pending_id=track['track_id'];self.pending_sign=sign
            out['motion_confirmation_hits']=self.pending_count
            if self.pending_count<2 or reference.get('source')!='RD motion'or reference.get('track_id')!=track['track_id']:
                out.update(track_id=None,state='confirming',reason='confirming_current_motion_and_reference_episode');return out
            self.track_id=track['track_id']
        out['track_id']=self.track_id
        def revoke(reason):
            ended=self.track_id;self.clear();self.last_sequence=seq
            out.update(track_id=None,ended_track_id=ended,state='cleared',reason=reason)
            return out
        track=next((t for t in tracks if t['track_id']==self.track_id),None)
        if track is None or not current(track):return revoke('motion_identity_lost_missing_or_ambiguous')
        if any(t['track_id']!=self.track_id for t in moving):return revoke('competing_current_mover')
        fine=fine_for(track)
        if not fine or fine.get('range_m')is None:return revoke('current_rd_refinement_unresolved')
        if reference.get('track_id')!=self.track_id:return revoke('reference_motion_episode_changed')
        peak=track['measurement']
        if peak['cycles_per_saved_block']!=0:
            if reference.get('source')!='RD motion':return revoke('reference_motion_not_current')
            out.update(state='armed',reason='same_feature_current_motion_already_supported');return out
        if reference.get('source')=='RD stopped'and reference.get('experimental_range_m')is not None:
            out.update(state='strong_stop',reason='same_feature_stop_already_supported');return out
        comparison=reading.get('clutter_comparison',{});weak=comparison.get('weak_selection')or{}
        os=comparison.get('os')or{};phase=comparison.get('weak_phase_fit')or{}
        if not weak.get('shape_supported')or weak.get('experimental_range_m')is None:
            return revoke('weak_stop_has_no_current_shape_support')
        if os.get('frame_sequence')!=seq or phase.get('frame_sequence')!=seq or not os.get('target_detected'):
            return revoke('weak_stop_support_is_stale_or_unconfirmed')
        if (weak.get('rd_range_bin')!=peak['range_bin']or
            weak.get('rd_cycles_per_saved_block')!=peak['cycles_per_saved_block']or
            peak['range_bin']not in os.get('selected_group_bins',[])):
            return revoke('weak_peak_is_not_the_seeded_current_feature')
        if abs(fine['range_m']-weak['experimental_range_m'])>METADATA['max_range_difference_bins']*self.config.spacing_m:
            return revoke('weak_os_and_current_rd_ranges_disagree')
        out.update(experimental_range_m=fine['range_m'],source='RD weak stopped',state='weak_stopped',
            reason='same_motion_seeded_feature_with_current_weak_stop_support',
            phase_model_accepted=weak['phase_model_accepted'],phase_model_reason=weak.get('phase_model_reason'))
        return out
