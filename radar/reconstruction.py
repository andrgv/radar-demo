"""Joint raw-domain range reconstruction and per-component direction fitting.

Finite snapshots and a sparse sinusoidal model do not identify arbitrary room
surfaces. Accepted points are measured scattering hypotheses; no surface fill,
sensor-pose assumption or held last point is introduced here.
"""

from dataclasses import dataclass
import numpy as np

from .pointcloud import PointCloud
from .spatial import SpatialMapper


@dataclass(frozen=True)
class ReconstructionSettings:
    max_components: int = 8
    minimum_model_fit: float = .65
    minimum_snr_db: float = 8.
    aperture_angle_difference_deg: float = 15.
    minimum_frequency_separation_bins: float = .35


def empty_cloud():
    return PointCloud(np.empty((0, 3)), np.empty(0, int), np.empty(0), np.empty(0),
                      np.empty(0), np.empty((0, 2)), np.empty(0))


def sinusoid_fit(traces, frequencies, samples, start=0):
    """Variable projection, with independent per-trace amplitudes, phase and DC."""
    frequencies = np.asarray(frequencies, float)
    t = (np.arange(traces.shape[1]) + start) / samples
    phase = 2 * np.pi * t[:, None] * frequencies
    design = np.column_stack([np.ones(len(t)), np.cos(phase), np.sin(phase)])
    coefficients = np.linalg.lstsq(design, traces.T, rcond=None)[0]
    residual = traces.T - design @ coefficients
    k = len(frequencies)
    amplitudes = (coefficients[1:1+k] - 1j * coefficients[1+k:]).T
    return design, coefficients, residual, amplitudes


def refine_frequencies(traces, frequencies, samples, minimum_separation=.35):
    """Off-grid variable-projection Gauss/Newton steps, without distance labels."""
    frequencies = np.sort(np.asarray(frequencies, float))
    t = np.arange(samples) / samples
    for _ in range(8):
        design, coefficients, residual, _ = sinusoid_fit(traces, frequencies, samples)
        q = np.linalg.qr(design)[0]
        k = len(frequencies)
        phase = 2 * np.pi * t[:, None] * frequencies
        derivatives = 2 * np.pi * t[:, None, None] * (
            -np.sin(phase)[:, :, None] * coefficients[1:1+k][None, :, :]
            + np.cos(phase)[:, :, None] * coefficients[1+k:][None, :, :])
        derivative = derivatives.reshape(samples, -1)
        derivative -= q @ (q.T @ derivative)
        jacobian = derivative.reshape(samples, k, len(traces)).transpose(0, 2, 1).reshape(-1, k)
        step = np.linalg.lstsq(jacobian, residual.reshape(-1), rcond=None)[0]
        if np.max(abs(step)) < 1e-6:
            break
        step *= min(1., .2 / max(float(np.max(abs(step))), 1e-20))
        accepted = False
        for fraction in (1., .5, .25, .125):
            trial = frequencies + fraction * step
            if (trial[0] < .5 or trial[-1] > samples / 2 - .5
                    or np.any(np.diff(trial) < minimum_separation)):
                continue
            if np.sum(sinusoid_fit(traces, trial, samples)[2]**2) < np.sum(residual**2):
                frequencies, accepted = trial, True
                break
        if not accepted:
            break
    return frequencies


