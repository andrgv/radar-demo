"""Replay an unbroken motion-seeded weak-stop link beside the frozen motion policy."""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from radar_min.core import Config
from radar_min.weak_motion import WeakMotionLink,METADATA
from tools.evaluate_weak_candidates import MANIFESTS
from tools.sweep_cfar import episodes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('evidence/weak-candidates-live-20261111/results.jsonl.gz'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    grouped={};policies={};configs={}
    with gzip.open(args.input,'rt')as source,gzip.open(args.output/'frames.jsonl.gz','wt')as target:
        for line in source:
            r=json.loads(line);name=r['recording']
            if name not in policies:
                configs[name]=Config.load(Path(name)/'config.json');policies[name]=WeakMotionLink(configs[name]);grouped[name]=[]
            before=deepcopy(r['motion_result']);result=policies[name].update(r)
            if r['motion_result']!=before:raise ValueError('Existing motion result mutated')
            reference=r['motion_result']['experimental_range_m']
            if result['experimental_range_m']is not None and reference is not None:raise ValueError('Link replaces a strong current point')
            if result['predicted']or result['primary_eligible']:raise ValueError('Inspection point promoted or predicted')
            weak=r.get('clutter_comparison',{}).get('weak_selection')or{}
            row=dict(recording=name,frame_sequence=r['frame_sequence'],timestamp_us=r['timestamp_us'],
                baseline_m=r.get('experimental_range_m'),reference_motion_m=reference,
                weak_candidate_m=weak.get('experimental_range_m'),weak_motion_result=result,
                weak_stage=result['weak_rd_stage'],
                hypothetical_supplement_m=reference if reference is not None else result['experimental_range_m'])
            grouped[name].append(row);target.write(json.dumps(row,allow_nan=False)+'\n')
    cases=[]
    for name in MANIFESTS:
        m=json.loads((Path('configs')/name).read_text());cases.extend(m.get('cases',[]))
        if 'recording'in m:cases.append(dict(recording=m['recording'],windows=m['windows']))
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',windows=[
        dict(label='80 cm stationary (approximate)',state='hold',nominal_target_m=.8,window_host_s=[2,73])]))
    sessions=[];plot_data=[]
    for case in cases:
        name=case['recording'];rows=grouped[name];c=configs[name]
        arrivals=[json.loads(x)for x in(Path(name)/'arrivals.jsonl').read_text().splitlines()]
        if [r['frame_sequence']for r in rows]!=[a['sequence']for a in arrivals]:raise ValueError('Arrival sequence mismatch')
        times=np.array([(a['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9 for a in arrivals])
        windows=[]
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
            channels={}
            for key in('baseline_m','reference_motion_m','weak_candidate_m','linked_m','hypothetical_supplement_m'):
                vals=[rows[i]['weak_motion_result']['experimental_range_m']if key=='linked_m'else rows[i][key]for i in ids]
                values=np.array([v for v in vals if v is not None]);label=w.get('nominal_target_m')
                fs=[SimpleNamespace(sequence=rows[i]['frame_sequence'],timestamp_us=rows[i]['timestamp_us'])for i in ids]
                runs=episodes([v is not None for v in vals],fs,c.frame_interval_s)
                channels[key]=dict(frames=len(ids),numeric_frames=len(values),episodes=len(runs),
                    longest_s=max((r['duration_s']for r in runs),default=0),
                    cm_p05_p50_p95=np.percentile(values*100,[5,50,95]).tolist()if len(values)else None,
                    conditional_placement_mae_cm=float(np.mean(abs(values-label))*100)if len(values)and label is not None else None)
            windows.append(dict(**w,channels=channels,
                weak_stages=dict(Counter(rows[i]['weak_stage']for i in ids if rows[i]['weak_stage']is not None)),
                link_reasons=dict(Counter(rows[i]['weak_motion_result']['reason']for i in ids)),
                link_states=dict(Counter(rows[i]['weak_motion_result']['state']for i in ids))))
        result=dict(recording=name,frames=len(rows),windows=windows,config_fingerprint=c.fingerprint,
            arrivals_sha256=hashlib.sha256((Path(name)/'arrivals.jsonl').read_bytes()).hexdigest(),
            linked_frames=sum(r['weak_motion_result']['experimental_range_m']is not None for r in rows),
            linked_events=[dict(frame_sequence=r['frame_sequence'],host_time_s=float(times[i]),
                range_m=r['weak_motion_result']['experimental_range_m'],baseline_m=r['baseline_m'],
                track_id=r['weak_motion_result']['track_id'],
                scored_labels=[w['label']for w in windows if w['window_host_s'][0]<=times[i]<w['window_host_s'][1]])
                for i,r in enumerate(rows)if r['weak_motion_result']['experimental_range_m']is not None],
            weak_stages=dict(Counter(r['weak_stage']for r in rows if r['weak_stage']is not None)),
            reasons=dict(Counter(r['weak_motion_result']['reason']for r in rows)))
        sessions.append(result);plot_data.append((case,times,rows))
        print(name,'linked frames',result['linked_frames'],result['reasons'],flush=True)
    paths=['tools/evaluate_weak_motion.py','radar_min/weak_motion.py','radar_min/motion_range.py']
    report=dict(method=METADATA,sessions=sessions,input=str(args.input),input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in paths},
        manifests={n:hashlib.sha256((Path('configs')/n).read_bytes()).hexdigest()for n in MANIFESTS},
        interpretation='One fixed rule specified before this replay; development recordings, no label fitting or parameter sweep. New link only supplements blank current motion output with a measured RD fine point, never a held or predicted point. No live primary change or verified target identity/accuracy claim.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plot_data),1,figsize=(13,2.5*len(plot_data)),layout='constrained')
    for ax,(case,times,rows)in zip(axes,plot_data):
        for key,label in(('reference_motion_m','Existing motion policy'),('linked_m','New linked weak stop (inspection)')):
            values=[r['weak_motion_result']['experimental_range_m']if key=='linked_m'else r[key]for r in rows]
            ax.plot(times,[v*100 if v is not None else np.nan for v in values],'.',ms=2,label=label)
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            lo,hi=w['window_host_s'];label=w.get('nominal_target_m')
            ax.axvspan(lo,hi,color='orange'if w['state']=='motion'else'teal'if label else'gray',alpha=.1)
            if label:ax.plot([lo,hi],[label*100]*2,'k--',lw=.7)
        numeric=[r[key]*100 for r in rows for key in('reference_motion_m','hypothetical_supplement_m')if r[key]is not None]
        ax.set(title=case['recording'],ylabel='Experimental cm',ylim=(0,max(170,max(numeric,default=0)*1.05)));ax.legend(fontsize=7)
    axes[-1].set_xlabel('Host seconds from first saved frame')
    fig.savefig(args.output/'comparison.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
