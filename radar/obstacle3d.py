"""Experimental per-RX obstacle candidates and sensor-relative 3D estimates.

No scene reference, material model, or surveyed target position enters detection.
Stationary energy is retained. A missing/ambiguous return never asserts clear.
"""
from collections import deque
from dataclasses import asdict, dataclass, fields
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from .config import Config, C
from .spatial import SpatialMapper


@dataclass(frozen=True)
class Settings:
    window_seconds: float = 1.0
    persistence_windows: int = 3
    contrast_db: float = 6.0
    association_bins: float = .25
    minimum_fit: float = .65
    minimum_coherence: float = .9
    interpolation: int = 8

    def validate(self):
        for name in ('window_seconds', 'contrast_db', 'association_bins'):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f'{name} must be finite and positive')
        if not .01 <= self.window_seconds <= 10:
            raise ValueError('Window must be between .01 and 10 seconds')
        for name in ('minimum_fit', 'minimum_coherence'):
            if not np.isfinite(getattr(self, name)) or not 0 < getattr(self, name) <= 1:
                raise ValueError(f'{name} must be in (0, 1]')
        if type(self.persistence_windows) is not int or not 1 <= self.persistence_windows <= 20:
            raise ValueError('Persistence must be 1 to 20 windows')
        if type(self.interpolation) is not int or not 1 <= self.interpolation <= 16:
            raise ValueError('Interpolation must be 1 to 16')
        return self


def load_config(path):
    """Also accept the archived radar_min acquisition configuration format.

    Missing geometry in that format uses the documented physical portrait model,
    explicitly UNVERIFIED. It does not inherit calibrated range/angle offsets.
    """
    data = json.loads(Path(path).read_text())
    if 'schema' not in data:
        return Config(**data).validate()
    from radar_min.core import Config as MinimalConfig
    MinimalConfig(**data)  # __post_init__ validates the archived schema.
    selected = {f.name: data[f.name] for f in fields(Config) if f.name in data}
    return Config(**selected, geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]],
                  geometry_label='Assumed portrait for archived acquisition; mounting/phase unverified',
                  calibration_id='archived-acquisition; geometry-and-range-unverified').validate()


