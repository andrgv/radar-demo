from collections import deque
from dataclasses import dataclass
import numpy as np
from .config import C


@dataclass
class Detection:
    range_m: float
    velocity_mps: float | None
    azimuth_deg: float
    elevation_deg: float
    xyz: tuple
    snr_db: float
    power_db: float
    moving: bool
    angle_valid: bool


@dataclass
class PhaseProbe:
    range_bin: int
    selected_range_m: float
    azimuth_deg: float
    elevation_deg: float
    xyz: tuple
    min_coherence: float
    snr_db: float
    threshold_db: float
    local_peak: bool
    angle_valid: bool
    relative_phase_deg: tuple = (float("nan"), float("nan"))

    @property
    def rejection_reason(self):
        if not self.angle_valid:
            return "phase does not give a valid direction"
        if self.min_coherence < 0.9:
            return "channel coherence below 0.90"
        if self.snr_db < self.threshold_db:
            return f"weak/unisolated return: {self.snr_db:.1f} dB < {self.threshold_db:.1f} dB"
        if not self.local_peak:
            return "selected bin is not a local range peak"
        return ""

    @property
    def usable(self):
        return not self.rejection_reason


@dataclass
class Result:
    sequence: int
    timestamp_us: int
    ranges: np.ndarray
    velocities: np.ndarray
    profile_db: np.ndarray
    doppler_db: np.ndarray
    azimuths: np.ndarray
    heatmap_db: np.ndarray
    detections: list
    features: dict
    calibrated: bool
    phase_probe: PhaseProbe | None = None
    background_subtracted: bool = False
    spatial_volume: object = None
    doppler_unit: str = 'cycles/chirp (uniform spacing unverified)'


def range_fft(adc, config):
    samples = adc[config.discard_chirps:].astype(float)
    samples -= samples.mean(axis=1, keepdims=True)
    window = np.hanning(config.samples)
    return np.fft.rfft(samples * window[None, :, None], axis=1) * (2 / window.sum()) * config.gains


def estimate_angle(channels, config):
    relative = channels[1:] * np.conj(channels[0])
    phase = np.angle(relative)
    geometry = config.array_geometry
    baselines = geometry[1:] - geometry[0]
    direction = np.linalg.solve(2 * np.pi * baselines, phase)
    valid = bool(np.dot(direction, direction) <= 1 and np.min(abs(channels)) > 1e-8)
    if not valid:
        return float("nan"), float("nan"), (float("nan"),) * 3, False
    horizontal, vertical = direction
    forward = np.sqrt(max(0, 1 - horizontal**2 - vertical**2))
    azimuth = np.degrees(np.arctan2(horizontal, forward))
    elevation = np.degrees(np.arcsin(vertical))
    return float(azimuth), float(elevation), (float(horizontal), float(forward), float(vertical)), True


def coherent_channels(channels):
    """Preserve relative phase without averaging away common chirp phase."""
    return np.mean(channels * channels[:, :1].conj(), axis=0)


def interpolated_range(power, range_bin, config):
    if not 1 <= range_bin < len(power) - 1:
        return float(config.ranges[range_bin])
    left, center, right = np.log(np.maximum(power[range_bin - 1:range_bin + 2], 1e-12))
    curvature = left - 2 * center + right
    offset = np.clip(0.5 * (left - right) / curvature, -0.5, 0.5) if curvature < -1e-12 else 0.0
    return float(config.ranges[range_bin] + offset * (config.ranges[1] - config.ranges[0]))


def noise_threshold(power, factor):
    threshold = np.empty_like(power)
    for index in range(len(power)):
        indices = np.arange(max(1, index - 10), min(len(power) - 1, index + 11))
        indices = indices[abs(indices - index) > 2]
        noise = np.median(power[indices]) if len(indices) else np.median(power)
        threshold[index] = max(float(noise), 1e-10) * factor
    return threshold


def range_doppler_peaks(power, thresholds):
    """Thresholded 3x3 local maxima, with circular Doppler but bounded range.

    Adjacent equal maxima choose the lowest flattened index, including across
    the Doppler seam. The supplied thresholds are empirical, not a Pfa model.
    """
    doppler_count, range_count = power.shape
    peaks = []
    for doppler_bin, offset in np.argwhere(power[:, 2:-1] > thresholds[:, 2:-1]):
        range_bin = int(offset + 2)
        doppler_bin = int(doppler_bin)
        rows = np.array([(doppler_bin - 1) % doppler_count, doppler_bin,
                         (doppler_bin + 1) % doppler_count])
        columns = np.arange(range_bin - 1, range_bin + 2)
        local = power[rows[:, None], columns]
        peak = power[doppler_bin, range_bin]
        if peak <= 0 or peak < local.max():
            continue
        indices = rows[:, None] * range_count + columns
        if doppler_bin * range_count + range_bin != indices[local == peak].min():
            continue
        peaks.append((doppler_bin, range_bin))
    return peaks


