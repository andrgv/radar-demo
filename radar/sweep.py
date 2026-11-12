from dataclasses import asdict, replace
import json
from pathlib import Path
import time
import numpy as np
from .background import SpectralBackground
from .config import Config
from .processing import noise_threshold, range_fft
from .storage import Recorder, replay


def sweep_poses(distance, offset, *, full_heldout=False):
    if not np.isfinite(distance) or not np.isfinite(offset) or distance <= 0 or offset <= 0 or offset >= distance:
        raise ValueError("Use positive distance and lateral offset smaller than distance")
    poses = [
        ("center", [0, distance, 0], True), ("left", [-offset, distance, 0], True),
        ("right", [offset, distance, 0], True), ("up", [0, distance, offset], True),
        ("check_right", [offset / 2, distance, 0], False),
        ("center_repeat", [0, distance, 0], False)]
    if full_heldout:
        # Validate both horizontal and vertical signs on positions excluded from fitting.
        poses[-1:-1] = [
            ("check_left", [-offset / 2, distance, 0], False),
            ("check_up", [0, distance, offset / 2], False),
            ("check_down", [0, distance, -offset / 2], False)]
    return [{"name": name, "xyz_m": xyz, "fit": fit} for name, xyz, fit in poses]


def record_sweep(root, config, port, distance, offset, seconds, handheld=False):
    from .acquisition import Source
    from .processing import Processor
    if not np.isfinite(seconds) or seconds < 2:
        raise ValueError("Record at least two seconds at each position")
    poses = sweep_poses(distance, offset, full_heldout=True)
    for pose in poses:
        expected_range = np.linalg.norm(pose["xyz_m"])
        if not config.ranges[2] <= expected_range <= config.ranges[-2]:
            raise ValueError("Sweep position outside usable configured range; adjust distance/offset")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": 1, "coordinate_frame": "right/forward/up, viewed from behind radar toward target",
        "target": "metal bottle alone; no iPad or separate metal support",
        "positions_are_user_placement_labels": True, "handheld": handheld,
        "seconds_per_pose": seconds, "poses": poses}
    (root / "sweep.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    config.save(root / "config.json")
    print("Keep the radar fixed. Use the metal bottle ALONE as the target.")
    print("Right/left are from BEHIND the radar looking toward the target. Keep forward distance fixed.")
    print("Match the bottle's reflecting region to antenna height; UP means raising it by the listed amount.")
    print("Use tape/ruler marks. These positions are labels, not automatically measured ground truth.")
    if handheld:
        print("HANDHELD: pause at each mark; slight movement is expected. Keep your body off to the side.")
        print("Hand/body reflections and approximate positioning prevent precision calibration claims.")

    def capture(name, metadata, background=None):
        processor = Processor(config, background=background) if background else None
        source = None
        if handheld:
            print("Recording starts in 3 seconds; keep your body position steady and pause the bottle at the mark." 
                  if name != "background" else
                  "Recording starts in 3 seconds; bottle absent, keep a similar body position to the holding test.")
        else:
            print("Recording starts in 3 seconds; step away now.")
        time.sleep(3)
        try:
            with Recorder(root / name, config, metadata) as recorder:
                if background is not None:
                    background.save(recorder.path / "spectral-background.npz")
                source = Source(config, port=port)
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    frame = source.read()
                    if frame is not None:
                        recorder.write(frame, processor.process(frame) if processor else None)
                count = recorder.count
        finally:
            if source is not None:
                source.close()
        if count < 10:
            raise ValueError(f"Only {count} frames recorded for {name}; incomplete sweep preserved")
        print(f"Saved {name}: {count} frames")

    background_prompt = ("Remove bottle and iPad; stay near your holding position. Press Enter for background: "
                         if handheld else "Remove bottle and iPad, step aside; press Enter to record EMPTY background: ")
    input(background_prompt)
    capture("background", {"label": "calibration_background", "scene_id": root.name, "handheld_sweep": handheld})
    background = SpectralBackground.from_path(root / "background", config)
    for pose in poses:
        right, forward, up = pose["xyz_m"]
        instruction = "Hold near the mark and press Enter: " if handheld else "Step aside; press Enter: "
        input(f"Place bottle at {pose['name']}: right {right:+.3f} m, forward {forward:.3f} m, "
              f"up {up:+.3f} m from center height. " + instruction)
        capture(pose["name"], {"label": "calibration", "scene_id": root.name,
            "sweep_pose": pose, "handheld_sweep": handheld, "background_method": "fixed_complex_spectrum",
            "background_source": "../background"}, background)
    return analyze_sweep(root)


def analyze_sweep(root):
    root = Path(root)
    manifest = json.loads((root / "sweep.json").read_text(encoding="utf-8"))
    config = Config.load(root / "config.json")
    neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
    background = SpectralBackground.from_path(root / "background", neutral)
    rows = []
    for pose in manifest["poses"]:
        directory = root / pose["name"]
        if not (directory / "frames.grd").exists():
            rows.append({**pose, "accepted": False, "reason": "recording missing"})
            continue
        if Config.load(directory / "config.json") != config:
            raise ValueError(f"Sweep configuration changed at {pose['name']}")
        position = np.asarray(pose["xyz_m"], dtype=float)
        distance = float(np.linalg.norm(position))
        range_bin = int(np.argmin(abs(config.ranges - distance)))
        if not 2 <= range_bin < len(config.ranges) - 1:
            raise ValueError("Sweep position is outside usable configured range bins")
        spectra = []
        for frame in replay(directory):
            if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
                raise ValueError("Sweep frame/configuration mismatch")
            spectra.append(background.subtract(range_fft(frame.adc, neutral), neutral))
        if len(spectra) < 10:
            rows.append({**pose, "accepted": False, "reason": "fewer than ten frames"})
            continue
        spectra = np.asarray(spectra)
        power = np.mean(abs(spectra)**2, axis=(0, 1, 3))
        channels = spectra[:, :, range_bin].reshape(-1, 3)
        channel_power = np.mean(abs(channels)**2, axis=0)
        cross = np.mean(channels * channels[:, :1].conj(), axis=0)
        coherence = abs(cross) / np.sqrt(np.maximum(channel_power * channel_power[0], 1e-20))
        contrast = float(10 * np.log10(max(power[range_bin], 1e-12) /
            max(noise_threshold(power, 1)[range_bin], 1e-12)))
        local_peak = bool(power[range_bin] >= max(power[range_bin - 1], power[range_bin + 1]))
        accepted = bool(np.min(coherence) >= 0.9 and contrast >= config.snr_db and local_peak)
        rows.append({**pose, "frames": len(spectra), "range_bin": range_bin,
            "expected_range_m": distance, "expected_azimuth_deg": float(np.degrees(np.arctan2(position[0], position[1]))),
            "expected_elevation_deg": float(np.degrees(np.arcsin(position[2] / distance))),
            "direction_right_up": (position[[0, 2]] / distance).tolist(),
            "relative_phase_deg": np.degrees(np.angle(cross[1:] * cross[0].conj())).tolist(),
            "min_coherence": float(np.clip(np.min(coherence), 0, 1)), "local_contrast_db": contrast,
            "local_peak": local_peak, "accepted": accepted,
            "reason": "passes reference checks" if accepted else "weak, incoherent or not a local peak"})
    center = next((row for row in rows if row["name"] == "center" and row["accepted"]), None)
    fit_rows = [row for row in rows if row.get("fit") and row["name"] != "center" and row["accepted"]]
    report = {"schema": 1, "synthetic": bool(manifest.get("synthetic", False)), "poses": rows, "calibration_saved": False,
        "handheld": bool(manifest.get("handheld", False)),
        "status": "insufficient accepted positions for angular characterization",
        "limitation": "Position labels are user measurements. This report neither validates world pose nor creates a point-cloud map."}
    if center is not None and len(fit_rows) >= 3:
        origin = np.radians(center["relative_phase_deg"])
        directions = np.array([row["direction_right_up"] for row in fit_rows])
        phases = np.angle(np.exp(1j * (np.radians([row["relative_phase_deg"] for row in fit_rows]) - origin)))
        if np.linalg.matrix_rank(directions) == 2:
            fitted = np.linalg.lstsq(directions, phases / (2 * np.pi), rcond=None)[0].T
            checks = []
            for row in rows:
                if row.get("fit") or not row["accepted"]:
                    continue
                predicted = origin + 2 * np.pi * (fitted @ row["direction_right_up"])
                residual = np.angle(np.exp(1j * (np.radians(row["relative_phase_deg"]) - predicted)))
                checks.append({"name": row["name"], "phase_prediction_error_deg": np.degrees(residual).tolist()})
            report.update({"status": "experimental phase response fitted; inspect independent checks before calibration",
                "fitted_baselines_wavelengths_rx2_rx3": fitted.tolist(), "heldout_phase_checks": checks,
                "accepted_heldout_poses": len(checks),
                "fitted_baseline_lengths_wavelengths": np.linalg.norm(fitted, axis=1).tolist(),
                "configured_baselines_wavelengths_rx2_rx3": (config.array_geometry[1:] - config.array_geometry[0]).tolist()})
    if report["handheld"]:
        report["status"] = "HANDHELD qualitative response test: " + report["status"]
        report["limitation"] += " Hand/body reflections, motion and approximate placement confound phase; fitted baselines are apparent responses, not calibrated physical geometry."
    (root / "sweep-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    plot_sweep(report, root / "sweep-phase-check.png")
    return report


def plot_sweep(report, path):
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    figure = Figure(figsize=(11, 7), layout="constrained")
    FigureCanvasAgg(figure)
    if report.get("synthetic"):
        figure.suptitle("SYNTHETIC validation fixture - not hardware results")
    elif report.get("handheld"):
        figure.suptitle("HANDHELD qualitative direction check - not precision calibration")
    rows = report["poses"]
    names = [row["name"] for row in rows]
    center = next((row for row in rows if row["name"] == "center" and row["accepted"]), None)
    origin = np.radians(center["relative_phase_deg"]) if center else np.zeros(2)
    fitted = np.asarray(report.get("fitted_baselines_wavelengths_rx2_rx3", []))
    for receiver in range(2):
        axes = figure.add_subplot(2, 1, receiver + 1)
        for index, row in enumerate(rows):
            if "relative_phase_deg" not in row:
                continue
            phase = float(np.degrees(np.angle(np.exp(1j * (np.radians(row["relative_phase_deg"][receiver]) - origin[receiver])))))
            axes.scatter(index, phase, marker="o" if row["accepted"] else "x",
                color="tab:blue" if row["accepted"] else "tab:red", s=70)
        if fitted.shape == (2, 2):
            predictions = []
            for row in rows:
                if "direction_right_up" not in row:
                    predictions.append(np.nan)
                    continue
                predicted_phase = 2 * np.pi * (fitted[receiver] @ row["direction_right_up"])
                predictions.append(float(np.degrees(np.angle(np.exp(1j * predicted_phase)))))
            axes.plot(range(len(rows)), predictions, ".--", color="gray", label="Fitted response (check poses excluded from fit)")
            axes.legend(fontsize=8)
        axes.set_xticks(range(len(names)), names)
        axes.set(ylabel="Phase relative to center (deg)" if center else "Raw phase (deg)", ylim=(-180, 180),
            title=f"RX{receiver + 2}-RX1: blue passes quality; red fails; no calibration applied")
        axes.grid(alpha=0.25)
    figure.savefig(path, dpi=140)
