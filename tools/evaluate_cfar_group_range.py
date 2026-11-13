"""Compare frozen CFAR v1 and group/fine-range v2 without retuning thresholds."""
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from tools.sweep_cfar import episodes


def measures(rows, frames, config, target):
    detected=[r['target_detected'] for r in rows]
    fine=[r.get('experimental_range_m') if r.get('algorithm')=='range-ca-cfar-v2' else r.get('provisional_range_m') for r in rows]
    values=[v for hit,v in zip(detected,fine) if hit and v is not None]
    runs=episodes(detected,frames,config.frame_interval_s)
    return dict(frames=len(rows),presence_frames=sum(detected),range_frames=len(values),
        presence_rate=sum(detected)/len(rows),range_coverage=len(values)/len(rows),
        conditional_mae_cm=float(np.mean(abs(np.array(values)-target))*100) if target is not None and values else None,
        range_cm_p05_median_p95=np.percentile(np.array(values)*100,[5,50,95]).tolist() if values else None,
        median_processing_ms=float(np.median([r['processing_ms'] for r in rows])),
        presence_episodes=len(runs),longest_presence_s=max((r['duration_s'] for r in runs),default=0))


def aggregate(sessions,variant):
    return dict(target_range_coverage=float(np.mean([r[variant]['range_coverage'] for r in sessions if r['target_m'] is not None])),
        target_presence_rate=float(np.mean([r[variant]['presence_rate'] for r in sessions if r['target_m'] is not None])),
        empty_presence_rate=float(np.mean([r[variant]['presence_rate'] for r in sessions if r['target_m'] is None])),
        empty_range_output_rate=float(np.mean([r[variant]['range_coverage'] for r in sessions if r['target_m'] is None])))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline-source',type=Path,default=Path('evidence/cfar-group-range-v2/baseline_cfar.py'))
    args=p.parse_args(argv)
    spec=importlib.util.spec_from_file_location('radar_min._frozen_cfar_v1',args.baseline_source)
    baseline=importlib.util.module_from_spec(spec);sys.modules[spec.name]=baseline;spec.loader.exec_module(baseline)
    study=json.loads(Path('configs/cfar-study.json').read_text())
    settings=CfarConfig(guard_cells=1,training_cells=4,min_training_cells=4,factor=2)
    cases=study['sessions']+[dict(recording=f'recordings/gui-20261109-215257-942086/live-{i:03}',split='fresh',target_m=None) for i in [1,2,3]]
    rows=[];all_readings={}
    for case in cases:
        path=Path(case['recording']);config,frames,_=read_recording(path)
        versions={}
        for name,cls in [('before',baseline.CfarDetector),('after',CfarDetector)]:
            detector=cls(config,settings)
            versions[name]=[detector.update(f) for f in frames]
        row=dict(**case,raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                 config_fingerprint=config.fingerprint,**{k:measures(v,frames,config,case['target_m']) for k,v in versions.items()})
        rows.append(row)
        if case['split']=='fresh':all_readings[path.name]=(frames,config,versions)
        print(path.name, row['before']['presence_frames'],row['after']['presence_frames'],flush=True)
    intervals=[]
    for name,windows in [('live-003',[(f'{i+1}: '+('empty' if i%2==0 else '50 cm'),i*6+1,(i+1)*6-1,None if i%2==0 else .5) for i in range(5)]),
                         ('live-002',[('initial empty',1,3,None),('50 cm target',8,24,.5),('ending empty',27,29.1,None)])]:
        frames,config,versions=all_readings[name]
        times=np.array([((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6 for f in frames])
        for label,start,end,target in windows:
            ids=np.flatnonzero((times>=start)&(times<end))
            selected=[frames[i] for i in ids]
            intervals.append(dict(recording=name,label=label,target_m=target,start_s=start,end_s=end,
                **{k:measures([v[i] for i in ids],selected,config,target) for k,v in versions.items()}))
    args.output.mkdir(parents=True,exist_ok=False)
    source_paths=['radar_min/core.py','radar_min/cfar.py','radar_min/cfar_range.py','tools/evaluate_cfar_group_range.py',str(args.baseline_source)]
    report=dict(settings=asdict(settings),source_sha256={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in source_paths},
        baseline_source=str(args.baseline_source),thresholds_retuned=False,interval_labels_approximate=True,
        session_note='Fresh recordings mix states; whole-recording metrics are output counts, not empty false-alarm scores. Only approximate interior windows carry state labels.',
        sessions=rows,intervals=intervals,
        historical_summary={variant:aggregate([r for r in rows if r['split']!='fresh'],variant) for variant in ['before','after']})
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (args.output/'frames.jsonl').open('w') as output:
        for name,(frames,config,versions) in all_readings.items():
            for i,f in enumerate(frames):
                output.write(json.dumps(dict(recording=name,time_s=((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6,
                    before_bin=versions['before'][i]['range_bin'],before_m=versions['before'][i]['provisional_range_m'],
                    after_presence=versions['after'][i]['target_detected'],after_m=versions['after'][i]['experimental_range_m'],
                    after_fine=versions['after'][i]['fine_range']))+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,8),layout='constrained')
    for ax,(name,(frames,config,versions)) in zip(axes,all_readings.items()):
        times=[((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6 for f in frames]
        for version,key,label in [('before','provisional_range_m','Before: bin center'),('after','experimental_range_m','After: fine peak')]:
            values=[r.get(key)*100 if r['target_detected'] and r.get(key) is not None else np.nan for r in versions[version]]
            ax.plot(times,values,'.',ms=2,label=label)
        for interval in intervals:
            if interval['recording']==name:
                ax.axvspan(interval['start_s'],interval['end_s'],alpha=.12,color='teal' if interval['target_m'] else 'gray')
        ax.set(title=name,ylabel='Experimental coordinate (cm)',ylim=(0,160));ax.legend(fontsize=8)
    axes[-1].set_xlabel('Seconds since first frame')
    fig.savefig(args.output/'fresh-comparison.png',dpi=150);plt.close(fig)
    lines=['# CFAR group confirmation and baseline-free fine range','',
        'Threshold settings remain frozen at guard 1, training/minimum 4, factor 2. Before uses the saved v1 source; after uses v2. No smoothing or empty subtraction.','',
        '## Fresh recording intervals (approximate)','',
        '| Recording / state | Window (s) | Before output | After fine output | After median (cm) | After conditional MAE (cm) |',
        '|---|---:|---:|---:|---:|---:|']
    for r in intervals:
        a=r['after'];q=a['range_cm_p05_median_p95'];mae=a['conditional_mae_cm']
        lines.append(f"| {r['recording']} {r['label']} | {r['start_s']:g}–{r['end_s']:g} | {r['before']['range_frames']}/{a['frames']} | {a['range_frames']}/{a['frames']} | {q[1]:.1f} | {mae:.1f} |" if q and mae is not None else
            f"| {r['recording']} {r['label']} | {r['start_s']:g}–{r['end_s']:g} | {r['before']['range_frames']}/{a['frames']} | {a['range_frames']}/{a['frames']} | {f'{q[1]:.1f}' if q else '—'} | — |")
    lines+=['','## Historical replay','',
        'All 30 labeled historical recordings were replayed, including empty captures and other profiles. Each recording has equal weight within target/empty classes.','',
        '| Method | Target range coverage | Empty presence | Empty numeric output |','|---|---:|---:|---:|']
    for version,m in report['historical_summary'].items():
        lines.append(f"| {version} | {m['target_range_coverage']:.1%} | {m['empty_presence_rate']:.1%} | {m['empty_range_output_rate']:.1%} |")
    lines+=['','## Limitations','',
        '- Group overlap allows confirmation to survive a change of maximum by one bin. It does not prove object identity, and can also confirm clutter more readily. Empty presence and numeric outputs are reported separately.',
        '- Refinement searches the current raw Hann spectrum within half-bin boundaries around the selected group. Boundary maxima or multiple local maxima within 3 dB of the strongest leave distance unresolved. Presence can remain true with no numeric distance.',
        '- Native `range_bin` and `provisional_range_m` retain coarse coordinates. `experimental_range_m` is the new UI/history value. `range_m` remains null and calibration false.',
        '- Fine sampling and interpolation do not add physical resolution or establish centimeter accuracy. Conditional error excludes unresolved/missing outputs; read it alongside coverage. Scene transition times and placements are approximate.',
        '- These fresh recordings informed the change. Results are development evidence, not independent validation. Empty-scene failures remain; no threshold retuning or firmware changes were made.',
        '', '[Before/after plot](fresh-comparison.png) · [Full per-session metrics and source hashes](report.json) · [Fresh-frame decisions](frames.jsonl)', '',
        'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.evaluate_cfar_group_range --baseline-source {args.baseline_source} --output evidence/new-cfar-v2-evaluation', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(report['historical_summary'],indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
