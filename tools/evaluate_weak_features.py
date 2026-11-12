"""Fixed consecutive confirmation of weak scene features, separate from objects."""
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
from radar_min.rd_association import AssociationConfig
from radar_min.weak_features import WeakFeatureConfirmer
from tools.evaluate_weak_candidates import MANIFESTS
from tools.sweep_cfar import episodes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,default=Path('evidence/weak-motion-live-20261111/results.jsonl.gz'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    upstream_path=args.input.parent/'report.json';upstream=json.loads(upstream_path.read_text())
    settings={s['recording']:s['settings']for s in upstream['sessions']}
    grouped={};policies={};configs={}
    with gzip.open(args.input,'rt')as source,gzip.open(args.output/'frames.jsonl.gz','wt')as target:
        for line in source:
            r=json.loads(line);name=r['recording']
            if name not in policies:
                c=Config.load(Path(name)/'config.json');configs[name]=c
                policies[name]=WeakFeatureConfirmer(c,AssociationConfig(**settings[name]['association']),settings[name]['cfar']['doppler_edge'])
                grouped[name]=[]
            before=deepcopy((r['results'],r['association'],r['motion_result'],r['clutter_comparison']['weak_selection']))
            result=policies[name].update(r)
            if before!=(r['results'],r['association'],r['motion_result'],r['clutter_comparison']['weak_selection']):
                raise ValueError('Existing output mutated')
            if result['primary_eligible']or result['predicted']:raise ValueError('Weak feature promoted or predicted')
            if result['experimental_range_m']is not None and result['measurement_sequence']!=r['frame_sequence']:
                raise ValueError('Held weak feature range')
            row=dict(recording=name,frame_sequence=r['frame_sequence'],timestamp_us=r['timestamp_us'],
                baseline_m=r.get('experimental_range_m'),motion_m=r['motion_result']['experimental_range_m'],
                weak_candidate_m=r['clutter_comparison']['weak_selection']['experimental_range_m'],weak_feature_result=result)
            grouped[name].append(row);target.write(json.dumps(row,allow_nan=False)+'\n')
    cases=[]
    for name in MANIFESTS:
        m=json.loads((Path('configs')/name).read_text());cases.extend(m.get('cases',[]))
        if 'recording'in m:cases.append(dict(recording=m['recording'],windows=m['windows']))
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',windows=[
        dict(label='80 cm stationary (approximate)',state='hold',nominal_target_m=.8,window_host_s=[2,73])]))
    sessions=[];plots=[]
    for case in cases:
        name=case['recording'];rows=grouped[name];c=configs[name]
        arrivals=[json.loads(x)for x in(Path(name)/'arrivals.jsonl').read_text().splitlines()]
        if [r['frame_sequence']for r in rows]!=[a['sequence']for a in arrivals]:raise ValueError('Arrival mismatch')
        times=np.array([(a['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9 for a in arrivals])
        windows=[]
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]));channels={}
            for key in('baseline_m','motion_m','weak_candidate_m','confirmed_m'):
                values=[rows[i]['weak_feature_result']['experimental_range_m']if key=='confirmed_m'else rows[i][key]for i in ids]
                numeric=np.array([v for v in values if v is not None]);label=w.get('nominal_target_m')
                fs=[SimpleNamespace(sequence=rows[i]['frame_sequence'],timestamp_us=rows[i]['timestamp_us'])for i in ids]
                runs=episodes([v is not None for v in values],fs,c.frame_interval_s)
                channels[key]=dict(frames=len(ids),numeric_frames=len(numeric),episodes=len(runs),
                    longest_s=max((run['duration_s']for run in runs),default=0),
                    cm_p05_p50_p95=np.percentile(numeric*100,[5,50,95]).tolist()if len(numeric)else None,
                    conditional_placement_mae_cm=float(np.mean(abs(numeric-label))*100)if len(numeric)and label is not None else None)
            windows.append(dict(**w,channels=channels,
                feature_states=dict(Counter(rows[i]['weak_feature_result']['state']for i in ids)),
                feature_reasons=dict(Counter(rows[i]['weak_feature_result']['reason']for i in ids)),
                confirmed_feature_ids=sorted({rows[i]['weak_feature_result']['feature_id']for i in ids if rows[i]['weak_feature_result']['confirmed']})))
        sessions.append(dict(recording=name,frames=len(rows),config_fingerprint=c.fingerprint,
            settings=policies[name].metadata,windows=windows,
            states=dict(Counter(r['weak_feature_result']['state']for r in rows)),
            arrivals_sha256=hashlib.sha256((Path(name)/'arrivals.jsonl').read_bytes()).hexdigest()))
        plots.append((case,times,rows));print(name,sessions[-1]['states'],flush=True)
    files=['tools/evaluate_weak_features.py','radar_min/weak_features.py','radar_min/rd_association.py']
    report=dict(sessions=sessions,input=str(args.input),input_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        upstream_report_sha256=hashlib.sha256(upstream_path.read_bytes()).hexdigest(),
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in files},
        manifests={n:hashlib.sha256((Path('configs')/n).read_bytes()).hexdigest()for n in MANIFESTS},
        interpretation='One fixed rule, inherited strong association persistence/native gates and existing RD isolation guard. No sweep, label fit or promotion; confirmed means consecutive supported scene peaks, not physical-object identity or calibrated accuracy.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plots),1,figsize=(13,2.5*len(plots)),layout='constrained')
    for ax,(case,times,rows)in zip(axes,plots):
        for key,label in(('weak_candidate_m','Weak candidate'),('confirmed_m','Confirmed weak scene feature (inspection)')):
            values=[r['weak_feature_result']['experimental_range_m']if key=='confirmed_m'else r[key]for r in rows]
            ax.plot(times,[v*100 if v is not None else np.nan for v in values],'.',ms=2,label=label)
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            lo,hi=w['window_host_s'];label=w.get('nominal_target_m')
            ax.axvspan(lo,hi,color='orange'if w['state']=='motion'else'teal'if label else'gray',alpha=.1)
            if label:ax.plot([lo,hi],[label*100]*2,'k--',lw=.7)
        ax.set(title=case['recording'],ylabel='Inspection cm',ylim=(0,170));ax.legend(fontsize=7)
    axes[-1].set_xlabel('Host seconds from first saved frame')
    fig.savefig(args.output/'comparison.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
