"""Inspectable range spectrum and conservative scene-change detector.

A detection means a sustained spectral change, never certified object identity.
Thresholds are engineering defaults, not calibrated false-alarm probabilities.
"""
from dataclasses import dataclass, asdict, fields
import hashlib
import json
from pathlib import Path
import numpy as np


@dataclass(frozen=True)
class Config:
    schema: int = 1
    profile_id: int = 0x33525801
    samples: int = 64
    chirps: int = 17
    sample_rate_hz: float = 5e6
    slope_hz_s: float = 33691406250000.0
    discard_chirps: int = 1
    frame_interval_s: float = 0.1
    min_bin: int = 1
    max_bin: int = 4
    min_excess_db: float = 3.0
    variability_multiplier: float = 6.0
    margin_db: float = 2.0
    confirmation_frames: int = 3

    def __post_init__(self):
        integers = ('schema','profile_id','samples','chirps','discard_chirps','min_bin','max_bin','confirmation_frames')
        if any(type(getattr(self,k)) is not int for k in integers):
            raise ValueError('Integer configuration fields required')
        if self.schema != 1 or not 0 <= self.profile_id <= 0xffffffff:
            raise ValueError('Unsupported schema/profile')
        if not (16 <= self.samples <= 2048 and 1 <= self.chirps <= 1024 and 0 <= self.discard_chirps < self.chirps):
            raise ValueError('Invalid acquisition shape')
        if not 1 <= self.min_bin <= self.max_bin < self.samples // 2 or self.confirmation_frames < 1:
            raise ValueError('Invalid bin mask/persistence')
        for key in ('sample_rate_hz','slope_hz_s','frame_interval_s','min_excess_db','variability_multiplier','margin_db'):
            if not np.isfinite(getattr(self,key)) or getattr(self,key) <= 0:
                raise ValueError(f'Invalid {key}')

    @property
    def spacing_m(self):
        return 299792458 * self.sample_rate_hz / (2 * self.slope_hz_s * self.samples)

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True).encode()).hexdigest()

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self),indent=2))

    @classmethod
    def load(cls, path):
        data=json.loads(Path(path).read_text())
        required={'profile_id','samples','chirps','sample_rate_hz','slope_hz_s'}
        if not required.issubset(data): raise ValueError('Missing acquisition configuration fields')
        # Legacy angle, gain, range scale/offset and verified flags confer no calibration.
        return cls(**{k:v for k,v in data.items() if k in {f.name for f in fields(cls)}})


def power(frame, config):
    if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps,config.samples,3):
        raise ValueError('frame_config_mismatch')
    x=np.asarray(frame.adc,dtype=float)[config.discard_chirps:]
    if not np.isfinite(x).all() or np.any((x<0)|(x>65535)):
        raise ValueError('invalid_adc')
    if np.any((x==0)|(x==65535)):
        raise ValueError('adc_container_rail')
    x=x-x.mean(axis=1,keepdims=True)
    w=np.hanning(config.samples)
    spectrum=np.fft.rfft(x*w[None,:,None],axis=1)*(2/w.sum())
    return np.mean(abs(spectrum)**2,axis=(0,2))


def db(p):
    return 10*np.log10(np.maximum(p,1e-12))


