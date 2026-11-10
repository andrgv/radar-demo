"""Sweep range CA-CFAR on labeled replay; select on tuning recordings only."""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
import hashlib
import itertools
import json
from pathlib import Path
import platform
import sys

import numpy as np
from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig, CfarDetector


def episodes(mask, frames, interval):
    """Return runs, splitting at sequence/time gaps; include one frame duration."""
    runs = []
    start = None
    for i, active in enumerate(mask):
        continuous = i > 0 and ((frames[i].sequence-frames[i-1].sequence) & 0xffffffff) == 1
        delta = ((frames[i].timestamp_us-frames[i-1].timestamp_us) & 0xffffffff)/1e6 if i else 0
        continuous = continuous and .5*interval <= delta <= 1.5*interval
        if start is not None and (not active or not continuous):
            runs.append(dict(start_index=start, end_index=i-1, frames=i-start,
                duration_s=round(((frames[i-1].timestamp_us-frames[start].timestamp_us) & 0xffffffff)/1e6+interval, 6)))
            start = None
        if active and start is None:
            start = i
    if start is not None:
        runs.append(dict(start_index=start, end_index=len(mask)-1, frames=len(mask)-start,
            duration_s=round(((frames[-1].timestamp_us-frames[start].timestamp_us) & 0xffffffff)/1e6+interval, 6)))
    return runs


def measure(readings, frames, config, label):
    detected = [bool(r['target_detected']) for r in readings]
    expected = int(np.floor(label/config.spacing_m+.5)) if label is not None else None
    matched = [hit and r['range_bin'] == expected for hit, r in zip(detected, readings)]
    active = episodes(detected, frames, config.frame_interval_s)
    missed = episodes([not hit for hit in detected], frames, config.frame_interval_s)
    wrong = sum(detected)-sum(matched) if label is not None else None
    switches = sum(a['target_detected'] and b['target_detected'] and a['range_bin'] != b['range_bin']
                   for a, b in zip(readings, readings[1:]))
    selected = [r['provisional_range_m'] for r in readings if r['target_detected']]
    return dict(frames=len(readings), detected_frames=sum(detected), detection_rate=sum(detected)/len(readings),
        expected_nominal_bin=expected, expected_bin_frames=sum(matched) if label is not None else None,
        expected_bin_rate=sum(matched)/len(readings) if label is not None else None,
        wrong_bin_frames=wrong, accepted_bins=dict(Counter(str(r['range_bin']) for r in readings if r['target_detected'])),
        detection_episodes=active, longest_detection_s=max((e['duration_s'] for e in active), default=0),
        longest_miss_s=max((e['duration_s'] for e in missed), default=0),
        accepted_bin_switches=switches,
        conditional_nominal_mae_cm=float(np.mean(abs(np.array(selected)-label))*100) if selected and label is not None else None,
        reasons=dict(Counter(r['reason'] for r in readings)))


def aggregate(rows):
    targets = [r['metrics'] for r in rows if r['target_m'] is not None]
    empties = [r['metrics'] for r in rows if r['target_m'] is None]
    def mean(group, field):
        return float(np.mean([m[field] for m in group])) if group else None
    target = mean(targets, 'detection_rate')
    matched = mean(targets, 'expected_bin_rate')
    empty = mean(empties, 'detection_rate')
    return dict(recordings=len(rows), target_recordings=len(targets), empty_recordings=len(empties),
        target_detection_rate=target, target_expected_bin_rate=matched, empty_detection_rate=empty,
        empty_detection_episodes=sum(len(m['detection_episodes']) for m in empties),
        longest_empty_detection_s=max((m['longest_detection_s'] for m in empties), default=0),
        longest_target_miss_s=max((m['longest_miss_s'] for m in targets), default=0),
        balanced_score=(matched+1-empty)/2 if matched is not None and empty is not None else None)


