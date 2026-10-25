from dataclasses import replace
import uuid
import numpy as np

if __name__ == "__main__":
    raise SystemExit(
        "Run calibration from the project root using:\n"
        "  python -m radar calibrate RECORDING OUTPUT_CONFIG --distance METERS\n"
        "For arguments: python -m radar calibrate --help\n"
        "This fits RX gain/phase corrections; it does not calibrate the distance scale."
    )

from .processing import noise_threshold, range_fft


def calibrate_channels(frames, config, distance_m, azimuth_deg=0, elevation_deg=0):
    if not frames:
        raise ValueError("No calibration frames")
    neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
    bin_index = int(np.argmin(abs(config.ranges - distance_m)))
    if not 2 <= bin_index < len(config.ranges) - 1:
        raise ValueError("Calibration target outside usable range")
    spectra = np.concatenate([range_fft(frame.adc, neutral)[:, bin_index] for frame in frames])
    reference_power = np.mean(abs(spectra[:, 0])**2)
    if reference_power < 1e-8:
        raise ValueError("Calibration reference has no signal")
    relative = np.mean(spectra * spectra[:, :1].conj(), axis=0) / reference_power
    coherence = abs(np.mean(spectra * spectra[:, :1].conj(), axis=0)) / np.sqrt(
        np.mean(abs(spectra)**2, axis=0) * reference_power)
    if np.min(coherence) < 0.9 or np.min(abs(relative)) < 1e-6:
        raise ValueError("Unstable/weak calibration target; isolate a stationary reflector")
    all_spectra = np.concatenate([range_fft(frame.adc, neutral) for frame in frames])
    range_power = np.mean(abs(all_spectra)**2, axis=(0, 2))
    background = noise_threshold(range_power, 1.0)[bin_index]
    snr_db = float(10 * np.log10(max(range_power[bin_index], 1e-12) / max(background, 1e-12)))
    if snr_db < config.snr_db:
        raise ValueError(
            f"Calibration return is not sufficiently isolated: local signal/background {snr_db:.1f} dB "
            f"is below {config.snr_db:.1f} dB. High channel coherence alone does not identify the target."
        )
    azimuth, elevation = np.radians([azimuth_deg, elevation_deg])
    direction = [np.sin(azimuth) * np.cos(elevation), np.sin(elevation)]
    geometry = config.array_geometry
    expected = np.exp(2j * np.pi * ((geometry - geometry[0]) @ direction))
    gains = expected / relative
    return replace(config, gains_real=gains.real.tolist(), gains_imag=gains.imag.tolist(),
                   calibration_id=str(uuid.uuid4())).validate()


def fit_range(measured, truth):
    measured, truth = np.asarray(measured), np.asarray(truth)
    if len(measured) < 3 or len(measured) != len(truth) or np.ptp(measured) < 0.3:
        raise ValueError("Use at least three separated measured and surveyed ranges")
    scale, offset = np.polyfit(measured, truth, 1)
    return {"scale": float(scale), "offset_m": float(offset),
            "rms_m": float(np.sqrt(np.mean((measured * scale + offset - truth)**2)))}
