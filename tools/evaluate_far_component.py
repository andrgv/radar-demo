"""Per-frame far-component nuisance fit, selected without target labels."""
import json
from pathlib import Path
import numpy as np
from radar_min.associated_fit import AssociatedFit
from radar_min.core import Baseline,Detector
from radar_min.__main__ import read_recording
from tools.fit_range_signal import traces
from tools.evaluate_association import measure

class FarComponentFit(AssociatedFit):
    def __init__(self,c):
        super().__init__(c);self.far_grid=np.arange(1.5,5.0001,.01);self.far_q=np.array([self.basis(r) for r in self.far_grid])
    def fit_associated(self,x,candidate_bin,qualified_bins=None,allow_boundary=False):
        x=np.asarray(x).reshape(-1,3,self.c.samples);x=x-x.mean(axis=2,keepdims=True)
        far_scores=np.sum(np.einsum('crn,gnk->rgck',x,self.far_q,optimize=True)**2,axis=(2,3))
        scores=np.zeros(len(self.grid));far=[]
        for rx in range(3):
            k=int(np.argmax(far_scores[rx]));u=self.far_q[k];far.append(float(self.far_grid[k]))
            q=self.q-np.einsum('nm,gmk->gnk',u@u.T,self.q,optimize=True)
            q,s,_=np.linalg.svd(q,full_matrices=False);q*= (s>1e-6)[:,None,:]
            scores+=np.sum(np.einsum('cn,gnk->gck',x[:,rx,:],q,optimize=True)**2,axis=(1,2))
        if np.argmax(scores) in (0,len(scores)-1):return dict(range_m=None,reason='boundary',far_m=far)
        low=high=candidate_bin;qualified=set(qualified_bins or [])
        while low-1 in qualified:low-=1
        while high+1 in qualified:high+=1
        ids=np.flatnonzero((scores[1:-1]>scores[:-2])&(scores[1:-1]>=scores[2:]))+1
        ids=ids[(self.grid[ids]>=(low-1)*self.c.spacing_m)&(self.grid[ids]<=(high+1)*self.c.spacing_m)]
        if not len(ids):return dict(range_m=None,reason='no_local_peak',far_m=far)
        k=ids[np.argmax(scores[ids])];return dict(range_m=float(self.grid[k]),reason='experimental_far_component',far_m=far)

def main():
    out=Path('evidence/far-component-2');out.mkdir(parents=True,exist_ok=True);report=[]
    roots=[(Path(f'recordings/hpf{run}-empty-before'),[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]) for run in ['350-a','100-a','350-b']]
    g=Path('recordings/gui-20261101-144515-340260');roots.append((g/'empty-001',[(g/n,v,0) for n,v in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (out/'frames.jsonl').open('w') as log:
        for root,cases in roots:
            c,e,_=read_recording(root);e=e[:30];b=Baseline.fit(e,c);ref=np.mean([traces(f,c) for f in e],axis=0);model=FarComponentFit(c)
            for path,label,skip in cases:
                _,fs,_=read_recording(path,c);d=Detector(b);values=[]
                for f in fs[skip:]:
                    r=d.update(f);result=model.fit_associated(traces(f,c)-ref,r['candidate_bin'],r.get('qualified_bins')) if r['target_detected'] else dict(range_m=None,reason='presence_rejected');v=result['range_m'] if r['target_detected'] else None;values.append(v)
                    log.write(json.dumps(dict(recording=str(path),sequence=f.sequence,range_m=v,diagnostic=result))+'\n')
                record=dict(recording=str(path),label_m=label,metrics=measure(values,label));report.append(record);print(path.name,record['metrics'],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
