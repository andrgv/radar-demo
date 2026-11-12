"""Conservative association of CFAR radar features, with no predicted measurements.

Local maxima seed tracks after quality/persistence checks. Current accepted
cells can explain a bounded ambiguous interval, but cannot create/confirm a
track or move its anchor. Native coordinates are not calibrated object ranges.
"""
from dataclasses import dataclass

import numpy as np

from .core import Continuity


@dataclass(frozen=True)
class AssociationConfig:
    confirmation_frames: int = 3
    birth_margin_db: float = 3.0
    range_gate: int = 1
    doppler_gate: int = 2
    max_missed_frames: int = 2
    max_ambiguous_frames: int = 5
    ambiguity_gap: float = .25
    range_metric: str = 'native'

    def __post_init__(self):
        if self.range_metric not in ('native','quadratic'):
            raise ValueError('Association range metric must be native or quadratic')
        for key in ('confirmation_frames','range_gate','doppler_gate','max_missed_frames','max_ambiguous_frames'):
            if type(getattr(self,key)) is not int or getattr(self,key) < 0:
                raise ValueError('Association counts/gates must be nonnegative integers')
        if self.confirmation_frames < 1:
            raise ValueError('Association confirmation must be positive')
        for key in ('birth_margin_db','ambiguity_gap'):
            if not np.isfinite(getattr(self,key)) or getattr(self,key) < 0:
                raise ValueError('Association margins must be finite and nonnegative')


@dataclass
class _Track:
    track_id: int
    anchor: tuple
    born_sequence: int
    last_peak_sequence: int
    age_frames: int = 1
    consecutive_hits: int = 1
    peak_hits: int = 1
    frames_since_peak: int = 0
    confirmed: bool = False
    has_nonzero_peak_history: bool = False
    range_coordinate: float | None = None


