from dataclasses import replace
from pathlib import Path
import zlib
import numpy as np
from .config import Config
from .processing import range_fft
from .protocol import Parser
from .storage import replay


def diagnose(recording):
    config = Config.load(Path(recording) / "config.json")
    neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
    parser = Parser()
    powers = []
    deviations = []
    minima = []
    maxima = []
    peak_counts = np.zeros((3, config.samples // 2 + 1), dtype=int)
    repeated = 0
    previous_crc = None
    first = None
    last = None
    for frame in replay(recording, parser):
        if frame.adc.shape != (config.chirps, config.samples, 3) or frame.profile_id != config.profile_id:
            raise ValueError("Recording dimensions/profile do not match configuration")
        if first is None:
            first = frame
        last = frame
        crc = zlib.crc32(frame.adc.tobytes())
        repeated += int(crc == previous_crc)
        previous_crc = crc
        power = np.mean(abs(range_fft(frame.adc, neutral))**2, axis=0)
        powers.append(power)
        for receiver in range(3):
            peak_counts[receiver, int(np.argmax(power[2:-1, receiver])) + 2] += 1
        deviations.append(np.std(frame.adc.astype(float), axis=1).mean(axis=0))
        minima.append(frame.adc.min(axis=(0, 1)))
        maxima.append(frame.adc.max(axis=(0, 1)))
    if not powers:
        raise ValueError("No complete valid frames in recording")
    mean_power = np.mean(powers, axis=0)
    channels = []
    for receiver in range(3):
        peaks = [index for index in range(2, len(mean_power) - 1)
                 if mean_power[index, receiver] >= max(mean_power[index - 1, receiver], mean_power[index + 1, receiver])]
        peaks = sorted(peaks, key=lambda index: mean_power[index, receiver], reverse=True)[:5]
        dominant = int(np.argmax(peak_counts[receiver]))
        channels.append({"rx": receiver + 1,
            "adc_min": int(np.min(minima, axis=0)[receiver]),
            "adc_max": int(np.max(maxima, axis=0)[receiver]),
            "mean_fast_time_std_counts": float(np.mean(deviations, axis=0)[receiver]),
            "dominant_bin": dominant,
            "dominant_bin_frame_fraction": float(peak_counts[receiver, dominant] / len(powers)),
            "local_spectral_peaks": [{"bin": index,
                "beat_hz_from_config": float(index * config.sample_rate_hz / config.samples),
                "range_m_from_config": float(config.ranges[index]),
                "power_db_adc2": float(10 * np.log10(mean_power[index, receiver] + 1e-12))} for index in peaks]})
    return {"frames": len(powers), "physical_scale_verified": config.verified,
        "interpretation": "Spectral peaks are not identified objects. Unverified config cannot establish distance.",
        "configured_bin_spacing_m": float(config.ranges[1] - config.ranges[0]),
        "configured_nyquist_range_m": float(config.ranges[-1]),
        "consecutive_identical_adc_frames": repeated,
        "recording_crc_errors": parser.bad_crc, "recording_header_errors": parser.bad_headers,
        "sequence_gaps": parser.gaps, "restarts": parser.restarts,
        "device_drop_counter_increase": (last.dropped - first.dropped) & 0xffffffff,
        "device_error_counter_increase": (last.errors - first.errors) & 0xffffffff,
        "channels": channels}
