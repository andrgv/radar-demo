"""Frozen first-empty background comparison; diagnostic only, never live distance."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.core import db
from tools.qualify_avg16_cfar import aligned_times


def spectrum(x, nfft):
    """Same DC removal, Hann window and amplitude scaling as core.range_spectrum."""
    x = x - x.mean(axis=-2, keepdims=True)
    w = np.hanning(x.shape[-2])
    return np.fft.rfft(x * w[:, None], n=nfft, axis=-2) * (2 / w.sum())


def background_products(x, template, reference_power, nfft):
    raw = np.mean(abs(spectrum(x, nfft)) ** 2, axis=0)
    residual = np.mean(abs(spectrum(x - template[None], nfft)) ** 2, axis=0)
    return dict(raw=raw, power_excess=np.maximum(raw-reference_power, 0),
                coherent_residual=residual)


def q(values):
    return np.percentile(values, [5, 50, 95], axis=0).tolist()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    manifest = json.loads(a.manifest.read_text())
    if len(manifest['cases']) != 1:
        raise ValueError('Use one matched recording per invocation')
    case = manifest['cases'][0]; source = Path(case['recording'])
    c, frames, parser = read_recording(source)
    if any((parser.bad_crc, parser.bad_headers, parser.gaps, parser.restarts)):
        raise ValueError('Raw integrity failure')
    arrivals = [json.loads(s) for s in (source/'arrivals.jsonl').read_text().splitlines()]
    times = aligned_times(frames, arrivals)
    windows = [w for w in case['windows'] if w.get('trim_s') == 2 and w['state'] in ('hold', 'target_absent')]
    ids = [np.flatnonzero((times >= w['window_host_s'][0]) & (times < w['window_host_s'][1])) for w in windows]
    if not windows or any(len(i) < 4 for i in ids) or windows[0]['state'] != 'target_absent':
        raise ValueError('Need first quiet empty and nonempty matched windows')
    train = ids[0][:len(ids[0])//2]
    # Training membership is fixed before looking at any target spectrum or label.
    xtrain = np.array([frames[i].adc[c.discard_chirps:] for i in train], dtype=float)
    xtrain -= xtrain.mean(axis=2, keepdims=True)
    template = xtrain.mean(axis=(0, 1))
    nfft = 2048
    reference = np.mean(abs(spectrum(xtrain, nfft))**2, axis=(0, 1))
    axis = np.arange(nfft//2+1) * c.samples*c.spacing_m/nfft
    mask = np.flatnonzero((axis >= (c.min_bin-.5)*c.spacing_m) & (axis <= (c.max_bin+.5)*c.spacing_m))
    selected = sorted(set(int(i) for v in ids for i in v))
    products = {name: [] for name in ('raw', 'power_excess', 'coherent_residual')}
    stability = []; coherence = []
    native = np.arange(c.samples//2+1)
    for i in selected:
        x = frames[i].adc[c.discard_chirps:].astype(float)
        x -= x.mean(axis=1, keepdims=True)
        for name, power in background_products(x, template, reference, nfft).items():
            products[name].append(power)
        energy = np.sum(x*x, axis=(0, 1))
        stability.append(np.sum((x-template[None])**2, axis=(0, 1))/energy)
        z = spectrum(x, c.samples)
        coherence.append(abs(z.mean(axis=0))**2 / np.maximum(np.mean(abs(z)**2, axis=0), 1e-12))
    products = {k: np.array(v) for k, v in products.items()}
    stability = np.array(stability); coherence = np.array(coherence)
    positions = {v: j for j, v in enumerate(selected)}
    training_positions = [positions[int(i)] for i in train]
    # Relative power change scan is a control diagnostic, not a CFAR/distance gate.
    ratio = products['raw'] / np.maximum(reference, 1e-12)
    scores = ratio[:, mask].mean(axis=2).max(axis=1)
    change_threshold = float(np.percentile(scores[training_positions], 99))
    training_coherent = products['coherent_residual'][training_positions].mean(axis=(0, 2))
    coherent_scores = (products['coherent_residual'].mean(axis=2)[:, mask] /
                       np.maximum(training_coherent[mask], 1e-12)).max(axis=1)
    coherent_threshold = float(np.percentile(coherent_scores[training_positions], 99))
    summaries = []; profiles = []
    def summarize(w, subset, role):
        js = np.array([positions[int(i)] for i in subset])
        item = dict(label=w['label'], role=role, frames=len(js), state=w['state'],
                    window_host_s=[float(times[subset[0]]), float(times[subset[-1]])],
                    waveform_residual_energy_fraction_rx_p05_p50_p95=q(stability[js]),
                    chirp_coherence_native_bins1_8_rx_median=np.median(coherence[js, 1:9], axis=0).tolist(),
                    relative_power_change_score_p05_p50_p95=q(scores[js]),
                    relative_power_changed_frames=int(np.sum(scores[js] > change_threshold)),
                    coherent_change_score_p05_p50_p95=q(coherent_scores[js]),
                    coherent_changed_frames=int(np.sum(coherent_scores[js] > coherent_threshold)),
                    methods={})
        target = w.get('nominal_target_m')
        for name, value in products.items():
            pooled = value[js].mean(axis=2)
            best = mask[np.argmax(pooled[:, mask], axis=1)]
            rxbest = mask[np.argmax(value[js][:, mask], axis=1)]
            peak = axis[best]
            details = dict(blind_peak_cm_p05_p50_p95=q(peak*100),
                           blind_rx_peak_cm_p05_p50_p95=q(axis[rxbest]*100),
                           rx_peak_spread_cm_p05_p50_p95=q(np.ptp(axis[rxbest], axis=1)*100),
                           scan_boundary_frames=int(np.sum((best == mask[0]) | (best == mask[-1]))),
                           median_profile_peak_cm=float(axis[mask[np.argmax(np.median(pooled, axis=0)[mask])]]*100))
            if target is not None:
                details['nominal_difference_mae_cm'] = float(np.mean(abs(peak-target))*100)
                details['within_half_native_bin_of_nominal_frames'] = int(np.sum(abs(peak-target) <= .5*c.spacing_m))
            item['methods'][name] = details
        summaries.append(item)
        profiles.append((item, {k: np.median(v[js], axis=0) for k, v in products.items()}))
    summarize(windows[0], train, 'training only')
    summarize(windows[0], ids[0][len(train):], 'held-out same-empty half')
    for w, subset in zip(windows[1:], ids[1:]):
        summarize(w, subset, 'held-out interval; sequential same-session evidence')
    a.output.mkdir(parents=True, exist_ok=False)
    with gzip.open(a.output/'frames.jsonl.gz', 'wt') as stream:
        for j, i in enumerate(selected):
            row = dict(sequence=frames[i].sequence, host_s=float(times[i]), training=i in train,
                       power_change_score=float(scores[j]), coherent_change_score=float(coherent_scores[j]),
                       waveform_residual_energy_fraction_rx=stability[j].tolist(), methods={})
            for name, value in products.items():
                k = mask[np.argmax(value[j, mask].mean(axis=1))]
                row['methods'][name] = dict(blind_peak_m=float(axis[k]), peak_power=float(value[j,k].mean()))
            stream.write(json.dumps(row, allow_nan=False)+'\n')
    paths = [str(a.manifest), str(source/'frames.grd'), str(source/'arrivals.jsonl'),
             str(source/'config.json'), 'tools/investigate_matched_background.py', 'radar_min/core.py']
    report = dict(protocol='Fixed first half of first 2s-trimmed empty trains mean DC-centered waveform and mean power, per RX. No phase/gain alignment, target-label fitting, threshold sweep or live policy changes. All other intervals held out from template fitting, but same-session development evidence, not independent validation. Change thresholds are training-99th-percentile max scores, empirical diagnostics only. Every quiet frame used. Nominal ranges used only for post-hoc scoring. Dense FFT does not create native range resolution.',
                  hashes={s: hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in paths},
                  recording=str(source), manifest=manifest, training_frame_sequences=[frames[i].sequence for i in train],
                  nfft=nfft, spacing_m=c.spacing_m, blind_scan_m=[float(axis[mask[0]]), float(axis[mask[-1]])],
                  power_change_threshold=change_threshold, coherent_change_threshold=coherent_threshold,
                  template_ac_rms_rx=np.sqrt(np.mean(template**2, axis=0)).tolist(), windows=summaries)
    (a.output/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    np.savez_compressed(a.output/'background.npz', template=template, mean_power=reference, range_m=axis,
                        **{f'{j}_{k}': v for j, (_, ps) in enumerate(profiles) for k,v in ps.items()})
    make_plots(a.output, profiles, axis, report)
    for w in summaries:
        print(w['label'], w['role'], w['frames'], 'changed', w['relative_power_changed_frames'],
              'coherent_changed', w['coherent_changed_frames'], 'residual', w['waveform_residual_energy_fraction_rx_p05_p50_p95'][1],
              {k: v['blind_peak_cm_p05_p50_p95'] for k,v in w['methods'].items()}, flush=True)


def make_plots(output, profiles, axis, report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(len(profiles), 3, figsize=(14, 2.2*len(profiles)), sharex=True, layout='constrained')
    for row, (w, products) in enumerate(profiles):
        for col, (name, power) in enumerate(products.items()):
            ax = axes[row, col]
            for rx in range(3):
                ax.plot(axis, db(power[:,rx]), lw=.8, label=f'RX {rx+1}')
            ax.set(xlim=(0,2.8), ylim=(0,90), ylabel='dB ADC²', title=f"{w['label']} / {name}")
            ax.axvline(.5, color='gray', ls='--', lw=.7)
            ax.axvline(1.2, color='gray', ls='--', lw=.7)
            ax.axvspan(*report['blind_scan_m'], alpha=.05, color='teal')
            if row == 0: ax.legend(fontsize=7)
            if row == len(profiles)-1: ax.set_xlabel('Nominal range (m); dashed reported placements')
    fig.savefig(output/'profiles.png', dpi=125); plt.close(fig)


if __name__ == '__main__':
    main()
