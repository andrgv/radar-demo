"""Current-frame range refinement within CFAR group support; no empty reference."""
import numpy as np
from .core import range_spectrum


def refine_group(frame, config, bins):
    """Locate an interior dense-spectrum peak, retaining an unresolved outcome.

    Half-bin cell boundaries define the group's support. Zero padding and local
    interpolation improve numerical peak location, not physical resolution.
    """
    nfft = max(4096, 8*config.samples)
    spectrum = range_spectrum(frame, config, nfft=nfft)
    p = np.mean(abs(spectrum)**2, axis=(0, 2))
    coordinates = np.arange(len(p))*config.spacing_m*config.samples/nfft
    lower = (min(bins)-.5)*config.spacing_m
    upper = (max(bins)+.5)*config.spacing_m
    indices = np.flatnonzero((coordinates >= lower) & (coordinates <= upper))
    result = dict(method='raw-Hann-dense-peak-v1', range_m=None,
                  support_m=[lower, upper], reason='fine_peak_at_group_boundary',
                  boundary=True, nfft=nfft)
    if len(indices) < 3:
        return result
    k = int(indices[np.argmax(p[indices])])
    if k in (indices[0], indices[-1]) or k == 0 or k == len(p)-1:
        return result
    # Distinct nearly equal maxima in the same group are unresolved, not averaged.
    peaks = [int(i) for i in indices[1:-1]
             if p[i] >= p[i-1] and p[i] > p[i+1] and p[i] >= .5*p[k]]
    result['comparable_peak_count'] = len(peaks)
    if len(peaks) > 1:
        result.update(reason='multiple_fine_peaks', boundary=False)
        return result
    y = np.log(np.maximum(p[k-1:k+2], 1e-12))
    curvature = y[0]-2*y[1]+y[2]
    if curvature >= 0:
        result.update(reason='nonconcave_fine_peak', boundary=False)
        return result
    delta = float(np.clip(.5*(y[0]-y[2])/curvature, -.5, .5))
    estimate = float((k+delta)*config.spacing_m*config.samples/nfft)
    if not lower < estimate < upper:
        return result
    result.update(range_m=estimate, reason='fine_peak_uncalibrated', boundary=False)
    return result
