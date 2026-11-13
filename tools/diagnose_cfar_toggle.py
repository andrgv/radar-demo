"""Inspect repeated empty/target intervals without tuning the live detector."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig
from radar_min.core import db


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--interval-seconds',type=float,default=6)
    parser.add_argument('--trim-seconds',type=float,default=1)
    parser.add_argument('--target-m',type=float,default=.5)
    args=parser.parse_args(argv)
    if not 0<=args.trim_seconds<args.interval_seconds/2:
        parser.error('Trim must be nonnegative and smaller than half the interval')
    config,frames,_=read_recording(args.recording)
    meta=json.loads((args.recording/'metadata.json').read_text())
    settings=CfarConfig(**meta['detector']['cfar'])
    # Diagnose recorded decisions, retaining the acquisition algorithm version.
    # Live code may have evolved since this recording was made.
    readings=[json.loads(line) for line in (args.recording/'readings.jsonl').read_text().splitlines()]
    if len(readings)!=len(frames) or any(r['frame_sequence']!=f.sequence for r,f in zip(readings,frames)):
        raise ValueError('Saved decisions do not align with raw frames')
    times=np.array([((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6 for f in frames])
    dense=[];rx_dense=[]
    nfft=4096
    for frame in frames:
        x=frame.adc[config.discard_chirps:].astype(float)
        x-=x.mean(axis=1,keepdims=True)
        spectrum=np.fft.rfft(x*np.hanning(config.samples)[None,:,None],n=nfft,axis=1)*(2/np.hanning(config.samples).sum())
        p=np.mean(abs(spectrum)**2,axis=0)
        dense.append(p.mean(axis=1));rx_dense.append(p)
    dense=np.array(dense);rx_dense=np.array(rx_dense)
    coords=np.arange(nfft//2+1)*config.spacing_m*config.samples/nfft
    search=(coords>=.15)&(coords<=1.5)
    peak_positions=coords[search][np.argmax(dense[:,search],axis=1)]
    intervals=[]
    for i in range(5):
        start=i*args.interval_seconds+args.trim_seconds
        end=(i+1)*args.interval_seconds-args.trim_seconds
        mask=(times>=start)&(times<end)
        indices=np.flatnonzero(mask)
        if not len(indices):raise ValueError('Recording does not cover all five trimmed intervals')
        rows=[readings[j] for j in indices]
        has_candidate=[bool(r['candidates']) for r in rows]
        accepted=[r['target_detected'] for r in rows]
        p=np.array([r['power'] for r in rows])
        delta=db(p[:,1])-db(p[:,2])
        percentiles=np.percentile(peak_positions[mask]*100,[5,50,95]).tolist()
        rx_peaks=[]
        for rx in range(3):
            positions=coords[search][np.argmax(rx_dense[mask][:,search,rx],axis=1)]
            rx_peaks.append(np.percentile(positions*100,[5,50,95]).tolist())
        intervals.append(dict(index=i,label='empty' if i%2==0 else 'target',
            target_m=None if i%2==0 else args.target_m,start_s=start,end_s=end,
            frames=len(rows),any_candidate_frames=sum(has_candidate),accepted_frames=sum(accepted),
            accepted_bins=dict(Counter(str(r['range_bin']) for r in rows if r['target_detected'])),
            candidate_bins=dict(Counter(str(r['candidate_bin']) for r in rows)),
            both_bins_1_2_qualified=sum(1 in r.get('qualified_bins',[]) and 2 in r.get('qualified_bins',[]) for r in rows),
            grouped_bins_1_2=sum(any(1 in c['bins'] and 2 in c['bins'] for c in r['candidates']) for r in rows),
            candidate_bin_switches=sum(a['candidate_bin'] is not None and b['candidate_bin'] is not None and a['candidate_bin']!=b['candidate_bin'] for a,b in zip(rows,rows[1:])),
            median_bin_1_minus_bin_2_db=float(np.median(delta)),
            bin_power_db_median=db(np.median(p,axis=0)).tolist(),
            dense_raw_peak_cm_p05_median_p95=percentiles,
            per_rx_dense_peak_cm_p05_median_p95=rx_peaks,
            reasons=dict(Counter(r['reason'] for r in rows))))
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(recording=str(args.recording),raw_sha256=hashlib.sha256((args.recording/'frames.grd').read_bytes()).hexdigest(),
        settings=meta['detector'],config_fingerprint=config.fingerprint,frames=len(frames),duration_s=float(times[-1]),
        approximate_interval_seconds=args.interval_seconds,trim_seconds=args.trim_seconds,
        timing_note='User reports approximately six seconds per state; transitions inferred, not instrumented. One second removed from each end of each nominal interval.',
        accepted_frame_transport=json.loads((args.recording/'capture-summary.json').read_text()),
        dense_peak_note='Raw mean-removed Hann FFT zero-padded to 4096 for inspection only. No empty subtraction, fine-fit gate, additional physical resolution or validated distance estimator.',
        intervals=intervals,excluded_transition_or_tail_frames=len(frames)-sum(r['frames'] for r in intervals))
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,9),layout='constrained')
    for row in intervals:
        for ax in axes[:2]:
            ax.axvspan(row['start_s'],row['end_s'],color='#167d8d' if row['label']=='target' else '#999999',alpha=.12)
    powers=np.array([r.get('power',[np.nan]*33) for r in readings])
    axes[0].plot(times,db(powers[:,1]),label='Bin 1 (~35 cm)')
    axes[0].plot(times,db(powers[:,2]),label='Bin 2 (~70 cm)')
    axes[0].set(title='Repeated empty / 50 cm target / empty / target / empty',ylabel='Power (dB, ADC units²)')
    axes[0].legend()
    accepted=[r['provisional_range_m']*100 if r['target_detected'] else np.nan for r in readings]
    axes[1].plot(times,accepted,'.',ms=4,label='Accepted coarse bin coordinate')
    axes[1].plot(times,peak_positions*100,color='gray',alpha=.6,lw=.8,label='Raw dense-spectrum maximum (diagnostic)')
    axes[1].axhline(args.target_m*100,color='black',ls='--',lw=.7,label='Reported target placement')
    axes[1].set(xlabel='Seconds since first frame',ylabel='Nominal coordinate (cm)',ylim=(0,160))
    axes[1].legend(fontsize=8)
    for row in intervals:
        mask=(times>=row['start_s'])&(times<row['end_s'])
        axes[2].plot(coords,db(np.median(dense[mask],axis=0)),label=f"{row['index']+1}: {row['label']} {row['start_s']:g}–{row['end_s']:g} s")
    for k in [1,2]:axes[2].axvline(k*config.spacing_m,color='gray',ls=':',lw=1)
    axes[2].axvline(args.target_m,color='black',ls='--',lw=.7)
    axes[2].set(xlim=(0,2),xlabel='Nominal beat-frequency coordinate (m)',ylabel='Median raw power (dB)',title='Trimmed interval spectra · no empty subtraction')
    axes[2].legend(fontsize=8)
    fig.savefig(args.output/'toggle-diagnosis.png',dpi=150);plt.close(fig)
    lines=['# Repeated empty/50 cm toggle diagnosis','',report['timing_note'],'',
        'Teal shading in the plot indicates approximate target interiors; gray shading indicates empty interiors. Other frames are excluded from interval metrics.','',
        '| Interval | Interior (s) | Frames | Has CFAR candidate | Accepted | Both bins 1/2 qualified | Candidate switches | Raw dense-peak median (cm) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in intervals:
        lines.append(f"| {r['index']+1}: {r['label']} | {r['start_s']:g}–{r['end_s']:g} | {r['frames']} | {r['any_candidate_frames']} | {r['accepted_frames']} | {r['both_bins_1_2_qualified']} | {r['candidate_bin_switches']} | {r['dense_raw_peak_cm_p05_median_p95'][1]:.1f} |")
    lines+=['','## Interpretation','',
        'Compare candidate availability against accepted output: a broad return can exceed threshold in two adjacent cells while its strongest bin changes. The detector groups adjacent cells, but persistence is keyed to the group maximum’s exact bin. Changes of maximum restart confirmation even if both bins remain in one group.',
        '', 'This identifies a possible rejection mechanism; it does not establish the cause of the empty-scene return in live-002. Different empty behavior between these recordings argues against treating one fixed threshold as a universally validated solution.',
        '', 'Dense-spectrum peaks are diagnostics of the raw signal, including clutter and leakage. Zero padding samples the spectrum more finely without adding physical resolution. A peak near the placement is not proof of target association or an accurate distance estimator; inspect all intervals and per-RX distributions in JSON.',
        '', 'No live algorithm, threshold, baseline, smoothing, or firmware was changed. These intervals are approximate and operator motion at transitions can contaminate them.',
        '', '[Plot](toggle-diagnosis.png) · [Full metrics and provenance](report.json)', '', 'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.diagnose_cfar_toggle {args.recording} --output evidence/new-toggle-diagnosis --interval-seconds {args.interval_seconds:g} --trim-seconds {args.trim_seconds:g} --target-m {args.target_m:g}', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    for r in intervals:print({k:r[k] for k in ['label','frames','any_candidate_frames','accepted_frames','both_bins_1_2_qualified','candidate_bin_switches','dense_raw_peak_cm_p05_median_p95']})
    return 0


if __name__=='__main__':raise SystemExit(main())
