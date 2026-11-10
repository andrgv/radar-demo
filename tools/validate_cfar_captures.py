"""Validate saved CFAR v2 decisions on explicit alternating scene labels; no tuning."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from tools.sweep_cfar import episodes


def summarize(rows,frames,config,target):
    values=np.array([r['experimental_range_m']*100 for r in rows if r['target_detected'] and r.get('experimental_range_m') is not None])
    mask=[r['target_detected'] and r.get('experimental_range_m') is not None for r in rows]
    runs=episodes(mask,frames,config.frame_interval_s)
    return dict(frames=len(rows),presence_frames=sum(r['target_detected'] for r in rows),range_frames=len(values),
        range_coverage=len(values)/len(rows) if rows else None,
        range_cm_p05_median_p95=np.percentile(values,[5,50,95]).tolist() if len(values) else None,
        conditional_mae_cm=float(np.mean(abs(values-target*100))) if target is not None and len(values) else None,
        conditional_bias_cm=float(np.mean(values-target*100)) if target is not None and len(values) else None,
        within_5cm_frames=int(np.sum(abs(values-target*100)<=5)) if target is not None else None,
        errors_over_10cm=int(np.sum(abs(values-target*100)>10)) if target is not None else None,
        accepted_bins=dict(Counter(str(r['range_bin']) for r in rows if r['target_detected'])),
        reasons=dict(Counter(r['reason'] for r in rows)),range_episodes=runs,
        longest_output_s=max((r['duration_s'] for r in runs),default=0))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,default=Path('configs/cfar-validation-20261109-224819.json'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    manifest=json.loads(args.manifest.read_text());sessions=[];plot_data=[]
    for case in manifest['cases']:
        path=Path(case['recording']);config,frames,_=read_recording(path)
        metadata=json.loads((path/'metadata.json').read_text())
        readings=[json.loads(line) for line in (path/'readings.jsonl').read_text().splitlines()]
        if len(readings)!=len(frames):raise ValueError('Saved/raw frame count differs')
        d=CfarDetector(config,CfarConfig(**metadata['detector']['cfar']))
        for f,saved in zip(frames,readings):
            current=d.update(f)
            if saved['frame_sequence']!=f.sequence or saved['target_detected']!=current['target_detected'] or saved['range_bin']!=current['range_bin']:
                raise ValueError('Current replay does not reproduce saved decisions')
            a,b=saved.get('experimental_range_m'),current.get('experimental_range_m')
            if (a is None)!=(b is None) or (a is not None and abs(a-b)>1e-9):
                raise ValueError('Current fine estimate does not reproduce saved output')
        times=np.array([((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6 for f in frames])
        interiors=[]
        for trim in [1,2]:
            for i in range(case['interval_count']):
                start=i*case['interval_seconds']+trim;end=(i+1)*case['interval_seconds']-trim
                ids=np.flatnonzero((times>=start)&(times<end))
                target=case['target_m'] if i%2 else None
                interiors.append(dict(index=i+1,label='target' if i%2 else 'empty',target_m=target,
                    trim_seconds=trim,start_s=start,end_s=end,truncated=bool(times[-1]<end-config.frame_interval_s),
                    **summarize([readings[j] for j in ids],[frames[j] for j in ids],config,target)))
        sessions.append(dict(**case,frames=len(frames),duration_s=float(times[-1]),metadata=metadata,
            raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),config_fingerprint=config.fingerprint,
            transport=json.loads((path/'capture-summary.json').read_text()),replay_matches_saved=True,intervals=interiors))
        plot_data.append((case,times,readings))
    args.output.mkdir(parents=True,exist_ok=False)
    sources=['radar_min/cfar.py','radar_min/cfar_range.py','radar_min/core.py','tools/validate_cfar_captures.py']
    report=dict(schema=1,manifest=manifest,manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        source_sha256={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in sources},
        no_tuning=True,primary_trim_seconds=2,label_uncertainty='Approximate user timing; trimmed windows are provisional scene labels, not frame-exact truth.',sessions=sessions)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plot_data),2,figsize=(12,7),layout='constrained')
    for index,(case,times,readings) in enumerate(plot_data):
        ax=axes[index,0]
        vals=[r['experimental_range_m']*100 if r['target_detected'] and r.get('experimental_range_m') is not None else np.nan for r in readings]
        ax.plot(times,vals,'.',ms=3,label='Accepted experimental peak')
        for i in range(case['interval_count']):
            start=i*case['interval_seconds'];end=(i+1)*case['interval_seconds']
            ax.axvspan(start+2,end-2,alpha=.15,color='teal' if i%2 else 'gray')
            if i%2:ax.plot([start,end],[case['target_m']*100]*2,'k--',lw=1)
        ax.set(title=f"{Path(case['recording']).name} · target {case['target_m']*100:g} cm",xlabel='Seconds since first frame',ylabel='Experimental coordinate (cm)',ylim=(0,160));ax.legend(fontsize=8)
        ax=axes[index,1]
        for k in [1,2,3]:
            ratios=[10*np.log10(r['power'][k]/r['threshold_power'][k]) if r.get('power') and r['threshold_power'][k] else np.nan for r in readings]
            ax.plot(times,ratios,lw=.8,label=f'Bin {k}')
        ax.axhline(0,color='black',ls='--',lw=1)
        ax.set(title='Power above CFAR threshold',xlabel='Seconds since first frame',ylabel='dB');ax.legend(fontsize=8)
    fig.savefig(args.output/'validation.png',dpi=150);plt.close(fig)
    lines=['# Fresh CFAR v2 validation: 50 cm and 80 cm','',
        'Both captures reproduce saved acquisition decisions and fine estimates under the current code. No thresholds or algorithms were tuned to these data.', '',
        'State changes are approximately every six seconds. Primary metrics exclude two seconds at each side of nominal intervals. One-second-trim metrics are included to expose timing sensitivity. The 50 cm recording ends after 27.5 s, so the last nominal empty window is truncated.','']
    for trim in [2,1]:
        lines += ['',f'## {trim}-second trim at each interval boundary','',
            '| Target / interval | State | Window (s) | Range outputs / frames | Median (cm) | 5th–95th (cm) | Conditional MAE (cm) |',
            '|---|---|---:|---:|---:|---:|---:|']
        for session in sessions:
            for r in session['intervals']:
                if r['trim_seconds']!=trim:continue
                q=r['range_cm_p05_median_p95'];mae=r['conditional_mae_cm']
                lines.append(f"| {session['target_m']*100:g} cm / {r['index']} | {r['label']} | {r['start_s']:g}–{r['end_s']:g}{' (truncated)' if r['truncated'] else ''} | {r['range_frames']}/{r['frames']} | {f'{q[1]:.1f}' if q else '—'} | {f'{q[0]:.1f}–{q[2]:.1f}' if q else '—'} | {f'{mae:.1f}' if mae is not None else '—'} |")
    lines+=['','## Main findings','']
    for session in sessions:
        primary=[r for r in session['intervals'] if r['trim_seconds']==2]
        targets=[r for r in primary if r['label']=='target'];empty=[r for r in primary if r['label']=='empty']
        lines.append(f"- At {session['target_m']*100:g} cm: {sum(r['range_frames'] for r in targets)}/{sum(r['frames'] for r in targets)} target-interior numeric outputs, and {sum(r['range_frames'] for r in empty)}/{sum(r['frames'] for r in empty)} unwanted empty-interior outputs. This pools the primary windows only; placement differences remain visible in the table.")
    lines+=['',
        'The 80 cm threshold plot shows a strong, sustained return in the middle placement and much more marginal returns in the other placements. Their missing outputs include no-candidate and confirmation rejections, not serial errors. The physical cause of the strength difference is not isolated.', '',
        'The two 50 cm placements give different peak medians despite the same reported distance. This argues against treating a single constant range offset or display smoothing as a complete fix. Preserve this validation set without retuning to it.', '',
        'A useful next controlled capture is a supported 80 cm target left untouched for 30 seconds, then removed/replaced at marked lateral position and orientation for repeated 15-second holds, with marked timestamps and the operator out of the beam. This can distinguish within-placement fluctuations from placement-dependent changes; it is evaluation data, not an empty baseline requirement.', '',
        '## Interpretation limits','',
        '- Coverage includes every available frame inside each labeled interior. Conditional errors use only numeric outputs, so they must be interpreted with coverage. No missing or wrong-range outputs are silently filled.',
        '- Zero outputs during short empty interiors do not establish a calibrated false-alarm rate. There are no reported CRC errors, sequence gaps or acquisition rejections in either capture; incomplete wire tails at stop are retained.',
        '- Approximate timing can assign removal/movement frames to nominal target windows. Neither low coverage nor a range outlier automatically identifies a specific physical cause.',
        '- These are new recordings collected after v2 implementation and are useful prospective checks. The small fixed scene, approximate placements, correlated frames and few repetitions do not establish general accuracy.',
        '- Fine spectrum peaks remain uncalibrated and can follow clutter/multipath. Presence qualification and peak estimation are assessed separately in JSON.', '',
        '[Timeline and threshold plots](validation.png) · [Full metrics, reasons and hashes](report.json)', '', 'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.validate_cfar_captures --manifest {args.manifest} --output evidence/new-cfar-fresh-validation', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    for s in sessions:
        print(s['recording'])
        for r in s['intervals']:
            if r['trim_seconds']==2:print(r['index'],r['label'],r['range_frames'],r['frames'],r['range_cm_p05_median_p95'],r['conditional_mae_cm'])
    return 0


if __name__=='__main__':raise SystemExit(main())
