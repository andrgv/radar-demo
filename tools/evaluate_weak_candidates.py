"""Fixed weak-candidate selector versus CA/OS and saved target/empty controls."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_os import OsCfarDetector,select_os_candidate
from radar_min.phase_range import CandidatePhaseRange
from radar_min.weak_candidate import METADATA,select_weak_candidate
from tools.qualify_avg16_cfar import aligned_times
from tools.sweep_cfar import episodes


MANIFESTS=['avg16-placements-20261111.json','avg16-repeat50-20261111.json',
    'avg16-operator-abab-20261111.json','avg16-operator-empty-abab-20261111.json',
    'avg16-motion-20261111.json','motion-aware-live-20261111.json',
    'reflector-live-20261111.json','foil-box-live-20261111.json','foil-box-repeat-20261111.json',
    'live-os-paired80-20261111.json']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rd-results',type=Path,default=Path('evidence/rx-diagnostics-20261111/results.jsonl.gz'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    # The existing joint audit independently verified these RD masks and peaks.
    rd={}
    with gzip.open(args.rd_results,'rt')as stream:
        for line in stream:
            r=json.loads(line);rd[(r['recording'],r['frame_sequence'])]=(r['valid'],r['cfar_clusters'])
    cases=[]
    for name in MANIFESTS:
        m=json.loads((Path('configs')/name).read_text())
        cases.extend(m.get('cases',[]))
        if 'recording'in m:cases.append(dict(recording=m['recording'],windows=m['windows']))
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',
        windows=[dict(label='80 cm stationary (approximate)',state='hold',nominal_target_m=.8,window_host_s=[2,73])]))
    settings=CfarConfig(1,4,4,2);sessions=[];plots=[]
    with gzip.open(args.output/'frames.jsonl.gz','wt')as stream:
        for case in cases:
            path=Path(case['recording']);c,frames,_=read_recording(path)
            saved=[json.loads(x)for x in(path/'readings.jsonl').read_text().splitlines()]
            arrivals=[json.loads(x)for x in(path/'arrivals.jsonl').read_text().splitlines()]
            times=aligned_times(frames,arrivals)
            if [f.sequence for f in frames]!=[r['frame_sequence']for r in saved]:raise ValueError('Saved sequence mismatch')
            ca=CfarDetector(c,settings);os=OsCfarDetector(c,settings);fitter=CandidatePhaseRange(c);rows=[]
            for frame,old,t in zip(frames,saved,times):
                baseline=ca.update(frame);candidate=os.update(frame);before=old.get('one_d',old)
                for k in('target_detected','range_bin','experimental_range_m','reason'):
                    if baseline[k]!=before[k]:raise ValueError('Frozen CA changed '+k)
                    if old.get('clutter_comparison')and candidate[k]!=old['clutter_comparison']['os'][k]:
                        raise ValueError('Saved OS changed '+k)
                if (str(path),frame.sequence)in rd:
                    valid,clusters=rd[(str(path),frame.sequence)]
                elif 'cfar_clusters'in old:
                    valid=old['valid'];clusters=old['cfar_clusters']
                else:raise ValueError('No validated RD sidecar')
                if not valid:clusters=[]
                previous=select_os_candidate(candidate,clusters);phase=None
                if previous['experimental_range_m']is not None:
                    phase=dict(frame_sequence=frame.sequence,**fitter.fit(frame,candidate['selected_group_bins']))
                weak=select_weak_candidate(candidate,clusters,phase,c)
                base=baseline['experimental_range_m'];proposed=base if base is not None else weak['experimental_range_m']
                row=dict(recording=str(path),frame_sequence=frame.sequence,host_time_s=float(t),
                    baseline_m=base,os_rd_m=previous['experimental_range_m'],weak_m=weak['experimental_range_m'],
                    hypothetical_fallback_m=proposed,recovery_m=weak['experimental_range_m']if base is None else None,
                    weak_selection=weak,phase_fit=phase)
                stream.write(json.dumps(row,allow_nan=False)+'\n');rows.append(row)
            windows=[]
            for w in case['windows']:
                if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
                ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
                channels={}
                for key in('baseline_m','os_rd_m','weak_m','hypothetical_fallback_m','recovery_m'):
                    values=np.array([rows[i][key]for i in ids if rows[i][key]is not None])
                    runs=episodes([rows[i][key]is not None for i in ids],[frames[i]for i in ids],c.frame_interval_s)
                    target=w.get('nominal_target_m')
                    channels[key]=dict(numeric_frames=len(values),frames=len(ids),
                        cm_p05_p50_p95=np.percentile(values*100,[5,50,95]).tolist()if len(values)else None,
                        conditional_placement_mae_cm=float(np.mean(abs(values-target))*100)if len(values)and target is not None else None,
                        episodes=len(runs),longest_s=max((r['duration_s']for r in runs),default=0))
                windows.append(dict(**w,channels=channels,weak_reasons=dict(Counter(rows[i]['weak_selection']['reason']for i in ids)),
                    selected_model_rejected_frames=sum(rows[i]['weak_m']is not None and not rows[i]['weak_selection']['phase_model_accepted']for i in ids)))
            sessions.append(dict(recording=str(path),frames=len(frames),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                config_fingerprint=c.fingerprint,ca_matches_saved=True,windows=windows,
                rd_source='audited current joint replay'if(str(path),frames[0].sequence)in rd else'saved joint readings with earlier live CA/OS/RD audit',
                saved_readings_sha256=hashlib.sha256((path/'readings.jsonl').read_bytes()).hexdigest()))
            plots.append((case,times,rows));print(str(path),dict(Counter(r['weak_selection']['reason']for r in rows)),flush=True)
    sources=['tools/evaluate_weak_candidates.py','radar_min/weak_candidate.py','radar_min/phase_range.py','radar_min/cfar.py','radar_min/cfar_os.py','radar_min/cfar_range.py','radar_min/core.py']
    report=dict(selector=METADATA,detector=dict(guard=1,training=4,min_training=4,factor=2,os_rank_fraction=.5),
        protocol='One fixed hypothesis using inherited phase geometry settings; no sweep or label fit. Default primary unchanged. Hypothetical fallback is a development comparison, not a promoted live policy. Global model rejection is preserved, and shape support alone does not certify range accuracy/identity. Quiet-window empty outputs must be read with all target failures.',
        sessions=sessions,rd_sidecar=str(args.rd_results),rd_sidecar_sha256=hashlib.sha256(args.rd_results.read_bytes()).hexdigest(),
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in sources},
        manifests={name:hashlib.sha256((Path('configs')/name).read_bytes()).hexdigest()for name in MANIFESTS})
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plots),1,figsize=(13,2.6*len(plots)),layout='constrained')
    for ax,(case,times,rows)in zip(axes,plots):
        for key,label in [('os_rd_m','Old OS + RD inspection'),('baseline_m','Frozen CA'),('recovery_m','New weak recovery inspection')]:
            ax.plot(times,[r[key]*100 if r[key]is not None else np.nan for r in rows],'.',ms=2,label=label)
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate')or w['state']=='motion':continue
            lo,hi=w['window_host_s'];target=w.get('nominal_target_m')
            ax.axvspan(lo,hi,color='teal'if target else'gray',alpha=.1)
            if target:ax.plot([lo,hi],[target*100]*2,'k--',lw=.7)
        ax.set(title=case['recording'],ylabel='Inspection cm',ylim=(0,170));ax.legend(fontsize=7)
    axes[-1].set_xlabel('Host seconds from first saved frame')
    fig.savefig(args.output/'comparison.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
