"""Baseline-free range CA-CFAR with explicit truncated-edge reference windows.

The multiplier is empirical: windowed, integrated radar powers do not satisfy
the independent exponential-cell model of the textbook single-look Pfa formula.
"""
from dataclasses import dataclass, asdict
import time
import numpy as np
from .core import Continuity, power, db


@dataclass(frozen=True)
class CfarConfig:
    guard_cells: int = 2
    training_cells: int = 8  # per side, before clipping at usable-spectrum edges
    min_training_cells: int = 8  # total; otherwise the CUT cannot be tested
    factor: float = 6.0

    def __post_init__(self):
        for key in ('guard_cells', 'training_cells', 'min_training_cells'):
            if type(getattr(self, key)) is not int:
                raise ValueError('CFAR cell counts must be integers')
        if self.guard_cells < 0 or self.training_cells < 1:
            raise ValueError('CFAR requires nonnegative guards and positive training cells')
        if not 1 <= self.min_training_cells <= 2*self.training_cells:
            raise ValueError('CFAR minimum training count must be 1..2*training_cells')
        if not np.isfinite(self.factor) or self.factor <= 1:
            raise ValueError('CFAR factor must be finite and greater than one')


def ca_thresholds(p, settings):
    """Linear-power means excluding DC, Nyquist, CUT and guards; no wrapping.

    Near an edge use the available portion of the same window, not distant
    replacement cells. Counts are exported so asymmetric estimates are visible.
    NaN marks an untestable cell internally; JSON output uses null instead.
    """
    p = np.asarray(p, dtype=float)
    if p.ndim != 1 or len(p) < 3 or not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError('CFAR expects finite nonnegative one-dimensional power')
    noise = np.full(len(p), np.nan)
    counts = np.zeros(len(p), dtype=int)
    usable = np.arange(1, len(p)-1)
    for k in usable:
        distance = abs(usable-k)
        refs = usable[(distance > settings.guard_cells) &
                      (distance <= settings.guard_cells+settings.training_cells)]
        counts[k] = len(refs)
        if len(refs) >= settings.min_training_cells:
            noise[k] = max(float(np.mean(p[refs])), 1e-12)
    return noise, noise*settings.factor, counts


def json_array(values):
    return [float(v) if np.isfinite(v) else None for v in values]


class CfarDetector:
    def __init__(self, config, settings=None):
        self.config = config
        self.settings = settings or CfarConfig()
        self.baseline = None
        self.metadata = dict(algorithm='range-ca-cfar-v1', cfar=asdict(self.settings),
                             selection='nearest qualifying peak group',
                             edge_policy='truncate; require minimum total reference count')
        self.guard = Continuity(config)
        # Fail early if the selected search interval cannot be tested at all.
        _, thresholds, _ = ca_thresholds(np.ones(config.samples//2+1), self.settings)
        if not np.isfinite(thresholds[config.min_bin:config.max_bin+1]).any():
            raise ValueError('No searchable CFAR bins have enough training cells')
        self.clear()

    def clear(self):
        self.bin = None
        self.hits = 0

    def update(self, frame):
        started = time.perf_counter()
        out = dict(**self.metadata, frame_sequence=frame.sequence,
                   timestamp_us=frame.timestamp_us, target_detected=False,
                   range_bin=None, range_m=None, calibrated=False,
                   provisional_range_m=None, candidate_bin=None,
                   device_dropped=frame.dropped, device_errors=frame.errors,
                   candidates=[], qualified_bins=[], reason='no_candidate_above_noise')
        reason = self.guard.check(frame)
        try:
            p = power(frame, self.config)
        except ValueError as error:
            reason = str(error)
        if reason:
            self.clear()
            out['reason'] = reason
        else:
            noise, thresholds, counts = ca_thresholds(p, self.settings)
            ids = np.arange(self.config.min_bin, self.config.max_bin+1)
            qualified = ids[p[ids] > thresholds[ids]]
            # Group contiguous above-threshold cells, and select one maximum
            # per group. A flank of a peak outside the search mask is rejected.
            groups = np.split(qualified, np.flatnonzero(np.diff(qualified) > 1)+1)
            candidates = []
            for group in groups:
                if not len(group):
                    continue
                k = int(group[np.argmax(p[group])])
                neighbors = p[max(1, k-1):min(len(p)-1, k+2)]
                if p[k] < max(neighbors):
                    continue
                candidates.append(dict(range_bin=k, bins=group.tolist(),
                    provisional_range_m=k*self.config.spacing_m,
                    power=float(p[k]), noise_power=float(noise[k]),
                    threshold_power=float(thresholds[k]),
                    signal_to_reference_db=float(db(p[k])-db(noise[k]))))
            out.update(power=p.tolist(), power_db=db(p).tolist(),
                       noise_power=json_array(noise), threshold_power=json_array(thresholds),
                       noise_profile_db=json_array(db(noise)),
                       threshold_profile_db=json_array(db(thresholds)),
                       training_cell_counts=counts.tolist(), qualified_bins=qualified.tolist(),
                       candidates=candidates)
            if candidates:
                best = candidates[0]  # ordered by increasing range, not power
                k = best['range_bin']
                self.hits = self.hits+1 if self.bin == k else 1
                self.bin = k
                out.update(candidate_bin=k, signal_to_reference_db=best['signal_to_reference_db'],
                           reason='checking_persistence')
                if self.hits >= self.config.confirmation_frames:
                    out.update(target_detected=True, range_bin=k,
                               provisional_range_m=best['provisional_range_m'],
                               reason='cfar_peak_uncalibrated')
            else:
                self.clear()
        out['processing_ms'] = (time.perf_counter()-started)*1000
        return out
