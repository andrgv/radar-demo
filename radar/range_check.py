"""Guided raw-ADC check of whether a target's range response moves outward.

This reports scene differences, not a calibrated object range or identity.
"""

from dataclasses import replace
from collections import Counter
import json
from pathlib import Path
import queue
import threading
import time

import numpy as np

from .acquisition import Source
from .background import SpectralBackground
from .config import Config
from .processing import range_fft
from .storage import Recorder, replay
from .tracking import ShortRangeAmplitudeTracker


def _frames(path, config):
    frames = list(replay(path))
    if len(frames) < 20:
        raise ValueError(f"{path}: at least 20 valid raw frames required; got {len(frames)}")
    for frame in frames:
        if frame.profile_id != config.profile_id or frame.adc.shape != (config.chirps, config.samples, 3):
            raise ValueError(f"{path}: raw frame does not match the configuration")
    return frames


def _median_residual_power(frames, background, neutral):
    spectra = [background.subtract(range_fft(frame.adc, neutral), neutral) for frame in frames]
    return np.median([np.mean(abs(spectrum)**2, axis=(0, 2)) for spectrum in spectra], axis=0)


def analyze_range_check(root):
    root = Path(root)
    config = Config.load(root / "config.json")
    manifest = json.loads((root / "range-check.json").read_text(encoding="utf-8"))
    for name in ("empty", "near", "far"):
        if Config.load(root / name / "config.json") != config:
            raise ValueError(f"{name}: configuration differs from the empty-scene recording")
    empty = _frames(root / "empty", config)
    near = _frames(root / "near", config)
    far = _frames(root / "far", config)
    expected_seconds = manifest.get("seconds_per_position")
    spans = {name: round(((frames[-1].timestamp_us - frames[0].timestamp_us) & 0xffffffff) / 1e6, 2)
             for name, frames in (("empty", empty), ("near", near), ("far", far))}
    timing_valid = (expected_seconds is None or all(
        span <= expected_seconds + max(1, expected_seconds * 0.25) for span in spans.values()))
    neutral = replace(config, gains_real=[1, 1, 1], gains_imag=[0, 0, 0])
    training_count = max(10, len(empty) // 2)
    background = SpectralBackground.fit(empty[:training_count], neutral)
    empty_power = _median_residual_power(empty[training_count:], background, neutral)

    def summarize(frames):
        power = _median_residual_power(frames, background, neutral)
        excess_db = 10 * np.log10(np.maximum(power, 1e-12) / np.maximum(empty_power, 1e-12))
        usable = np.arange(2, len(excess_db) - 1)
        ranked = sorted(usable, key=lambda index: excess_db[index], reverse=True)
        top = [{"bin": int(index), "excess_over_empty_db": round(float(excess_db[index]), 2),
                "config_plot_m_unvalidated": round(float(config.ranges[index]), 3)} for index in ranked[:5]]
        return {"frames": len(frames), "top_changed_bins": top,
                "strongest_changed_bin": top[0]["bin"] if top and top[0]["excess_over_empty_db"] >= 6 else None}

    near_report = summarize(near)
    far_report = summarize(far)
    near_bin = near_report["strongest_changed_bin"]
    far_bin = far_report["strongest_changed_bin"]
    outward = near_bin is not None and far_bin is not None and far_bin > near_bin
    short_range = ShortRangeAmplitudeTracker(config)
    short_range.fit(empty[:training_count])

    def short_summary(frames):
        counts = Counter()
        profiles = []
        for frame in frames:
            status, excess_db = short_range.update(frame)
            profiles.append(excess_db)
            if status.state == "confirmed":
                counts[status.bin_index] += 1
        dominant = counts.most_common(1)[0][0] if counts else None
        median_db = np.median(profiles, axis=0)
        return {"dominant_confirmed_bin": dominant,
                "confirmed_frames_by_bin": {str(index): count for index, count in sorted(counts.items())},
                "median_excess_db_at_dominant_bin": round(float(median_db[dominant]), 2) if dominant is not None else None}

    empty_short = short_summary(empty[training_count:])
    near_short = short_summary(near)
    far_short = short_summary(far)
    short_outward = (near_short["dominant_confirmed_bin"] is not None and
                     far_short["dominant_confirmed_bin"] is not None and
                     far_short["dominant_confirmed_bin"] > near_short["dominant_confirmed_bin"])
    report = {"schema": 1, "measured_distances_m": manifest.get("measured_distances_m"),
              "one_continuous_sensor_session": manifest.get("one_continuous_sensor_session", False),
              "sensor_timestamp_spans_s": spans, "capture_timing_valid": timing_valid,
              "empty_frames": len(empty), "empty_holdout_frames": len(empty) - training_count,
              "near": near_report, "far": far_report,
              "short_range_live_selector": {"empty": empty_short, "near": near_short, "far": far_short,
                                            "dominant_bin_moves_outward": short_outward if timing_valid else None},
              "strongest_changed_bin_moves_outward": outward if timing_valid else None,
              "interpretation": ("INVALID CAPTURE: sensor timestamps span more than the requested wall-time window; "
                                 "buffered frames make position labels unreliable. Repeat with continuously drained input."
                                 if not timing_valid else
                                 "The short-range selector moves outward in this capture; object association and range calibration remain unverified."
                                 if short_outward else
                                 "The short-range selector did not demonstrate outward movement; do not report its bin as box distance."),
              "caution": "A changed bin can be clutter or multipath. The meter coordinate is config-derived, not validated object distance."}
    (root / "range-check-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def record_range_check(root, config, port, seconds=6):
    if not np.isfinite(seconds) or seconds < 3:
        raise ValueError("Record at least three seconds per position")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    config.save(root / "config.json")
    print("Keep the radar fixed and aimed the same way. Move only the box.", flush=True)
    print("Measure from the radar antenna face to the nearest face of the box.", flush=True)
    distances = {}
    source = Source(config, port=port)
    incoming = queue.Queue(maxsize=256)
    stop_reader = threading.Event()
    reader_errors = []

    def read_continuously():
        try:
            while not stop_reader.is_set():
                frame = source.read()
                if frame is not None:
                    try:
                        incoming.put_nowait(frame)
                    except queue.Full:
                        incoming.get_nowait()
                        incoming.put_nowait(frame)
        except Exception as error:
            reader_errors.append(error)
            stop_reader.set()

    reader = threading.Thread(target=read_continuously, daemon=True)
    reader.start()
    try:
        for name, placement in (("empty", "Remove the box completely"),
                                ("near", "Place the box at a measured NEAR position"),
                                ("far", "Place the box at a measured FAR position")):
            if name != "empty":
                answer = input(f"{name.upper()} distance in meters (for example 0.80): ").strip()
                distance = float(answer)
                if not np.isfinite(distance) or distance <= 0:
                    raise ValueError("Distance must be a positive number in meters")
                if name == "far" and distance <= distances["near"]:
                    raise ValueError("FAR distance must be greater than NEAR distance")
                distances[name] = distance
            input(f"{placement}. Press Enter when positioned: ")
            print("Step away and keep your hands still. Recording starts in 3 seconds...", flush=True)
            time.sleep(3)
            # The reader has kept the USB stream drained during the prompts.
            # Discard only the latest transition frames, then record new ones.
            while True:
                try:
                    incoming.get_nowait()
                except queue.Empty:
                    break
            if reader_errors:
                raise RuntimeError("Radar read failed") from reader_errors[0]
            with Recorder(root / name, config,
                          {"label": name, "scene_id": root.name, "measured_distance_m": distances.get(name),
                           "range_check": True, "one_continuous_sensor_session": True}) as recorder:
                deadline = time.monotonic() + seconds
                first_timestamp = None
                last_timestamp = None
                while time.monotonic() < deadline:
                    if reader_errors:
                        raise RuntimeError("Radar read failed") from reader_errors[0]
                    try:
                        frame = incoming.get(timeout=min(0.2, max(0.001, deadline - time.monotonic())))
                    except queue.Empty:
                        continue
                    recorder.write(frame)
                    first_timestamp = frame.timestamp_us if first_timestamp is None else first_timestamp
                    last_timestamp = frame.timestamp_us
                count = recorder.count
            print(f"Saved {name}: {count} raw frames", flush=True)
            if count < 20:
                raise ValueError(f"Only {count} frames captured for {name}; partial recordings preserved at {root}")
            sensor_span_s = ((last_timestamp - first_timestamp) & 0xffffffff) / 1e6
            if sensor_span_s > seconds + max(1, seconds * 0.25):
                raise ValueError(f"{name}: {seconds:g}s wall-time capture spans {sensor_span_s:.1f}s of sensor time; "
                                 f"stale buffered frames suspected. Partial recordings preserved at {root}")
    finally:
        stop_reader.set()
        reader.join(timeout=2)
        source.close()
    (root / "range-check.json").write_text(json.dumps({"schema": 1, "measured_distances_m": distances,
        "seconds_per_position": seconds, "one_continuous_sensor_session": True,
        "note": "User-measured labels, not radar ground truth"}, indent=2),
        encoding="utf-8")
    return analyze_range_check(root)
