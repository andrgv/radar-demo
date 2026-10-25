import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from radar.config import Config
from radar.diagnostics import diagnose
from radar.processing import Processor, range_fft
from radar.storage import replay


def summarize(directory, surveyed_range):
    config = Config.load(directory / "config.json")
    frames = list(replay(directory))
    spectra = np.array([range_fft(frame.adc, config) for frame in frames])
    powers = np.mean(abs(spectra)**2, axis=(1, 3))
    mean_power = powers.mean(axis=0)
    peak_bin = int(np.argmax(mean_power[2:-1]) + 2)
    log_power = np.log(mean_power + 1e-12)
    curvature = log_power[peak_bin - 1] - 2 * log_power[peak_bin] + log_power[peak_bin + 1]
    offset = 0.5 * (log_power[peak_bin - 1] - log_power[peak_bin + 1]) / curvature
    interpolated_bin = peak_bin + float(np.clip(offset, -0.5, 0.5))
    coherent_power = np.mean(abs(spectra.mean(axis=1))**2, axis=2)
    processor = Processor(config)
    detections = [processor.process(frame).detections for frame in frames]
    result = diagnose(directory)
    result.update({"recording": str(directory), "surveyed_range_m": surveyed_range,
        "mean_spectrum_peak_bin": peak_bin,
        "log_parabolic_peak_bin": interpolated_bin,
        "configured_integer_peak_range_m": float(config.ranges[peak_bin]),
        "configured_interpolated_peak_range_m": float(np.interp(interpolated_bin, np.arange(len(config.ranges)), config.ranges)),
        "median_coherent_power_fraction": float(np.median(coherent_power[:, peak_bin] / powers[:, peak_bin])),
        "target_integer_bin_detection_frames": sum(any(int(np.argmin(abs(config.ranges - item.range_m))) == peak_bin for item in items) for items in detections)})
    return result, mean_power, np.mean(abs(spectra)**2, axis=(0, 1))


def main():
    output = Path("artifacts/plate-comparison")
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    figure, axes = plt.subplots(2, 3, figsize=(16, 8), layout="constrained")
    for column, (name, surveyed) in enumerate((("plate_0_6m", 0.6), ("plate_1_3m", 1.3), ("plate_2m", 2.0))):
        report, combined, per_rx = summarize(Path("recordings") / name, surveyed)
        reports.append(report)
        for receiver in range(3):
            axes[0, column].plot(10 * np.log10(per_rx[:, receiver] + 1e-12), label=f"RX{receiver + 1}")
        axes[0, column].set(title=f"Plate at {surveyed:.1f} m: per-RX mean spectra", xlabel="FFT bin", ylabel="Power (dB ADC squared)", xlim=(0, 32))
        axes[0, column].legend()
        axes[1, column].plot(10 * np.log10(combined + 1e-12), "o-")
        axes[1, column].axvline(report["log_parabolic_peak_bin"], color="tab:red", label="Interpolated main peak")
        axes[1, column].set(title=f"Main bin {report['mean_spectrum_peak_bin']}; interpolated {report['log_parabolic_peak_bin']:.3f}", xlabel="FFT bin (not calibrated metres)", ylabel="Power (dB ADC squared)", xlim=(0, 12))
        axes[1, column].legend()
    measured = np.array([report["configured_interpolated_peak_range_m"] for report in reports])
    truth = np.array([report["surveyed_range_m"] for report in reports])
    scale = float((truth[1] - truth[0]) / (measured[1] - measured[0]))
    offset = float(truth[0] - scale * measured[0])
    summary = {"sessions": reports,
        "heldout_2m_prediction_m": float(scale * measured[2] + offset),
        "heldout_2m_error_m": float(scale * measured[2] + offset - truth[2]),
        "diagnostic_two_point_fit": {"scale": scale, "offset_m": offset,
            "status": "Fit uses 0.6/1.3 m only; 2 m is held out. Pilot range calibration; RF, velocity and angles remain unverified."}}
    (output / "report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    figure.savefig(output / "spectra.png", dpi=150)
    plt.close(figure)
    print(json.dumps({"sessions": [{key: report[key] for key in (
        "recording", "frames", "surveyed_range_m", "mean_spectrum_peak_bin", "log_parabolic_peak_bin",
        "configured_integer_peak_range_m", "configured_interpolated_peak_range_m",
        "median_coherent_power_fraction", "target_integer_bin_detection_frames", "sequence_gaps")}
        for report in reports], "diagnostic_two_point_fit": summary["diagnostic_two_point_fit"],
        "heldout_2m_prediction_m": summary["heldout_2m_prediction_m"],
        "heldout_2m_error_m": summary["heldout_2m_error_m"]}, indent=2))


if __name__ == "__main__":
    main()
