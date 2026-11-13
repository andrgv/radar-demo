"""Range-first echo selection using the repository's DSP primitives.

Motion/angle estimates never gate the range candidate list. One range peak is
one echo, not proof of one physical object. No implicit background learning.
"""
import math
from collections import deque
from radar.angle_lab import infer_azimuth_rx2
from radar.range_azimuth import load_reference
from pathlib import Path
import sys

import numpy as np

from radar.background import SpectralBackground
from radar.config import C, Config
from radar.processing import (
    Processor, coherent_channels, estimate_angle, interpolated_range,
    noise_threshold, range_fft,
)


def json_safe(value):
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def config_path(attributes):
    value = attributes.get('config_path')
    if not isinstance(value, str) or not value.strip():
        raise ValueError('config_path is required: use the exact repository configuration tested on your radar')
    path = Path(value).expanduser()
    if not path.is_absolute():
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1]))
        path = root / path
    return path


def radar_config(attributes):
    # Load the user's tested file without overriding geometry, phase or RF values.
    cfg = Config.load(config_path(attributes))
    if type(cfg.verified) is not bool:
        raise ValueError('Configuration verified flag must be boolean')
    if not 0 < cfg.snr_db <= 80:
        raise ValueError('Configuration snr_db must be between 0 and 80 dB')
    return cfg


