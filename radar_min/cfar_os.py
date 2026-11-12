"""Experimental range OS reference; unchanged CA baseline remains available."""
from dataclasses import dataclass, asdict

import numpy as np

from .cfar import CfarConfig, CfarDetector


@dataclass(frozen=True)
class OsConfig:
    # Lower median for even counts. This tolerates a contaminated upper half,
    # at the cost of a lower reference and potentially more nuisance detections.
    rank_fraction: float = .5

    def __post_init__(self):
        if not np.isfinite(self.rank_fraction) or not 0 < self.rank_fraction <= 1:
            raise ValueError('OS rank fraction must be in (0,1]')


def os_thresholds(power, settings, os_settings=None):
    p=np.asarray(power,dtype=float)
    if p.ndim!=1 or len(p)<3 or not np.isfinite(p).all() or np.any(p<0):
        raise ValueError('CFAR expects finite nonnegative one-dimensional power')
    policy=os_settings or OsConfig()
    noise=np.full(len(p),np.nan);counts=np.zeros(len(p),dtype=int)
    usable=np.arange(1,len(p)-1)
    for k in usable:
        distance=abs(usable-k)
        refs=usable[(distance>settings.guard_cells)&(distance<=settings.guard_cells+settings.training_cells)]
        counts[k]=len(refs)
        if len(refs)>=settings.min_training_cells:
            rank=int(np.ceil(policy.rank_fraction*len(refs)))
            noise[k]=max(float(np.partition(p[refs],rank-1)[rank-1]),1e-12)
    return noise,noise*settings.factor,counts


class OsCfarDetector(CfarDetector):
    """Same grouping, confirmation and fine estimator; only reference changes."""
    def __init__(self,config,settings=None,os_settings=None):
        self.os_settings=os_settings or OsConfig()
        super().__init__(config,settings or CfarConfig(1,4,4,2))
        self.metadata.update(algorithm='range-os-cfar-experimental-v1',
            os=asdict(self.os_settings),reference='kth smallest; k=ceil(rank_fraction*actual reference count)',
            threshold_interpretation='Empirical multiplier; no calibrated Pfa; not interchangeable with CA statistics')

    def thresholds(self,p):
        return os_thresholds(p,self.settings,self.os_settings)


def select_os_candidate(reading,clusters):
    """Inspection-only selection; never certifies added-target identity.

    Require one current 1D group and one current RD maximum in its support.
    A raw RD maximum is association evidence, not independent confirmation.
    """
    result=dict(experimental_range_m=None,primary_eligible=False,
                reason=reading['reason'],rd_peak_count=0)
    if not reading['target_detected']:return result
    if len(reading['candidates'])!=1:
        result['reason']='multiple_os_groups';return result
    fine=reading.get('fine_range')
    if not fine or fine['range_m'] is None:
        result['reason']=fine['reason'] if fine else 'unresolved_os_range';return result
    peaks=[p for c in clusters for p in c['local_maxima'] if p['range_bin'] in reading['selected_group_bins']]
    result['rd_peak_count']=len(peaks)
    if len(peaks)!=1:
        result['reason']='multiple_current_rd_peaks' if peaks else 'no_current_rd_peak'
        return result
    result.update(experimental_range_m=fine['range_m'],reason='experimental_os_with_unique_current_rd_support',
                  rd_range_bin=peaks[0]['range_bin'],rd_cycles_per_saved_block=peaks[0]['cycles_per_saved_block'])
    return result