def moving_noise_thresholds(power, factor):
    """Separable median gates in range and circular Doppler, in power units.

    Use the larger gate so a quiet Doppler row cannot promote the sidelobes of
    a strong return in the same range cell. Exclude the central three Doppler
    bins from both detection and Doppler training. Two guard bins protect the
    CUT in each direction. No available Doppler references means no detection.
    """
    thresholds = np.array([noise_threshold(row, factor) for row in power])
    count = len(power)
    indices = np.arange(count)
    central = abs(indices - count // 2) <= 1
    for index in indices:
        distance = abs(indices - index)
        circular_distance = np.minimum(distance, count - distance)
        training = (circular_distance > 2) & ~central
        if central[index] or not training.any():
            thresholds[index] = np.inf
        else:
            doppler_noise = np.maximum(np.median(power[training], axis=0), 1e-10)
            thresholds[index] = np.maximum(thresholds[index], doppler_noise * factor)
    return thresholds


class Processor:
    def __init__(self, config, phase_probe_range=None, background=None, spatial_map=False, point_cloud=False):
        self.config = config.validate()
        from .spatial import SpatialMapper
        self.spatial_mapper = SpatialMapper(config) if spatial_map or point_cloud else None
        from .pointcloud import CloudProcessor
        self.cloud_processor=CloudProcessor(config) if point_cloud else None
        self.background = background
        if background is not None:
            background.validate(config)
        self.history = deque(maxlen=30)
        self.last_sequence = None
        self.angles = np.linspace(-60, 60, 121)
        radians = np.radians(self.angles)
        geometry = config.array_geometry
        self.steering = np.exp(2j * np.pi * geometry[:, 0, None] * np.sin(radians))
        self.probe_bin = None
        if phase_probe_range is not None:
            if not np.isfinite(phase_probe_range) or not config.ranges[2] <= phase_probe_range <= config.ranges[-2]:
                raise ValueError("Phase probe range outside usable FFT bins")
            self.probe_bin = int(np.argmin(abs(config.ranges - phase_probe_range)))

    def process(self, frame):
        config = self.config
        if (frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3)
                or not frame.flags & 1):
            raise ValueError("Frame/configuration mismatch; refusing incorrect axes")
        if self.last_sequence is not None and ((frame.sequence - self.last_sequence) & 0xffffffff) != 1:
            self.history.clear()
        self.last_sequence = frame.sequence
        spectrum = range_fft(frame.adc, config)
        if self.background is not None:
            spectrum = self.background.subtract(spectrum, config)
        # Mix snapshots BEFORE covariance; mixing an already reduced cross-vector
        # is not equivalent when the calibration has cross-channel terms.
        angle_spectrum = spectrum @ config.angle_matrix.T
        power = np.mean(abs(spectrum)**2, axis=(0, 2))
        slow_window = np.hanning(len(spectrum))
        doppler = np.fft.fftshift(np.fft.fft(spectrum * slow_window[:, None, None], axis=0), axes=0) / slow_window.sum()
        rd_power = np.mean(abs(doppler)**2, axis=2)
        velocities = np.fft.fftshift(np.fft.fftfreq(len(spectrum)))
        if config.velocity_scale_verified:
            velocities = velocities / config.chirp_interval_s * C / (2 * config.carrier_hz)
        center = len(spectrum) // 2
        moving_spectrum = spectrum - spectrum.mean(axis=0, keepdims=True)
        moving_fft = np.fft.fftshift(np.fft.fft(moving_spectrum * slow_window[:, None, None], axis=0), axes=0) / slow_window.sum()
        unmasked_moving_power = np.mean(abs(moving_fft)**2, axis=2)
        moving_power = unmasked_moving_power.copy()
        moving_power[max(0, center - 1):center + 2] = 0
        thresholds = noise_threshold(power, 10**(config.snr_db / 10))
        moving_profile = moving_power.max(axis=0)
        if config.moving_detector == "range_doppler":
            moving_thresholds = moving_noise_thresholds(unmasked_moving_power, 10**(config.snr_db / 10))
            # Keep the unmasked neighbors for peak tests: zeroing the notch can
            # turn the skirt of a central lobe into a false peak at its edge.
            moving_peaks = range_doppler_peaks(unmasked_moving_power, moving_thresholds)
        else:
            profile_thresholds = noise_threshold(moving_profile, 10**(config.snr_db / 10))
            moving_thresholds = np.broadcast_to(profile_thresholds, moving_power.shape)
            moving_peaks = [(int(moving_power[:, r].argmax()), r)
                for r in range(2, len(power) - 1)
                if moving_profile[r] > profile_thresholds[r]
                and moving_profile[r] >= max(moving_profile[r - 1], moving_profile[r + 1])]
        moving_by_range = {}
        for doppler_bin, range_bin in moving_peaks:
            moving_by_range.setdefault(range_bin, []).append(doppler_bin)
        probe = None
        if self.probe_bin is not None:
            range_bin = self.probe_bin
            radius = config.probe_search_bins
            if radius:
                lower = max(2, range_bin - radius)
                upper = min(len(power) - 2, range_bin + radius)
                peaks = [index for index in range(lower, upper + 1)
                    if power[index] >= max(power[index - 1], power[index + 1])]
                if peaks:
                    range_bin = max(peaks, key=lambda index: power[index])
            channels = angle_spectrum[:, range_bin]
            channel_power = np.mean(abs(channels)**2, axis=0)
            cross = coherent_channels(channels)
            coherence = abs(cross) / np.sqrt(np.maximum(channel_power * channel_power[0], 1e-20))
            azimuth, elevation, direction, valid = estimate_angle(cross, config)
            distance = interpolated_range(power, range_bin, config) if radius else float(config.ranges[range_bin])
            probe = PhaseProbe(range_bin, distance, azimuth, elevation,
                tuple(distance * value for value in direction), float(np.clip(np.min(coherence), 0, 1)),
                float(10 * np.log10(max(power[range_bin], 1e-12) /
                    max(thresholds[range_bin] / 10**(config.snr_db / 10), 1e-12))), config.snr_db,
                bool(power[range_bin] >= max(power[range_bin - 1], power[range_bin + 1])), valid,
                tuple(float(value) for value in np.degrees(np.angle(
                    coherent_channels(spectrum[:, range_bin])[1:]))))
        detections = []
        for range_bin in range(2, len(power) - 1):
            static_peak = (power[range_bin] >= thresholds[range_bin] and
                power[range_bin] >= max(power[range_bin - 1], power[range_bin + 1]))
            if not static_peak and range_bin not in moving_by_range:
                continue
            static_channels = spectrum[:, range_bin].mean(axis=0)
            static_power = float(np.mean(abs(static_channels)**2))
            candidates = []
            if static_peak and static_power > max(thresholds[range_bin] * 0.5, moving_profile[range_bin] * 0.1):
                # The coherent mean selects zero Doppler. A covariance over all
                # chirps also includes movers and biases a co-range static AoA.
                candidates.append((False, center, config.angle_matrix @ static_channels,
                                   static_power, thresholds[range_bin]))
            for moving_bin in moving_by_range.get(range_bin, []):
                candidates.append((True, moving_bin, config.angle_matrix @ moving_fft[moving_bin, range_bin],
                                   float(moving_power[moving_bin, range_bin]), moving_thresholds[moving_bin, range_bin]))
            for moving, doppler_bin, channels, peak_power, threshold in candidates:
                azimuth, elevation, direction, valid = estimate_angle(channels, config)
                range_profile = power
                if moving:
                    range_profile = (moving_power[doppler_bin] if config.moving_detector == "range_doppler"
                                     else moving_profile)
                distance = interpolated_range(range_profile, range_bin, config)
                velocity=(float(velocities[doppler_bin]) if moving else 0.0) if config.velocity_scale_verified else None
                detections.append(Detection(distance, velocity,
                    azimuth, elevation, tuple(distance * value for value in direction),
                    float(10 * np.log10(max(peak_power, 1e-12) / max(threshold / 10**(config.snr_db / 10), 1e-12))),
                    float(10 * np.log10(max(peak_power, 1e-12))), moving, valid))
        beam = np.einsum("cra,ak->crk", angle_spectrum, self.steering.conj(), optimize=True) / 3
        heatmap = np.mean(abs(beam)**2, axis=0)
        self.history.append(power.copy())
        peak = int(np.argmax(power[2:]) + 2)
        history = np.asarray(self.history)
        temporal_cv = float(np.std(history[:, peak]) / max(np.mean(history[:, peak]), 1e-10))
        weights = power / max(power.sum(), 1e-10)
        angles_weights = heatmap[peak] / max(heatmap[peak].sum(), 1e-10)
        angle_mean = float(angles_weights @ self.angles)
        phase_delta = np.angle(spectrum[1:, peak] * np.conj(spectrum[:-1, peak]))
        features = {
            "peak_range_m": interpolated_range(power, peak, config),
            "reflection_db": float(10 * np.log10(max(power[peak], 1e-12))),
            "range_entropy": float(-np.sum(weights * np.log(weights + 1e-12))),
            "angular_width_deg": float(np.sqrt(angles_weights @ (self.angles - angle_mean)**2)),
            "temporal_cv": temporal_cv,
            "temporal_frames": len(history),
            "phase_consistency": float(abs(np.mean(np.exp(1j * phase_delta)))),
            "late_energy_ratio": float(power[peak + 3:].sum() / max(power[peak], 1e-10)),
            "moving_energy_fraction": float(moving_power.sum() / max(rd_power.sum(), 1e-10)),
            "saturation_fraction": float(np.mean((frame.adc == 0) | (frame.adc == 65535))),
        }
        spatial_volume=self.spatial_mapper.process(spectrum) if self.spatial_mapper is not None else None
        if spatial_volume is not None and self.cloud_processor is not None:
            spatial_volume.point_cloud=self.cloud_processor.process(spectrum)
        return Result(frame.sequence, frame.timestamp_us, config.ranges, velocities,
            10 * np.log10(power + 1e-12), 10 * np.log10(rd_power + 1e-12),
            self.angles, 10 * np.log10(heatmap + 1e-12), detections, features, config.verified, probe,
            self.background is not None,
            spatial_volume, 'm/s' if config.velocity_scale_verified else 'cycles/chirp (uniform spacing unverified)')
