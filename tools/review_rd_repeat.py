"""Repeat review using stopwatch-defined middle-half windows, with no fitted shifts."""
from pathlib import Path
import hashlib
import json

from tools import review_rd_fixed_wall as review


def main():
    review.SOURCE = Path('recordings/gui-20261110-162410-575208/live-002')
    review.OUTPUT = Path('evidence/rd-repeat-wall-20261110')
    review.PHASES = list(zip(
        ['wall start', 'placing', '120 cm A', 'approach A', '60 cm A', 'retreat A',
         '120 cm B', 'approach B', '60 cm B', 'retreat B', '120 cm C', 'removed/wall'],
        [20.48, 5.86, 17.29, 9.63, 18.24, 6.04, 17.51, 5.46, 18.09, 6.74, 16.21, 17.43]))
    review.main(window_fraction=0.5, figure_title='Wheeled target 120↔60 cm, fixed radar + wall — approximate stopwatch labels')
    path = review.OUTPUT/'report.json'
    report = json.loads(path.read_text())
    report.update(wrapper_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scene_notes='Wheeled target manually rolled; operator to side but likely within radar view; speed variable.',
                  labels='Consecutive approximate durations supplied by user. Assume stopwatch near first frame. Middle 50% windows, no fitted shift.')
    path.write_text(json.dumps(report, indent=2, allow_nan=False))
    # Show all data rather than moving windows to the strongest-looking motion.
    import matplotlib.pyplot as plt
    import numpy as np
    arrays = np.load(review.OUTPUT/'review-timelines.npz')
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(14, 7), layout='constrained')
    times = arrays['host_time_s']
    phase = arrays['phase_cycles_per_chirp']
    for k in (2, 3, 4):
        axes[0].plot(times, phase[:, k], '.', ms=2, alpha=0.5, label=f'range bin {k}')
    axes[0].set(ylabel='Cycles/chirp', ylim=(-0.006, 0.006),
                title='Full adjacent-phase timeline; physical timing/sign unverified; operator may contribute')
    axes[0].legend()
    power = arrays['native_range_power']
    im = axes[1].pcolormesh(times, np.arange(5), review.db(power[:, 1:6]).T,
                            shading='nearest', vmin=45, vmax=70)
    axes[1].set(ylabel='Range bin minus 1', xlabel='Host seconds', title='Native range power, bins 1–5 (no subtraction)')
    axes[1].set_yticks(np.arange(5), labels=[str(k) for k in range(1, 6)])
    axes[1].set_ylabel('Range bin')
    fig.colorbar(im, ax=axes[1], label='dB ADC units²')
    for item in report['phases']:
        left, right = item['buffered_host_window_s']
        for ax in axes:
            ax.axvspan(left, right, alpha=0.08, color='green')
    for edge in report['phase_boundaries_host_s'][1:-1]:
        for ax in axes:
            ax.axvline(edge, color='black', ls='--', alpha=0.4)
    fig.savefig(review.OUTPUT/'phase-detail.png', dpi=150)
    plt.close(fig)


if __name__ == '__main__':
    main()
