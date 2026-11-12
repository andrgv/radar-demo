"""Separate confirmation of current weak scene features, never physical objects."""
from dataclasses import asdict
import math

from .rd_association import AssociationConfig


class WeakFeatureConfirmer:
    """Confirm one uniquely supported weak peak using consecutive measurements.

    Strong RD births keep their original margin. This separate namespace uses
    the already gated OS/RD/raw-shape observation; it never updates strong
    tracks, detector masks, the result bank or a primary distance policy.
    """
    def __init__(self,config,settings=None,doppler_edge='wrap'):
        self.config=config;self.settings=settings or AssociationConfig()
        if doppler_edge not in('wrap','truncate'):raise ValueError('Invalid Doppler edge policy')
        self.doppler_edge=doppler_edge;self.count=config.chirps-config.discard_chirps
        self.next_id=1;self.clear()
        self.metadata=dict(method='consecutive-weak-scene-feature-v1',
            confirmation_frames=self.settings.confirmation_frames,range_gate=self.settings.range_gate,
            doppler_gate=self.settings.doppler_gate,doppler_edge=doppler_edge,
            original_association=asdict(self.settings),
            isolation_range_bins=1,isolation_doppler_bins=2,
            missed_or_ambiguous_retention_frames=0,
            evidence='Confirmed OS + unique current RD maximum + original raw-peak geometry, then consecutive native-gated current observations; original RD birth margin is unchanged',
            range_method='Existing current OS Hann FFT fine range, not a rejected phase estimate or Doppler-conditioned range',
            interpretation='Separate weak: IDs denote scene-feature hypotheses, not objects; no primary eligibility, holding or prediction; shared ADC evidence is not independent confirmation')

    def clear(self):
        self.feature_id=None;self.anchor=None;self.hits=0;self.last_sequence=None

    def _doppler_distance(self,a,b):
        delta=abs(a-b)
        return min(delta,self.count-delta)if self.doppler_edge=='wrap'else delta

    def update(self,reading):
        seq=reading.get('frame_sequence')
        out=dict(frame_sequence=seq,feature_id=None,state='absent',confirmed=False,confirmation_hits=0,
            candidate_range_m=None,experimental_range_m=None,measurement_sequence=None,
            strong_rd_track_id=None,reason='no_current_weak_support',inspection_only=True,
            primary_eligible=False,predicted=False,physical_identity='unverified')
        old=self.feature_id
        def stop(reason,state='absent'):
            self.clear();out.update(state=state,reason=reason)
            if old is not None:out['ended_feature_id']=old
            return out
        association=reading.get('association',{})
        if (not reading.get('valid')or not association.get('valid')or association.get('sequence')!=seq or
            reading.get('results',{}).get('frame_sequence')!=seq):return stop('invalid_or_mismatched_current_results','invalid')
        comparison=reading.get('clutter_comparison',{})
        weak=comparison.get('weak_selection')or{};os=comparison.get('os')or{};phase=comparison.get('weak_phase_fit')or{}
        value=weak.get('experimental_range_m')
        if value is None or not weak.get('shape_supported'):return stop('no_current_weak_support')
        if (not math.isfinite(value)or os.get('frame_sequence')!=seq or phase.get('frame_sequence')!=seq or
            not os.get('target_detected')):return stop('invalid_or_stale_weak_support','invalid')
        bins=os.get('selected_group_bins',[]);r=weak.get('rd_range_bin');frequency=weak.get('rd_cycles_per_saved_block')
        if (not bins or r not in bins or
            not ((min(bins)-.5)*self.config.spacing_m<value<(max(bins)+.5)*self.config.spacing_m)):
            return stop('weak_range_outside_current_support','invalid')
        observations=[o for o in association.get('observations',[])if o['range_bin']==r and o['cycles_per_saved_block']==frequency]
        if len(observations)!=1:return stop('no_unique_current_rd_observation','ambiguous')
        observation=observations[0];d=observation['doppler_bin']
        if observation.get('disposition')in('unresolved_track_gate','overlaps_assigned_peak'):
            return stop('strong_rd_association_ambiguous','ambiguous')
        if not(0<=d<self.count and 1<=r<self.config.samples//2 and
               math.isfinite(observation['power'])and math.isfinite(observation['threshold_power'])and
               observation['threshold_power']>0 and observation['power']>observation['threshold_power']):
            return stop('rd_observation_not_above_original_cfar','invalid')
        peaks=[p for cluster in reading.get('cfar_clusters',[])for p in cluster['local_maxima']]
        nearby=[p for p in peaks if abs(p['range_bin']-r)<=1 and self._doppler_distance(p['doppler_bin'],d)<=2]
        if len(nearby)!=1 or (nearby[0]['doppler_bin'],nearby[0]['range_bin'])!=(d,r):
            return stop('competing_current_rd_neighborhood','ambiguous')
        contiguous=self.last_sequence is not None and ((seq-self.last_sequence)&0xffffffff)==1
        gated=(self.anchor is not None and abs(self.anchor[1]-r)<=self.settings.range_gate and
               self._doppler_distance(self.anchor[0],d)<=self.settings.doppler_gate)
        if not(contiguous and gated):
            if old is not None:out['ended_feature_id']=old
            self.feature_id=f'weak:{self.next_id}';self.next_id+=1;self.hits=0
        self.hits+=1;self.anchor=(d,r);self.last_sequence=seq
        confirmed=self.hits>=self.settings.confirmation_frames
        out.update(feature_id=self.feature_id,state='confirmed'if confirmed else'confirming',confirmed=confirmed,
            confirmation_hits=self.hits,candidate_range_m=value,
            experimental_range_m=value if confirmed else None,measurement_sequence=seq if confirmed else None,
            strong_rd_track_id=observation.get('track_id'),
            reason='consecutive_current_weak_scene_feature'if confirmed else'confirming_current_weak_scene_feature',
            rd_range_bin=r,rd_doppler_bin=d,rd_cycles_per_saved_block=frequency,
            phase_model_accepted=weak['phase_model_accepted'],phase_model_reason=weak.get('phase_model_reason'))
        return out