@dataclass
class Baseline:
    config: Config
    median_db: np.ndarray
    threshold_db: np.ndarray
    training_frames: int
    provenance: dict

    @classmethod
    def fit(cls, frames, config, provenance=None):
        frames=list(frames)
        if len(frames)<20:
            raise ValueError('At least 20 empty training frames required')
        guard=Continuity(config)
        for f in frames:
            reason=guard.check(f)
            if reason: raise ValueError('Invalid training stream: '+reason)
        spectra=np.array([db(power(f,config)) for f in frames])
        center=np.median(spectra,axis=0)
        sigma=1.4826*np.median(abs(spectra-center),axis=0)
        return cls(config,center,np.maximum(config.min_excess_db,config.variability_multiplier*sigma),len(frames),provenance or {})

    def save(self,path):
        with Path(path).open('x') as f:
            json.dump(dict(schema=1,config=asdict(self.config),fingerprint=self.config.fingerprint,
                median_db=self.median_db.tolist(),threshold_db=self.threshold_db.tolist(),
                training_frames=self.training_frames,provenance=self.provenance),f,indent=2)

    @classmethod
    def load(cls,path):
        d=json.loads(Path(path).read_text()); c=Config(**d['config'])
        if d['schema']!=1 or d['fingerprint']!=c.fingerprint: raise ValueError('Invalid baseline fingerprint')
        arrays=[np.array(d[k],dtype=float) for k in ('median_db','threshold_db')]
        if any(a.shape!=(c.samples//2+1,) or not np.isfinite(a).all() for a in arrays) or np.any(arrays[1]<c.min_excess_db) or d['training_frames']<20:
            raise ValueError('Invalid baseline arrays/count')
        return cls(c,*arrays,d['training_frames'],d['provenance'])


class Continuity:
    def __init__(self,config):
        self.config=config; self.previous=None

    def check(self,f):
        old=self.previous; self.previous=f
        if old is None: return None
        ds=(f.sequence-old.sequence)&0xffffffff
        dt=(f.timestamp_us-old.timestamp_us)&0xffffffff
        if ds==0 or ds>=0x80000000 or dt==0 or dt>=0x80000000: return 'restart_or_duplicate'
        if f.errors!=old.errors or f.dropped!=old.dropped: return 'device_counter_changed'
        if ds!=1: return 'sequence_gap'
        if not 0.5*self.config.frame_interval_s*1e6 <= dt <= 1.5*self.config.frame_interval_s*1e6:
            return 'timestamp_gap'
        return None


class Detector:
    def __init__(self,baseline):
        self.baseline=baseline; self.config=baseline.config
        self.guard=Continuity(self.config); self.invalidated=False; self.clear()

    def clear(self):
        self.bin=None; self.hits=0

    def update(self,frame):
        import time
        start=time.perf_counter()
        out=dict(frame_sequence=frame.sequence,timestamp_us=frame.timestamp_us,target_detected=False,
                 range_bin=None,range_m=None,calibrated=False,provisional_range_m=None,
                 candidate_bin=None,excess_db=None,threshold_db=None,margin_db=None,
                 device_dropped=frame.dropped,device_errors=frame.errors,reason='no_candidate_above_noise')
        reason=self.guard.check(frame)
        if reason=='restart_or_duplicate': self.invalidated=True
        if self.invalidated: reason='baseline_invalidated_by_restart'
        try: p=power(frame,self.config)
        except ValueError as error: reason=str(error);p=None
        if reason:
            self.clear();out['reason']=reason
        else:
            excess=db(p)-self.baseline.median_db
            ids=np.arange(self.config.min_bin,self.config.max_bin+1)
            best=int(ids[np.argmax(excess[ids])])
            others=ids[abs(ids-best)>1]
            margin=float(excess[best]-max(excess[others])) if len(others) else None
            out.update(candidate_bin=best,excess_db=float(excess[best]),threshold_db=float(self.baseline.threshold_db[best]),margin_db=margin,
                       power=p.tolist(),excess_profile_db=excess.tolist())
            if excess[best]<self.baseline.threshold_db[best]: self.clear()
            elif margin is not None and margin<self.config.margin_db:
                self.clear();out['reason']='ambiguous_separate_peak'
            else:
                self.hits=self.hits+1 if self.bin==best else 1;self.bin=best
                out['reason']='checking_persistence'
                if self.hits>=self.config.confirmation_frames:
                    out.update(target_detected=True,range_bin=best,provisional_range_m=best*self.config.spacing_m,
                               reason='spectral_change_uncalibrated')
        out['processing_ms']=(time.perf_counter()-start)*1000
        return out
