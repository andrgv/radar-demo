"""Reproduce retrospective obstacle-template development evidence from door captures.

Run from the checkout: python -m tools.study_obstacles recordings artifacts/obstacle-study-01
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from radar.config import Config
from radar.door_check import _session
from radar.obstacle import fit_experiment, replay_obstacle, fit_profiles, classify_profile, _write_new


def study(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results, skipped, models, summaries, folds, windows = {}, {}, {}, {}, {}, []
    for manifest_path in sorted(root.glob('*/door-check.json')):
        experiment = manifest_path.parent
        name = experiment.name
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not manifest.get('complete'):
            skipped[name] = 'Incomplete capture; excluded'
            continue
        model_path = output/f'{name}-model.json'
        model = fit_experiment(experiment, model_path)
        models[name] = model
        config = Config.load(experiment/'config.json')
        n = manifest['repeats']
        sessions = {f'{state}-{i:02d}': _session(experiment/f'{state}-{i:02d}', config)
                    for i in range(1, n+1) for state in ('open', 'closed')}
        summaries[name] = sessions
        results[name] = dict(distance_inches=manifest['measured_glass_distance_m']/.0254,
                             selected_bins=model['selected_bins'], evaluation={})
        for state in ('open', 'closed'):
            session_name = f'{state}-{n:02d}'
            report = replay_obstacle(experiment/session_name, model_path, output/f'{name}-{session_name}.json')
            scores = [d['similarity_score'] for d in report['decisions']]
            results[name]['evaluation'][state] = dict(counts=report['counts'], score_min=min(scores), score_max=max(scores))
            for d in report['decisions']:
                windows.append(dict(experiment=name, expected='clear' if state == 'open' else 'obstacle', **d))
        folds[name] = []
        for test in range(1, n+1):
            train = [i for i in range(1, n+1) if i != test]
            try:
                fitted = fit_profiles([sessions[f'open-{i:02d}']['median_db'] for i in train],
                                      [sessions[f'closed-{i:02d}']['median_db'] for i in train],
                                      [sessions[f'open-{i:02d}']['within_recording_mad_db'] for i in train])
                fold = dict(excluded_pair=test, selected_bins=fitted['selected_bins'], evaluation={
                    state: classify_profile(sessions[f'{state}-{test:02d}']['median_db'], fitted)
                    for state in ('open', 'closed')})
            except ValueError as error:
                fold = dict(excluded_pair=test, calibration_refused=str(error))
            folds[name].append(fold)
    transfers = []
    for source, model in models.items():
        for target, sessions in summaries.items():
            if source == target:
                continue
            # These are all-recording session medians, not independent door trials.
            decisions = {n: classify_profile(v['median_db'], model) for n, v in sessions.items()}
            transfers.append(dict(source=source, target=target, decisions=decisions))
    report = dict(schema=1, evaluation='Retrospective development evidence; final pairs already inspected. '
                  'Correlated one-second windows are not independent accuracy trials. No threshold search.',
                  decision_margins=dict(clear_max=.25, obstacle_min=.75), results=results,
                  skipped=skipped, leave_one_pair_out=folds, cross_setup_session_medians=transfers)
    _write_new(output/'study.json', report)
    with (output/'windows.csv').open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(windows[0]))
        writer.writeheader()
        writer.writerows(windows)
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    fig = Figure(figsize=(10, 3*len(results)), tight_layout=True)
    FigureCanvasAgg(fig)
    axes = np.atleast_1d(fig.subplots(len(results), 1))
    for axis, name in zip(axes, results):
        for expected, color in [('clear', 'tab:blue'), ('obstacle', 'tab:orange')]:
            scores = [d['similarity_score'] for d in windows if d['experiment'] == name and d['expected'] == expected]
            axis.plot(range(1, len(scores)+1), scores, color=color, label=expected)
        axis.axhspan(.25, .75, color='gray', alpha=.15, label='uncertain')
        axis.axhline(.25, color='gray', linestyle='--')
        axis.axhline(.75, color='gray', linestyle='--')
        axis.set(title=f'{name}: final pair, calibration from earlier pairs', xlabel='Nonoverlapping window (~1 second)',
                 ylabel='Template score (not probability)', ylim=(-.15, 1.2))
        axis.legend(loc='center right')
    fig.savefig(output/'scores.png', dpi=150)
    print(json.dumps(dict(results=results, skipped=skipped), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root')
    parser.add_argument('output')
    args = parser.parse_args()
    study(args.root, args.output)
