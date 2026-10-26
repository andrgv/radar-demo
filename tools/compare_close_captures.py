"""Compare close-range repeats and independent empty controls offline."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from radar.config import Config
from radar.storage import replay
from radar.processing import range_fft, Processor
from radar.background import SpectralBackground
from radar.diagnostics import diagnose


def main():
    root = Path(__file__).resolve().parents[1]
    names = ['close_empty_before', 'close_near_1', 'close_far', 'close_near_2', 'close_empty_after']
    out = root / 'artifacts/close-comparison'
    out.mkdir(parents=True, exist_ok=True)
    configs, frames, spectra = {}, {}, {}
    for name in names:
        path = root / 'recordings' / name
        configs[name] = Config.load(path / 'config.json')
        frames[name] = list(replay(path))
        spectra[name] = np.array([range_fft(f.adc, configs[name]) for f in frames[name]])
    config = configs[names[0]]
    if any(c != config for c in configs.values()):
        raise ValueError('Configs differ')
    bg = SpectralBackground.fit(frames[names[0]], config)
    report = {}
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), layout='constrained')
    for name in names:
        s = spectra[name]
        raw = np.mean(abs(s)**2, axis=(1, 3))
        residual = np.mean(abs(s-bg.reference[None, None, :, :]*config.gains)**2, axis=(1, 3))
        item = diagnose(root / 'recordings' / name)
        item['last_transport'] = json.loads((root/'recordings'/name/'transport.jsonl').read_text().splitlines()[-1])
        item['metadata'] = json.loads((root/'recordings'/name/'metadata.json').read_text())
        for mode, p in [('raw', raw), ('subtracted', residual)]:
            db = 10*np.log10(p.mean(axis=0)+1e-12)
            frame_db = 10*np.log10(p+1e-12)
            near = p[:, 1:5]
            item[mode] = dict(mean_power_db=db.tolist(),
                near_peak_counts=np.bincount(near.argmax(axis=1)+1, minlength=5).tolist(),
                near_energy_db_percentiles=(10*np.log10(np.percentile(near.sum(axis=1),[5,50,95]))).tolist(),
                frame_db_percentiles=np.percentile(frame_db,[5,50,95],axis=0).tolist())
            row = 0 if mode == 'raw' else 1
            for col in [0,1]:
                axes[row,col].plot(np.arange(len(db)),db,marker='.',label=name.removeprefix('close_'))
            axes[row,1].fill_between(np.arange(len(db)),*np.percentile(frame_db,[5,95],axis=0),alpha=.08)
        # Complex stability: 1 means constant phase/amplitude across snapshots.
        item['complex_mean_power_fraction_per_bin_rx'] = (abs(s.mean(axis=(0,1)))**2 / np.maximum(np.mean(abs(s)**2,axis=(0,1)),1e-12)).tolist()
        item['mean_power_db_per_bin_rx'] = (10*np.log10(np.mean(abs(s)**2,axis=(0,1))+1e-12)).tolist()
        for mode, background in [('raw',None),('subtracted',bg)]:
            proc = Processor(config,background=background)
            counts = np.zeros(config.samples//2+1,dtype=int)
            for f in frames[name]:
                detected = {int(np.argmin(abs(config.ranges-d.range_m))) for d in proc.process(f).detections}
                for b in detected:
                    counts[b] += 1
            item[mode]['detection_frame_counts_by_bin'] = counts.tolist()
        report[name] = item
    for row in [0,1]:
        for col in [0,1]:
            ax=axes[row,col]
            ax.set(title=('Raw' if row==0 else 'Fixed complex background subtracted')+(' — near bins, shading 5–95%' if col else ' — full spectrum'),xlabel='FFT bin',ylabel='dB ADC²',xlim=(0,6) if col else (0,32))
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
    fig.savefig(out/'comparison.png',dpi=150)
    (out/'report.json').write_text(json.dumps(report,indent=2))
    for name,item in report.items():
        print(name, 'frames', item['frames'], 'health',item['sequence_gaps'],item['device_error_counter_increase'],item['device_drop_counter_increase'])
        for mode in ['raw','subtracted']:
            print(mode,'bins0:11',np.round(item[mode]['mean_power_db'][:11],1),'nearenergy',np.round(item[mode]['near_energy_db_percentiles'],1),'detect',item[mode]['detection_frame_counts_by_bin'][:12])
        print('bin9 complex stability',np.round(item['complex_mean_power_fraction_per_bin_rx'][9],3))


if __name__ == '__main__':
    main()
