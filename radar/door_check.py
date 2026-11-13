"""Repeated open/closed-door experiment; scene evidence, not glass identification."""

import csv
import json
from pathlib import Path
import queue
import threading
import time

import numpy as np

from .acquisition import Source
from .config import Config
from .protocol import Parser
from .storage import Recorder, replay


def _save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def _profile(adc, config):
    # Unpadded, stationary-preserving range power. No complex reference or gains.
    x = adc[config.discard_chirps:].astype(float)
    x -= x.mean(axis=1, keepdims=True)
    window = np.hanning(config.samples)
    spectrum = np.fft.rfft(x * window[None, :, None], axis=1) * (2 / window.sum())
    return 10 * np.log10(np.maximum(np.mean(abs(spectrum)**2, axis=(0, 2)), 1e-12))


def _validate_frame_config(frame, config):
    expected_shape = (config.chirps, config.samples, 3)
    if frame.profile_id != config.profile_id or frame.adc.shape != expected_shape:
        hint = {0x33514802: 'configs/qualification-hpf350.json',
                0x33514801: 'configs/qualification-hpf100.json'}.get(frame.profile_id)
        raise ValueError(
            f"Frame/config mismatch: device profile 0x{frame.profile_id:08x}, shape {frame.adc.shape}; "
            f"config expects 0x{config.profile_id:08x}, shape {expected_shape}. "
            + (f"Use --config {hint} for this reported profile. " if hint else "Use a config matching the device. ")
            + "Repeat in a fresh output directory.")


def _session(path, config):
    if Config.load(path / "config.json") != config:
        raise ValueError(f"{path}: configuration mismatch")
    parser = Parser()
    profiles, stamps = [], []
    previous = None
    for frame in replay(path, parser):
        _validate_frame_config(frame, config)
        if np.any(frame.adc == 0) or np.any(frame.adc == 65535):
            raise ValueError(f"{path}: ADC container rails; inspect raw data")
        if previous is not None:
            if frame.dropped != previous.dropped or frame.errors != previous.errors:
                raise ValueError(f"{path}: device loss/error counters changed")
            step = ((frame.timestamp_us - previous.timestamp_us) & 0xffffffff) / 1e6
            if not 0 < step <= max(1, 5 * config.frame_interval_s):
                raise ValueError(f"{path}: discontinuous sensor timestamps")
        previous = frame
        profiles.append(_profile(frame.adc, config))
        stamps.append(frame.timestamp_us)
    if len(profiles) < 20:
        raise ValueError(f"{path}: at least 20 frames required")
    if parser.bad_crc or parser.bad_headers or parser.gaps or parser.restarts or parser.discarded_bytes or parser.buffer:
        raise ValueError(f"{path}: corrupt, truncated or discontinuous recording")
    arrivals = [json.loads(line) for line in (path / "arrivals.jsonl").read_text().splitlines()]
    if len(arrivals) != len(profiles):
        raise ValueError(f"{path}: arrival count mismatch")
    sensor_elapsed = np.cumsum([0] + [((b - a) & 0xffffffff) / 1e6 for a, b in zip(stamps, stamps[1:])])
    host_elapsed = np.array([(a["host_unix_ns"] - arrivals[0]["host_unix_ns"]) / 1e9 for a in arrivals])
    if np.any(np.diff(host_elapsed) < 0) or np.max(abs(sensor_elapsed - host_elapsed)) > max(.5, .2 * sensor_elapsed[-1]):
        raise ValueError(f"{path}: sensor/arrival timing mismatch; stale data suspected")
    data = np.asarray(profiles)
    return {"frames": len(data), "sensor_span_s": float(sensor_elapsed[-1]),
            "median_db": np.median(data, axis=0).tolist(),
            "within_recording_mad_db": np.median(abs(data - np.median(data, axis=0)), axis=0).tolist()}


