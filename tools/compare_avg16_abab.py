"""Compare the frozen target-present and target-absent operator A/B controls."""
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.core import db


def main():
    root = Path('evidence')
    output = root/'avg16-operator-empty-abab-20261111'
    results = {}
    inputs = {}
    for name, directory in [('target_present', root/'avg16-operator-abab-20261111'),
                            ('target_absent', output)]:
        report = json.loads((directory/'report.json').read_text())
        session = report['sessions'][0]
        inputs[name] = dict(recording=session['recording'], config_fingerprint=session['config_fingerprint'],
                            settings=report['settings'], raw_sha256=session['raw_sha256'],
                            report_sha256=hashlib.sha256((directory/'report.json').read_bytes()).hexdigest())
        rows = [json.loads(line) for line in (directory/'readings.jsonl').read_text().splitlines()]
        data = []
        for w in session['windows']:
            if w['trim_s'] != 2:
                continue
            left, right = w['window_host_s']
            selected = [r for r in rows if left <= r['host_time_s'] < right]
            power = np.array([r['power'] for r in selected])
            threshold = np.array([r['threshold_power'] for r in selected], dtype=float)
            data.append(dict(label=w['label'], frames=len(selected),
                numeric_frames=w['numeric_frames'],
                bin1_median_power_db=float(np.median(db(power[:, 1]))),
                bin1_median_threshold_db=float(np.median(db(threshold[:, 1]))),
                bin1_median_margin_db=float(np.median(db(power[:, 1]/threshold[:, 1])))))
        results[name] = data
    for key in ('config_fingerprint', 'settings'):
        if inputs['target_present'][key] != inputs['target_absent'][key]:
            raise ValueError('Matched controls differ in '+key)
    comparison = [dict(label=a['label'],
                       present_minus_absent_bin1_median_power_db=a['bin1_median_power_db']-b['bin1_median_power_db'])
                  for a, b in zip(results['target_present'], results['target_absent'])]
    report = dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  inputs=inputs, windows=results, comparison=comparison,
                  interpretation='Sequential captures with described matching operator positions, not simultaneous paired measurements. No target-alone physical identity certification; results support a target-presence-linked close return in this placement. Two-second trims, no tuning.')
    (output/'matched-comparison.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True, layout='constrained')
    x = np.arange(4)
    for name, label in [('target_present', 'Target present (live-004)'), ('target_absent', 'Target absent (live-005)')]:
        rows = results[name]
        axes[0].plot(x, [r['bin1_median_power_db'] for r in rows], 'o-', label=label+' power')
        axes[0].plot(x, [r['bin1_median_threshold_db'] for r in rows], 'x--', label=label+' threshold')
        axes[1].plot(x, [r['bin1_median_margin_db'] for r in rows], 'o-', label=label)
    axes[0].set(ylabel='Median dB ADC units squared', title='Near-range bin 1: target-present and target-absent controls')
    axes[1].axhline(0, color='black', ls='--', lw=1)
    axes[1].set(ylabel='Median margin above CFAR threshold (dB)', xlabel='Quiet operator interval')
    axes[1].set_xticks(x, ['A1', 'B1', 'A2', 'B2'])
    for ax in axes:
        ax.legend(fontsize=8)
    fig.savefig(output/'matched-comparison.png', dpi=150)
    plt.close(fig)
    print(json.dumps(comparison))


if __name__ == '__main__':
    main()
