"""Offline comparison of the four initial range experiments; raw data unchanged."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from radar.config import Config
from radar.processing import range_fft
from radar.storage import replay
from radar.diagnostics import diagnose


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'artifacts/range-experiments'
    output.mkdir(parents=True, exist_ok=True)
    names = ['empty_check', '1ft', '2ft', '3ft']
    report, powers = {}, {}
    reference = None
    for name in names:
        path = root / 'recordings' / name
        config = Config.load(path / 'config.json')
        if reference is None:
            reference = config
        if config != reference:
            raise ValueError('Capture configs differ')
        frames = list(replay(path))
        p = np.array([np.mean(abs(range_fft(f.adc, config))**2, axis=0) for f in frames])
        powers[name] = p
        adc = np.stack([f.adc for f in frames])
        item = diagnose(path)
        item['metadata'] = json.loads((path / 'metadata.json').read_text())
        item['last_transport'] = json.loads((path / 'transport.jsonl').read_text().splitlines()[-1])
        item['fraction_at_observed_min_max'] = [float(np.mean(adc == adc.min())), float(np.mean(adc == adc.max()))]
        mean = p.mean(axis=(0, 2))
        item['mean_power_db_by_bin'] = (10*np.log10(mean+1e-12)).tolist()
        item['top_bins_excluding_dc'] = (np.argsort(mean[1:])[::-1][:6]+1).tolist()
        item['per_frame_peak_counts_including_bin1'] = np.bincount(p.mean(axis=2)[:, 1:].argmax(axis=1)+1, minlength=len(mean)).tolist()
        report[name] = item
    empty = powers['empty_check'].mean(axis=0)
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), layout='constrained')
    bins = np.arange(len(empty))
    for name, p in powers.items():
        mean = p.mean(axis=(0, 2))
        db = 10*np.log10(mean+1e-12)
        axes[0, 0].plot(bins, db, label=name)
        axes[0, 1].plot(bins, db, marker='.', label=name)
        if name != 'empty_check':
            ratio = 10*np.log10((p.mean(axis=0)+1e-12)/(empty+1e-12))
            report[name]['power_change_db_per_bin_per_rx'] = ratio.tolist()
            axes[1, 0].plot(bins, 10*np.log10(mean/(empty.mean(axis=1)+1e-12)), marker='.', label=name)
        perframe = 10*np.log10(p.mean(axis=2)+1e-12)
        axes[1, 1].plot(bins, np.median(perframe, axis=0), label=name)
        axes[1, 1].fill_between(bins, *np.percentile(perframe, [5, 95], axis=0), alpha=.12)
    axes[0, 0].set(title='Mean power: full spectrum', ylabel='dB ADC²')
    axes[0, 1].set(title='Near bins (DC/bin 1 retained)', xlim=(0, 8), ylabel='dB ADC²')
    axes[1, 0].set(title='Mean power relative to empty (not isolated target power)', xlim=(0, 12), ylabel='dB change')
    axes[1, 0].axhline(0, color='gray', linewidth=.7)
    axes[1, 1].set(title='Median and 5–95% frame spread', xlim=(0, 12), ylabel='dB ADC²')
    for ax in axes.flat:
        ax.set_xlabel('FFT bin')
        ax.legend()
        ax.grid(alpha=.2)
    fig.savefig(output / 'comparison.png', dpi=160)
    (output / 'report.json').write_text(json.dumps(report, indent=2))
    for name, item in report.items():
        print(name, json.dumps(item))


if __name__ == '__main__':
    main()
