"""Operator-position diagnostics for the November 11 repeated 50 cm capture."""
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.core import db


def main():
    output = Path('evidence/avg16-repeat50-20261111')
    report = json.loads((output/'report.json').read_text())
    rows = [json.loads(x) for x in (output/'readings.jsonl').read_text().splitlines()]
    times = np.array([r['host_time_s'] for r in rows])
    p = np.array([r['power'] for r in rows])
    threshold = np.array([r['threshold_power'] for r in rows], dtype=float)
    hold = next(w for w in report['sessions'][0]['windows'] if w['label']=='50 cm C (trim 2s)')
    left, right = hold['original_window_host_s']
    midpoint = (left+right)/2

    def summarize(start, end):
        ids = np.flatnonzero((times >= start) & (times < end))
        selected = [rows[i] for i in ids]
        numeric = [r['experimental_range_m'] for r in selected if r['target_detected'] and r['experimental_range_m'] is not None]
        return dict(window_host_s=[start, end], frames=len(ids), numeric_frames=len(numeric),
                    median_range_cm=float(np.median(numeric)*100) if numeric else None,
                    median_power_db_bins1_8=np.median(db(p[ids, 1:9]), axis=0).tolist(),
                    median_threshold_db_bins1_8=np.median(db(threshold[ids, 1:9]), axis=0).tolist(),
                    median_margin_db_bins1_8=np.median(db(p[ids, 1:9]/threshold[ids, 1:9]), axis=0).tolist())

    sensitivity = [dict(midpoint_offset_s=shift,
                        first=summarize(left+2, midpoint+shift-2),
                        second=summarize(midpoint+shift+2, right-2))
                   for shift in (-2, -1, 0, 1, 2)]
    result = dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  raw_sha256=report['sessions'][0]['raw_sha256'],
                  qualification_report_sha256=hashlib.sha256((output/'report.json').read_bytes()).hexdigest(),
                  hold_window_host_s=[left, right], assumed_operator_switch_host_s=midpoint,
                  interpretation='Approximate user half-hold split, not an identified switch time. No fitted offset or causal proof. Both halves compare the same target placement, but operator motion and timing uncertainty remain confounds.',
                  midpoint_sensitivity=sensitivity)
    (output/'operator.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, layout='constrained')
    ids = (times >= left) & (times < right)
    distance = np.array([r['experimental_range_m']*100 if r['target_detected'] and r['experimental_range_m'] is not None else np.nan for r in rows])
    axes[0].plot(times[ids], distance[ids], '.', ms=3)
    axes[0].axhline(50, color='black', ls='--', lw=1)
    axes[0].set(ylabel='Experimental cm', title='Same third target placement; displayed current distances only', ylim=(30, 65))
    for k, color in [(1, 'tab:blue'), (2, 'tab:orange')]:
        axes[1].plot(times[ids], db(p[ids, k]), color=color, label=f'Bin {k} power')
        axes[1].plot(times[ids], db(threshold[ids, k]), color=color, ls='--', label=f'Bin {k} threshold')
        axes[2].plot(times[ids], db(p[ids, k]/threshold[ids, k]), color=color, label=f'Bin {k}')
    axes[1].set(ylabel='dB ADC units squared', title='Solid = raw native-bin power; dashed = current CFAR threshold')
    axes[2].axhline(0, color='black', ls='--', lw=1)
    axes[2].set(ylabel='Margin above threshold (dB)', xlabel='Host seconds from first saved frame')
    axes[1].legend(ncol=2);axes[2].legend()
    for ax in axes:
        ax.axvline(midpoint, color='red', ls=':', label='Approximate operator switch')
        ax.axvspan(midpoint-2, midpoint+2, color='gray', alpha=.15)
    fig.suptitle('Final 50 cm hold: approximate operator-position comparison; not verified reflector identity')
    fig.savefig(output/'operator.png', dpi=150)
    plt.close(fig)
    for row in sensitivity:
        print('midpoint offset', row['midpoint_offset_s'],
              'first', row['first']['numeric_frames'], '/', row['first']['frames'],
              'second', row['second']['numeric_frames'], '/', row['second']['frames'])
    a, b = sensitivity[2]['first'], sensitivity[2]['second']
    for key in ('median_power_db_bins1_8', 'median_threshold_db_bins1_8', 'median_margin_db_bins1_8'):
        print(key, 'first', a[key][:2], 'second', b[key][:2])


if __name__ == '__main__':
    main()
