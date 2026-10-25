import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from radar.calibration import calibrate_channels
from radar.config import Config
from radar.diagnostics import diagnose
from radar.processing import noise_threshold, range_fft
from radar.storage import replay


def main():
    parser = argparse.ArgumentParser(description="Review a recorded phase reference without applying corrections")
    parser.add_argument("recording", type=Path)
    parser.add_argument("--distance", type=float, required=True)
    arguments = parser.parse_args()
    config = Config.load(arguments.recording / "config.json")
    frames = list(replay(arguments.recording))
    if not frames:
        raise ValueError("Recording contains no complete frames")
    spectra = np.array([range_fft(frame.adc, config) for frame in frames])
    power_by_frame = np.mean(abs(spectra)**2, axis=(1, 3))
    power = power_by_frame.mean(axis=0)
    range_bin = int(np.argmin(abs(config.ranges - arguments.distance)))
    samples = spectra[:, :, range_bin, :].reshape(-1, 3)
    cross = np.mean(samples * samples[:, :1].conj(), axis=0)
    channel_power = np.mean(abs(samples)**2, axis=0)
    coherence = abs(cross) / np.sqrt(np.maximum(channel_power * channel_power[0], 1e-20))
    frame_cross = np.mean(spectra[:, :, range_bin] * spectra[:, :, range_bin, :1].conj(), axis=1)
    phase_deg = np.degrees(np.angle(frame_cross[:, 1:]))
    contrast_db = float(10 * np.log10(max(power[range_bin], 1e-12) /
        max(noise_threshold(power, 1)[range_bin], 1e-12)))
    report = diagnose(arguments.recording)
    report.update({"surveyed_range_m": arguments.distance, "selected_bin": range_bin,
        "selected_cell_signal_background_db": contrast_db, "relative_rx_coherence": coherence.tolist(),
        "relative_rx_phase_deg": np.degrees(np.angle(cross)).tolist(),
        "new_correction_saved": False})
    try:
        calibrate_channels(frames, config, arguments.distance)
        report["calibration_check"] = "passes software quality checks; no correction saved or angular validation implied"
    except ValueError as error:
        report["calibration_check"] = "REJECTED: " + str(error)
    output = Path("artifacts") / (arguments.recording.name + "-review")
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    figure, axes = plt.subplots(2, 1, figsize=(11, 8), layout="constrained")
    per_rx = np.mean(abs(spectra)**2, axis=(0, 1))
    for receiver in range(3):
        axes[0].plot(config.ranges, 10 * np.log10(per_rx[:, receiver] + 1e-12), label=f"RX{receiver + 1}")
    axes[0].axvline(config.ranges[range_bin], color="red", linestyle="--", label=f"Selected bin {range_bin}")
    axes[0].set(xlabel="Empirically corrected range (m)", ylabel="Power (dB ADC squared)",
        title=f"{arguments.recording.name}: selected cell contrast {contrast_db:.1f} dB")
    axes[0].legend()
    axes[1].plot(phase_deg[:, 0], label="RAW RX2-RX1 phase")
    axes[1].plot(phase_deg[:, 1], label="RAW RX3-RX1 phase")
    axes[1].set(xlabel="Recorded frame", ylabel="Wrapped phase (degrees)", ylim=(-180, 180),
        title="Raw channel phase: not calibrated azimuth/elevation")
    axes[1].legend()
    figure.savefig(output / "review.png", dpi=150)
    plt.close(figure)
    print(json.dumps({key: report[key] for key in ["frames", "selected_bin", "selected_cell_signal_background_db",
        "relative_rx_coherence", "sequence_gaps", "device_error_counter_increase", "calibration_check",
        "new_correction_saved"]}, indent=2))


if __name__ == "__main__":
    main()