def choose(candidates, max_empty_rate, max_empty_episode_s):
    def feasible(item):
        a = item['tune']
        return a['empty_detection_rate'] <= max_empty_rate and a['longest_empty_detection_s'] <= max_empty_episode_s
    eligible = [item for item in candidates if feasible(item)]
    def rank(item):
        a, s = item['tune'], item['settings']
        return (a['target_expected_bin_rate'] if eligible else a['balanced_score'],
                -a['empty_detection_rate'], a['target_detection_rate'],
                s['factor'], -s['guard_cells'], -s['training_cells'])
    return max(eligible or candidates, key=rank), bool(eligible)


def load_sessions(manifest_path, root):
    manifest = json.loads(manifest_path.read_text())
    sessions = []
    hashes = set()
    group_splits = {}
    for entry in manifest['sessions']:
        if entry['split'] not in ('tune', 'validation', 'stress'):
            raise ValueError('Unknown split: '+entry['split'])
        group = entry.get('group', entry['recording'])
        if group in group_splits and group_splits[group] != entry['split']:
            raise ValueError('A capture group cannot span splits: '+group)
        group_splits[group] = entry['split']
        label = entry['target_m']
        if label is not None and (not np.isfinite(label) or label <= 0):
            raise ValueError('Target labels must be positive distances or null')
        path = root/entry['recording']
        config, frames, _ = read_recording(path)
        digest = hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError('Duplicate raw recording in manifest: '+str(path))
        hashes.add(digest)
        sessions.append(dict(**entry, raw_sha256=digest, config_fingerprint=config.fingerprint,
                             profile_id=config.profile_id, config=config, frames=frames))
    tune = [s for s in sessions if s['split'] == 'tune']
    if not any(s['target_m'] is None for s in tune) or not any(s['target_m'] is not None for s in tune):
        raise ValueError('Tuning needs both empty and target recordings')
    return manifest, sessions


def evaluate(settings, sessions, timeline=None, variant=None):
    rows = []
    for session in sessions:
        c = session['config']; frames = session['frames']
        detector = CfarDetector(c, settings)
        readings = [detector.update(f) for f in frames]
        metrics = measure(readings, frames, c, session['target_m'])
        row = {k:v for k,v in session.items() if k not in ('config', 'frames')}
        row['metrics'] = metrics
        rows.append(row)
        if timeline is not None:
            for frame, reading in zip(frames, readings):
                timeline.write(json.dumps(dict(variant=variant, recording=session['recording'],
                    sequence=frame.sequence, timestamp_us=frame.timestamp_us,
                    target_m=session['target_m'], expected_nominal_bin=metrics['expected_nominal_bin'],
                    target_detected=reading['target_detected'], range_bin=reading['range_bin'],
                    provisional_range_m=reading['provisional_range_m'], experimental_range_m=reading.get('experimental_range_m'), reason=reading['reason']))+'\n')
    return rows


