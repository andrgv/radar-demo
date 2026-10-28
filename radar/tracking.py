"""Conservative association of background-subtracted range detections.

This is a display aid, not evidence that a reflection belongs to a particular
physical object. A missed return never becomes a current detection.
"""

from dataclasses import dataclass
from dataclasses import replace
import numpy as np

from .processing import range_fft


@dataclass(frozen=True)
class TrackStatus:
    state: str
    bin_index: int | None = None
    range_m: float | None = None
    hits: int = 0
    misses: int = 0
    observed_range_m: float | None = None


class RangeTracker:
    def __init__(self, confirmation_frames=3, max_misses=3, gate_bins=2):
        self.confirmation_frames = confirmation_frames
        self.max_misses = max_misses
        self.gate_bins = gate_bins
        self.reset()

    def reset(self):
        self.bin_index = None
        self.range_m = None
        self.hits = 0
        self.misses = 0
        self.confirmed = False

    def update(self, detections, ranges):
        candidates = {}
        for detection in detections:
            index = int(np.argmin(abs(ranges - detection.range_m)))
            if index not in candidates or detection.snr_db > candidates[index].snr_db:
                candidates[index] = detection

        chosen = None
        if self.bin_index is not None:
            nearby = [(index, item) for index, item in candidates.items()
                      if abs(index - self.bin_index) <= self.gate_bins]
            if nearby:
                chosen = min(nearby, key=lambda pair: (abs(pair[0] - self.bin_index), -pair[1].snr_db))
            else:
                self.misses += 1
                if not self.confirmed:
                    self.hits = 0
                if self.misses >= self.max_misses:
                    self.reset()
                    return TrackStatus("lost")
                return TrackStatus("missing", self.bin_index, self.range_m, self.hits, self.misses)
        elif candidates:
            chosen = max(candidates.items(), key=lambda pair: pair[1].snr_db)

        if chosen is None:
            return TrackStatus("no change")

        index, detection = chosen
        if self.bin_index is None:
            self.bin_index = index
            self.range_m = detection.range_m
            self.hits = 1
        else:
            self.bin_index = index
            self.range_m = 0.5 * self.range_m + 0.5 * detection.range_m
            self.hits += 1
        self.misses = 0
        self.confirmed = self.confirmed or self.hits >= self.confirmation_frames
        return TrackStatus("confirmed" if self.confirmed else "checking",
                           self.bin_index, self.range_m, self.hits,
                           observed_range_m=detection.range_m)


@dataclass(frozen=True)
class _AmplitudeCandidate:
    range_m: float
    snr_db: float


class ShortRangeAmplitudeTracker:
    """Experimental near-field scene-change indicator, not a range calibration.

    Complex subtraction makes distant phase/clutter changes look like targets.
    This compares raw per-bin *power* to an empty-scene reference and considers
    only the configured short-range window. No physical object is identified.
    """

    def __init__(self, config, max_plot_range_m=2.0, min_excess_db=3.0, min_margin_db=2.0):
        self.config = config
        self.neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
        self.min_excess_db = min_excess_db
        self.min_margin_db = min_margin_db
        # Bin zero is dominated by leakage/DC. Bin one can still carry a
        # close-in presence change, even though it is not a calibrated range.
        self.indices = np.flatnonzero((config.ranges <= max_plot_range_m) &
                                      (np.arange(len(config.ranges)) >= 1) &
                                      (np.arange(len(config.ranges)) < len(config.ranges) - 1))
        self.reference_power = None
        self.tracker = RangeTracker()

    def power(self, frame):
        if frame.profile_id != self.config.profile_id or frame.adc.shape != (self.config.chirps, self.config.samples, 3):
            raise ValueError("Short-range frame/configuration mismatch")
        spectrum = range_fft(frame.adc, self.neutral)
        return np.mean(abs(spectrum)**2, axis=(0, 2))

    def fit(self, frames):
        if len(frames) < 10:
            raise ValueError("Short-range reference needs at least ten empty frames")
        self.reference_power = np.median([self.power(frame) for frame in frames], axis=0)
        self.tracker.reset()

    def update(self, frame):
        if self.reference_power is None:
            raise ValueError("Capture an empty-scene reference first")
        excess_db = 10 * np.log10(np.maximum(self.power(frame), 1e-12) /
                                  np.maximum(self.reference_power, 1e-12))
        candidates = []
        if len(self.indices):
            ranked = sorted(self.indices, key=lambda index: excess_db[index], reverse=True)
            best = ranked[0]
            # An extended target spreads energy into adjacent FFT bins. Compare
            # against separate peaks, not the same return's immediate neighbor.
            runner_up = max((excess_db[index] for index in ranked if abs(index - best) > 1),
                            default=-np.inf)
            if excess_db[best] >= self.min_excess_db and excess_db[best] - runner_up >= self.min_margin_db:
                candidates = [_AmplitudeCandidate(float(self.config.ranges[best]), float(excess_db[best]))]
        return self.tracker.update(candidates, self.config.ranges), excess_db
