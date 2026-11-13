"""Simultaneous experimental range and RX2 azimuth, with live USB or replay.

Example (reference and target share the same known height):
python -m radar.range_azimuth --replay recordings/box-angle-01/check_right \
  --reference recordings/box-angle-01/center_repeat --reference-xyz 0 2 -.1125 \
  --min-range 1.5 --max-range 2.5 --plot

The strongest local range peak in the requested interval is the candidate.
This does not identify an object or estimate elevation. Reference calibration
requires unchanged mounting, acquisition settings and channel response. The
existing recordings validate azimuth only locally near 2 m and at fixed height.
"""
from collections import deque
from pathlib import Path
import argparse
import json
import time
import numpy as np
from radar.angle_lab import infer_azimuth_rx2
from radar.background import SpectralBackground
from radar.config import Config
from radar.processing import range_fft, noise_threshold, interpolated_range
from radar.storage import replay


def check_acquisition(folder, config):
    original = Config.load(Path(folder) / 'config.json')
    for key in ('profile_id', 'samples', 'chirps', 'sample_rate_hz', 'slope_hz_s',
                'carrier_hz', 'discard_chirps', 'chirp_interval_s'):
        if getattr(original, key) != getattr(config, key):
            raise ValueError(f'{folder}: acquisition parameter differs: {key}')


def spectrum(frame, config, background=None):
    if (frame.profile_id != config.profile_id or not frame.flags & 1
            or frame.adc.shape != (config.chirps, config.samples, 3)
            or frame.errors or frame.dropped):
        raise ValueError('Invalid, dropped or incompatible raw ADC frame')
    s = range_fft(frame.adc, config)
    return background.subtract(s, config) if background is not None else s


def statistics(s):
    power = np.mean(abs(s)**2, axis=(0, 1, 3))
    rx_power = np.mean(abs(s)**2, axis=(0, 1))
    cross = np.mean(s[..., 1] * s[..., 0].conj(), axis=(0, 1))
    coherence = np.clip(abs(cross) / np.sqrt(np.maximum(rx_power[:, 0]*rx_power[:, 1], 1e-24)), 0, 1)
    contrast = 10*np.log10(np.maximum(power, 1e-24)/noise_threshold(power, 1))
    return power, np.angle(cross), coherence, contrast


def load_background(folder, config):
    path = Path(folder) / 'spectral-background.npz'
    return SpectralBackground.from_path(path, config) if path.is_file() else None


def load_reference(folder, xyz, config):
    check_acquisition(folder, config)
    xyz = np.asarray(xyz, float)
    if xyz.shape != (3,) or not np.isfinite(xyz).all() or xyz[1] <= 0:
        raise ValueError('Reference needs finite X,Y,Z and positive forward Y')
    background = load_background(folder, config)
    spectra = [spectrum(f, config, background) for f in replay(folder)]
    if len(spectra) < 10:
        raise ValueError('Reference needs at least ten raw frames')
    power, phase, coherence, contrast = statistics(np.asarray(spectra))
    k = int(np.argmin(abs(config.ranges-np.linalg.norm(xyz))))
    if not 2 <= k < len(power)-1:
        raise ValueError('Reference range is outside usable range bins')
    if coherence[k] < .9 or contrast[k] < config.snr_db or power[k] < max(power[k-1], power[k+1]):
        raise ValueError(f'Reference fails quality checks: coherence={coherence[k]:.3f}, contrast={contrast[k]:.1f} dB')
    # Check that the configured receive channel responds to horizontal angle.
    infer_azimuth_rx2(phase[k], phase[k], xyz, config)
    return float(phase[k])


