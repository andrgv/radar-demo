"""Review video-labeled AVG16 motion without fitting the recording/video offset."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from radar.protocol import Parser
from radar.storage import replay
from radar_min.core import Config, db, range_spectrum
from radar_min.range_doppler import RangeDoppler

ROOT = Path(__file__).resolve().parents[1]
MOTIONS = [('approach 1', 11.35, 12.80), ('retreat 1', 23.27, 24.64),
           ('approach 2', 36.64, 37.93), ('retreat 2', 47.11, 48.48)]


def main():
    source = ROOT/'recordings/avg16-motion-01'
    output = ROOT/'evidence/rd-avg16-motion-20261110'
    output.mkdir(parents=True, exist_ok=True)
    config = Config.load(source/'config.json')
    parser = Parser()
    frames = list(replay(source, parser))
    if not frames or parser.bad_crc or parser.bad_headers or parser.buffer or parser.discarded_bytes:
        raise ValueError('Empty or damaged saved recording')
    arrivals = [json.loads(line) for line in (source/'arrivals.jsonl').read_text().splitlines()]
    if [r['sequence'] for r in arrivals] != [f.sequence for f in frames]:
        raise ValueError('Arrival/frame sequence mismatch')
    times = (np.array([r['host_unix_ns'] for r in arrivals])-arrivals[0]['host_unix_ns'])/1e9
    processor = RangeDoppler(config)
    maps, validity = [], []
    for frame in frames:
        full, _, info = processor.update(frame)
        validity.append(info['valid'])
        maps.append(full if full is not None else np.full((16, 33), np.nan))
    maps = np.array(maps)
    valid = np.array(validity)
    spectra = np.stack([range_spectrum(f, config) for f in frames])
    increments = spectra[:, 1:]*spectra[:, :-1].conj()
    unit = increments/np.maximum(abs(increments), 1e-20)
    pooled = np.mean(unit, axis=(1, 3))
    phase = np.angle(pooled)/(2*np.pi)
    resultant = abs(pooled)
    native_power = np.mean(abs(spectra)**2, axis=(1, 3))
    peaks = np.argmax(maps, axis=1)

    def summary(left, right):
        mask = (times >= left) & (times <= right)
        use = mask & valid
        if not use.any():
            return dict(window_host_s=[left, right], saved_frames=int(mask.sum()), valid_frames=0)
        return dict(window_host_s=[left, right], saved_frames=int(mask.sum()), valid_frames=int(use.sum()),
            phase_median_cycles_per_saved_block_bins1_8=np.median(phase[use, 1:9], axis=0).tolist(),
            phase_resultant_median_bins1_8=np.median(resultant[use, 1:9], axis=0).tolist(),
            full_peak_nonzero_fraction_bins1_8=np.mean(peaks[use, 1:9] != 8, axis=0).tolist(),
            full_peak_positive_fraction_bins1_8=np.mean(peaks[use, 1:9] > 8, axis=0).tolist(),
            full_peak_negative_fraction_bins1_8=np.mean(peaks[use, 1:9] < 8, axis=0).tolist(),
            full_peak_counts_bins1_8=[dict(Counter(int(x)-8 for x in peaks[use, k])) for k in range(1, 9)],
            native_power_median_bins1_8=np.median(native_power[use, 1:9], axis=0).tolist())

    motions = []
    for label, left, right in MOTIONS:
        motions.append(dict(label=label, video_window_s=[left, right],
            primary=summary(left+.2, right-.2),
            supplied_window=summary(left, right),
            offset_sensitivity=[dict(offset_s=shift, **summary(left+.2+shift, right-.2+shift))
                                for shift in (-.5, -.25, 0, .25, .5)]))
    holds = [('120 cm A', 0, 11.35), ('60 cm A', 12.80, 23.27),
             ('120 cm B', 24.64, 36.64), ('60 cm B', 37.93, 47.11),
             ('120 cm C', 48.48, float(times[-1]))]
    hold_report = [dict(label=label, **summary(left+2, right-2)) for label, left, right in holds]
    readings = [json.loads(line) for line in (source/'readings.jsonl').read_text().splitlines()]
    edge_periods = [(f.edge_times_us[256]-f.edge_times_us[0])/16 for f in frames]
    report = dict(schema=1, recording=str(source.relative_to(ROOT)), frames=len(frames),
        valid_frames=int(valid.sum()), host_span_s=float(times[-1]), profile_id=hex(frames[0].profile_id),
        raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        transform_sha256=hashlib.sha256((ROOT/'radar_min/range_doppler.py').read_bytes()).hexdigest(),
        range_source_sha256=hashlib.sha256((ROOT/'radar_min/core.py').read_bytes()).hexdigest(),
        saved_integrity={k: getattr(parser, k) for k in ('gaps','bad_crc','bad_headers','restarts','discarded_bytes')},
        edge_counts=dict(Counter(f.edge_count for f in frames)), edge_overflow_frames=sum(f.edge_overflow for f in frames),
        device_errors=sorted({f.errors for f in frames}), device_drops=sorted({f.dropped for f in frames}),
        host_reasons=dict(Counter(r['reason'] for r in readings)),
        endpoint_group_period_us_p05_p50_p95=np.percentile(edge_periods, [5,50,95]).tolist(),
        motions=motions, holds=hold_report,
        labels='User video timestamps; first retreat corrected to 23.27–24.64 s. No fitted offset. Motion interiors trim 0.2 s per side; holds trim 2 s. Sensitivity shifts all motion interiors by ±0.25/0.5 s.',
        interpretation='Exploratory full-map peaks and fixed-bin phase, not CFAR detections, target identity, calibrated speed, or measured false-alarm rates. Zero Doppler retained; no background subtraction.')
    (output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(output/'timelines.npz', host_time_s=times, full_map=maps,
                        phase_cycles_per_saved_block=phase, phase_resultant=resultant,
                        native_range_power=native_power, valid=valid)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(5, 1, figsize=(13, 12), sharex=True, layout='constrained')
    vmax = float(np.nanpercentile(db(maps[:, :, 1:9]), 99.7))
    for ax, k in zip(axes[:3], (2, 3, 4)):
        im = ax.pcolormesh(times, processor.doppler, db(maps[:, :, k]).T,
                           shading='nearest', vmin=vmax-45, vmax=vmax)
        ax.set(ylabel='Cycles/block', title=f'Full map at range bin {k}; zero Doppler retained')
    fig.colorbar(im, ax=axes[:3], label='dB ADC units²')
    for k in (2, 3, 4):
        axes[3].plot(times, phase[:, k], '.', ms=2, label=f'bin {k}')
    axes[3].set(ylabel='Cycles/block', ylim=(-.18, .18), title='Adjacent-phase progression, fixed bins')
    axes[3].legend(loc='upper right', ncol=3)
    im = axes[4].pcolormesh(times, np.arange(1, 9), db(native_power[:, 1:9]).T, shading='nearest')
    axes[4].set(xlabel='Host seconds from first saved frame', ylabel='Native range bin', title='Range power, no background subtraction')
    fig.colorbar(im, ax=axes[4], label='dB ADC units²')
    for ax in axes:
        for label, left, right in MOTIONS:
            ax.axvspan(left, right, color='orange' if label.startswith('approach') else 'lime', alpha=.18)
        ax.set_xlim(0, times[-1])
    fig.suptitle('AVG16 motion: orange = approach, green = retreat; video offset unfitted; physical speed uncalibrated')
    fig.savefig(output/'timeline.png', dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 4, figsize=(15, 4), layout='constrained', sharex=True, sharey=True)
    for ax, (label, left, right) in zip(axes, MOTIONS):
        index = int(np.argmin(abs(times-(left+right)/2)))
        im = ax.imshow(db(maps[index, :, 1:9]), origin='lower', aspect='auto',
                       extent=(.5,8.5,-.53125,.46875), vmin=vmax-45, vmax=vmax)
        ax.set(title=f'{label}\nmidpoint frame {times[index]:.2f} s', xlabel='Native range bin')
        ax.axhline(0, color='white', lw=.6)
    axes[0].set_ylabel('Cycles/saved block')
    fig.colorbar(im, ax=axes, label='dB ADC units²')
    fig.suptitle('Full maps at video-window midpoints; frames selected by time, not strongest response')
    fig.savefig(output/'motion-midpoints.png', dpi=150)
    plt.close(fig)
    for item in motions:
        s = item['primary']
        print(item['label'], s['valid_frames'],
              'phase bins2–4',np.round(s['phase_median_cycles_per_saved_block_bins1_8'][1:4],4),
              'nonzero peak fractions',np.round(s['full_peak_nonzero_fraction_bins1_8'][1:4],3))


if __name__ == '__main__':
    main()
