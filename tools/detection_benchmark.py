"""Reproducible synthetic detector comparison; not hardware qualification."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import time
import numpy as np

from radar.config import C, Config
from radar.processing import Processor
from radar.synthetic import Target, generate


def benchmark(frames=100):
    if frames < 1:
        raise ValueError("Frame count must be positive")
    # RF scale from the source-derived profile; timing/geometry are KNOWN ONLY
    # inside this synthetic model. This does not certify the physical sensor.
    config = Config(sample_rate_hz=5e6, slope_hz_s=33_691_406_250_000,
                    geometry_mm=[[0, 0], [0, 2.35], [-2.35, 0]],
                    chirp_timing_verified=True, carrier_frequency_verified=True)
    spacing = config.ranges[1] - config.ranges[0]
    velocity_scale = C / (2 * config.carrier_hz * config.chirp_interval_s)
    velocity_bin = velocity_scale / (config.chirps - config.discard_chirps)
    distance = config.ranges[12]
    scenes = {
        "same_range_two_movers": [Target(distance, -0.25 * velocity_scale, -25, 5, 1800),
                                   Target(distance, 0.25 * velocity_scale, 30, -10, 900)],
        "adjacent_ranges_two_movers": [Target(distance + 0.2 * spacing, -0.25 * velocity_scale, -25, 5, 1800),
                                       Target(distance + 0.8 * spacing, 0.25 * velocity_scale, 30, -10, 900)],
        "same_range_static_and_moving": [Target(distance, 0, -20, 5, 1800),
                                         Target(distance, 0.25 * velocity_scale, 30, -10, 900)],
        "off_bin_mover": [Target(distance + 0.3 * spacing, 0.18 * velocity_scale, 30, -10)],
        "near_nyquist": [Target(distance, 0.49 * velocity_scale, 15, 5)],
        "stationary": [Target(distance, 0, -20, 5)],
        "same_range_weak_mover_20db_down": [Target(distance, -0.25 * velocity_scale, -25, 5, 1800),
                                            Target(distance, 0.25 * velocity_scale, 30, -10, 180)],
        "noise_only": [],
    }
    summaries = []
    for name, targets in scenes.items():
        inputs = [generate(config, sequence=i + 1, targets=targets, seed=i, noise=15)
                  for i in range(frames)]
        for mode in ("range_profile", "range_doppler"):
            processor = Processor(replace(config, moving_detector=mode))
            matched = extras = complete = 0
            timings = []
            for frame in inputs:
                start = time.perf_counter()
                detections = processor.process(frame).detections
                timings.append((time.perf_counter() - start) * 1000)
                remaining = list(detections)
                frame_matches = 0
                for target in targets:
                    eligible = []
                    for index, detection in enumerate(remaining):
                        dr = abs(detection.range_m - target.range_m) / spacing
                        dv = abs(detection.velocity_mps - target.velocity_mps)
                        dv = min(dv, abs(velocity_scale - dv)) / velocity_bin
                        if (detection.angle_valid and detection.moving == (target.velocity_mps != 0)
                                and dr <= 0.1 and dv <= 0.51
                                and abs(detection.azimuth_deg - target.azimuth_deg) <= 2
                                and abs(detection.elevation_deg - target.elevation_deg) <= 2):
                            eligible.append((dr + dv, index))
                    if eligible:
                        remaining.pop(min(eligible)[1])
                        frame_matches += 1
                matched += frame_matches
                extras += len(remaining)
                complete += frame_matches == len(targets)
            summaries.append(dict(scene=name, moving_detector=mode, frames=frames,
                expected_targets=frames * len(targets), matched_targets=matched,
                missed_targets=frames * len(targets) - matched, unmatched_detections=extras,
                frames_with_all_targets=int(complete),
                processing_ms_p50_p95=np.percentile(timings, [50, 95]).tolist()))
    return dict(synthetic_only=True, seed_range=[0, frames - 1], noise_adc_std=15,
                matching="range <= 0.1 bin, circular Doppler <= 0.51 bin, az/el <= 2 deg; one-to-one",
                caveats="Ideal point targets, white noise, known simulated timing and array. "
                        "No analog filters, multipath, phase drift or measured recordings. "
                        "Neither mode has a calibrated hardware false-alarm probability.",
                results=summaries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.frames < 1:
        parser.error("--frames must be positive")
    result = json.dumps(benchmark(args.frames), indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
