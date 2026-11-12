"""Summarize signal/reference changes during labeled fixed-target A/B holds."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.core import db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('evidence/avg16-operator-abab-20261111'))
    args = parser.parse_args()
    report = json.loads((args.output/'report.json').read_text())
    session = report['sessions'][0]
    source = Path(session['recording'])
    rows = [json.loads(x) for x in (args.output/'readings.jsonl').read_text().splitlines()]
    saved = [json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
    keys = ('frame_sequence', 'target_detected', 'range_bin', 'experimental_range_m', 'reason')
    if len(rows) != len(saved) or not all(all(a[k] == b[k] for k in keys) for a, b in zip(rows, saved)):
        raise ValueError('Replay does not reproduce saved live output')
    times = np.array([r['host_time_s'] for r in rows])
    p = np.array([r['power'] for r in rows])
    threshold = np.array([r['threshold_power'] for r in rows], dtype=float)
    distance = np.array([r['experimental_range_m']*100 if r['target_detected'] and r['experimental_range_m'] is not None else np.nan for r in rows])
    summaries = []
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True, layout='constrained')
    axes[0].plot(times, distance, '.', ms=2)
    axes[0].axhline(50, color='black', ls='--', lw=1)
    axes[0].set(ylabel='Experimental range (cm)', ylim=(40, 60), title='Fixed target at nominal 50 cm; current confirmed distance')
    axes[1].plot(times, db(p[:, 1]), label='Bin 1 power')
    axes[1].plot(times, db(threshold[:, 1]), label='Bin 1 threshold')
    axes[1].set(ylabel='dB ADC units squared', title='Current-frame power and empirical CFAR threshold')
    axes[1].legend()
    axes[2].plot(times, db(p[:, 1]/threshold[:, 1]))
    axes[2].axhline(0, color='black', ls='--', lw=1)
    axes[2].set(xlabel='Host seconds from first saved frame', ylabel='Margin above threshold (dB)')
    for w in session['windows']:
        if w['trim_s'] != 2:
            continue
        left, right = w['window_host_s']
        ids = np.flatnonzero((times >= left) & (times < right))
        summaries.append(dict(label=w['label'], operator_position=w['operator_position'],
            window_host_s=[left, right], frames=len(ids), numeric_frames=int(np.isfinite(distance[ids]).sum()),
            distance_std_cm=float(np.nanstd(distance[ids])),
            median_power_db_bins1_8=np.median(db(p[ids, 1:9]), axis=0).tolist(),
            median_threshold_db_bins1_8=np.median(db(threshold[ids, 1:9]), axis=0).tolist(),
            median_margin_db_bins1_8=np.median(db(p[ids, 1:9]/threshold[ids, 1:9]), axis=0).tolist()))
        for ax in axes:
            ax.axvspan(left, right, color='orange' if w['operator_position']=='A' else 'teal', alpha=.12)
        axes[0].text((left+right)/2, 57, w['label'].split()[0], ha='center')
    axes[-1].set_xlim(0, max(w['original_window_host_s'][1] for w in session['windows']))
    fig.suptitle('Operator A → B → A → B; identical target placement, unchanged thresholds')
    fig.savefig(args.output/'operator.png', dpi=150)
    plt.close(fig)
    detail = dict(saved_live_replay_matches=True, compared_frames=len(rows),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualification_report_sha256=hashlib.sha256((args.output/'report.json').read_bytes()).hexdigest(),
        interpretation='Two-second quiet-interior trims; no tuning or fitted timing offset. Described operator positions are labels, not verified RF visibility. No target-absent A/B control in this capture.',
        windows=summaries)
    (args.output/'operator.json').write_text(json.dumps(detail, indent=2, allow_nan=False)+'\n')
    for w in summaries:
        print(w['label'], 'coverage', w['numeric_frames'], '/', w['frames'],
              'bin1 power/threshold/margin', w['median_power_db_bins1_8'][0],
              w['median_threshold_db_bins1_8'][0], w['median_margin_db_bins1_8'][0])


if __name__ == '__main__':
    main()
