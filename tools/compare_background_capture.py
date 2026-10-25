import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from radar.config import Config
from radar.diagnostics import diagnose
from radar.processing import noise_threshold, range_fft
from radar.storage import replay


def load_capture(path, distance):
    config = Config.load(path / "config.json")
    frames = list(replay(path))
    if not frames:
        raise ValueError(f"No complete frames: {path}")
    spectra = np.array([range_fft(frame.adc, config) for frame in frames])
    power = np.mean(abs(spectra)**2, axis=(0, 1))
    range_bin = int(np.argmin(abs(config.ranges - distance)))
    samples = spectra[:, :, range_bin].reshape(-1, 3)
    channel_power = np.mean(abs(samples)**2, axis=0)
    cross = np.mean(samples * samples[:, :1].conj(), axis=0)
    coherence = abs(cross) / np.sqrt(np.maximum(channel_power * channel_power[0], 1e-20))
    combined = power.mean(axis=1)
    report = diagnose(path)
    report.update({"recording": str(path), "selected_bin": range_bin,
        "selected_cell_power_db_per_rx": (10 * np.log10(power[range_bin] + 1e-12)).tolist(),
        "selected_cell_coherence_relative_rx1": coherence.tolist(),
        "selected_cell_relative_phase_deg": np.degrees(np.angle(cross)).tolist(),
        "selected_cell_local_contrast_db": float(10 * np.log10(max(combined[range_bin], 1e-12) /
            max(noise_threshold(combined, 1)[range_bin], 1e-12)))})
    return config, power, report


def main():
    parser = argparse.ArgumentParser(description="Compare mean ADC spectra; no complex background subtraction or calibration")
    parser.add_argument("empty", type=Path)
    parser.add_argument("added", type=Path)
    parser.add_argument("--distance", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    config, empty_power, empty = load_capture(arguments.empty, arguments.distance)
    added_config, added_power, added = load_capture(arguments.added, arguments.distance)
    if config != added_config:
        raise ValueError("Capture configurations differ; compare like-for-like acquisition and corrections")
    range_bin = empty["selected_bin"]
    changes = 10 * np.log10(np.maximum(added_power, 1e-12) / np.maximum(empty_power, 1e-12))
    report = {"empty": empty, "added_target_and_support": added,
        "selected_cell_power_change_db_per_rx": changes[range_bin].tolist(),
        "selected_cell_combined_power_change_db": float(10 * np.log10(
            added_power[range_bin].mean() / max(empty_power[range_bin].mean(), 1e-12))),
        "interpretation": "Combined effect of target AND metal support. Positive/negative power differences are not isolated target amplitude: coherent addition, cancellation and shadowing can affect them. No phase correction saved."}
    arguments.output.mkdir(parents=True, exist_ok=True)
    (arguments.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    figure, axes = plt.subplots(3, 2, figsize=(13, 9), layout="constrained")
    for receiver in range(3):
        axes[receiver, 0].plot(config.ranges, 10 * np.log10(empty_power[:, receiver] + 1e-12), label="Empty")
        axes[receiver, 0].plot(config.ranges, 10 * np.log10(added_power[:, receiver] + 1e-12), label="Target + bottle")
        axes[receiver, 0].axvline(config.ranges[range_bin], color="gray", linestyle="--")
        axes[receiver, 0].set(title=f"RX{receiver + 1}: recorded mean spectra", xlim=(0, 3),
            xlabel="Empirically corrected range (m)", ylabel="Power (dB ADC squared)")
        axes[receiver, 0].legend()
        axes[receiver, 1].plot(config.ranges, changes[:, receiver], marker=".")
        axes[receiver, 1].axhline(0, color="gray", linewidth=0.8)
        axes[receiver, 1].axvline(config.ranges[range_bin], color="gray", linestyle="--")
        axes[receiver, 1].set(title=f"RX{receiver + 1}: added / empty power ratio", xlim=(0, 3),
            xlabel="Empirically corrected range (m)", ylabel="Change (dB)")
    figure.savefig(arguments.output / "comparison.png", dpi=150)
    plt.close(figure)
    print(json.dumps({"empty_frames": empty["frames"], "added_frames": added["frames"],
        "selected_bin": range_bin, "power_change_db_per_rx": report["selected_cell_power_change_db_per_rx"],
        "combined_power_change_db": report["selected_cell_combined_power_change_db"],
        "added_cell_coherence": added["selected_cell_coherence_relative_rx1"],
        "added_cell_local_contrast_db": added["selected_cell_local_contrast_db"]}, indent=2))


if __name__ == "__main__":
    main()
