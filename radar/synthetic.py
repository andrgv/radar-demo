from dataclasses import dataclass
import numpy as np
from .config import C
from .protocol import Frame


@dataclass
class Target:
    range_m: float
    velocity_mps: float = 0.0
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    amplitude: float = 1800.0


def generate(config, sequence=1, targets=None, noise=15.0, seed=None, channel_response=None):
    if targets is None:
        targets = [Target(float(config.ranges[7]), azimuth_deg=-20, elevation_deg=10),
                   Target(float(config.ranges[17]), velocity_mps=0.35, azimuth_deg=30, elevation_deg=-8, amplitude=1300)]
    rng = np.random.default_rng(seed)
    samples = np.arange(config.samples)[None, :, None] / config.sample_rate_hz
    chirps = np.arange(config.chirps)[:, None, None] * config.chirp_interval_s
    geometry = config.array_geometry
    signal = np.full((config.chirps, config.samples, 3), 32768.0)
    response = np.ones(3, dtype=complex) if channel_response is None else np.asarray(channel_response)
    for target in targets:
        azimuth, elevation = np.radians([target.azimuth_deg, target.elevation_deg])
        direction = np.array([np.sin(azimuth) * np.cos(elevation), np.sin(elevation)])
        spatial_phase = 2 * np.pi * (geometry @ direction)[None, None, :]
        beat = 2 * config.slope_hz_s * (target.range_m - config.range_offset_m) / (C * config.range_scale)
        doppler = 2 * target.velocity_mps * config.carrier_hz / C
        phase = 2 * np.pi * (beat * samples + doppler * chirps) + spatial_phase
        signal += target.amplitude * np.real(np.exp(1j * phase) * response[None, None, :])
    signal += rng.normal(0, noise, signal.shape)
    adc = np.clip(np.rint(signal), 0, 65535).astype("<u2")
    return Frame(sequence, int(sequence * config.frame_interval_s * 1e6) & 0xffffffff, config.profile_id, adc)
