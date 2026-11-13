"""Audit paired raw-signal effects without fitting a glass classifier.

Run from the checkout: python -m tools.audit_glass_signature recordings OUTPUT
The surveyed pane range is supplied to every recording. Door state is not a
glass identity label. See evidence/glass-signature-20261111/PROTOCOL.md.
"""

import argparse
import csv
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np

from radar.config import C, Config
from radar.material import FeatureSpec, recording_features
from radar.storage import replay


SKIP_FRAMES = 10
WINDOW_FRAMES = 10
CHANNELS = ('rx1', 'rx2', 'rx3', 'combined')
FAMILIES = ('pane_power_db', 'local_contrast_db', 'pane_fraction',
            'later_over_pane_db', 'chirp_stationary_fraction', 'temporal_cv')
METRICS = tuple(f'{family}_{channel}' for family in FAMILIES for channel in CHANNELS) + (
    'cross_rx_coherence_12', 'cross_rx_coherence_13', 'cross_rx_coherence_23')
DOOR_GROUPS = {'door03': 'first-door', 'door04': 'first-door', 'door07': 'second-door'}


def range_regions(config, distance_m):
    """Fixed native-bin regions around a supplied surveyed distance."""
    if not np.isfinite(distance_m) or distance_m <= 0:
        raise ValueError('A positive surveyed pane distance is required')
    spacing = C * config.sample_rate_hz / (2 * config.slope_hz_s * config.samples)
    center = distance_m / spacing
    bins = np.arange(1, config.samples // 2)
    roi = bins[abs(bins - center) <= 1]
    refs = bins[(abs(bins - center) > 1) & (abs(bins - center) <= 5)]
    if not len(roi) or len(refs) < 3:
        raise ValueError('Surveyed ROI is unavailable or lacks reference bins')
    later = bins[bins > roi[-1]]
    if not len(later):
        raise ValueError('No later-energy bins after the pane ROI')
    return dict(center_native_bin=float(center), nominal_bin_spacing_m=float(spacing),
                roi=roi.tolist(), references=refs.tolist(), later=later.tolist())


def _combined(values):
    return np.concatenate((values, values.mean(axis=-1, keepdims=True)), axis=-1)


def _db(values):
    return 10 * np.log10(np.maximum(values, 1e-12))


def window_metrics(spectra, regions):
    """spectra: frames x chirps x native range bins x three receivers."""
    spectra = np.asarray(spectra)
    if (spectra.ndim != 4 or spectra.shape[-1] != 3
            or len(spectra) < 2 or not np.isfinite(spectra).all()):
        raise ValueError('Need finite spectra for at least two frames and three RXs')
    roi, refs, later = (regions[k] for k in ('roi', 'references', 'later'))
    frame_power = np.mean(abs(spectra)**2, axis=1)
    power = _combined(frame_power.mean(axis=0))
    pane_energy = power[roi].sum(axis=0)
    pane_power = pane_energy / len(roi)
    coherent_power = _combined(np.mean(abs(spectra.mean(axis=1))**2, axis=0))
    frame_pane_power = _combined(frame_power[:, roi].mean(axis=1))
    families = (
        _db(pane_power),
        _db(pane_power / np.maximum(np.median(power[refs], axis=0), 1e-12)),
        pane_energy / np.maximum(power[1:-1].sum(axis=0), 1e-12),
        _db(power[later].sum(axis=0) / np.maximum(pane_energy, 1e-12)),
        coherent_power[roi].sum(axis=0) / np.maximum(pane_energy, 1e-12),
        frame_pane_power.std(axis=0) / np.maximum(frame_pane_power.mean(axis=0), 1e-12),
    )
    values = np.concatenate(families).tolist()
    for a, b in combinations(range(3), 2):
        cov = np.mean(spectra[:, :, roi, a] * spectra[:, :, roi, b].conj(), axis=(0, 1))
        denominator = np.sqrt(np.maximum(
            frame_power[:, roi, a].mean(axis=0) * frame_power[:, roi, b].mean(axis=0), 0)).sum()
        values.append(float(np.abs(cov).sum() / max(float(denominator), 1e-12)))
    return dict(zip(METRICS, values)), _db(power[:, :3])


def paired_statistics(opened, closed):
    """Descriptive recording-level effects; no independence/p-value assumption."""
    opened, closed = np.asarray(opened, float), np.asarray(closed, float)
    if (opened.ndim != 1 or closed.shape != opened.shape or len(opened) < 3
            or not np.isfinite(opened).all() or not np.isfinite(closed).all()):
        raise ValueError('Need at least three finite matched recording pairs')
    effects = closed - opened
    within = [float(b - a) for state in (opened, closed) for a, b in combinations(state, 2)]
    maximum_within = float(np.max(np.abs(within)))
    direction = 1 if np.all(effects > 0) else -1 if np.all(effects < 0) else 0
    comparisons = closed[:, None] - opened[None, :]
    interval_direction = (1 if min(closed) > max(opened)
                          else -1 if max(closed) < min(opened) else 0)
    return dict(open=opened.tolist(), closed=closed.tolist(), paired_effects=effects.tolist(),
                median_effect=float(np.median(effects)), same_sign_direction=direction,
                within_state_repeat_differences=within, max_abs_same_state_change=maximum_within,
                min_abs_paired_effect=float(np.min(abs(effects))),
                strict_repeatability=bool(direction and np.min(abs(effects)) > maximum_within),
                recording_range_separation_direction=interval_direction,
                recording_rank_auc_higher_is_closed=float(np.mean(
                    (comparisons > 0) + .5 * (comparisons == 0))))


def cross_setup_statistics(stats):
    effects = np.concatenate([s['paired_effects'] for s in stats.values()])
    direction = 1 if np.all(effects > 0) else -1 if np.all(effects < 0) else 0
    opened = [v for s in stats.values() for v in s['open']]
    closed = [v for s in stats.values() for v in s['closed']]
    common_threshold_direction = (1 if min(closed) > max(opened)
                                  else -1 if max(closed) < min(opened) else 0)
    return dict(same_direction_all_pairs=direction,
                strict_repeatability_every_setup=all(s['strict_repeatability'] for s in stats.values()),
                common_direction_and_strict_repeatability=bool(direction and all(
                    s['strict_repeatability'] for s in stats.values())),
                common_threshold_separation_direction=common_threshold_direction,
                by_setup=stats)


def extract_recording(path, config, regions, seconds):
    # Reuse the existing full integrity and relative host/device timing audit.
    quality = recording_features(path, config, FeatureSpec())
    if abs(quality['sensor_span_s'] - seconds) > max(1., .2 * seconds):
        raise ValueError(f'{path}: requested capture duration is not covered')
    taper = np.hanning(config.samples)
    windows, profiles, pending = [], [], []
    sequences = []
    for i, frame in enumerate(replay(path)):
        sequences.append(frame.sequence)
        if i < SKIP_FRAMES:
            continue
        raw = frame.adc[config.discard_chirps:].astype(float)
        raw -= raw.mean(axis=1, keepdims=True)
        pending.append(np.fft.rfft(raw * taper[None, :, None], axis=1) * (2 / taper.sum()))
        if len(pending) == WINDOW_FRAMES:
            values, profile = window_metrics(pending, regions)
            windows.append(dict(first_sequence=sequences[-WINDOW_FRAMES],
                                last_sequence=frame.sequence, **values))
            profiles.append(profile)
            pending.clear()
    arrivals = [json.loads(line) for line in (path / 'arrivals.jsonl').read_text().splitlines()]
    if [r['sequence'] for r in arrivals] != sequences:
        raise ValueError(f'{path}: arrival sequences differ from the raw frames')
    if not windows:
        raise ValueError(f'{path}: no complete windows')
    summary = dict(path=str(path), frames=quality['frames'], windows=len(windows),
                   sensor_span_s=quality['sensor_span_s'], discarded_tail_frames=len(pending),
                   raw_sha256=quality['raw_sha256'],
                   medians={k:float(np.median([w[k] for w in windows])) for k in METRICS},
                   median_window_power_db_per_rx=np.median(profiles, axis=0).tolist())
    return summary, windows, set(quality['frame_sha256'])


def plot_results(report, output):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    setups = list(report['setups'])
    metrics = [f'{family}_combined' for family in FAMILIES] + list(METRICS[-3:])
    fig = Figure(figsize=(15, 12), tight_layout=True)
    FigureCanvasAgg(fig)
    for ax, metric in zip(fig.subplots(3, 3).flat, metrics):
        for i, setup in enumerate(setups):
            s = report['metrics'][metric]['by_setup'][setup]
            for pair, (a, b) in enumerate(zip(s['open'], s['closed'])):
                offset = (pair - 1) * .06
                ax.plot([i - .18 + offset, i + .18 + offset], [a, b], color='gray', alpha=.45)
                ax.scatter(i - .18 + offset, a, color='tab:blue', marker='o',
                           label='Open' if i == pair == 0 else None)
                ax.scatter(i + .18 + offset, b, color='tab:orange', marker='s',
                           label='Closed' if i == pair == 0 else None)
        ax.set(title=metric.replace('_', ' '), xticks=range(len(setups)), xticklabels=setups)
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('Surveyed pane ROI: each point is one recording median; lines join capture pairs', fontsize=13)
    fig.savefig(output / 'signature-metrics.png', dpi=150)
    fig = Figure(figsize=(13, 3.8 * len(setups)), tight_layout=True)
    FigureCanvasAgg(fig)
    axes = np.asarray(fig.subplots(len(setups), 2)).reshape(len(setups), 2)
    for row, setup in enumerate(setups):
        meta = report['setups'][setup]
        records = [s for s in report['sessions'] if s['setup'] == setup]
        for pair in range(1, meta['repeats'] + 1):
            for rx, color in enumerate(('tab:blue', 'tab:orange', 'tab:green')):
                opened, closed = [np.asarray(next(s for s in records if s['pair'] == pair and s['state'] == state)[
                    'median_window_power_db_per_rx'])[:, rx] for state in ('open', 'closed')]
                bins = np.arange(1, len(opened) - 1)
                label = f'RX{rx + 1}' if pair == 1 else None
                axes[row, 0].plot(bins, (closed - opened)[1:-1], color=color, alpha=.65, label=label)
                axes[row, 1].plot(bins, (closed - opened)[1:-1], color=color, alpha=.65, label=label)
        for ax in axes[row]:
            ax.axhline(0, color='gray', linewidth=.7)
            ax.axvspan(meta['regions']['roi'][0] - .5, meta['regions']['roi'][-1] + .5,
                       color='gray', alpha=.12, label='Surveyed ROI')
            ax.axvline(meta['regions']['center_native_bin'], color='black', linestyle='--')
            ax.set(title=setup, xlabel='Native range bin', ylabel='Closed - open power (dB)')
            ax.legend(fontsize=8)
        axes[row, 1].set_xlim(max(.5, meta['regions']['center_native_bin'] - 3),
                             meta['regions']['center_native_bin'] + 6)
    fig.savefig(output / 'paired-power-profiles.png', dpi=150)


def audit(root, output):
    root, output = Path(root), Path(output)
    if output.exists():
        raise FileExistsError('Use a fresh output directory')
    sessions, window_rows, setups, exclusions = [], [], {}, {}
    seen_frames, seen_raw = set(), set()
    for manifest_path in sorted(root.glob('*/door-check.json')):
        setup = manifest_path.parent.name
        manifest = json.loads(manifest_path.read_text())
        if not manifest.get('complete'):
            exclusions[setup] = 'Incomplete door experiment'
            continue
        if setup not in DOOR_GROUPS:
            exclusions[setup] = 'Not in the fixed three-setup protocol'
            continue
        config = Config.load(manifest_path.parent / 'config.json')
        repeats = manifest['repeats']
        if type(repeats) is not int or repeats < 3:
            raise ValueError(f'{setup}: at least three pairs required')
        seconds = manifest['seconds_per_state']
        if not np.isfinite(seconds) or seconds < 3:
            raise ValueError(f'{setup}: invalid capture duration')
        regions = range_regions(config, manifest['measured_glass_distance_m'])
        setups[setup] = dict(physical_door_group=DOOR_GROUPS[setup], repeats=repeats,
                             measured_distance_m=manifest['measured_glass_distance_m'],
                             regions=regions, config_sha256=hashlib.sha256(
                                 (manifest_path.parent / 'config.json').read_bytes()).hexdigest(),
                             manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest())
        for pair in range(1, repeats + 1):
            for state in ('open', 'closed'):
                path = manifest_path.parent / f'{state}-{pair:02d}'
                summary, windows, hashes = extract_recording(path, config, regions, seconds)
                if seen_frames.intersection(hashes) or summary['raw_sha256'] in seen_raw:
                    raise ValueError(f'{path}: duplicate raw data across recordings')
                seen_frames.update(hashes)
                seen_raw.add(summary['raw_sha256'])
                sessions.append(dict(setup=setup, state=state, pair=pair, **summary))
                window_rows.extend(dict(setup=setup, state=state, pair=pair, **w) for w in windows)
        print(f'{setup}: quality checked and summarized all {2 * repeats} recordings', flush=True)
    if set(setups) != set(DOOR_GROUPS):
        raise ValueError('The fixed protocol requires complete door03, door04 and door07 inputs')
    metrics = {}
    for metric in METRICS:
        stats = {}
        for setup in setups:
            states = [[s['medians'][metric] for s in sessions if s['setup'] == setup and s['state'] == state]
                      for state in ('open', 'closed')]
            stats[setup] = paired_statistics(*states)
        metrics[metric] = cross_setup_statistics(stats)
    report = dict(schema=1, experiment='paired_scene_signal_audit_not_glass_identity',
                  parameters=dict(skip_frames=SKIP_FRAMES, window_frames=WINDOW_FRAMES,
                                  roi_half_width_native_bins=1, reference_outer_width_native_bins=5),
                  numpy_version=np.__version__, setups=setups, exclusions=exclusions,
                  sessions=sessions, metrics=metrics,
                  findings=dict(recordings=len(sessions), frames=sum(s['frames'] for s in sessions),
                      windows=sum(s['windows'] for s in sessions),
                      physical_door_groups=len({s['physical_door_group'] for s in setups.values()}),
                      same_direction_metrics=[k for k, v in metrics.items() if v['same_direction_all_pairs']],
                      repeatable_same_direction_metrics=[k for k, v in metrics.items()
                          if v['common_direction_and_strict_repeatability']],
                      globally_separable_metrics=[k for k, v in metrics.items()
                          if v['common_threshold_separation_direction']]),
                  limitations=[
                      'Surveyed pane range supplied; RF scale and pane-return attribution unverified.',
                      'Previously inspected development data, two physical doors, no blind accuracy estimate.',
                      'Open/closed also changes frame/handle/occlusion/multipath; no matched opaque material control.',
                      'Same-state differences are limited repeat controls, not randomized sham insertions.',
                      'No inference of impossibility from failure of these fixed summaries.',
                      'Arrival timing checks are relative; no proof of absolute USB freshness or RF calibration.'])
    output.mkdir(parents=True)
    (output / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (output / 'windows.csv').open('x', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(window_rows[0]))
        writer.writeheader()
        writer.writerows(window_rows)
    plot_results(report, output)
    print(json.dumps(report['findings'], indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recordings', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    audit(args.recordings, args.output)


if __name__ == '__main__':
    main()