class RangeAzimuth:
    def __init__(self, config, reference_phase, reference_xyz, *, min_range,
                 max_range, window=5, target_z=None, limit_deg=25):
        self.config = config
        self.reference_xyz = np.asarray(reference_xyz, float)
        self.reference_phase = reference_phase
        self.z = float(self.reference_xyz[2] if target_z is None else target_z)
        if (not np.isfinite([min_range, max_range, self.z, limit_deg]).all()
                or not 0 < min_range < max_range or window < 1 or not 0 < limit_deg <= 60):
            raise ValueError('Invalid range, window, height or azimuth bounds')
        self.bins = np.flatnonzero((config.ranges >= min_range) & (config.ranges <= max_range)
                                  & (np.arange(len(config.ranges)) >= 2)
                                  & (np.arange(len(config.ranges)) < len(config.ranges)-1))
        if not len(self.bins):
            raise ValueError('Range interval contains no usable FFT bins')
        self.history = deque(maxlen=window)
        self.limit_deg = limit_deg
        self.last_sequence = None

    def update(self, frame, background=None):
        if self.last_sequence is not None and frame.sequence != self.last_sequence+1:
            self.history.clear()
        self.last_sequence = frame.sequence
        self.history.append(spectrum(frame, self.config, background))
        power, phases, coherence, contrast = statistics(np.asarray(self.history))
        peaks = [k for k in self.bins if power[k] > max(power[k-1], power[k+1])]
        result = dict(sequence=int(frame.sequence), state='NO_TARGET', range_m=None,
                      azimuth_deg=None, x_m=None, y_m=None, assumed_z_m=self.z,
                      coherence_rx2=None, contrast_db=None, reason='No local range peak in search interval',
                      background_subtracted=background is not None, averaged_frames=len(self.history))
        if not peaks:
            return result, power
        k = max(peaks, key=lambda k: power[k])
        distance = interpolated_range(power, k, self.config)
        result.update(range_bin=int(k), range_m=distance, coherence_rx2=float(coherence[k]),
                      contrast_db=float(contrast[k]), candidate_peaks=len(peaks), state='WEAK')
        if contrast[k] < self.config.snr_db or coherence[k] < .9:
            result['reason'] = 'Insufficient contrast or RX2 coherence'
            return result, power
        if distance <= abs(self.z):
            result['reason'] = 'Range incompatible with assumed height'
            return result, power
        horizontal_range = np.sqrt(distance**2-self.z**2)
        forward = horizontal_range
        for _ in range(3):
            az, residual = infer_azimuth_rx2(phases[k], self.reference_phase, self.reference_xyz,
                       self.config, forward_m=forward, z_m=self.z, limit_deg=self.limit_deg)
            forward = horizontal_range*np.cos(np.radians(az))
        if abs(az) >= self.limit_deg-.05 or residual > 1:
            result['reason'] = 'Phase outside configured azimuth model'
            return result, power
        result.update(state='CANDIDATE', azimuth_deg=az, x_m=float(horizontal_range*np.sin(np.radians(az))),
                      y_m=float(forward), phase_residual_deg=residual, reason='Strongest peak in search interval')
        return result, power


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--port')
    source.add_argument('--replay')
    p.add_argument('--config', default='configs/exploratory-roll90-phase.json')
    p.add_argument('--reference', required=True, help='Known-position target recording; optional paired background snapshot used')
    p.add_argument('--reference-xyz', type=float, nargs=3, required=True, metavar=('X','Y','Z'))
    p.add_argument('--target-z', type=float, help='Assumed target height relative to radar; default: reference Z')
    p.add_argument('--background', help='Matching static background recording or NPZ; replay defaults to its saved snapshot')
    p.add_argument('--min-range', type=float, required=True)
    p.add_argument('--max-range', type=float, required=True)
    p.add_argument('--window', type=int, default=5, help='Frames averaged (default 5, about 0.5 s)')
    p.add_argument('--seconds', type=float)
    p.add_argument('--jsonl', help='Save measurements to a new JSONL file')
    p.add_argument('--plot', action='store_true', help='Show live range profile and top-down target position')
    a = p.parse_args(argv)
    if a.seconds is not None and (not np.isfinite(a.seconds) or a.seconds <= 0):
        p.error('--seconds must be positive')
    cfg = Config.load(a.config)
    phase = load_reference(a.reference, a.reference_xyz, cfg)
    estimator = RangeAzimuth(cfg, phase, a.reference_xyz, min_range=a.min_range,
                            max_range=a.max_range, window=a.window, target_z=a.target_z)
    if a.replay:
        check_acquisition(a.replay, cfg)
    background = (SpectralBackground.from_path(a.background, cfg) if a.background
                  else load_background(a.replay, cfg) if a.replay else None)
    from radar.acquisition import Source
    output = None
    src = None
    plt = None
    try:
        if a.jsonl:
            output = open(a.jsonl, 'x', encoding='utf-8')
        if a.plot:
            import matplotlib.pyplot as plt
            plt.ion()
            fig, (profile, plan) = plt.subplots(1, 2, figsize=(11, 5))
            line, = profile.plot(cfg.ranges, np.zeros_like(cfg.ranges))
            profile.set(xlim=(a.min_range, a.max_range), xlabel='Range (m)', ylabel='Power (dB)')
            dot, = plan.plot([], [], 'o')
            plan.set(xlim=(-a.max_range, a.max_range), ylim=(0, a.max_range), xlabel='Right X (m)', ylabel='Forward Y (m)')
            plan.set_aspect('equal'); plan.grid(alpha=.3)
            fig.suptitle(f'Experimental RX2 azimuth | assumed Z = {estimator.z:+.3f} m')
        src = Source(cfg, port=a.port, recording=a.replay)
        print(f'Experimental range + azimuth | assumed Z={estimator.z:+.3f} m | strongest peak in [{a.min_range}, {a.max_range}] m', flush=True)
        start = time.monotonic()
        while a.seconds is None or time.monotonic()-start < a.seconds:
            if plt is not None and not plt.fignum_exists(fig.number):
                break
            try:
                frame = src.read()
            except StopIteration:
                break
            if frame is None:
                if plt is not None:
                    plt.pause(.01)
                continue
            result, power = estimator.update(frame, background)
            r = result['range_m']; az = result['azimuth_deg']
            print(f"{result['state']:9} range={r:.3f} m  az={az:+.2f}°  X={result['x_m']:+.3f} m  Y={result['y_m']:.3f} m" if az is not None
                  else f"{result['state']:9} range={f'{r:.3f} m' if r is not None else '--'}  az=--  {result['reason']}", flush=True)
            if output:
                output.write(json.dumps(result, allow_nan=False)+'\n'); output.flush()
            if plt is not None:
                line.set_ydata(10*np.log10(np.maximum(power, 1e-12))); profile.relim(); profile.autoscale_view(scalex=False)
                dot.set_data([result['x_m']] if az is not None else [], [result['y_m']] if az is not None else [])
                plan.set_title(f"{result['state']} | range {r:.3f} m | az {az:+.2f}°" if az is not None else result['state'])
                fig.canvas.draw_idle(); plt.pause(.01)
            if a.replay:
                time.sleep(cfg.frame_interval_s)
    except KeyboardInterrupt:
        pass
    finally:
        if src is not None:
            src.close()
        if output is not None:
            output.close()
        if plt is not None:
            plt.close(fig)


if __name__ == '__main__':
    main()
