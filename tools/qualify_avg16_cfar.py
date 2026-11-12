"""Replay frozen 1D CFAR on AVG16 captures with explicit scene windows; no tuning."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording, stats
from radar_min.cfar import CfarConfig, CfarDetector
from tools.sweep_cfar import episodes

ROOT = Path(__file__).resolve().parents[1]


def aligned_times(frames, arrivals):
    if [f.sequence for f in frames] != [r['sequence'] for r in arrivals]:
        raise ValueError('Arrival/frame sequence mismatch')
    stamps = [r['host_unix_ns'] for r in arrivals]
    if any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise ValueError('Host timestamps must increase')
    return np.array([(t-stamps[0])/1e9 for t in stamps])


def summarize(rows, frames, config, times, window):
    start, end = window['window_host_s']
    if not 0 <= start < end:
        raise ValueError('Invalid scene window')
    ids = np.flatnonzero((times >= start) & (times < end))
    selected = [rows[i] for i in ids]
    numeric = [r['target_detected'] and r.get('experimental_range_m') is not None for r in selected]
    values = np.array([r['experimental_range_m'] for r, hit in zip(selected, numeric) if hit])
    runs = episodes(numeric, [frames[i] for i in ids], config.frame_interval_s)
    for run in runs:
        run['start_host_s'] = float(times[ids[run['start_index']]])
        run['end_host_s'] = float(times[ids[run['end_index']]])
    target = window.get('nominal_target_m')
    error = values-target if target is not None else np.array([])
    return dict(**window, frames=len(ids),
        truncated=bool(end > times[-1]+config.frame_interval_s),
        presence_frames=sum(r['target_detected'] for r in selected),
        numeric_frames=len(values), numeric_coverage=len(values)/len(ids) if len(ids) else None,
        unresolved_presence_frames=sum(r['target_detected'] and not hit for r, hit in zip(selected, numeric)),
        range_cm_p05_p50_p95=(np.percentile(values*100, [5, 50, 95]).tolist() if len(values) else None),
        # Placement comparison is not range error conditional on verified reflector identity.
        conditional_placement_bias_cm=float(np.mean(error)*100) if len(error) else None,
        conditional_placement_mae_cm=float(np.mean(abs(error))*100) if len(error) else None,
        selected_bins=dict(Counter(str(r['range_bin']) for r in selected if r['target_detected'])),
        reasons=dict(Counter(r['reason'] for r in selected)),
        fine_reasons=dict(Counter(r['fine_range']['reason'] for r in selected if r.get('fine_range'))),
        numeric_episodes=runs,
        longest_numeric_episode_s=max((r['duration_s'] for r in runs), default=0))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT/'configs/avg16-cfar-qualification.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    settings = CfarConfig(**manifest['cfar'])
    # Never overwrite earlier evidence.
    args.output.mkdir(parents=True, exist_ok=False)
    sessions, plot_data = [], []
    with (args.output/'readings.jsonl').open('w') as stream:
        for case in manifest['cases']:
            source = ROOT/case['recording']
            config, frames, transport = read_recording(source)
            if config.profile_id != 0x33515403:
                raise ValueError('Expected AVG16 profile 0x33515403')
            arrivals = [json.loads(line) for line in (source/'arrivals.jsonl').read_text().splitlines()]
            times = aligned_times(frames, arrivals)
            detector = CfarDetector(config, settings)
            rows = []
            for frame in frames:
                row = detector.update(frame)
                if not frame.flags & 1:
                    detector.clear()
                    row.update(target_detected=False, range_bin=None, range_m=None,
                               provisional_range_m=None, experimental_range_m=None,
                               fine_range=None, reason='invalid_frame_flags')
                rows.append(row)
            for t, row in zip(times, rows):
                stream.write(json.dumps(dict(recording=case['recording'], host_time_s=float(t), **row), allow_nan=False)+'\n')
            saved = [json.loads(line) for line in (source/'readings.jsonl').read_text().splitlines()]
            saved_frames = [r for r in saved if 'frame_sequence' in r]
            if [r['frame_sequence'] for r in saved_frames] != [f.sequence for f in frames]:
                raise ValueError('Saved reading/frame sequence mismatch')
            intervals = [summarize(rows, frames, config, times, w) for w in case['windows']]
            sessions.append(dict(recording=case['recording'], config=asdict(config),
                config_fingerprint=config.fingerprint,
                raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
                sidecar_sha256={name: hashlib.sha256((source/name).read_bytes()).hexdigest()
                                for name in ('config.json', 'arrivals.jsonl', 'readings.jsonl')},
                saved_transport=stats(transport), frames=len(frames), host_span_s=float(times[-1]),
                saved_host_clock_states=dict(Counter(r.get('clock_sync', {}).get('state', 'unknown') for r in saved_frames)),
                saved_reading_reasons=dict(Counter(r['reason'] for r in saved_frames)),
                invalid_flag_frames=sum(not f.flags & 1 for f in frames),
                edge_counts=dict(Counter(str(f.edge_count) for f in frames)),
                edge_overflow_frames=sum(f.edge_overflow for f in frames),
                device_errors=sorted({f.errors for f in frames}),
                device_drops=sorted({f.dropped for f in frames}),
                windows=intervals))
            plot_data.append((case, times, rows))
    paths = ['radar_min/core.py', 'radar_min/cfar.py', 'radar_min/cfar_range.py',
             'radar/protocol.py', 'tools/qualify_avg16_cfar.py', 'tools/sweep_cfar.py']
    report = dict(schema=1, manifest=manifest,
        manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        source_sha256={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        settings=asdict(settings), thresholds_retuned=False,
        interpretation='Development replay only. Saved ADC/device continuity checks apply; original host freshness gates are NOT replayed. Saved host states/reasons are reported separately. Placement errors do not certify reflector identity. Target-absent outputs may be legitimate scene reflectors. No matched AVG1/AVG16 comparison or physical accuracy acceptance.',
        sessions=sessions)
    (args.output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(plot_data), 1, squeeze=False,
                             figsize=(13, 3.5*len(plot_data)), layout='constrained')
    for ax, (case, times, rows) in zip(axes[:, 0], plot_data):
        values = [r['experimental_range_m']*100 if r['target_detected'] and r.get('experimental_range_m') is not None else np.nan for r in rows]
        ax.plot(times, values, '.-', ms=2, lw=.5, label='Current 1D fine estimate (gaps preserved)')
        for window in case['windows']:
            left, right = window['window_host_s']
            target = window.get('nominal_target_m')
            ax.axvspan(left, right, color='teal' if target is not None else 'gray', alpha=.12)
            if target is not None:
                ax.plot([left, right], [100*target]*2, 'k--', lw=1)
        ax.set(title=case['recording'], xlabel='Host seconds from first saved frame',
               ylabel='Experimental range (cm)', ylim=(0, 160))
        ax.legend(fontsize=8)
    fig.suptitle('Frozen 1D CFAR on AVG16 — development replay; host freshness not certified')
    fig.savefig(args.output/'timeline.png', dpi=150)
    plt.close(fig)
    lines = ['# Frozen 1D CFAR on AVG16', '', report['interpretation'], '',
             'Settings: guard 1, training/minimum 4, multiplier 2; per-recording bin mask and confirmation preserved. No detector, firmware or threshold changes.', '',
             '| Recording / labeled window | Numeric / frames | Median cm | Placement MAE cm* |',
             '|---|---:|---:|---:|']
    for session in sessions:
        for w in session['windows']:
            q, mae = w['range_cm_p05_p50_p95'], w['conditional_placement_mae_cm']
            lines.append(f"| {session['recording']} / {w['label']} | {w['numeric_frames']}/{w['frames']} | {f'{q[1]:.1f}' if q else '—'} | {f'{mae:.1f}' if mae is not None else '—'} |")
    lines += ['', '*Conditional on numeric output; identity unverified. Read with coverage. Black dashed plot segments are nominal placements, not certified measured-reflector truth.', '',
              '[Timeline](timeline.png) · [Full metrics and hashes](report.json) · [Recomputed frame results](readings.jsonl)', '',
              'Existing captures were already examined during development. Fresh labeled sessions are needed for acceptance; see [capture protocol](../../docs/AVG16_CFAR_QUALIFICATION.md).', '']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(dict(output=str(args.output), sessions=len(sessions), frames=sum(s['frames'] for s in sessions))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
