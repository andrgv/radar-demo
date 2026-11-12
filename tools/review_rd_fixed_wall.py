"""Preliminary, provisionally labeled review of the November 10 fixed-radar capture."""
import hashlib
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from radar_min.__main__ import read_recording
from radar_min.core import db, range_spectrum


SOURCE = Path('recordings/gui-20261110-162410-575208/live-001')
OUTPUT = Path('evidence/rd-fixed-wall-20261110')
PHASES = [('far hold 1', 18.58), ('approach', 28.03), ('near hold (~30 cm)', 31.01),
          ('retreat', 25.53), ('far hold 2', 30.71), ('wall only', 33.64)]


def main(window_fraction=None, figure_title='Fixed radar + moving target + nearby wall — provisional stopwatch labels'):
    config, frames, parser = read_recording(SOURCE)
    arrays = np.load(OUTPUT/'maps/maps.npz')
    full, moving = arrays['full_power'], arrays['moving_power']
    frequency = arrays['cycles_per_chirp']
    arrivals = [json.loads(line) for line in (SOURCE/'arrivals.jsonl').read_text().splitlines()]
    readings = [json.loads(line) for line in (SOURCE/'readings.jsonl').read_text().splitlines()]
    if [f.sequence for f in frames] != [a['sequence'] for a in arrivals]:
        raise ValueError('Arrival/frame alignment mismatch')
    if [f.sequence for f in frames] != [r['frame_sequence'] for r in readings]:
        raise ValueError('Reading/frame alignment mismatch')
    times = (np.array([a['host_unix_ns'] for a in arrivals], dtype=np.int64)-arrivals[0]['host_unix_ns'])/1e9
    power = np.array([r['power'] if len(r.get('power', [])) == config.samples//2+1
                      else [np.nan]*(config.samples//2+1) for r in readings])
    fine = np.array([r.get('experimental_range_m') if r.get('experimental_range_m') is not None
                     else np.nan for r in readings])
    presence = np.array([r['target_detected'] for r in readings])
    # Fixed range-bin probes complement the viewer's changing strongest-bin probe.
    phase = []
    consistency = []
    for frame in frames:
        spectrum = range_spectrum(frame, config)
        products = spectrum[1:]*spectrum[:-1].conj()
        z = products.sum(axis=(0, 2))/np.maximum(np.abs(products).sum(axis=(0, 2)), 1e-30)
        phase.append(np.angle(z)/(2*np.pi))
        consistency.append(np.abs(z))
    phase, consistency = np.array(phase), np.array(consistency)
    ratio = moving[:, :, 1:9].sum(axis=(1, 2))/full[:, :, 1:9].sum(axis=(1, 2))
    peak_d = frequency[np.argmax(full[:, :, 1:9].max(axis=2), axis=1)]
    bounds = np.r_[0, np.cumsum([duration for _, duration in PHASES])]
    summaries = []
    for i, (label, _) in enumerate(PHASES):
        # Approach's last few seconds were already static; use a wider end margin.
        if window_fraction is None:
            start, end = bounds[i]+3, min(bounds[i+1]-(6 if label == 'approach' else 3), times[-1])
        else:
            margin = (bounds[i+1]-bounds[i])*(1-window_fraction)/2
            start, end = bounds[i]+margin, min(bounds[i+1]-margin, times[-1])
        ids = (times >= start) & (times < end)
        valid_ids = ids & arrays['valid']
        numeric = fine[ids & np.isfinite(fine)]
        summaries.append(dict(label=label, buffered_host_window_s=[start, end], frames=int(ids.sum()),
            valid_doppler_frames=int(valid_ids.sum()),
            presence_rate=float(presence[ids].mean()), numeric_rate=float(np.isfinite(fine[ids]).mean()),
            reasons=dict(Counter(readings[j]['reason'] for j in np.flatnonzero(ids))),
            full_peak_nonzero_fraction_by_range_bin1to8=np.mean(
                np.argmax(full[valid_ids, :, 1:9], axis=1) != len(frequency)//2, axis=0).tolist(),
            conditional_range_cm_p05_median_p95=(np.percentile(numeric*100, [5, 50, 95]).tolist()
                                                if len(numeric) else None),
            full_peak_nonzero_bin_fraction=float(np.mean(peak_d[valid_ids] != 0)),
            moving_full_power_ratio_p05_median_p95=np.percentile(ratio[valid_ids], [5, 50, 95]).tolist(),
            median_native_range_power_db=db(np.nanmedian(power[ids], axis=0)).tolist(),
            phase_cycles_per_chirp_p05_median_p95_bins1to8=np.percentile(phase[ids, 1:9], [5, 50, 95], axis=0).tolist(),
            median_phase_resultant_bins1to8=np.median(consistency[ids, 1:9], axis=0).tolist()))
    report = dict(recording=str(SOURCE), input_sha256=hashlib.sha256((SOURCE/'frames.grd').read_bytes()).hexdigest(),
        review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        config_fingerprint=config.fingerprint, frames=len(frames), host_duration_s=float(times[-1]),
        labels='User confirmed consecutive approximate phase durations. Assumed aligned to first frame; no fitted time shift. Transition margins excluded.',
        requested_phase_durations_s=PHASES, phase_boundaries_host_s=bounds.tolist(),
        window_policy='middle fraction '+str(window_fraction) if window_fraction is not None else '3 s margins; approach end 6 s',
        notes='No subtraction or threshold tuning. Wall-only is a comparison control. Ratios use range bins 1..8, not target association. '
              'Phase probes mix reflectors and are not physical velocity estimates. Full Doppler peak at zero does not prove absence of motion.',
        timing_verified=False, calibrated=False,
        capture_summary=json.loads((SOURCE/'capture-summary.json').read_text()),
        maximum_corrected_clock_error_s=max(r['relative_timing_error_s'] for r in readings),
        maximum_frozen_clock_error_s=max(r['relative_timing_error_s'] for r in readings if r['clock_sync']['state']=='frozen'),
        final_clock=readings[-1]['clock_sync'], phases=summaries)
    (OUTPUT/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False))
    np.savez_compressed(OUTPUT/'review-timelines.npz', host_time_s=times,
                        phase_cycles_per_chirp=phase, phase_resultant=consistency,
                        moving_full_ratio=ratio, native_range_power=power)

    fig, axes = plt.subplots(5, 1, figsize=(14, 15), sharex=True, layout='constrained')
    for ax, values, title in zip(axes[:2], (full, moving), ('Full map: maximum over Doppler (diagnostic projection)',
                                                        'Mean-removed map: maximum over Doppler')):
        im = ax.pcolormesh(times, np.arange(13)*config.spacing_m, db(values[:, :, :13].max(axis=1)).T,
                           shading='nearest', vmin=20, vmax=80, rasterized=True)
        fig.colorbar(im, ax=ax, label='dB ADC units²')
        ax.set_ylabel('Nominal range (m)')
        ax.set_title(title)
    im = axes[2].pcolormesh(times, frequency, db(full[:, :, 1:9].max(axis=2)).T,
                            shading='nearest', vmin=20, vmax=80, rasterized=True)
    fig.colorbar(im, ax=axes[2], label='dB ADC units²')
    axes[2].set_ylabel('Cycles/chirp')
    axes[2].set_title('Full-map Doppler projection, range bins 1–8; timing unverified')
    axes[3].plot(times, db(ratio), lw=0.7)
    axes[3].set_ylabel('Moving/full power (dB)')
    axes[3].set_title('Mean-removed/full total power ratio, range bins 1–8')
    axes[3].grid(alpha=0.25)
    axes[4].plot(times, fine*100, '.', ms=2)
    axes[4].set_ylabel('Experimental range (cm)')
    axes[4].set_xlabel('Host seconds from first saved frame')
    axes[4].set_title('Recorded 1D CFAR output; gaps remain blank; no target-identity claim')
    axes[4].grid(alpha=0.25)
    for ax in axes:
        for edge in bounds[1:-1]:
            ax.axvline(edge, color='black', ls='--', alpha=0.5)
        ax.set_xlim(0, times[-1])
    for i, (label, _) in enumerate(PHASES):
        axes[0].text((bounds[i]+bounds[i+1])/2, 1.02, label, ha='center',
                     transform=axes[0].get_xaxis_transform(), fontsize=8)
    axes[0].set_title('Full map: maximum over Doppler (diagnostic projection)', pad=30)
    fig.suptitle(figure_title, fontsize=14)
    fig.savefig(OUTPUT/'timeline.png', dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    for item in summaries:
        axes[0].plot(np.arange(13)*config.spacing_m, item['median_native_range_power_db'][:13], label=item['label'])
    axes[0].set(xlabel='Nominal range (m)', ylabel='Median native power (dB ADC units²)', title='Buffered phase spectra (no subtraction)')
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)
    for k in (1, 2, 3, 4, 6, 7):
        axes[1].plot(times, phase[:, k], '.', ms=1, label=f'bin {k}', alpha=0.5)
    axes[1].set(xlabel='Host seconds', ylabel='Cycles/chirp from adjacent phase products',
                title='Fixed-bin phase probes; mixed returns, timing unverified', ylim=(-0.004, 0.004))
    axes[1].legend(fontsize=8)
    for edge in bounds[1:-1]:
        axes[1].axvline(edge, color='black', ls='--', alpha=0.5)
    fig.savefig(OUTPUT/'spectra-and-phase.png', dpi=150)
    plt.close(fig)
    for item in summaries:
        print(item['label'], item['frames'], 'CFAR numeric', round(item['numeric_rate'], 3),
              'range cm', item['conditional_range_cm_p05_median_p95'],
              'moving/full median dB', round(float(db(item['moving_full_power_ratio_p05_median_p95'][1])), 2),
              'nonzero Doppler peak fraction', item['full_peak_nonzero_bin_fraction'])


if __name__ == '__main__':
    main()
