"""Wavvy: stable 1-D range-profile target selection.

Input: linear (not dB), nonnegative FFT magnitude profile + its range axis.
Do NOT pass a normalized-to-each-frame maximum plot or a range-Doppler image.

For empty-scene calibration: collect profiles with the target REMOVED and call
calibrate_empty_scene(profiles), then update(profile, ranges_m, subtract_background=True).
For stationary-target measurements use subtract_background=False.
"""
from collections import deque
from dataclasses import dataclass
import numpy as np
from scipy.signal import find_peaks

@dataclass
class Reading:
    distance_m: float | None
    raw_peak_m: float | None
    confidence: float
    status: str
    snr_db: float | None

class StableRangeTracker:
    def __init__(self, min_m=0.15, max_m=1.5, history=5,
                 prominence_sigma=4.0, lock_gate_m=0.25,
                 alpha_still=0.12, alpha_moving=0.65, max_missed=4):
        self.min_m, self.max_m = min_m, max_m
        self.prominence_sigma = prominence_sigma
        self.lock_gate_m = lock_gate_m
        self.alpha_still, self.alpha_moving = alpha_still, alpha_moving
        self.history = deque(maxlen=history)
        self.estimate = None
        self.missed = 0
        self.max_missed = max_missed
        self.background = None

    def calibrate_empty_scene(self, profiles):
        profiles = np.asarray(profiles, dtype=float)
        if profiles.ndim != 2 or len(profiles) < 10:
            raise ValueError('Use >=10 equal-sized empty-scene profiles')
        self.background = np.median(profiles, axis=0)

    def reset(self):
        self.history.clear()
        self.estimate = None
        self.missed = 0

    def update(self, profile, ranges_m, subtract_background=False):
        p = np.asarray(profile, dtype=float)
        r = np.asarray(ranges_m, dtype=float)
        if p.ndim != 1 or p.size != r.size or p.size < 4:
            raise ValueError('profile and ranges_m must be 1D, same size, >=4')
        if not np.all(np.isfinite(p)) or not np.all(np.isfinite(r)) or np.any(np.diff(r)<=0):
            raise ValueError('finite profile and strictly increasing ranges required')
        if np.any(p < 0):
            raise ValueError('Use LINEAR magnitude, not dB or complex FFT values')
        if subtract_background:
            if self.background is None or self.background.shape != p.shape:
                raise ValueError('Calibrate empty scene first, using the same FFT and bins')
            # Difference magnitude provides moving-target contrast; abs avoids only-negative dips.
            p = np.abs(p - self.background)
        valid = (r >= self.min_m) & (r <= self.max_m)
        ids = np.flatnonzero(valid)
        if len(ids) < 3:
            raise ValueError('Not enough FFT bins inside measurement window')
        x = p[ids]
        # Robust noise estimate and peak prominence; never simply choose global argmax.
        med = np.median(x)
        mad = 1.4826 * np.median(np.abs(x-med))
        noise = max(mad, med * 0.05, np.finfo(float).eps)
        # Peaking against local neighborhood rejects broad elevated floors.
        peaks, props = find_peaks(x, prominence=self.prominence_sigma * noise)
        if len(peaks) == 0:
            return self._miss('NO_TARGET')
        candidates = []
        for k, pk in enumerate(peaks):
            original_i = ids[pk]
            peak_m = self._interpolate_peak(p, r, original_i)
            prominence = props['prominences'][k]
            score = float(prominence/noise)
            if self.estimate is not None:
                offset = abs(peak_m-self.estimate)
                if offset <= self.lock_gate_m:
                    score += 5.0*(1.0-offset/self.lock_gate_m)
                else:
                    score -= 5.0
            candidates.append((score, peak_m, prominence))
        score, raw, prominence = max(candidates, key=lambda item: item[0])
        self.missed = 0
        self.history.append(raw)
        robust = float(np.median(self.history))
        if self.estimate is None:
            self.estimate = robust
        else:
            # Larger smoothing coefficient during genuine movement.
            moving = abs(robust-self.estimate) > 0.06
            alpha = self.alpha_moving if moving else self.alpha_still
            self.estimate += alpha*(robust-self.estimate)
        ratio = max(float(prominence/noise), 1e-9)
        snr = 20*np.log10(ratio)
        confidence = float(np.clip((ratio-self.prominence_sigma)/12, 0, 1))
        return Reading(round(self.estimate, 4), round(raw, 4),
                       round(confidence, 2), 'TRACKING', round(float(snr), 1))

    def _miss(self, status):
        self.missed += 1
        if self.missed > self.max_missed:
            self.reset()
            return Reading(None, None, 0., status, None)
        return Reading(None, None, 0., 'TEMPORARILY_LOST', None)

    @staticmethod
    def _interpolate_peak(p, r, i):
        if i < 1 or i >= len(p)-1:
            return float(r[i])
        # Sub-bin parabola on logarithmic amplitude; modest refinement only.
        a,b,c = np.log(np.maximum(p[i-1:i+2], 1e-15))
        den = a-2*b+c
        frac = 0. if abs(den)<1e-12 else float(np.clip(0.5*(a-c)/den, -.5,.5))
        return float(r[i]+frac*0.5*(r[i+1]-r[i-1]))


def range_profile_from_chirps(adc, bandwidth_hz, nfft=None):
    """Example for a REAL ADC array shaped (chirps, samples).

    Only use if firmware emits raw ADC samples. For complex IQ data use fft,
    not rfft, and ensure firmware chirp configuration matches bandwidth_hz.
    """
    adc = np.asarray(adc, dtype=float)
    if adc.ndim != 2 or adc.shape[0]<2 or adc.shape[1]<8:
        raise ValueError('Expected raw ADC shape (chirps, samples)')
    n_samples = adc.shape[1]
    if nfft is None:
        nfft = 4 * 2**int(np.ceil(np.log2(n_samples)))
    if nfft < n_samples or bandwidth_hz <= 0:
        raise ValueError('Invalid FFT size or bandwidth')
    samples = adc - np.mean(adc,axis=1,keepdims=True)
    samples *= np.hanning(n_samples)[None,:]
    spec = np.fft.rfft(samples, n=nfft, axis=1)
    magnitude = np.mean(np.abs(spec), axis=0)
    # If B is chirp's ACTUAL swept bandwidth (not sensor's rated maximum):
    ranges = np.arange(magnitude.size) * 299792458*n_samples/(2*bandwidth_hz*nfft)
    return magnitude, ranges

if __name__ == '__main__':
    ranges = np.arange(0, 2.01, 0.01)
    tracker = StableRangeTracker()
    rng = np.random.default_rng(4)
    for actual_m in [0.4]*25 + [0.55]*25:
        signal = 0.02+rng.uniform(0,0.006,len(ranges))
        signal += 1.0*np.exp(-0.5*((ranges-actual_m)/0.025)**2)
        reading = tracker.update(signal, ranges)
        print(actual_m, reading.distance_m, reading.status)