class EchoProcessor:
    def __init__(self, config, min_range=0.5, max_range=3.0, angles=False, reference=None):
        self.config = config
        self.min_range, self.max_range = min_range, max_range
        self.angles = angles
        self.reference = reference
        self.angle_history = deque(maxlen=5)
        self.last_sequence = None
        self.background = None
        self.processor = Processor(config)
        self.capture_target = 0
        self.capture_frames = []

    def capture_background(self, frames=30):
        self.clear_background()
        self.capture_target = frames

    def clear_background(self):
        self.background = None
        self.angle_history.clear()
        self.processor.background = None
        self.processor.history.clear()
        self.capture_target = 0
        self.capture_frames = []

    def process(self, frame):
        cfg = self.config
        if (frame.profile_id != cfg.profile_id or frame.adc.shape != (cfg.chirps, cfg.samples, 3)
                or not frame.flags & 1 or frame.flags & 8):
            raise ValueError(f'Firmware mismatch: got {frame.profile_id:#x} {frame.adc.shape} flags={frame.flags}; expected raw {cfg.profile_id:#x} {(cfg.chirps, cfg.samples, 3)}')
        if frame.errors:
            raise ValueError(f'Device acquisition error: {frame.errors}')
        if self.capture_target:
            self.capture_frames.append(frame)
            if len(self.capture_frames) == self.capture_target:
                self.background = SpectralBackground.fit(self.capture_frames, cfg)
                self.processor.background = self.background
                self.processor.history.clear()
                self.angle_history.clear()
                self.capture_target = 0
                self.capture_frames = []

        if self.last_sequence is not None and ((frame.sequence-self.last_sequence) & 0xffffffff) != 1:
            self.angle_history.clear()
        self.last_sequence = frame.sequence
        # Repository diagnostics; its static/moving candidate list is deliberately
        # not used for Viam echo selection, which must not veto stationary peaks.
        report = self.processor.process(frame)
        spectrum = range_fft(frame.adc, cfg)
        if self.background is not None:
            spectrum = self.background.subtract(spectrum, cfg)
        self.angle_history.append(spectrum.copy())
        power = np.mean(np.abs(spectrum)**2, axis=(0, 2))
        threshold = noise_threshold(power, 10 ** (cfg.snr_db / 10))
        window = np.hanning(len(spectrum))
        doppler = np.fft.fftshift(np.fft.fft(
            spectrum * window[:, None, None], axis=0), axes=0) / window.sum()
        rd_power = np.mean(np.abs(doppler)**2, axis=2)
        echoes = []
        for r in range(2, len(power) - 1):
            if power[r] <= threshold[r] or power[r] <= max(power[r-1], power[r+1]):
                continue
            distance = interpolated_range(power, r, cfg)
            if not self.min_range <= distance <= self.max_range:
                continue
            snr = float(10 * np.log10(power[r] / max(threshold[r] / 10**(cfg.snr_db/10), 1e-12)))
            echo = dict(distance_m=distance, range_bin=r, snr_db=snr,
                        power_db=float(10*np.log10(max(power[r], 1e-12))),
                        **self._doppler(rd_power[:, r]))
            if self.reference is not None and self.angles:
                echo.update(self._reference_angle(r, distance))
            else:
                echo.update(self._angle(spectrum[:, r] @ cfg.angle_matrix.T))
            echoes.append(echo)
        echoes.sort(key=lambda item: item['distance_m'])
        selected = echoes[0] if echoes else {}
        return json_safe(dict(
            detected=bool(echoes), echo_count=len(echoes), echoes=echoes,
            distance_m=selected.get('distance_m'), azimuth_deg=selected.get('azimuth_deg'),
            elevation_deg=selected.get('elevation_deg'),
            doppler_cycles_per_chirp=selected.get('doppler_cycles_per_chirp'),
            doppler_resolved=selected.get('doppler_resolved', False),
            doppler_hz=selected.get('doppler_hz'),
            radial_velocity_mps=selected.get('radial_velocity_mps'),
            selection='nearest_range_echo_motion_independent',
            echo_count_basis='qualifying_range_peaks_not_physical_objects',
            range_calibrated=cfg.verified, angle_calibrated=False,
            angle_status=selected.get('angle_status', 'no_echo'),
            chirp_timing_verified=cfg.chirp_timing_verified,
            carrier_frequency_verified=cfg.carrier_frequency_verified,
            velocity_scale_verified=cfg.velocity_scale_verified,
            doppler_unit='cycles/output_chirp',
            range_bin_spacing_m=float(cfg.ranges[1]-cfg.ranges[0]),
            profile_id=f'0x{frame.profile_id:08x}',
            sequence=frame.sequence, device_timestamp_us=frame.timestamp_us,
            device_dropped=frame.dropped, device_errors=frame.errors,
            background_subtracted=self.background is not None,
            background_capture_remaining=max(0, self.capture_target-len(self.capture_frames)),
            calibration_id=cfg.calibration_id,
            angle_method='rx2_reference' if self.reference is not None else 'matrix_phase',
            features=report.features,
        ))

    def _doppler(self, column):
        n = len(column)
        d = int(np.argmax(column))
        center = n // 2
        mask = np.ones(n, dtype=bool)
        mask[[(d-1) % n, d, (d+1) % n]] = False
        noise = max(float(np.median(column[mask])), 1e-12)
        # A zero-bin peak can resolve zero Doppler; that is not proof of no motion
        # below this burst's resolution. Reject Nyquist and symmetric ambiguity.
        resolved = (d != 0 and column[d] > noise * 10**1.2 and
                    (d == center or column[d] > 4*column[(2*center-d) % n]))
        cycles = float((d-center)/n) if resolved else None
        hz = cycles/self.config.chirp_interval_s if resolved and self.config.chirp_timing_verified else None
        velocity = hz*C/(2*self.config.carrier_hz) if hz is not None and self.config.velocity_scale_verified else None
        return dict(doppler_cycles_per_chirp=cycles, doppler_resolved=bool(resolved),
                    moving=bool(d != center) if resolved else None,
                    doppler_hz=hz, radial_velocity_mps=velocity)

    def _angle(self, channels):
        result = dict(azimuth_deg=None, elevation_deg=None, angle_coherence=None,
                      angle_valid=False, angle_calibrated=False, angle_status='disabled')
        if not self.angles:
            return result
        power = np.mean(abs(channels)**2, axis=0)
        cross = coherent_channels(channels)
        coherence = abs(cross[1:])/np.sqrt(np.maximum(power[1:]*power[0], 1e-20))
        result['angle_coherence'] = float(np.clip(np.min(coherence), 0, 1))
        if result['angle_coherence'] < .9 or np.min(power) < 1e-12:
            result['angle_status'] = 'weak_or_incoherent'
            return result
        az, el, _, valid = estimate_angle(cross, self.config)
        result.update(angle_valid=valid, angle_status='estimate_unverified' if valid else 'invalid_direction')
        if valid:
            result.update(azimuth_deg=az, elevation_deg=el)
        return result

    def _reference_angle(self, r, distance):
        result = dict(azimuth_deg=None, elevation_deg=None, angle_coherence=None,
                      angle_valid=False, angle_calibrated=False, angle_status='weak_or_incoherent')
        phase, xyz, target_z = self.reference
        result['assumed_target_z_m'] = target_z
        samples = np.concatenate([s[:, r] for s in self.angle_history], axis=0)
        power = np.mean(abs(samples)**2, axis=0)
        cross = np.mean(samples[:, 1]*samples[:, 0].conj())
        coherence = float(np.clip(abs(cross)/np.sqrt(max(power[0]*power[1], 1e-24)), 0, 1))
        result['angle_coherence'] = coherence
        if coherence < .9 or min(power[:2]) < 1e-12:
            return result
        if distance <= abs(target_z):
            result['angle_status'] = 'range_incompatible_with_assumed_height'
            return result
        horizontal_range = np.sqrt(distance**2-target_z**2)
        forward = horizontal_range
        try:
            for _ in range(3):
                az, residual = infer_azimuth_rx2(np.angle(cross), phase, xyz,
                    self.config, forward_m=forward, z_m=target_z, limit_deg=25)
                forward = horizontal_range*np.cos(np.radians(az))
        except ValueError:
            result['angle_status'] = 'invalid_reference_model'
            return result
        if abs(az) >= 24.95 or residual > 1:
            result['angle_status'] = 'outside_reference_model'
            return result
        result.update(azimuth_deg=az, angle_valid=True, angle_status='reference_estimate_unverified',
                      phase_residual_deg=residual, angle_average_frames=len(self.angle_history))
        return result