class CandidateAssociator:
    def __init__(self, config, settings=None, doppler_edge='wrap'):
        self.config = config
        self.settings = settings or AssociationConfig()
        self.shape = (config.chirps-config.discard_chirps, config.samples//2+1)
        if doppler_edge not in ('wrap','truncate'):
            raise ValueError('Association Doppler edge must be wrap or truncate')
        if self.settings.doppler_gate >= self.shape[0]/2 or self.settings.range_gate >= self.shape[1]-1:
            raise ValueError('Association gates are too wide for this grid')
        self.doppler_edge = doppler_edge
        self.frequencies = np.fft.fftshift(np.fft.fftfreq(self.shape[0]))
        self.guard = Continuity(config)
        self.tracks = []
        self.next_id = 1

    def _distance(self, a, b):
        dd = abs(a[0]-b[0])
        if self.doppler_edge == 'wrap':
            dd = min(dd,self.shape[0]-dd)
        return dd, abs(a[1]-b[1])

    def _cost(self, a, b):
        dd, dr = self._distance(a,b)
        c = self.settings
        return dr/max(1,c.range_gate)+dd/max(1,c.doppler_gate) if dr<=c.range_gate and dd<=c.doppler_gate else np.inf

    def _record(self, track, state, reason, *, observation=None, support=()):
        measured = state == 'measured'
        return dict(track_id=track.track_id,state=state,reason=reason,confirmed=track.confirmed,
            measurement_valid=measured,measurement=dict(observation) if measured else None,
            current_peak=dict(observation) if observation is not None else None,
            current_support_cells=[list(cell) for cell in support],
            born_sequence=track.born_sequence,age_frames=track.age_frames,peak_hits=track.peak_hits,consecutive_peak_hits=track.consecutive_hits,
            frames_since_peak=track.frames_since_peak,last_peak_sequence=track.last_peak_sequence,
            has_nonzero_peak_history=track.has_nonzero_peak_history,
            doppler_evidence=('zero_doppler' if observation['doppler_bin']==self.shape[0]//2 else 'nonzero_doppler')
                if measured else None)

    def clear(self, reason='external_reset'):
        """End active hypotheses without recycling IDs or inventing a frame."""
        ended = [self._record(t,'lost',reason) for t in self.tracks]
        self.tracks = []
        return ended

    def _reset(self, frame, reason):
        ended = self.clear(reason)
        return dict(sequence=frame.sequence,timestamp_us=frame.timestamp_us,valid=False,reason=reason,
                    tracks=[],ended_tracks=ended,observations=[])

    def update(self, frame, power, threshold, accepted, clusters, *, valid=True, reason=None):
        continuity = self.guard.check(frame)
        if continuity or not valid or not frame.flags & 1:
            return self._reset(frame,continuity or reason or 'invalid_frame')
        if frame.profile_id!=self.config.profile_id or frame.adc.shape!=(self.config.chirps,self.config.samples,3):
            return self._reset(frame,'frame_config_mismatch')
        p, th, mask = np.asarray(power),np.asarray(threshold),np.asarray(accepted,dtype=bool)
        if (p.shape!=self.shape or th.shape!=self.shape or mask.shape!=self.shape or
                not np.isfinite(p).all() or np.any(p<0) or
                np.any(mask & (~np.isfinite(th) | (th<=0) | (p<=th))) or
                np.any(mask[:,(0,self.shape[1]-1)])):
            return self._reset(frame,'invalid_association_map')
        observations = []
        seen = set()
        for group in clusters:
            for peak in group['local_maxima']:
                cell = (peak['doppler_bin'],peak['range_bin'])
                if (not 0<=cell[0]<self.shape[0] or not 1<=cell[1]<self.shape[1]-1 or
                        not mask[cell] or cell in seen):
                    return self._reset(frame,'invalid_association_candidates')
                seen.add(cell)
                observations.append(dict(doppler_bin=int(cell[0]),range_bin=int(cell[1]),
                    cycles_per_saved_block=float(self.frequencies[cell[0]]),power=float(p[cell]),
                    threshold_power=float(th[cell]),margin_db=float(10*np.log10(p[cell]/th[cell])),
                    cluster_id=int(group['cluster_id']),cluster_local_maxima=len(group['local_maxima'])))
                if self.settings.range_metric=='quadratic':
                    # Association coordinate only, not an exported physical range.
                    r=cell[1];delta=0.
                    if 1<r<self.shape[1]-2:
                        y=np.log(np.maximum(p[cell[0],r-1:r+2],1e-12))
                        curvature=y[0]-2*y[1]+y[2]
                        if curvature<0:delta=float(np.clip(.5*(y[0]-y[2])/curvature,-.5,.5))
                    observations[-1]['range_coordinate']=r+delta
        observations.sort(key=lambda o:(o['doppler_bin'],o['range_bin']))
        old_tracks = self.tracks
        cost = np.full((len(old_tracks),len(observations)),np.inf)
        for i,track in enumerate(old_tracks):
            for j,obs in enumerate(observations):
                cost[i,j] = self._cost(track.anchor,(obs['doppler_bin'],obs['range_bin']))
                if self.settings.range_metric=='quadratic' and np.isfinite(cost[i,j]):
                    dd,_=self._distance(track.anchor,(obs['doppler_bin'],obs['range_bin']))
                    coordinate=track.range_coordinate if track.range_coordinate is not None else track.anchor[1]
                    cost[i,j]=abs(coordinate-obs['range_coordinate'])/max(1,self.settings.range_gate)+dd/max(1,self.settings.doppler_gate)

        def unique_best(values):
            order = np.argsort(values,kind='stable')
            if not len(order) or not np.isfinite(values[order[0]]):
                return None
            if len(order)>1 and values[order[1]]-values[order[0]]<=self.settings.ambiguity_gap:
                return None
            return int(order[0])

        row_best = [unique_best(row) for row in cost]
        col_best = [unique_best(cost[:,j]) for j in range(len(observations))]
        assignments = {i:j for i,j in enumerate(row_best) if j is not None and col_best[j]==i}
        assigned_observations = set(assignments.values())
        active, ended, records = [], [], []
        accepted_cells = [tuple(int(x) for x in cell) for cell in np.argwhere(mask)]
        for i,track in enumerate(old_tracks):
            track.age_frames += 1
            track.frames_since_peak += 1
            if i in assignments:
                j = assignments[i]
                obs = observations[j]
                obs['track_id'] = track.track_id
                obs['disposition'] = 'associated_peak'
                if not track.confirmed and obs['margin_db']<self.settings.birth_margin_db:
                    obs['disposition'] = 'confirmation_quality_interrupted'
                    track.consecutive_hits = 0
                    ended.append(self._record(track,'lost','confirmation_quality_interrupted',observation=obs))
                    continue
                track.anchor = (obs['doppler_bin'],obs['range_bin'])
                track.range_coordinate=obs.get('range_coordinate')
                track.last_peak_sequence = frame.sequence
                track.frames_since_peak = 0
                track.peak_hits += 1
                track.consecutive_hits += 1
                track.confirmed |= track.consecutive_hits>=self.settings.confirmation_frames
                track.has_nonzero_peak_history |= obs['doppler_bin']!=self.shape[0]//2
                state = 'measured' if track.confirmed else 'tentative'
                records.append(self._record(track,state,'unique_current_peak',observation=obs))
                active.append(track)
                continue
            track.consecutive_hits = 0
            support = [cell for cell in accepted_cells if np.isfinite(self._cost(track.anchor,cell))]
            competition = bool(np.isfinite(cost[i]).any())
            if not track.confirmed:
                ended.append(self._record(track,'lost','confirmation_interrupted',support=support))
                continue
            if support or competition:
                if track.frames_since_peak>self.settings.max_ambiguous_frames:
                    ended.append(self._record(track,'lost','ambiguous_support_expired',support=support))
                    continue
                why = 'competing_peaks_or_tracks' if competition else 'accepted_cells_without_isolated_peak'
                records.append(self._record(track,'ambiguous',why,support=support))
            else:
                if track.frames_since_peak>self.settings.max_missed_frames:
                    ended.append(self._record(track,'lost','no_support_expired'))
                    continue
                records.append(self._record(track,'missed','no_current_support'))
            active.append(track)

        # Do not duplicate an unresolved hypothesis. Distinct peaks can seed
        # alongside successfully measured tracks, even inside their broad gates.
        unresolved_rows = [i for i in range(len(old_tracks)) if i not in assignments]
        current_assigned_cells = [(observations[j]['doppler_bin'],observations[j]['range_bin'])
                                  for j in assigned_observations]
        for j,obs in enumerate(observations):
            if j in assigned_observations:
                continue
            cell = (obs['doppler_bin'],obs['range_bin'])
            if any(np.isfinite(cost[i,j]) for i in unresolved_rows):
                obs['disposition'] = 'unresolved_track_gate'
            elif any(dd<=1 and dr<=1 for dd,dr in (self._distance(cell,other) for other in current_assigned_cells)):
                obs['disposition'] = 'overlaps_assigned_peak'
            elif obs['margin_db']<self.settings.birth_margin_db:
                obs['disposition'] = 'below_birth_margin'
            else:
                track = _Track(self.next_id,cell,frame.sequence,frame.sequence,
                    confirmed=self.settings.confirmation_frames==1,
                    has_nonzero_peak_history=cell[0]!=self.shape[0]//2,
                    range_coordinate=obs.get('range_coordinate'))
                self.next_id += 1
                obs['track_id'] = track.track_id
                obs['disposition'] = 'new_peak_hypothesis'
                state = 'measured' if track.confirmed else 'tentative'
                records.append(self._record(track,state,'new_peak',observation=obs))
                active.append(track)
        self.tracks = sorted(active,key=lambda t:t.track_id)
        return dict(sequence=frame.sequence,timestamp_us=frame.timestamp_us,valid=True,
            reason='radar_feature_association_only',tracks=sorted(records,key=lambda t:t['track_id']),
            ended_tracks=ended,observations=observations)