class Obstacle3DDetector:
    def __init__(self, config, settings=None):
        self.config = config.validate()
        self.settings = (settings or Settings()).validate()
        self.window_frames = max(1, int(np.ceil(self.settings.window_seconds / config.frame_interval_s)))
        self.mapper = SpatialMapper(config)
        self.taper = np.hanning(config.samples)
        self.axis = np.arange(config.samples * self.settings.interpolation // 2 + 1) / self.settings.interpolation
        self.spacing = C * config.sample_rate_hz / (2 * config.slope_hz_s * config.samples)
        self.previous = None
        self.latched = False
        self.powers, self.covariances = [], []
        self.history = deque(maxlen=max(1, self.settings.persistence_windows - 1))

    def invalidate(self, reason, frame=None):
        self.powers.clear()
        self.covariances.clear()
        self.history.clear()
        return dict(schema=1, method='per_rx_obstacle_3d_v1', state='uncertain', reason=reason,
                    sequence=frame.sequence if frame is not None else None,
                    timestamp_us=frame.timestamp_us if frame is not None else None,
                    complete_window=False, returns=[], material='unknown',
                    angular_calibration_verified=False, range_calibration_verified=self.config.verified,
                    frame_id='radar', axes=['right', 'forward', 'up'])

    def push(self, frame):
        c = self.config
        if self.latched:
            return self.invalidate('device_restart_requires_new_detector', frame)
        if (frame.profile_id != c.profile_id or frame.adc.shape != (c.chirps, c.samples, 3)
                or not frame.flags & 1):
            self.previous = None
            return self.invalidate('frame_config_mismatch', frame)
        if not np.isfinite(frame.adc).all() or np.any((frame.adc <= 0) | (frame.adc >= 65535)):
            self.previous = frame
            return self.invalidate('invalid_adc_or_container_rails', frame)
        if self.previous is not None:
            previous = self.previous
            self.previous = frame
            step = (frame.sequence - previous.sequence) & 0xffffffff
            elapsed = ((frame.timestamp_us - previous.timestamp_us) & 0xffffffff) / 1e6
            if frame.sequence < previous.sequence and step != 1:
                self.latched = True
                return self.invalidate('device_restart_requires_new_detector', frame)
            if (step != 1 or frame.dropped != previous.dropped or frame.errors != previous.errors
                    or not 0 < elapsed <= max(1., 5 * c.frame_interval_s)):
                return self.invalidate('frame_discontinuity', frame)
        self.previous = frame
        if not self.powers:
            self.first_sequence = frame.sequence
        raw = frame.adc[c.discard_chirps:].astype(float)
        raw -= raw.mean(axis=1, keepdims=True)
        spectrum = np.fft.rfft(raw * self.taper[None, :, None],
                               n=c.samples * self.settings.interpolation, axis=1) * (2 / self.taper.sum()) * c.gains
        # Joint raw-domain covariance cancels common chirp/frame phase without
        # averaging a stationary/moving echo to zero. No background subtraction.
        covariance = np.einsum('cfa,cfb->fab', spectrum, spectrum.conj()) / len(spectrum)
        self.powers.append(np.diagonal(covariance, axis1=1, axis2=2).real.copy())
        self.covariances.append(covariance)
        if len(self.powers) < self.window_frames:
            return None
        power = np.median(self.powers, axis=0)
        covariance = np.mean(self.covariances, axis=0)
        self.powers.clear()
        self.covariances.clear()
        candidates = self._candidates(power)
        for item in candidates:
            b = item.pop('_index')
            item.update(self._direction(covariance[b], power, b, item['peak_receivers']))
            common_rx = set(item['peak_receivers'])
            hits = 1
            for prior in reversed(self.history):
                matched_rx = {rx for old in prior
                              if abs(old['native_bin'] - item['native_bin']) <= self.settings.association_bins
                              for rx in old['peak_receivers']}
                common_rx &= matched_rx
                if not common_rx:
                    break
                hits += 1
            item['consecutive_windows'] = hits
            item['persistent'] = hits >= self.settings.persistence_windows
        self.history.append(candidates)
        persistent = [item for item in candidates if item['persistent']]
        return dict(schema=1, method='per_rx_obstacle_3d_v1', frame_id='radar', axes=['right', 'forward', 'up'],
                    sequence=frame.sequence, timestamp_us=frame.timestamp_us, first_sequence=self.first_sequence,
                    complete_window=True, window_frames=self.window_frames,
                    state='obstacle_candidates' if persistent else 'uncertain',
                    reason='persistent_returns' if persistent else 'no_persistent_returns',
                    material='unknown', angular_calibration_verified=False,
                    range_calibration_verified=c.verified, returns=candidates)

    def _contrast(self, power, b):
        center = self.axis[b]
        refs = [center + offset for offset in (-5, -4, -3, -2, 2, 3, 4, 5)
                if 1 <= center + offset < self.axis[-1]]
        if len(refs) < 3:
            return np.full(3, -np.inf)
        floor = np.array([np.median(np.interp(refs, self.axis, power[:, rx])) for rx in range(3)])
        return 10 * np.log10(np.maximum(power[b], 1e-12) / np.maximum(floor, 1e-12))

    def _candidates(self, power):
        peaks = []
        pad = self.settings.interpolation
        for rx in range(3):
            p = power[:, rx]
            indices = np.flatnonzero((p[1:-1] >= p[:-2]) & (p[1:-1] > p[2:])) + 1
            for b in indices[(indices >= pad) & (indices < len(power) - pad)]:
                contrast = float(self._contrast(power, b)[rx])
                if contrast >= self.settings.contrast_db:
                    peaks.append(dict(index=int(b), rx=rx + 1, contrast=contrast, power=float(p[b])))
        groups = []
        for peak in sorted(peaks, key=lambda p: p['index']):
            if (groups and (peak['index'] - groups[-1][0]['index']) / pad <= self.settings.association_bins
                    and peak['rx'] not in {p['rx'] for p in groups[-1]}):
                groups[-1].append(peak)
            else:
                groups.append([peak])
        returns = []
        for group in groups:
            best = max(group, key=lambda p: p['contrast'])
            b = best['index']
            distance = float(self.axis[b] * self.spacing * self.config.range_scale + self.config.range_offset_m)
            returns.append(dict(_index=b, native_bin=float(self.axis[b]), provisional_range_m=distance,
                                peak_receivers=sorted(p['rx'] for p in group),
                                contrast_db=max(p['contrast'] for p in group),
                                power_db=float(10 * np.log10(max(best['power'], 1e-12)))))
        return returns

    def _direction(self, covariance, power, b, peak_receivers):
        diag = np.maximum(np.diag(covariance).real, 1e-12)
        coherence = [float(np.clip(abs(covariance[a, j]) / np.sqrt(diag[a] * diag[j]), 0, 1))
                     for a, j in ((0, 1), (0, 2), (1, 2))]
        contrasts = self._contrast(power, b)
        support = np.flatnonzero(contrasts >= self.settings.contrast_db) + 1
        response = np.maximum(np.einsum('ak,ab,bk->k', self.mapper.weights.conj(), covariance,
                                        self.mapper.weights, optimize=True).real, 0)
        peak = int(response.argmax())
        fit = float(response[peak] / max(float(np.trace(covariance).real), 1e-12))
        e, a = np.unravel_index(peak, (len(self.mapper.elevations), len(self.mapper.azimuths)))
        half = (response >= response[peak] / 2).reshape(len(self.mapper.elevations), len(self.mapper.azimuths))
        ei, ai = np.flatnonzero(half.any(axis=1)), np.flatnonzero(half.any(axis=0))
        width = [float(self.mapper.azimuths[ai[-1]] - self.mapper.azimuths[ai[0]]),
                 float(self.mapper.elevations[ei[-1]] - self.mapper.elevations[ei[0]])]
        reasons = []
        if len(peak_receivers) < 3:
            reasons.append('unmatched_receiver_peaks')
        if len(support) < 3:
            reasons.append('insufficient_three_rx_support')
        if min(coherence) < self.settings.minimum_coherence:
            reasons.append('incoherent_or_mixed_returns')
        if fit < self.settings.minimum_fit:
            reasons.append('poor_array_model_fit')
        if e in (0, len(self.mapper.elevations) - 1) or a in (0, len(self.mapper.azimuths) - 1):
            reasons.append('angle_search_boundary')
        if self.axis[b] * self.spacing * self.config.range_scale + self.config.range_offset_m <= 0:
            reasons.append('nonpositive_provisional_range')
        xyz = azimuth = elevation = None
        if not reasons:
            azimuth, elevation = float(self.mapper.azimuths[a]), float(self.mapper.elevations[e])
            az, el = np.radians([azimuth, elevation])
            distance = self.axis[b] * self.spacing * self.config.range_scale + self.config.range_offset_m
            xyz = [float(distance * np.sin(az) * np.cos(el)), float(distance * np.cos(az) * np.cos(el)),
                   float(distance * np.sin(el))]
        return dict(xyz=xyz, azimuth_deg=azimuth, elevation_deg=elevation,
                    direction_status='provisional_3d' if xyz is not None else 'unresolved',
                    direction_reasons=reasons, phase_receivers=support.tolist(),
                    min_coherence=min(coherence), model_fit=fit, angular_width_deg=width)


def parser_counters(parser):
    return tuple(getattr(parser, name) for name in ('bad_crc', 'bad_headers', 'gaps', 'restarts', 'discarded_bytes'))


def iter_results(config, *, recording=None, port=None, output=None, settings=None,
                 seconds=None, stop=None, paced=False):
    """Same causal DSP for replay, live CLI and GUI. Raw bytes precede DSP.

    Terminal events always withdraw current returns. Replay integrity failures
    are recorded as uncertain, not silently accepted. Partial serial tails are
    retained on live stop; a partial replay file is an integrity failure.
    """
    from .acquisition import Source
    from .storage import Recorder
    if bool(recording) == bool(port):
        raise ValueError('Supply exactly one recording or serial port')
    if seconds is not None and (not np.isfinite(seconds) or seconds <= 0):
        raise ValueError('Duration must be finite and positive')
    if recording:
        original = load_config(Path(recording) / 'config.json')
        for key in ('profile_id', 'samples', 'chirps', 'sample_rate_hz', 'slope_hz_s',
                    'discard_chirps', 'frame_interval_s'):
            if getattr(original, key) != getattr(config, key):
                raise ValueError(f'Replay acquisition configuration differs: {key}')
    detector = Obstacle3DDetector(config, settings)
    recorder = log = source = None
    out = Path(output) if output else None
    counts = dict(frames=0, windows=0, persistent_returns=0, provisional_3d=0, unresolved=0)
    quality_events = {}
    timings = []
    complete, terminal = False, 'interrupted'
    try:
        if out:
            if port:
                recorder = Recorder(out, config, dict(label='unknown', detector='per_rx_obstacle_3d_v1'))
            else:
                out.mkdir(parents=True, exist_ok=False)
                config.save(out / 'config.json')
            log = (out / 'obstacles3d.jsonl').open('x')
            (out / 'settings.json').write_text(json.dumps(asdict(detector.settings), indent=2))
        source = Source(config, port=port, recording=recording)
        source.transport_recorder = recorder
        previous_parser = parser_counters(source.parser)
        start = last = time.monotonic()
        anchor = device_anchor = None
        elapsed = 0.
        deadline = start
        while stop is None or not stop.is_set():
            if seconds is not None and time.monotonic() - start >= seconds:
                terminal = 'duration_ended'
                complete = counts['windows'] > 0 and not quality_events and not detector.latched
                break
            try:
                frame = source.read()
            except StopIteration:
                terminal = 'recording_ended'
                complete = (counts['windows'] > 0 and not quality_events
                            and not source.parser.buffer and not any(parser_counters(source.parser)))
                if not complete:
                    damaged = source.parser.buffer or any(parser_counters(source.parser)) or quality_events
                    terminal = 'recording_integrity_failure' if damaged else 'empty_or_short_recording'
                break
            now = time.monotonic()
            if frame is None:
                if now - last > max(1., 5 * config.frame_interval_s):
                    terminal = 'serial_timeout'
                    break
                continue
            last = now
            counts['frames'] += 1
            if recorder:
                recorder.write(frame)
            counters = parser_counters(source.parser)
            if counters != previous_parser:
                if counters[3] != previous_parser[3]:
                    detector.latched = True
                previous_parser = counters
                result = detector.invalidate('transport_discontinuity', frame)
                # Do not allow persistence to bridge rejected transport bytes.
                detector.previous = frame
            else:
                before = time.perf_counter()
                result = detector.push(frame)
                timings.append((time.perf_counter() - before) * 1000)
            if port:
                if anchor is None:
                    anchor, device_anchor = now, frame.timestamp_us
                else:
                    elapsed += ((frame.timestamp_us - device_anchor) & 0xffffffff) / 1e6
                    device_anchor = frame.timestamp_us
                if abs((now - anchor) - elapsed) > .5 or len(source.pending) > 2:
                    result = detector.invalidate('serial_backlog_or_timing_mismatch', frame)
            if result is not None:
                if not result['complete_window']:
                    quality_events[result['reason']] = quality_events.get(result['reason'], 0) + 1
                if result['complete_window']:
                    counts['windows'] += 1
                    for item in result['returns']:
                        if item['persistent']:
                            counts['persistent_returns'] += 1
                            counts['provisional_3d' if item['xyz'] is not None else 'unresolved'] += 1
                if log:
                    log.write(json.dumps(result, allow_nan=False) + '\n')
                    log.flush()
                yield result
            if paced and recording:
                deadline += config.frame_interval_s
                delay = max(0., deadline - time.monotonic())
                if stop is not None:
                    stop.wait(delay)
                elif delay:
                    time.sleep(delay)
        else:
            terminal = 'stopped'
        tail = len(detector.powers)
        result = detector.invalidate(terminal)
        if log:
            log.write(json.dumps(result, allow_nan=False) + '\n')
        yield result
    except Exception:
        terminal, complete = 'acquisition_error', False
        raise
    finally:
        cleanup_errors = []
        for resource in (source, recorder, log):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    cleanup_errors.append(str(error))
        if cleanup_errors:
            terminal, complete = 'resource_close_failure', False
        if out and log:
            report = dict(schema=1, complete=complete, terminal_reason=terminal, **counts,
                          quality_events=quality_events,
                          cleanup_errors=cleanup_errors,
                          config=asdict(config), settings=asdict(detector.settings),
                          processing_ms_p50_p95=np.percentile(timings, [50, 95]).tolist() if timings else [],
                          discarded_tail_frames=len(detector.powers) if 'tail' not in locals() else tail,
                          angular_calibration_verified=False,
                          limitations='Experimental reflector candidates, not glass identity or certified clear path. '
                          'XYZ is unvalidated sensor-relative position. One direction per range cluster; '
                          'mixed same-range returns may be unresolved. No world map or moving-board validation. '
                          'Relative USB timing cannot establish absolute freshness without a firmware handshake.')
            if recording:
                raw = Path(recording) / 'frames.grd'
                digest = hashlib.sha256()
                with raw.open('rb') as handle:
                    for chunk in iter(lambda: handle.read(65536), b''):
                        digest.update(chunk)
                report['raw_sha256'] = digest.hexdigest()
            (out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False))
