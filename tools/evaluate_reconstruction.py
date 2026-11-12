"""Replay the new point cloud on the frozen raw inventory, without target fitting."""

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from radar.obstacle3d import load_config
from radar.pointcloud import CloudProcessor
from radar.processing import range_fft
from radar.reconstruction import ReconstructionSettings, SceneReconstructor
from tools.audit_pointcloud_recordings import load_frames, percentiles


def evaluate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    inventory = json.loads(Path('evidence/pointcloud-resolution-20261111/pointcloud-report.json').read_text())
    settings = ReconstructionSettings()
    rows, examples = [], []
    for source in inventory['recordings']:
        path = Path(source['recording'])
        digest = hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest()
        if digest != source['raw_sha256']:
            raise ValueError(f'{path}: input differs from original cloud audit')
        config = load_config(path/'config.json')
        frames = load_frames(path, config)
        processor = SceneReconstructor(config, settings)
        case = output/path.relative_to('recordings')
        case.mkdir(parents=True)
        counts, times, residuals, unresolved, capped, near = [], [], [], Counter(), 0, 0
        view_frames = []
        with (case/'points.jsonl').open('x') as stream:
            for index, frame in enumerate(frames):
                start = time.perf_counter()
                cloud = processor.process(frame.adc)
                times.append((time.perf_counter()-start)*1000)
                report = processor.last_report
                counts.append(len(cloud.xyz))
                capped += bool(report.get('subspace_rank_capped'))
                if 'residual_fraction' in report:
                    residuals.append(report['residual_fraction'])
                unresolved.update(reason for c in report['components'] for reason in c['reasons'])
                ranges = np.linalg.norm(cloud.xyz, axis=1)
                target = source['surveyed_range_m']
                near += bool(target is not None and np.any(abs(ranges-target)<=.1))
                exported = dict(sequence=frame.sequence, timestamp_us=frame.timestamp_us,
                                **{k:v.tolist() for k,v in asdict(cloud).items()}, reconstruction=report)
                # Full reports retain fitting diagnostics, not only successful points.
                stream.write(json.dumps(exported, allow_nan=False)+'\n')
                if path.parent.name in ('door03','door04','door07'):
                    view_frames.append(dict(sequence=frame.sequence, xyz=cloud.xyz.tolist(), power=cloud.power_db.tolist(),
                        snr=cloud.snr_db.tolist(), unresolved=sum(not c['accepted'] for c in report['components']),
                        residual=report.get('residual_fraction')))
                if index == 10 and path.parent.name in ('door03','door04','door07') and path.name=='closed-01':
                    legacy = CloudProcessor(config).process(range_fft(frame.adc, config))
                    examples.append(dict(recording=str(path), sequence=frame.sequence,
                                         new=cloud.xyz.tolist(), old=legacy.xyz.tolist(),
                                         components=report['components']))
        row = dict(recording=str(path), raw_sha256=digest, frames=len(frames),
            old_points=source['points'], points=int(sum(counts)),
            old_points_per_frame_p05_median_p95=source['points_per_frame_p05_median_p95'],
            points_per_frame_p05_median_p95=percentiles(counts),
            processing_ms_p05_median_p95=percentiles(times),
            residual_fraction_p05_median_p95=percentiles(residuals),
            unresolved_reasons=dict(unresolved), order_limit_frames=capped,
            surveyed_range_m=source['surveyed_range_m'],
            old_any_point_within_10cm_range_frames=source['any_point_within_10cm_surveyed_range_frames'],
            any_point_within_10cm_range_frames=near if target is not None else None)
        rows.append(row)
        if view_frames:
            (case/'view.json').write_text(json.dumps(dict(name=str(path), frames=view_frames), allow_nan=False))
        print(f'{path}: median {source["points_per_frame_p05_median_p95"][1]} -> {np.median(counts)} points; '
              f'p95 {np.percentile(times,95):.1f} ms', flush=True)
    report = dict(schema=1, method='raw_multitone_range_angle', settings=asdict(settings),
        recordings=rows, examples=examples, total_frames=sum(r['frames'] for r in rows),
        old_total_points=sum(r['old_points'] for r in rows), total_points=sum(r['points'] for r in rows),
        interpretation='Previously inspected raw captures, no scene labels used for extraction. '
            'Fewer or more points do not demonstrate better geometry. Range-neighborhood counts do not attribute a point to the target. '
            'No surveyed angles or room geometry are available; geometric improvement remains unverified.')
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    evaluate(args.output)
