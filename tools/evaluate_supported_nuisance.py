"""Replay the fixed joint-component refinement over the complete regression corpus."""
import json
from pathlib import Path
import numpy as np
from tools.supported_nuisance_fit import SupportedNuisanceFit
from radar_min.core import Baseline,Detector
from radar_min.__main__ import read_recording
from tools.fit_range_signal import traces
from tools.evaluate_association import measure

def main():
    out=Path('evidence/supported-nuisance-1');out.mkdir(parents=True,exist_ok=True);report=[]
    roots=[(Path(f'recordings/hpf{run}-empty-before'),[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]) for run in ['350-a','100-a','350-b']]
    g=Path('recordings/gui-20261101-144515-340260');roots.append((g/'empty-001',[(g/n,v,0) for n,v in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (out/'frames.jsonl').open('w') as log:
        for root,cases in roots:
            c,e,_=read_recording(root);e=e[:30];b=Baseline.fit(e,c);ref=np.mean([traces(f,c) for f in e],axis=0);model=SupportedNuisanceFit(c)
            for path,label,skip in cases:
                _,fs,_=read_recording(path,c);d=Detector(b);values=[]
                for f in fs[skip:]:
                    r=d.update(f);result=model.fit_associated(traces(f,c)-ref,r['candidate_bin'],r.get('qualified_bins')) if r['target_detected'] else dict(range_m=None,reason='presence_rejected');v=result['range_m'] if r['target_detected'] else None;values.append(v)
                    log.write(json.dumps(dict(recording=str(path),sequence=f.sequence,range_m=v,diagnostic=result))+'\n')
                record=dict(recording=str(path),label_m=label,metrics=measure(values,label));report.append(record);print(path.name,record['metrics'],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
