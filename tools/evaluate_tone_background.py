"""Physical sinusoid nuisance basis estimated only from empty data; offline trial."""
import json
from pathlib import Path
import numpy as np
from tools.evaluate_power_fit import metrics,covariance
from tools.fit_range_signal import ToneFit,traces
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector,Config

class JointBackground:
    def __init__(self,c,empty,count):
        self.c=c;self.target=ToneFit(c)
        wide=ToneFit(c);wide.grid=np.linspace(.05,5,991);wide.q=np.array([wide.basis(r) for r in wide.grid])
        cov=np.mean([covariance(f,c) for f in empty],axis=0)
        self.nuisance=[];self.frequencies=[];self.q=[]
        for rx in range(3):
            residual=cov[rx].copy();columns=[];selected=[]
            for _ in range(count):
                scores=np.einsum('gnk,nm,gmk->g',wide.q,residual,wide.q)
                k=int(np.argmax(scores));selected.append(float(wide.grid[k]));columns.extend(wide.q[k].T)
                u,s,_=np.linalg.svd(np.asarray(columns).T,full_matrices=False);u=u[:,s>1e-8]
                project=np.eye(c.samples)-u@u.T;residual=project@cov[rx]@project
            self.nuisance.append(u);self.frequencies.append(selected)
            qs=[]
            for basis in self.target.q:
                z=basis-u@(u.T@basis);uz,sz,_=np.linalg.svd(z,full_matrices=False)
                # Avoid amplifying virtually absorbed target basis.
                uz[:,sz<1e-6]=0;qs.append(uz)
            self.q.append(np.array(qs))
        self.q=np.array(self.q)
    def fit(self,x):
        x=x.reshape(-1,3,self.c.samples);x=x-x.mean(axis=2,keepdims=True)
        projection=np.einsum('crn,rgnk->rgck',x,self.q)
        scores=np.sum(projection**2,axis=(0,2,3));k=int(np.argmax(scores))
        return float(self.target.grid[k])

def main():
    out=Path('evidence/tone-background-1');out.mkdir(parents=True,exist_ok=True);report=[]
    roots=[(Path(f'recordings/hpf{run}-empty-before'),[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]) for run in ['350-a','100-a','350-b']]
    g=Path('recordings/gui-20261101-144515-340260');roots.append((g/'empty-001',[(g/n,v,0) for n,v in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (out/'frames.jsonl').open('w') as log:
        for root,cases in roots:
            c,empty,_=read_recording(root);empty=empty[:30];b=Baseline.fit(empty,c);ref=np.mean([traces(f,c) for f in empty],axis=0)
            models={str(n):JointBackground(c,empty,n) for n in [1,2]}
            for path,label,skip in cases:
                _,frames,_=read_recording(path,c);frames=frames[skip:];d=Detector(b);a=[];values={k:[] for k in models}
                for f in frames:
                    accepted=d.update(f)['target_detected'];a.append(accepted);x=traces(f,c)-ref
                    for key,model in models.items():
                        v=model.fit(x);values[key].append(v);log.write(json.dumps(dict(recording=str(path),sequence=f.sequence,tones=int(key),range_m=v,accepted=accepted))+'\n')
                row=dict(recording=str(path),label_m=label,reference=str(root),background_nominal_ranges={k:m.frequencies for k,m in models.items()},methods={k:metrics(v,a,label) for k,v in values.items()});report.append(row)
                print(path.name,{k:round(v['all_mae_cm'],2) for k,v in row['methods'].items() if 'all_mae_cm' in v},flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
