"""Inspect the frozen qualification replay for the November 11 placement capture."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from tools.sweep_cfar import episodes
from radar_min.__main__ import read_recording


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('evidence/avg16-placements-20261111'))
    args = parser.parse_args()
    report = json.loads((args.output/'report.json').read_text())
    session = report['sessions'][0]
    source = Path(session['recording'])
    config, frames, _ = read_recording(source)
    rows = [json.loads(x) for x in (args.output/'readings.jsonl').read_text().splitlines()]
    saved = [json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
    keys = ('frame_sequence', 'target_detected', 'range_bin', 'experimental_range_m', 'reason')
    if len(rows) != len(saved) or not all(all(a[k] == b[k] for k in keys) for a, b in zip(rows, saved)):
        raise ValueError('Recomputed outputs do not match saved live results')
    times = np.array([r['host_time_s'] for r in rows])
    power = np.array([r['power'] for r in rows])
    threshold = np.array([r['threshold_power'] for r in rows], dtype=float)
    windows = []
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(12, 8), layout='constrained')
    for w in session['windows']:
        if w['trim_s'] != 2:
            continue
        left, right = w['window_host_s']
        ids = np.flatnonzero((times >= left) & (times < right))
        selected = [rows[i] for i in ids]
        no_numeric = [not (r['target_detected'] and r['experimental_range_m'] is not None) for r in selected]
        misses = episodes(no_numeric, [frames[i] for i in ids], config.frame_interval_s)
        window = dict(label=w['label'], frames=len(ids),
            above_threshold_frames=sum(bool(r['qualified_bins']) for r in selected),
            candidate_frames=sum(bool(r['candidates']) for r in selected),
            qualified_but_no_local_candidate_frames=sum(bool(r['qualified_bins']) and not r['candidates'] for r in selected),
            candidate_bin_counts=dict(Counter(str(r['candidate_bin']) for r in selected if r['candidates'])),
            threshold_margin_db_p05_p50_p95_bins1_8=np.percentile(10*np.log10(power[ids, 1:9]/threshold[ids, 1:9]), [5, 50, 95], axis=0).tolist(),
            numeric_gap_episodes=misses,
            longest_numeric_gap_s=max((e['duration_s'] for e in misses), default=0))
        windows.append(window)
        axes[0].plot(np.arange(1, 9), 10*np.log10(np.median(power[ids, 1:9], axis=0)), 'o-', label=w['label'])
        axes[1].plot(np.arange(1, 9), np.median(10*np.log10(power[ids, 1:9]/threshold[ids, 1:9]), axis=0), 'o-', label=w['label'])
    axes[0].set(title='Native range power during quiet interiors', ylabel='Median dB ADC units squared')
    axes[1].set(title='Margin above frozen 1D CFAR threshold', xlabel='Native range bin', ylabel='Median margin (dB)')
    axes[1].axhline(0, color='black', ls='--', lw=1)
    for ax in axes:
        ax.axvspan(.5, 4.5, color='gray', alpha=.08)
        ax.legend(fontsize=8, loc='center left', bbox_to_anchor=(1.01, .5))
    fig.savefig(args.output/'spectra.png', dpi=150)
    plt.close(fig)
    detail = dict(saved_live_replay_matches=True, compared_frames=len(rows),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  qualification_report_sha256=hashlib.sha256((args.output/'report.json').read_bytes()).hexdigest(),
                  interpretation='Selected return versus labeled placement only; no verified reflector identity. Windows are two-second-trimmed host intervals. Thresholds and search mask unchanged. Candidate failures separate below-threshold/peak-shape effects from persistence.',
                  windows=windows)
    (args.output/'diagnostics.json').write_text(json.dumps(detail, indent=2, allow_nan=False)+'\n')
    for w in windows:
        print(w['label'], 'frames', w['frames'], 'above threshold', w['above_threshold_frames'],
              'candidate', w['candidate_frames'], 'flank rejected', w['qualified_but_no_local_candidate_frames'],
              'longest numeric gap', w['longest_numeric_gap_s'])


if __name__ == '__main__':
    main()
