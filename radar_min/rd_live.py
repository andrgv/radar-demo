"""Live adapter for the same RD/CFAR/association algorithms used by replay."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import time

import numpy as np

from .cfar_2d import CaCfar2D, Cfar2DConfig
from .range_doppler import RangeDoppler
from .rd_association import AssociationConfig, CandidateAssociator
from .cfar import CfarConfig, CfarDetector
from .joint_results import ResultBank
from .cfar_os import OsCfarDetector, select_os_candidate
from .motion_range import MotionRangePolicy
from .rx_diagnostics import METADATA as RX_METADATA
from .phase_range import CandidatePhaseRange
from .weak_candidate import METADATA as WEAK_METADATA,select_weak_candidate
from .weak_motion import WeakMotionLink,METADATA as WEAK_MOTION_METADATA
from .weak_features import WeakFeatureConfirmer


@dataclass(frozen=True)
class RDView:
    sequence: int
    full_power: np.ndarray
    threshold_power: np.ndarray
    accepted: np.ndarray


def current_measurement(track, sequence):
    return (track['state']=='measured'and track['confirmed']and track['measurement_valid']
            and track['measurement']is not None and track['last_peak_sequence']==sequence)


def feature_table_rows(reading, config, fresh=True):
    """Only a fresh confirmed measurement gets distance/frequency columns."""
    if not fresh or not reading.get('valid',False) or not reading.get('association',{}).get('valid',False):return []
    rows = []
    names = dict(measured='Measured peak',tentative='Confirming',ambiguous='Ambiguous support',missed='Missing')
    for track in reading.get('association',{}).get('tracks',[]):
        measured = current_measurement(track,reading['frame_sequence'])
        peak = track['measurement'] if measured else None
        support = sorted({r for _,r in track['current_support_cells']})
        support_text = ', '.join(map(str,support)) if len(support)<=6 else f'{support[0]}–{support[-1]}'
        if measured:support_text = 'Current peak'
        elif track['state']=='tentative':support_text = 'Unconfirmed peak'
        row = [str(track['track_id']),names.get(track['state'],track['state']),
            f'~{peak["range_bin"]*config.spacing_m:.2f}' if peak else '—',
            str(peak['range_bin']) if peak else '—',
            f'{peak["cycles_per_saved_block"]:+.4f}' if peak else '—',
            f'{peak["margin_db"]:+.1f}' if peak else '—',
            support_text or '—',str(track['frames_since_peak'])]
        rows.append((track['state'],row))
    return rows


def settings_from_args(args):
    return (Cfar2DConfig(args.rd_guard_range,args.rd_guard_doppler,
                args.rd_training_range,args.rd_training_doppler,args.rd_min_training,
                args.rd_factor,args.rd_doppler_edge),
            AssociationConfig(args.track_confirmation,args.track_birth_margin,
                args.track_range_gate,args.track_doppler_gate,args.track_max_missed,
                args.track_max_ambiguous,args.track_ambiguity_gap,getattr(args,'track_range_metric','native')))


class LiveRangeDoppler:
    baseline = None

    def __init__(self, config, cfar_settings=None, association_settings=None, one_d_settings=None, experimental_os=False, experimental_weak=False):
        self.config = config
        self.rd = RangeDoppler(config)
        self.cfar = CaCfar2D((self.rd.count,config.samples//2+1),cfar_settings or Cfar2DConfig())
        self.associator = CandidateAssociator(config,association_settings or AssociationConfig(),self.cfar.settings.doppler_edge)
        self.one_d = CfarDetector(config, one_d_settings or CfarConfig(1,4,4,2))
        self.os_comparison = OsCfarDetector(config,self.one_d.settings) if experimental_os or experimental_weak else None
        self.weak_phase=CandidatePhaseRange(config)if experimental_weak else None
        self.weak_motion=WeakMotionLink(config)if experimental_weak else None
        self.weak_features=WeakFeatureConfirmer(config,self.associator.settings,self.cfar.settings.doppler_edge)if experimental_weak else None
        self.bank = ResultBank(config, self.cfar.settings.doppler_edge)
        self.motion_policy = MotionRangePolicy()
        self.snapshot = None
        self.metadata = dict(algorithm='joint-range-cfar-rd-v1',
            cfar=asdict(self.cfar.settings),association=asdict(self.associator.settings),
            one_d_cfar=asdict(self.one_d.settings),
            source_sha256={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('rd_live.py','range_doppler.py','cfar_2d.py','rd_association.py','core.py',
                             'cfar.py','cfar_range.py','joint_results.py','cfar_os.py','motion_range.py','rx_diagnostics.py',
                             'phase_range.py','weak_candidate.py','weak_motion.py','weak_features.py')},
            measurement='Confirmed current CFAR local maxima only; native bins; no held or predicted distance',
            input='Full RD power; zero Doppler retained; no empty/background subtraction',
            nominal_distance='Native range bin × nominal spacing; no fine interpolation or distance calibration',
            identity='Radar feature hypotheses, not certified object identities or obstacle decisions',
            freshness='Live stream continuity, host clock, backlog and timeout gates clear all hypotheses')
        self.metadata.update(primary_policy='Exact frozen 1D baseline; no automatic RD-only promotion',
            refinement='Current dense range FFT then slow-time Hann FFT; three Doppler rows; native half-bin range support; competing nearby peaks withheld',
            evidence='1D and RD share ADC data; source agreement is not independent confirmation',
            nominal_distance='Native RD bin centers retained beside experimental uncalibrated refinements')
        self.metadata['experimental_os'] = self.os_comparison.metadata if self.os_comparison else None
        self.metadata['motion_policy']='v2: two consecutive same-sign confirmed RD motion measurements; stopped continuation requires current CA threshold and local-peak support; no held/predicted range'
        self.metadata['motion_policy_settings']=dict(motion_confirmation_frames=2,stationary_support_required=True)
        self.metadata['receiver_diagnostics']=dict(RX_METADATA)
        self.metadata['experimental_weak_candidate']=dict(WEAK_METADATA,phase_estimator=self.weak_phase.metadata)if self.weak_phase else None
        self.metadata['experimental_weak_motion_link']=dict(WEAK_MOTION_METADATA)if self.weak_motion else None
        self.metadata['experimental_weak_feature_confirmation']=self.weak_features.metadata if self.weak_features else None

    def _reading(self, frame, association, reason, clusters=(), processing_ms=0):
        tracks = association['tracks']
        return dict(algorithm=self.metadata['algorithm'],frame_sequence=frame.sequence,
            timestamp_us=frame.timestamp_us,valid=association['valid'],reason=reason,
            target_detected=False,range_bin=None,range_m=None,calibrated=False,
            timing_verified=False,association=association,cfar_clusters=list(clusters),
            measured_features=sum(t['measurement_valid']for t in tracks),
            tentative_features=sum(t['state']=='tentative'for t in tracks),
            ambiguous_features=sum(t['state']=='ambiguous'for t in tracks),
            missed_features=sum(t['state']=='missed'for t in tracks),processing_ms=processing_ms)

    def update(self, frame):
        start = time.perf_counter()
        full, _, info = self.rd.update(frame)
        if not info['valid']:
            self.one_d.guard.check(frame)
            self.one_d.clear();self.bank.clear()
            if self.os_comparison:
                self.os_comparison.guard.check(frame);self.os_comparison.clear()
            self.snapshot = None
            association = self.associator.update(frame,None,None,None,[],valid=False,reason=info['reason'])
            reading=self._reading(frame,association,association['reason'],processing_ms=(time.perf_counter()-start)*1000)
            reading['motion_result']=self.motion_policy.update(reading)
            if self.weak_motion:reading['weak_motion_result']=self.weak_motion.update(reading)
            if self.weak_features:reading['weak_feature_result']=self.weak_features.update(reading)
            return reading
        _, threshold, accepted, clusters = self.cfar.detect(full)
        association = self.associator.update(frame,full,threshold,accepted,clusters)
        baseline = self.one_d.update(frame)
        result = self.bank.update(frame,baseline,association,clusters)
        if association['valid']:
            for array in (full,threshold,accepted):array.setflags(write=False)
            self.snapshot = RDView(frame.sequence,full,threshold,accepted)
        else:self.snapshot = None
        reading = self._reading(frame,association,association['reason'],clusters,(time.perf_counter()-start)*1000)
        reading.update(one_d=baseline, results=result, target_detected=baseline['target_detected'],
                       experimental_range_m=baseline['experimental_range_m'],receiver_diagnostics=self.bank.receiver_diagnostics)
        if self.os_comparison:
            comparison=self.os_comparison.update(frame)
            reading['clutter_comparison']=dict(os=comparison,selection=select_os_candidate(comparison,clusters))
            if self.weak_phase:
                phase=None
                if reading['clutter_comparison']['selection']['experimental_range_m']is not None:
                    phase=dict(frame_sequence=frame.sequence,**self.weak_phase.fit(frame,comparison['selected_group_bins']))
                reading['clutter_comparison'].update(weak_phase_fit=phase,
                    weak_selection=select_weak_candidate(comparison,clusters,phase,self.config))
            reading['processing_ms']=(time.perf_counter()-start)*1000
        reading['motion_result']=self.motion_policy.update(reading)
        if self.weak_motion:
            reading['weak_motion_result']=self.weak_motion.update(reading)
            reading['weak_feature_result']=self.weak_features.update(reading)
            reading['processing_ms']=(time.perf_counter()-start)*1000
        return reading

    def reject_frame(self, frame, reason):
        """Advance both continuity guards, clear identities, and publish no map."""
        self.rd.guard.check(frame)
        self.one_d.guard.check(frame)
        self.one_d.clear();self.bank.clear()
        if self.os_comparison:
            self.os_comparison.guard.check(frame);self.os_comparison.clear()
        association = self.associator.update(frame,None,None,None,[],valid=False,reason=reason)
        self.snapshot = None
        reading=self._reading(frame,association,association['reason'])
        reading['motion_result']=self.motion_policy.update(reading)
        if self.weak_motion:reading['weak_motion_result']=self.weak_motion.update(reading)
        if self.weak_features:reading['weak_feature_result']=self.weak_features.update(reading)
        return reading

    def clear(self):
        self.associator.clear('stream_cleared')
        self.one_d.clear();self.bank.clear()
        self.motion_policy.clear()
        if self.weak_motion:self.weak_motion.clear()
        if self.weak_features:self.weak_features.clear()
        if self.os_comparison:self.os_comparison.clear()
        self.snapshot = None
