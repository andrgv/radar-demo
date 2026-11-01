"""Weighted finite-record tone fit, data and basis weighted consistently."""
import json
from pathlib import Path
import numpy as np
from radar_min.associated_fit import AssociatedFit
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from tools.fit_range_signal import traces
from tools.evaluate_association import measure

class WeightedFit(AssociatedFit):
    def __init__(self,c):
        self.weight=np.sqrt(np.hanning(c.samples));self.dc=self.weight/np.linalg.norm(self.weight)
        super().__init__(c)
    def basis(self,distance):
        phase=2*np.pi*(2*self.c.slope_hz_s*distance/299792458)*self.t
        a=np.column_stack((np.cos(phase),np.sin(phase)))*self.weight[:,None]
        a-=self.dc[:,None]*(self.dc@a)[None,:]
        return np.linalg.qr(a)[0]
    def prepare(self,x):
        x=x*self.weight[None,:]
        return x-(x@self.dc)[:,None]*self.dc[None,:]

def main():
    out=Path('evidence/weighted-fit-1');out.mkdir(parents=True,exist_ok=True);report=[]
    roots=[(Path(f'recordings/hpf{run}-empty-before'),[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]) for run in ['350-a','100-a','350-b']]
    g=Path('recordings/gui-20261101-144515-340260');roots.append((g/'empty-001',[(g/n,v,0) for n,v in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (out/'frames.jsonl').open('w') as log:
        for root,cases in roots:
            c,e,_=read_recording(root);e=e[:30];b=Baseline.fit(e,c);ref=np.mean([traces(f,c) for f in e],axis=0);models={'associated':AssociatedFit(c),'weighted':WeightedFit(c)}
            for path,label,skip in cases:
                _,fs,_=read_recording(path,c);fs=fs[skip:];d=Detector(b);values={k:[] for k in models}
                for f in fs:
                    r=d.update(f);x=traces(f,c)-ref;row=dict(recording=str(path),sequence=f.sequence)
                    for name,model in models.items():
                        result=model.fit_associated(x,r['candidate_bin'],r.get('qualified_bins'));v=result['range_m'] if r['target_detected'] else None;values[name].append(v);row[name]=v
                    log.write(json.dumps(row)+'\n')
                record=dict(recording=str(path),label_m=label,methods={k:measure(v,label) for k,v in values.items()});report.append(record)
                print(path.name,{k:(v['reported'],round(v['mae_cm'],2) if v.get('mae_cm') is not None else None) for k,v in record['methods'].items()},flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
