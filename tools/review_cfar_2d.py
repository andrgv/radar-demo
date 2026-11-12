"""Summarize the untuned replay CFAR prototype on the labeled AVG16 run."""
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.config import Config as LegacyConfig
from radar.processing import Processor
from radar.storage import replay
from radar_min.core import Config, db
from radar_min.cfar import CfarConfig, CfarDetector
from tools.review_avg16_motion import MOTIONS

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'recordings/avg16-motion-01'
    output = ROOT/'evidence/rd-cfar2d-20261110'
    exported = output/'replay'
    metadata = json.loads((exported/'metadata.json').read_text())
    if metadata['raw_sha256'] != hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest():
        raise ValueError('Replay export does not match recording')
    reports = [json.loads(x) for x in (exported/'candidates.jsonl').read_text().splitlines()]
    diagnostics = [json.loads(x) for x in (exported/'diagnostics.jsonl').read_text().splitlines()]
    arrivals = [json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
    frames = list(replay(source))
    if not ([f.sequence for f in frames] == [r['sequence'] for r in reports] == [r['sequence'] for r in arrivals]):
        raise ValueError('Frame/report/arrival mismatch')
    times = (np.array([r['host_unix_ns'] for r in arrivals])-arrivals[0]['host_unix_ns'])/1e9
    with np.load(exported/'maps.npz') as arrays:
        full = arrays['full_power']; frequencies = arrays['cycles_per_saved_block']
    with np.load(exported/'cfar.npz') as arrays:
        accepted = arrays['accepted']; thresholds = arrays['threshold_power']; counts = arrays['reference_count']
    config = Config.load(source/'config.json')
    range_settings = CfarConfig(guard_cells=1, training_cells=4, min_training_cells=4, factor=2)
    range_detector = CfarDetector(config, range_settings)
    range_readings = [range_detector.update(f) for f in frames]
    legacy_config = LegacyConfig(profile_id=config.profile_id, samples=config.samples, chirps=config.chirps,
        sample_rate_hz=config.sample_rate_hz, slope_hz_s=config.slope_hz_s,
        discard_chirps=config.discard_chirps, snr_db=12)
    legacy = Processor(legacy_config)
    legacy_results = [legacy.process(f) for f in frames]
    maxima = [[p for group in report['clusters'] for p in group['local_maxima']] for report in reports]

    def summarize(label, left, right):
        ids = np.flatnonzero((times >= left) & (times <= right))
        roi = [[p for p in maxima[i] if 2 <= p['range_bin'] <= 4] for i in ids]
        nonzero = [any(p['doppler_bin'] != 8 for p in points) for points in roi]
        zero = [any(p['doppler_bin'] == 8 for p in points) for points in roi]
        legacy_roi = [[d for d in legacy_results[i].detections
                       if 2 <= int(np.argmin(abs(legacy_config.ranges-d.range_m))) <= 4] for i in ids]
        mixed = [any(g['touches_zero_doppler'] and any(p['doppler_bin'] != 8 for p in g['local_maxima'])
                     for g in reports[i]['clusters']) for i in ids]
        return dict(label=label, window_host_s=[left, right], frames=len(ids),
            roi_nonzero_local_maximum_frames=sum(nonzero), roi_zero_local_maximum_frames=sum(zero),
            roi_negative_local_maximum_frames=sum(any(p['doppler_bin'] < 8 for p in points) for points in roi),
            roi_positive_local_maximum_frames=sum(any(p['doppler_bin'] > 8 for p in points) for points in roi),
            all_range_zero_local_maximum_frames=sum(any(p['doppler_bin'] == 8 for p in maxima[i]) for i in ids),
            all_range_nonzero_local_maximum_frames=sum(any(p['doppler_bin'] != 8 for p in maxima[i]) for i in ids),
            zero_peak_range_bins1_4_counts=dict(Counter(p['range_bin'] for i in ids for p in maxima[i]
                                                       if p['doppler_bin'] == 8 and 1 <= p['range_bin'] <= 4)),
            zero_touching_cluster_with_nonzero_local_peak_frames=sum(mixed),
            cluster_count_p05_p50_p95=np.percentile([len(reports[i]['clusters']) for i in ids], [5,50,95]).tolist(),
            range_1d_confirmed_output_frames=sum(range_readings[i]['target_detected'] for i in ids),
            legacy_median_static_roi_output_frames=sum(any(not d.moving for d in detections) for detections in legacy_roi),
            legacy_median_moving_roi_output_frames=sum(any(d.moving for d in detections) for detections in legacy_roi))

    motions = [summarize(label, left+.2, right-.2) for label, left, right in MOTIONS]
    holds = [summarize(label, left+2, right-2) for label, left, right in [
        ('120 cm A', 0, 11.35), ('60 cm A', 12.80, 23.27), ('120 cm B', 24.64, 36.64),
        ('60 cm B', 37.93, 47.11), ('120 cm C', 48.48, float(times[-1]))]]
    summary = dict(algorithm=metadata['algorithm'], settings=metadata['cfar'],
        raw_sha256=metadata['raw_sha256'], cfar_source_sha256=metadata['cfar_source_sha256'],
        review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        legacy_source_sha256=hashlib.sha256((ROOT/'radar/processing.py').read_bytes()).hexdigest(),
        range_1d_settings=asdict(range_settings), range_1d_search_bins=[config.min_bin,config.max_bin],
        legacy_settings='Unmodified radar.processing.Processor, no background, 12 dB local median multiplier; moving path removes slow-time mean and notches zero ±1 before max-over-Doppler range tests. Angles/velocity are not scored.',
        frames=len(reports), valid_frames=sum(r['valid'] for r in reports),
        training_reference_count_min_max=[int(counts[:,1:-1].min()),int(counts.max())],
        cluster_count_distribution=dict(Counter(len(r['clusters']) for r in reports)),
        cfar_processing_ms_p05_p50_p95_max=np.percentile([d['cfar_processing_ms'] for d in diagnostics], [5,50,95,100]).tolist(),
        motions=motions, holds=holds,
        note='Default factor/windows were selected as an empirical starting point, not optimized on labels. Counts are development candidate outputs, not object detection or false-alarm rates. ROI bins 2–4 are analysis probes only; CFAR tests all usable range bins.')
    (output/'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(13, 10), layout='constrained')
    points = [(times[i], p['range_bin'], p['cycles_per_saved_block']) for i, row in enumerate(maxima) for p in row]
    xyz = np.array(points)
    stationary = xyz[:,2] == 0
    for ax, zoom in zip(axes[:2], (False, True)):
        ax.scatter(xyz[stationary,0], xyz[stationary,1], s=3, c='grey', alpha=.35, label='zero-Doppler local maximum')
        im = ax.scatter(xyz[~stationary,0], xyz[~stationary,1], s=8, c=xyz[~stationary,2], cmap='coolwarm', vmin=-.25, vmax=.25)
        ax.set(ylabel='Native range bin', ylim=(.5,8.5) if zoom else (.5,31.5),
               title='Accepted local maxima; all usable ranges tested' if not zoom else 'Same candidates, zoomed to range bins 1–8')
    fig.colorbar(im, ax=axes[:2], label='Cycles/saved block, physical timing unverified')
    roi = np.isin(xyz[:,1], [2,3,4])
    axes[2].scatter(xyz[roi,0], xyz[roi,2], s=8)
    axes[2].axhline(0, color='grey', lw=.7)
    axes[2].set(xlabel='Host seconds from first saved frame', ylabel='Cycles/saved block', ylim=(-.3,.3),
                title='Accepted local maxima in exploratory path bins 2–4')
    for ax in axes:
        for label, left, right in MOTIONS:
            ax.axvspan(left, right, color='orange' if label.startswith('approach') else 'lime', alpha=.18)
        ax.set_xlim(0, times[-1])
    fig.suptitle('Empirical 2D CFAR candidate replay — no background subtraction or zero-Doppler notch')
    fig.savefig(output/'candidate-timeline.png', dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(15, 4), layout='constrained', sharex=True, sharey=True)
    for ax, (label, left, right) in zip(axes, MOTIONS):
        index = int(np.argmin(abs(times-(left+right)/2)))
        ratio = full[index]/thresholds[index]
        im = ax.imshow(np.ma.masked_invalid(db(ratio[:,1:9])), origin='lower', aspect='auto',
                       extent=(.5,8.5,-.53125,.46875), vmin=-12,vmax=12)
        cells = [(r,frequencies[d]) for d,r in np.argwhere(accepted[index]) if 1<=r<=8]
        xy = np.array(cells).reshape(-1,2)
        ax.scatter(xy[:,0],xy[:,1],s=25,marker='s',facecolors='none',edgecolors='white',linewidths=.7)
        peaks = [p for p in maxima[index] if 1<=p['range_bin']<=8]
        ax.scatter([p['range_bin'] for p in peaks],[p['cycles_per_saved_block'] for p in peaks],marker='x',c='red',s=35)
        ax.set(title=f'{label}\nmidpoint {times[index]:.2f} s', xlabel='Native range bin')
    axes[0].set_ylabel('Cycles/saved block')
    fig.colorbar(im, ax=axes, label='dB above/below empirical CFAR threshold')
    fig.suptitle('Time-selected midpoint frames: accepted cells outlined, local maxima marked ×')
    fig.savefig(output/'threshold-midpoints.png', dpi=150)
    plt.close(fig)
    print(json.dumps(dict(motions=motions,holds=holds),indent=2))


if __name__ == '__main__':
    main()