def plots(out, grid, comparisons, sessions):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    fig, ax = plt.subplots(figsize=(7, 4), layout='constrained')
    ax.scatter([r['tune']['empty_detection_rate']*100 for r in grid],
               [r['tune']['target_expected_bin_rate']*100 for r in grid],
               c=[r['settings']['factor'] for r in grid], cmap='viridis', s=30)
    selected = comparisons['selected']['splits']['tune']
    ax.scatter(selected['empty_detection_rate']*100, selected['target_expected_bin_rate']*100,
               marker='*', s=180, color='red', label='Selected on tuning data')
    ax.set(xlabel='Empty-scene detection rate (%)', ylabel='Target expected-bin coverage (%)',
           title='Tuning tradeoff · equal weight per recording')
    ax.legend();fig.savefig(out/'tradeoff.png', dpi=150);plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 8), layout='constrained')
    names = [s['recording'].removeprefix('recordings/') for s in sessions]
    y = np.arange(len(sessions))
    for name, offset, color in [('default', -.18, '#999999'), ('selected', .18, '#167d8d')]:
        ax.barh(y+offset, [r['metrics']['detection_rate']*100 for r in comparisons[name]['sessions']],
                height=.34, label=name, color=color)
    ax.set_yticks(y, names, fontsize=7);ax.invert_yaxis()
    ax.set(xlim=(0, 100), xlabel='Accepted detection frames (%)', title='Any-return detection · empty rows are unwanted detections')
    ax.legend();fig.savefig(out/'recording-coverage.png', dpi=150);plt.close(fig)
    timeline = [json.loads(line) for line in (out/'timelines.jsonl').read_text().splitlines()]
    width = max(len(s['frames']) for s in sessions)
    matrix = np.full((len(sessions), width), np.nan)
    for i, s in enumerate(sessions):
        rows = [r for r in timeline if r['variant'] == 'selected' and r['recording'] == s['recording']]
        for j, r in enumerate(rows):
            matrix[i,j] = 0 if not r['target_detected'] else (1 if r['target_m'] is not None and r['range_bin'] == r['expected_nominal_bin'] else 2)
    fig, ax = plt.subplots(figsize=(11, 8), layout='constrained')
    image = ax.imshow(matrix, aspect='auto', interpolation='nearest', cmap=ListedColormap(['#dddddd','#167d8d','#de8b27']), vmin=0, vmax=2)
    ax.set_yticks(y, names, fontsize=7)
    ax.set(xlabel='Frame index within recording', title='Selected settings · gray: no output; teal: expected bin; orange: other/empty return')
    fig.savefig(out/'selected-timeline.png', dpi=150);plt.close(fig)


def pct(value):
    return 'n/a' if value is None else f'{100*value:.1f}%'