def analyze_door_check(root):
    root = Path(root)
    manifest = json.loads((root / "door-check.json").read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise ValueError("Capture incomplete; partial raw data preserved, repeat in a fresh directory")
    config = Config.load(root / "config.json")
    repeats = manifest["repeats"]
    if type(repeats) is not int or repeats < 3:
        raise ValueError("At least three open/closed pairs required")
    sessions = {f"{state}-{i:02d}": _session(root / f"{state}-{i:02d}", config)
                for i in range(1, repeats + 1) for state in ("open", "closed")}
    expected = manifest.get("seconds_per_state")
    if expected is not None:
        if not np.isfinite(expected) or expected < 3:
            raise ValueError("Invalid requested recording duration")
        tolerance = max(1., .2 * expected)
        if any(abs(session["sensor_span_s"] - expected) > tolerance for session in sessions.values()):
            raise ValueError("Recording does not cover the requested capture window")
    opened = np.array([sessions[f"open-{i:02d}"]["median_db"] for i in range(1, repeats + 1)])
    closed = np.array([sessions[f"closed-{i:02d}"]["median_db"] for i in range(1, repeats + 1)])
    # Last pair is untouched by bin/threshold selection. Independent recordings,
    # not adjacent frames, are the units of repeatability and evaluation.
    delta = closed - opened
    train_delta = np.median(delta[:-1], axis=0)
    control_spread = np.ptp(opened[:-1], axis=0)
    noise = np.max([sessions[f"open-{i:02d}"]["within_recording_mad_db"]
                    for i in range(1, repeats)], axis=0)
    threshold = np.maximum(3., np.maximum(2 * control_spread, 6 * noise))
    direction = np.sign(train_delta)
    consistent = np.all(delta[:-1] * direction >= threshold, axis=0)
    consistent[0] = consistent[-1] = False  # leakage/DC and Nyquist
    candidates = np.flatnonzero(consistent)
    selected = int(candidates[np.argmax(abs(train_delta[candidates]))]) if len(candidates) else None
    evaluation = None
    if selected is not None:
        baseline = float(np.median(opened[:-1, selected]))
        cutoff = float(threshold[selected])
        scores = direction[selected] * (np.array([opened[-1, selected], closed[-1, selected]]) - baseline)
        evaluation = {"open_score_db": float(scores[0]), "closed_score_db": float(scores[1]),
                      "threshold_db": cutoff, "open_false_detection": bool(scores[0] >= cutoff),
                      "closed_detected": bool(scores[1] >= cutoff)}
    rows = []
    for b in range(len(train_delta)):
        rows.append({"bin": b, "config_plot_m_unvalidated": float(config.ranges[b]),
                     "training_closed_minus_open_db": float(train_delta[b]),
                     "open_repeat_spread_db": float(control_spread[b]),
                     "threshold_db": float(threshold[b]), "repeatable_training_change": bool(consistent[b]),
                     "heldout_closed_minus_open_db": float(delta[-1, b])})
    report = {"schema": 1, "experiment": "door_state_not_material_identity",
              "measured_glass_distance_m": manifest["measured_glass_distance_m"],
              "training_pairs": repeats - 1, "heldout_pair": repeats,
              "selected_bin": selected, "heldout": evaluation, "bins": rows, "sessions": sessions,
              "limitations": "Exploratory thresholds, no calibrated range or glass probability. Frame/handle and background changes confound glass attribution. One held-out pair does not establish accuracy."}
    with (root / "door-profiles.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    # Use the noninteractive API so analysis also works without a display.
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(10, 7), tight_layout=True)
    FigureCanvasAgg(fig)
    upper, lower = fig.subplots(2, 1)
    for i in range(repeats):
        upper.plot(opened[i], color="tab:blue", alpha=.55, label="Open" if i == 0 else None)
        upper.plot(closed[i], color="tab:orange", alpha=.55, label="Closed" if i == 0 else None)
    upper.set(ylabel="Median power (dB ADC²)", title="Repeated door states — uncalibrated range bins")
    upper.legend()
    lower.plot(train_delta, label="Training closed − open")
    lower.plot(delta[-1], label="Held-out closed − open")
    lower.plot(threshold, "k--", label="Training threshold (±)")
    lower.plot(-threshold, "k--")
    lower.set(xlabel="Range FFT bin", ylabel="Change (dB)")
    lower.legend()
    fig.savefig(root / "door-profiles.png", dpi=150)
    _save(root / "door-check-report.json", report)
    return report


def record_door_check(root, config, port, distance, seconds=30, repeats=3, settle=5, notes=""):
    config.validate()
    if not np.isfinite(distance) or distance <= 0:
        raise ValueError("Glass distance must be positive and finite")
    if not np.isfinite(seconds) or seconds < 3 or type(repeats) is not int or repeats < 3:
        raise ValueError("Use at least three pairs and three seconds per recording")
    if not np.isfinite(settle) or settle < 3:
        raise ValueError("Allow at least three seconds to step away")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    config.save(root / "config.json")
    manifest = dict(schema=1, complete=False, repeats=repeats, seconds_per_state=seconds,
                    settle_seconds=settle, measured_glass_distance_m=distance, notes=notes,
                    one_continuous_sensor_session=True, completed_sessions=[])
    _save(root / "door-check.json", manifest)
    print("Fix radar facing the pane center. Keep the background unchanged and people clear.\n"
          "Open the door fully out of the beam. Frame/handle remain possible confounds.\n"
          "The final pair is reserved for evaluation. Raw data survive interruption.", flush=True)
    source = Source(config, port=port)
    incoming = queue.Queue(maxsize=256)
    stop = threading.Event()
    failures = []
    counters = ("gaps", "bad_crc", "bad_headers", "restarts", "discarded_bytes")
    try:
        # Entire wire stream is retained, including transitions and rejected bytes.
        with Recorder(root / "stream", config, {"label": "unknown", "door_check_stream": True}) as stream:
            source.transport_recorder = stream

            def reader():
                try:
                    while not stop.is_set():
                        frame = source.read()
                        if frame is not None:
                            _validate_frame_config(frame, config)
                            item = (time.monotonic(), frame)
                            try:
                                incoming.put_nowait(item)
                            except queue.Full:
                                incoming.get_nowait()
                                incoming.put_nowait(item)
                except Exception as error:
                    failures.append(error)
                    stop.set()

            thread = threading.Thread(target=reader, daemon=True)
            thread.start()
            try:
                # Verify live layout/profile before asking the user to position a door.
                deadline = time.monotonic() + 3
                while True:
                    if failures:
                        raise failures[0]
                    if time.monotonic() >= deadline:
                        raise ValueError("No radar frames received during startup; check port and board")
                    try:
                        incoming.get(timeout=.2)
                        break
                    except queue.Empty:
                        continue
                for i in range(1, repeats + 1):
                    for state in ("open", "closed"):
                        name = f"{state}-{i:02d}"
                        input(f"Pair {i}/{repeats}: set door {state.upper()}, then press Enter: ")
                        print(f"Step clear. Recording in {settle:g} seconds...", flush=True)
                        time.sleep(settle)
                        start = time.monotonic()
                        last_arrival = start
                        before = [getattr(source.parser, key) for key in counters]
                        with Recorder(root / name, config, {"label": "unknown", "door_state": state,
                                      "pair": i, "scene_id": root.name, "notes": notes,
                                      "measured_glass_distance_m": distance}) as recording:
                            while time.monotonic() - start < seconds:
                                if failures:
                                    raise RuntimeError("Radar reader failed") from failures[0]
                                try:
                                    arrived, frame = incoming.get(timeout=.2)
                                except queue.Empty:
                                    if time.monotonic() - last_arrival > max(1., 5 * config.frame_interval_s):
                                        raise ValueError("Radar frame timeout; partial raw data preserved")
                                    continue
                                if arrived < start:
                                    continue
                                if time.monotonic() - arrived > .5:
                                    raise ValueError("Host recording queue fell behind; repeat capture")
                                last_arrival = arrived
                                recording.write(frame)
                        after = [getattr(source.parser, key) for key in counters]
                        if before != after:
                            raise ValueError("Transport errors during capture; partial raw data preserved")
                        summary = _session(root / name, config)
                        if abs(summary['sensor_span_s'] - seconds) > max(1., .2 * seconds):
                            raise ValueError("Recording does not cover requested window; partial data preserved")
                        manifest["completed_sessions"].append(name)
                        _save(root / "door-check.json", manifest)
                        print(f"Saved {name}: {recording.count} frames", flush=True)
            finally:
                stop.set()
                thread.join(timeout=3)
                if thread.is_alive():
                    raise RuntimeError("Radar reader did not stop")
                source.transport_recorder = None
    finally:
        source.close()
    manifest["complete"] = True
    _save(root / "door-check.json", manifest)
    return analyze_door_check(root)
