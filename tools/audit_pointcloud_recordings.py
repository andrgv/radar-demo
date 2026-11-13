"""Measure current point-cloud output on saved raw captures, without tuning.

Recording jitter is not geometric accuracy or two-object resolution. Range
labels from retained experiment notes are used only after extraction. No poses
or object identities are inferred from filenames. Run from the checkout.
"""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.material import _check_frame
from radar.obstacle3d import load_config
from radar.pointcloud import CloudProcessor
from radar.processing import range_fft
from radar.protocol import Parser
from radar.storage import replay


def percentiles(values):
    return np.percentile(values, [5, 50, 95], axis=0).tolist() if len(values) else None


def load_frames(path, config):
    parser = Parser()
    frames = list(replay(path, parser))
    if not frames:
        raise ValueError('No complete raw frames')
    if any(getattr(parser, k) for k in ('bad_crc', 'bad_headers', 'gaps', 'restarts', 'discarded_bytes')) or parser.buffer:
        raise ValueError('Corrupt, truncated or discontinuous accepted-frame file')
    previous = None
    for frame in frames:
        _check_frame(frame, config, previous)
        if not frame.flags & 1:
            raise ValueError('Frame is not marked raw')
        previous = frame
    arrivals = [json.loads(line) for line in (path / 'arrivals.jsonl').read_text().splitlines()]
    if [r['sequence'] for r in arrivals] != [f.sequence for f in frames]:
        raise ValueError('Arrival/raw frame sequences differ')
    device = np.cumsum([0] + [((b.timestamp_us - a.timestamp_us) & 0xffffffff) / 1e6
                              for a, b in zip(frames, frames[1:])])
    host = np.array([(r['host_unix_ns'] - arrivals[0]['host_unix_ns']) / 1e9 for r in arrivals])
    if np.any(np.diff(host) < 0) or np.max(abs(host - device)) > max(.5, .2 * device[-1]):
        raise ValueError('Relative host/device timing mismatch')
    return frames


def summarize_cells(cells, frame_count):
    if not cells:
        return None
    modal, points = max(cells.items(), key=lambda item: len(item[1]))
    values = np.asarray(points)
    xyz = values[:, :3]
    ranges = np.linalg.norm(xyz, axis=1)
    return dict(native_range_bin=modal[0], doppler_cycles_per_chirp=modal[1],
                frames_present=len(points), fraction_frames_present=len(points) / frame_count,
                xyz_p05_median_p95_m=percentiles(xyz), range_p05_median_p95_m=percentiles(ranges),
                xyz_std_m=xyz.std(axis=0).tolist(),
                angular_response_span_p05_median_p95_deg=percentiles(values[:, 3:5]),
                interpretation='Most frequently detected range/Doppler cell, selected without range labels. '
                    'Identity is unknown; jitter within this cell excludes other cells and missing frames. '
                    'Small jitter can describe a stable wrong direction. Response spans are not confidence bounds.')


def audit(recordings, output):
    recordings, output = Path(recordings), Path(output)
    if output.exists():
        raise FileExistsError('Use a fresh output directory')
    prior = json.loads(Path('evidence/obstacle3d-20261109/summary.json').read_text())
    labels = {str(Path(s['recording'])):s for s in prior['recordings']}
    rows, rejected, frame_rows = [], [], []
    raw_seen = set()
    for raw in sorted(recordings.rglob('frames.grd')):
        path = raw.parent
        incomplete = next((p / 'door-check.json' for p in [path, *path.parents]
                           if p.is_relative_to(recordings) and (p / 'door-check.json').exists()
                           and not json.loads((p / 'door-check.json').read_text()).get('complete')), None)
        if incomplete:
            rejected.append(dict(recording=str(path), reason='Incomplete door experiment'))
            continue
        try:
            config = load_config(path / 'config.json')
            frames = load_frames(path, config)
        except (ValueError, OSError, KeyError, TypeError) as error:
            rejected.append(dict(recording=str(path), reason=str(error)))
            continue
        digest = hashlib.sha256(raw.read_bytes()).hexdigest()
        if digest in raw_seen:
            raise ValueError(f'Duplicate raw recording: {path}')
        raw_seen.add(digest)
        processor = CloudProcessor(config)  # Existing defaults; no threshold changes.
        counts, strongest_ranges, cells, all_spans = [], [], {}, []
        target = labels.get(str(path), {}).get('measured_range_m')
        near_frames = 0
        for frame in frames:
            cloud = processor.process(range_fft(frame.adc, config))
            counts.append(len(cloud.xyz))
            radial = np.linalg.norm(cloud.xyz, axis=1)
            strongest = float(radial[np.argmax(cloud.power_db)]) if len(radial) else None
            if strongest is not None:
                strongest_ranges.append(strongest)
            near = bool(target is not None and np.any(abs(radial - target) <= .10))
            near_frames += near
            for i in range(len(radial)):
                cell = (int(cloud.range_bins[i]), float(cloud.doppler_cycles_per_chirp[i]))
                cells.setdefault(cell, []).append([*cloud.xyz[i].tolist(), *cloud.angular_width_deg[i].tolist()])
                all_spans.append(cloud.angular_width_deg[i].tolist())
            frame_rows.append(dict(recording=str(path), sequence=frame.sequence,
                points=len(radial), strongest_point_range_m=strongest,
                any_point_within_10cm_of_surveyed_range=near if target is not None else None))
        row = dict(recording=str(path), raw_sha256=digest, frames=len(frames),
            configuration_sha256=hashlib.sha256((path / 'config.json').read_bytes()).hexdigest(),
            geometry_label=config.geometry_label, native_bin_spacing_m=float(config.ranges[1] - config.ranges[0]),
            points=int(sum(counts)), frames_with_points=int(np.count_nonzero(counts)),
            points_per_frame_p05_median_p95=percentiles(counts),
            strongest_point_range_p05_median_p95_m=percentiles(strongest_ranges),
            all_point_angular_response_span_p05_median_p95_deg=percentiles(all_spans),
            modal_cell=summarize_cells(cells, len(frames)),
            surveyed_range_m=target, range_label_source=labels.get(str(path), {}).get('label_source'),
            any_point_within_10cm_surveyed_range_frames=near_frames if target is not None else None,
            angular_ground_truth_available=False,
            surveyed_range_hit_interpretation='After-extraction diagnostic, not attributed target detection. '
                'Open-door surveyed range refers to the closed pane position. '
                'Current cloud extraction excludes native bins 0 and 1.')
        rows.append(row)
        if len(rows) % 10 == 0:
            print(f'Summarized {len(rows)} recordings / {sum(r["frames"] for r in rows)} frames', flush=True)
    report = dict(schema=1, method=__doc__, settings=dict(snr_db=8, minimum_fit=.65, angular_grid_step_deg=5),
                  recordings=rows, rejected=rejected, total_frames=sum(r['frames'] for r in rows),
                  total_points=sum(r['points'] for r in rows),
                  limitations=['No supplied surveyed angles, two-object separations or moving-sensor trajectories.',
                      'Map accuracy and two-object spatial resolution cannot be inferred from point jitter.',
                      'Archived minimal configs use assumed portrait geometry and neutral channel gains.',
                      'No empty-scene subtraction, adaptive tuning, angular calibration or persistence added.'])
    output.mkdir(parents=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (output / 'frames.csv').open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(frame_rows[0]))
        writer.writeheader()
        writer.writerows(frame_rows)
    print(json.dumps(dict(recordings=len(rows), rejected=len(rejected), frames=report['total_frames'],
                          points=report['total_points']), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recordings', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    audit(args.recordings, args.output)