class SceneReconstructor:
    """Raw-ADC reconstruction; independent frames, all chirps and all three RXs."""

    def __init__(self, config, settings=None):
        self.config = config.validate()
        self.settings = settings or ReconstructionSettings()
        s = self.settings
        if (not 1 <= s.max_components <= min(12, (config.samples - 8) // 2)
                or not 0 < s.minimum_model_fit <= 1
                or s.minimum_snr_db <= 0
                or s.aperture_angle_difference_deg <= 0 or s.minimum_frequency_separation_bins <= 0):
            raise ValueError('Invalid reconstruction settings')
        self.mapper = SpatialMapper(config)
        self.n = config.samples
        self.last_report = {}

    def _candidates(self, raw):
        traces = raw.reshape(-1, self.n)
        length = self.n // 2
        hankel = np.lib.stride_tricks.sliding_window_view(traces, length, axis=1)
        hankel = hankel.transpose(2, 0, 1).reshape(length, -1)
        covariance = hankel @ hankel.T / hankel.shape[1]
        eigenvalues, vectors = np.linalg.eigh(covariance)
        eigenvalues = np.maximum(eigenvalues, 0)
        models = []
        for k in range(1, self.settings.max_components + 1):
            subspace = vectors[:, -2*k:]
            shift = np.linalg.lstsq(subspace[:-1], subspace[1:], rcond=None)[0]
            poles = np.linalg.eigvals(shift)
            frequencies = sorted(float(np.angle(p) * self.n / (2*np.pi)) for p in poles
                                 if np.angle(p) > 1e-5 and .85 < abs(p) < 1.15
                                 and .5 <= np.angle(p) * self.n / (2*np.pi) <= self.n/2-.5)
            if not frequencies:
                continue
            design, _, residual, amplitudes = sinusoid_fit(traces, frequencies, self.n)
            if np.linalg.cond(design) > 1e4:
                continue
            parameters = len(traces) * (1 + 2*len(frequencies)) + len(frequencies)
            bic = float(traces.size * np.log(max(float(np.mean(residual**2)), 1e-20))
                        + parameters * np.log(traces.size))
            models.append(dict(order=k, bic=bic, frequencies=frequencies,
                               powers=np.mean(abs(amplitudes)**2, axis=0).tolist()))
        if not models:
            return [], dict(reason='no_stable_frequency_model', model_orders=[])
        best = min(models, key=lambda model:model['bic'])
        candidates = [dict(native_bin=f, power=p) for f,p in zip(best['frequencies'], best['powers'])]
        candidates.sort(key=lambda item:item['power'], reverse=True)
        selected = []
        for candidate in candidates:
            if all(abs(candidate['native_bin'] - other['native_bin']) >=
                   self.settings.minimum_frequency_separation_bins for other in selected):
                selected.append(candidate)
            if len(selected) == self.settings.max_components:
                break
        selected.sort(key=lambda item:item['native_bin'])
        return selected, dict(signal_dimensions=2*best['order'],
                              subspace_rank_capped=best['order'] == self.settings.max_components,
                              eigenvalues=eigenvalues.tolist(),
                              model_orders=[{k:v for k,v in model.items() if k != 'powers'} for model in models])

    def _direction(self, vector):
        response = abs(self.mapper.weights.conj().T @ vector)**2
        peak = int(np.argmax(response))
        e, a = np.unravel_index(peak, (len(self.mapper.elevations), len(self.mapper.azimuths)))
        az, el = np.radians([self.mapper.azimuths[a], self.mapper.elevations[e]])
        xyz = np.array([np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)])
        mask = (response >= response[peak] / 2).reshape(len(self.mapper.elevations), len(self.mapper.azimuths))
        ai = np.flatnonzero(mask.any(axis=0))
        ei = np.flatnonzero(mask.any(axis=1))
        widths = [float(self.mapper.azimuths[ai[-1]] - self.mapper.azimuths[ai[0]]),
                  float(self.mapper.elevations[ei[-1]] - self.mapper.elevations[ei[0]])]
        fit = float(response[peak] / max(float(np.vdot(vector, vector).real), 1e-12))
        interior = 0 < a < len(self.mapper.azimuths) - 1 and 0 < e < len(self.mapper.elevations) - 1
        return xyz, fit, widths, interior, float(response[peak])

    def process(self, adc):
        c, s = self.config, self.settings
        adc = np.asarray(adc)
        if (adc.shape != (c.chirps, c.samples, 3) or not np.isfinite(adc).all()
                or np.any(adc <= 0) or np.any(adc >= 65535)):
            raise ValueError('Invalid ADC dimensions or container rails')
        raw = adc[c.discard_chirps:].astype(float).transpose(0, 2, 1)
        raw -= raw.mean(axis=2, keepdims=True)
        self.last_report = dict(method='raw_multitone_range_angle', points=0, components=[], state='unresolved')
        if np.sum(raw**2) <= 1e-15:
            self.last_report['reason'] = 'no_ac_energy'
            return empty_cloud()
        candidates, diagnostics = self._candidates(raw)
        self.last_report.update(diagnostics)
        if not candidates:
            self.last_report['reason'] = 'no_supported_components'
            return empty_cloud()
        traces = raw.reshape(-1, self.n)
        frequencies = refine_frequencies(traces, [p['native_bin'] for p in candidates], self.n,
                                         s.minimum_frequency_separation_bins)
        design, _, residual, amplitudes = sinusoid_fit(traces, frequencies, self.n)
        condition = float(np.linalg.cond(design))
        self.last_report.update(design_condition=condition,
                                residual_fraction=float(np.sum(residual**2) / np.sum(traces**2)))
        if condition > 1e4:
            self.last_report['reason'] = 'ill_conditioned_component_fit'
            return empty_cloud()
        count = len(frequencies)
        chirps = len(raw)
        amplitudes = amplitudes.reshape(chirps, 3, count).transpose(0, 2, 1) * c.gains
        width = 3 * self.n // 4
        subset_amplitudes = []
        subset_errors = []
        for start in (0, self.n - width):
            subset = traces[:, start:start+width]
            subset_design, subset_coefficients, _, values = sinusoid_fit(subset, frequencies, self.n, start)
            # This is aperture sensitivity: frequencies came from the full frame.
            # It is not an independent held-out validation of those frequencies.
            test = np.setdiff1d(np.arange(self.n), np.arange(start, start+width))
            phase = 2 * np.pi * test[:, None] * frequencies / self.n
            predicted = np.column_stack([np.ones(len(test)), np.cos(phase), np.sin(phase)]) @ subset_coefficients
            subset_errors.append(float(np.sum((traces[:, test].T - predicted)**2) /
                                       max(float(np.sum(traces[:, test]**2)), 1e-12)))
            subset_amplitudes.append(values.reshape(chirps, 3, count).transpose(0, 2, 1) * c.gains)
        self.last_report['aperture_prediction_error_fractions'] = subset_errors
        gram = np.linalg.pinv(design.T @ design)
        noise_variance = np.sum(residual**2, axis=0) / max(1, self.n - design.shape[1])
        noise_variance = noise_variance.reshape(chirps, 3)
        taper = np.hanning(chirps)
        slow = np.fft.fftshift(np.fft.fft(amplitudes * taper[:, None, None], axis=0), axes=0) / taper.sum()
        subset_slow = [np.fft.fftshift(np.fft.fft(v * taper[:, None, None], axis=0), axes=0) / taper.sum()
                       for v in subset_amplitudes]
        dopplers = np.fft.fftshift(np.fft.fftfreq(chirps))
        spacing = float(c.ranges[1] - c.ranges[0])
        points = []
        for k, frequency in enumerate(frequencies):
            multiplier = float(gram[1+k, 1+k] + gram[1+count+k, 1+count+k])
            expected_noise = np.sum(noise_variance * taper[:, None]**2, axis=0) / taper.sum()**2
            expected_noise = expected_noise * multiplier * abs(c.gains)**2
            powers = np.mean(abs(slow[:, k])**2, axis=1)
            for d in range(chirps):
                if powers[d] < powers[(d-1) % chirps] or powers[d] <= powers[(d+1) % chirps]:
                    continue
                snr = float(10 * np.log10(max(float(powers[d]), 1e-12) /
                                          max(float(expected_noise.mean()), 1e-12)))
                if snr < s.minimum_snr_db:
                    continue
                direction, fit, response_widths, interior, energy = self._direction(slow[d, k])
                differences = []
                coefficient_differences = []
                for subset in subset_slow:
                    other, _, _, _, _ = self._direction(subset[d, k])
                    differences.append(float(np.degrees(np.arccos(np.clip(direction @ other, -1, 1)))))
                    coefficient_differences.append(float(np.linalg.norm(subset[d, k] - slow[d, k]) /
                                                        max(float(np.linalg.norm(slow[d, k])), 1e-12)))
                angle_difference = max(differences)
                reasons = []
                if not interior:
                    reasons.append('direction_at_search_boundary')
                if fit < s.minimum_model_fit:
                    reasons.append('array_model_mismatch')
                if angle_difference > s.aperture_angle_difference_deg + 1e-8:
                    reasons.append('direction_changes_with_sample_aperture')
                if max(coefficient_differences) > .5:
                    reasons.append('component_changes_with_sample_aperture')
                component = dict(native_bin=float(frequency), range_m=float(frequency * spacing + c.range_offset_m),
                    doppler_cycles_per_chirp=float(dopplers[d]), snr_db=snr, model_fit=fit,
                    aperture_direction_difference_deg=angle_difference,
                    aperture_complex_coefficient_relative_difference=max(coefficient_differences),
                    direction_response_width_deg=response_widths, accepted=not reasons, reasons=reasons)
                self.last_report['components'].append(component)
                if not reasons:
                    points.append((component['range_m'] * direction, int(round(frequency)),
                                   float(dopplers[d]), snr, fit, response_widths,
                                   float(10 * np.log10(max(energy, 1e-12)))))
        self.last_report.update(points=len(points), state='candidates' if points else 'unresolved',
                                reason='frame_reconstructed' if points else 'no_consistent_directions')
        if not points:
            return empty_cloud()
        return PointCloud(np.array([p[0] for p in points]), np.array([p[1] for p in points], int),
                          *[np.array([p[i] for p in points]) for i in range(2, 7)])