def markdown(report):
    s = report['selected_settings']
    lines = ['# CA-CFAR parameter sweep', '',
        'Retrospective replay of labeled recordings; no hardware changes or baseline subtraction.', '',
        f"Swept {len(report['grid'])} settings on tuning recordings only. Selected: guard **{s['guard_cells']}**, training **{s['training_cells']}** per side, minimum total **{s['min_training_cells']}**, factor **{s['factor']:g}**.", '',
        'Selection maximizes mean target expected-bin coverage subject to mean empty detection rate ≤ '+pct(report['selection_policy']['max_empty_rate'])+
        f" and longest empty episode ≤ {report['selection_policy']['max_empty_episode_s']:g} s. Each recording has equal weight. Ties favor fewer empty detections, more target detections, then a larger factor and smaller windows.", '',
        f"A feasible candidate existed: **{report['selection_feasible']}**. If none is feasible, selection falls back to balanced expected-bin/empty-specificity score; inspect limitations before using it.", '',
        '| Split | Settings | Target any detection | Target expected-bin coverage | Empty detection | Empty episodes | Longest empty episode |',
        '|---|---|---:|---:|---:|---:|---:|']
    for split in ('tune','validation','stress'):
        for variant in ('default','selected'):
            a = report['comparisons'][variant]['splits'][split]
            lines.append(f"| {split} | {variant} | {pct(a['target_detection_rate'])} | {pct(a['target_expected_bin_rate'])} | {pct(a['empty_detection_rate'])} | {a['empty_detection_episodes']} | {a['longest_empty_detection_s']:.2f} s |")
    lines += ['', 'The selected settings '+('meet' if report['comparisons']['selected']['splits']['validation']['meets_empty_constraints'] else '**fail**')+
        ' the tuning empty-scene limits on validation, and '+('meet' if report['comparisons']['selected']['splits']['stress']['meets_empty_constraints'] else '**fail**')+
        ' them on stress data. Do not interpret tuning feasibility as validation success.', '',
        '## Selected settings by capture group', '',
        '| Group | Target any detection | Expected-bin coverage | Empty detection | Longest empty episode |',
        '|---|---:|---:|---:|---:|']
    for group, a in report['comparisons']['selected']['groups'].items():
        lines.append(f"| {group} | {pct(a['target_detection_rate'])} | {pct(a['target_expected_bin_rate'])} | {pct(a['empty_detection_rate'])} | {a['longest_empty_detection_s']:.2f} s |")
    lines += ['', '## Use the selected settings', '', '```sh', './range-v1 gui --detector cfar \\',
        '  --config artifacts/hpf-pair-2/hpf350/range-config.json \\',
        '  --port /dev/cu.usbmodemACTUAL \\',
        f"  --cfar-guard {s['guard_cells']} --cfar-training {s['training_cells']} \\",
        f"  --cfar-min-training {s['min_training_cells']} --cfar-factor {s['factor']:g}", '```', '',
        'Defaults are unchanged. These are an experimental preset, not a deployment qualification.', '',
        '## Per-recording results', '',
        '| Recording | Split | Target | Default detection | Selected detection | Selected expected bin | Selected bin coverage | Longest miss |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for default, selected in zip(report['comparisons']['default']['sessions'], report['comparisons']['selected']['sessions']):
        m = selected['metrics'];label=selected['target_m']
        lines.append(f"| {selected['recording']} | {selected['split']} | {'empty' if label is None else f'{label*100:g} cm'} | {pct(default['metrics']['detection_rate'])} | {pct(m['detection_rate'])} | {m['expected_nominal_bin']} | {pct(m['expected_bin_rate'])} | {m['longest_miss_s']:.2f} s |")
    lines += ['', '## Interpretation and limits', '',
        '- For this study, 30/40/50 cm all map to nearest nominal bin 1. This score does not establish that the detector distinguishes those distances.',
        '- Default means the original CA-CFAR settings (2 guard, 8 training, factor 6), not the empty-reference detector.',
        '- The 1% empty-rate and 0.5 s episode constraints are explicit exploratory engineering targets, not measured reliability guarantees.',
        '- Expected-bin agreement means rounding the user-reported distance to the nearest nominal FFT bin. It is a coarse diagnostic, not proof of box identity or physical accuracy; the grid is about 35 cm.',
        '- Any detection counts can include the wrong reflector. Empty captures contain real clutter; their detections are unwanted outputs for this box experiment, not necessarily thermal-noise false alarms.',
        '- Target misses include confirmation startup and every invalid frame. No failed recording or rejected target frame is dropped. Conditional range errors in JSON describe accepted outputs only and must be read with coverage.',
        '- The tuning run was already explored before this sweep. Validation is another existing run, not a prospective blind experiment. Stress tests mix other sessions/profiles and are reported separately. No setting is selected using validation/stress results.',
        '- All repeats from a run stay in the same split. Raw hashes detect exact duplicate files but cannot establish that distinct files have no overlapping samples. Correlated frames are not independent trials.',
        '- Empty episodes and frame rates are empirical observations over short captures; they are not calibrated Pfa or confidence bounds. Frozen settings need longer fresh empty/target captures in new scenes.',
        '- This sweep scores native bin coordinates, not fine range accuracy. It does not change the detector implementation, confirmation-frame count, search mask, or firmware. Consult the source hashes for the exact confirmation and range-estimation implementation.', '',
        '## Artifacts', '',
        '- [Tuning tradeoff](tradeoff.png)', '- [Per-recording detection coverage](recording-coverage.png)',
        '- [Selected-setting frame timeline](selected-timeline.png)', '- [Full report and provenance](report.json)',
        '- [Selected experimental settings](selected-settings.json)', '- [Tuning grid CSV](grid.csv)', '- [Default/selected per-frame decisions](timelines.jsonl)', '',
        '## Reproduce', '', '```sh', report['reproduce'], '```', '']
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, default=Path('configs/cfar-study.json'))
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--guards', type=int, nargs='+', default=[1,2,3])
    p.add_argument('--training', type=int, nargs='+', default=[4,8,12])
    p.add_argument('--factors', type=float, nargs='+', default=[1.5,2,2.5,3,3.5,4,4.5,5,6])
    p.add_argument('--max-empty-rate', type=float, default=.01)
    p.add_argument('--max-empty-episode-s', type=float, default=.5)
    args = p.parse_args(argv)
    if not 0 <= args.max_empty_rate <= 1 or not np.isfinite(args.max_empty_episode_s) or args.max_empty_episode_s < 0:
        p.error('Invalid empty-scene constraints')
    settings = [CfarConfig(g,t,t,f) for g,t,f in itertools.product(sorted(set(args.guards)),sorted(set(args.training)),sorted(set(args.factors)))]
    manifest, sessions = load_sessions(args.manifest, args.root)
    args.output.mkdir(parents=True, exist_ok=False)
    tuning = [s for s in sessions if s['split'] == 'tune']
    grid = []
    for i, setting in enumerate(settings):
        rows = evaluate(setting, tuning)
        grid.append(dict(settings=asdict(setting), tune=aggregate(rows), sessions=rows))
        if (i+1)%9 == 0 or i+1 == len(settings):print(f'Swept {i+1}/{len(settings)} settings', flush=True)
    selected, feasible = choose(grid, args.max_empty_rate, args.max_empty_episode_s)
    best = CfarConfig(**selected['settings'])
    comparisons = {}
    with (args.output/'timelines.jsonl').open('w') as timeline:
        for variant, setting in [('default', CfarConfig()), ('selected', best)]:
            rows = evaluate(setting, sessions, timeline, variant)
            comparisons[variant] = dict(settings=asdict(setting), sessions=rows,
                splits={split:aggregate([r for r in rows if r['split'] == split]) for split in ('tune','validation','stress')})
            comparisons[variant]['groups'] = {group:aggregate([r for r in rows if r.get('group', r['recording']) == group])
                for group in sorted({r.get('group', r['recording']) for r in rows})}
            for metrics in comparisons[variant]['splits'].values():
                metrics['meets_empty_constraints'] = (metrics['empty_detection_rate'] is not None
                    and metrics['empty_detection_rate'] <= args.max_empty_rate
                    and metrics['longest_empty_detection_s'] <= args.max_empty_episode_s)
    source_paths = ['radar_min/cfar.py', 'radar_min/core.py', 'radar_min/__main__.py', 'tools/sweep_cfar.py']
    reproduction = ['.venv/bin/python','-m','tools.sweep_cfar','--manifest',str(args.manifest),
        '--output',str(args.output)+'-rerun','--guards',*map(str,args.guards),'--training',*map(str,args.training),
        '--factors',*map(str,args.factors),'--max-empty-rate',str(args.max_empty_rate),'--max-empty-episode-s',str(args.max_empty_episode_s), '--root', str(args.root)]
    import shlex
    report = dict(schema=1, runtime=dict(python=sys.version, numpy=np.__version__, platform=platform.platform()), manifest=manifest, manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        source_sha256={s:hashlib.sha256((Path(__file__).resolve().parents[1]/s).read_bytes()).hexdigest() for s in source_paths},
        selection_policy=dict(max_empty_rate=args.max_empty_rate,max_empty_episode_s=args.max_empty_episode_s,
            objective='maximize mean expected-bin coverage on tuning targets; equal recording weights'),
        selected_settings=asdict(best), selection_feasible=feasible, grid=grid, comparisons=comparisons,
        reproduce=shlex.join(reproduction))
    (args.output/'selected-settings.json').write_text(json.dumps(asdict(best), indent=2)+'\n')
    (args.output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    with (args.output/'grid.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=list(grid[0]['settings'])+list(grid[0]['tune']))
        writer.writeheader()
        for item in grid:writer.writerow({**item['settings'],**item['tune']})
    plots(args.output, grid, comparisons, sessions)
    (args.output/'README.md').write_text(markdown(report))
    print(json.dumps(dict(selected=asdict(best), feasible=feasible,
        splits=comparisons['selected']['splits']), indent=2))
    return 0


if __name__ == '__main__':raise SystemExit(main())
