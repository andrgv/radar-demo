"""Inspect edge-timestamp frames and export CHIRP_ACTIVE edges for timing review."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

from radar.protocol import Parser
from radar.storage import replay


def analyze_recording(recording, csv_path):
    parser = Parser()
    frames = list(replay(recording, parser))
    if not frames or parser.bad_crc or parser.bad_headers or parser.buffer or parser.discarded_bytes:
        raise ValueError("Recording is empty or damaged")
    if any(frame.profile_id not in (0x33515401, 0x33515402, 0x33515403) or frame.edge_times_us is None for frame in frames):
        raise ValueError("Recording contains frames without the MCU edge-timing profile")
    counts = Counter(frame.edge_count for frame in frames)
    valid = []
    complete = 0
    partial = 0
    with Path(csv_path).open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["burst_id", "time_us"])
        writer.writeheader()
        for index, frame in enumerate(frames):
            edges = np.asarray(frame.edge_times_us, dtype=np.int64)
            if len(edges) < 2 or np.any(np.diff(edges) <= 0):
                continue
            if frame.edge_overflow:
                partial += 1
            else:
                complete += 1
            valid.append(np.diff(edges))
            for tick in edges:
                writer.writerow({"burst_id": f"{'partial-' if frame.edge_overflow else ''}{index}-{frame.sequence}", "time_us": int(tick)})
    if not valid:
        raise ValueError("No frames have at least two ordered, non-overflowed edges")
    medians = [float(np.median(intervals)) for intervals in valid]
    return dict(frames=len(frames), complete_edge_bursts=complete,
                partial_edge_bursts=partial, ordered_edge_prefixes=len(valid),
                edge_counts=dict(sorted(counts.items())),
                overflow_frames=sum(frame.edge_overflow for frame in frames),
                median_interval_us=float(np.median(medians)),
                interval_median_range_us=[float(min(medians)), float(max(medians))],
                csv=str(Path(csv_path).resolve()),
                caveat="Overflowed frames export only the stored prefix. MCU GPIO ISR timestamps have interrupt latency and 1 MHz timer quantization. Verify edge/block correspondence and raw phase coherence before converting Doppler to m/s.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recording", type=Path)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze_recording(args.recording, args.csv), indent=2))


if __name__ == "__main__":
    main()
