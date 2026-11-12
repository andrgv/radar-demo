"""Fixed lower-median OS reference versus frozen CA; development evidence only."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_os import OsCfarDetector,OsConfig,select_os_candidate
from radar_min.range_doppler import RangeDoppler
from radar_min.cfar_2d import CaCfar2D
from tools.qualify_avg16_cfar import aligned_times,summarize


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    manifests=[Path('configs/'+name) for name in ('avg16-placements-20261111.json',
        'avg16-repeat50-20261111.json','avg16-operator-abab-20261111.json',
        'avg16-operator-empty-abab-20261111.json','avg16-motion-20261111.json')]
    cases=[]
    for path in manifests:
        cases.extend(json.loads(path.read_text())['cases'])
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',
        windows=[dict(label='approximately 80 cm stationary',window_host_s=[2,73],
                      nominal_target_m=.8,state='hold',trim_s=2)]))
    settings=CfarConfig(1,4,4,2);policy=OsConfig(.5)
    sessions=[];plots=[]
    with gzip.open(args.output/'readings.jsonl.gz','wt') as stream:
        for case in cases:
            source=Path(case['recording']);config,frames,_=read_recording(source)
            arrivals=[json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
            saved=[json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
            if [r['frame_sequence'] for r in saved]!=[f.sequence for f in frames]:
                raise ValueError('Saved/frame sequence mismatch')
            times=aligned_times(frames,arrivals)
            ca=CfarDetector(config,settings);os=OsCfarDetector(config,settings,policy)
            rd=RangeDoppler(config);cfar2d=CaCfar2D((rd.count,config.samples//2+1))
            selections=[]
            readings={'ca':[],'os':[]}
            for frame,original,t in zip(frames,saved,times):
                a=ca.update(frame);b=os.update(frame)
                full,_,info=rd.update(frame)
                clusters=cfar2d.detect(full)[3] if info['valid'] else []
                selection=select_os_candidate(b,clusters)
                if not info['valid']:selection.update(experimental_range_m=None,reason=info['reason'])
                selections.append(selection)
                expected=original.get('one_d',original)
                for key in ('target_detected','range_bin','experimental_range_m','reason'):
                    if a[key]!=expected[key]:raise ValueError('Frozen CA mismatch: '+key)
                readings['ca'].append(a);readings['os'].append(b)
                stream.write(json.dumps(dict(recording=str(source),host_time_s=float(t),ca=a,os=b,selection=selection),allow_nan=False)+'\n')
            windows=[]
            for w in case['windows']:
                if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
                ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
                windows.append(dict(label=w['label'],state=w['state'],
                    selected_frames=sum(selections[i]['experimental_range_m'] is not None for i in ids),
                    selection_reasons=dict(Counter(selections[i]['reason'] for i in ids)),
                    ca=summarize(readings['ca'],frames,config,times,w),
                    os=summarize(readings['os'],frames,config,times,w)))
            sessions.append(dict(recording=str(source),raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
                config_fingerprint=config.fingerprint,frames=len(frames),ca_matches_saved=True,windows=windows,
                os_reasons=dict(Counter(r['reason'] for r in readings['os']))))
            plots.append((case,times,readings))
            print(str(source),'CA',sum(r['experimental_range_m'] is not None for r in readings['ca']),
                  'OS',sum(r['experimental_range_m'] is not None for r in readings['os']),flush=True)
    paths=['radar_min/cfar.py','radar_min/cfar_os.py','radar_min/cfar_range.py','radar_min/core.py',
           'radar_min/range_doppler.py','radar_min/cfar_2d.py',
           'tools/evaluate_clutter_reference.py','tools/qualify_avg16_cfar.py']
    report=dict(settings=asdict(settings),os=asdict(policy),
        policy='k=ceil(0.5*actual reference count); no rank/factor sweep; same guards, search mask, confirmation, fine estimator',
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
        manifests={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in manifests},sessions=sessions,
        interpretation='All recordings are development data. Conditional placement differences do not verify reflector identity. Target-absent returns may be real scene reflectors; they fail added-target specificity. OS reference remains experimental; no calibrated Pfa or automatic primary change.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plots),1,figsize=(13,3*len(plots)),layout='constrained')
    for ax,(case,times,readings) in zip(axes,plots):
        for mode in ('ca','os'):
            values=[r['experimental_range_m']*100 if r['experimental_range_m'] is not None else np.nan for r in readings[mode]]
            ax.plot(times,values,'.',ms=2,label=mode.upper())
        for w in case['windows']:
            if w.get('trim_s')!=2 or w.get('operator_split_approximate'):continue
            left,right=w['window_host_s'];target=w.get('nominal_target_m')
            ax.axvspan(left,right,color='gray' if target is None else 'teal',alpha=.1)
            if target is not None:ax.plot([left,right],[target*100]*2,'k--',lw=.8)
        ax.set(title=case['recording'],ylabel='Experimental cm',ylim=(0,170));ax.legend(fontsize=8)
    axes[-1].set_xlabel('Host seconds from first saved frame')
    fig.savefig(args.output/'comparison.png',dpi=150);plt.close(fig)
    lines=['# Fixed OS reference versus frozen CA','',report['interpretation'],'',
        '| Recording / window | CA numeric / frames | OS numeric / frames | OS median cm | Unique-support selection frames |',
        '|---|---:|---:|---:|---:|']
    for s in sessions:
        for w in s['windows']:
            a,b=w['ca'],w['os'];q=b['range_cm_p05_p50_p95']
            lines.append(f"| {s['recording']}: {w['label']} | {a['numeric_frames']}/{a['frames']} | {b['numeric_frames']}/{b['frames']} | {f'{q[1]:.1f}' if q else '—'} | {w['selected_frames']} |")
    lines+=['','[Detailed metrics and hashes](report.json) · [Comparison plot](comparison.png)',
            '', 'No automatic primary policy or detector default changed.']
    (args.output/'README.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
