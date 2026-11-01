"""Offline empty-covariance weighted sinusoid fit with split empty calibration.

20 empty frames fit waveform/covariance; following 10 set a frozen threshold.
No target-distance labels enter model or threshold. No PFA claim from 10 samples.
"""
import json
from pathlib import Path
import numpy as np
from radar_min.core import Continuity,power
from radar_min.__main__ import read_recording
from tools.fit_range_signal import ToneFit,traces
from tools.evaluate_association import measure

class WhitenedRange:
    def __init__(self,c,empty,fit_frames=20,calibration_frames=10):
        if fit_frames<2 or calibration_frames<1 or len(empty)<fit_frames+calibration_frames:raise ValueError('Insufficient split calibration frames')
        self.c=c;self.base=ToneFit(c);self.grid=self.base.grid
        cubes=np.array([traces(f,c).reshape(-1,3,c.samples).mean(axis=0) for f in empty])
        self.reference=np.mean(cubes[:fit_frames],axis=0);self.transforms=[];self.bases=[]
        for rx in range(3):
            residual=cubes[:fit_frames,rx]-self.reference[rx];cov=residual.T@residual/(fit_frames-1)
            scale=max(float(np.trace(cov)/c.samples),1e-6)
            cov=.5*cov+.5*scale*np.eye(c.samples)
            eigen,vectors=np.linalg.eigh(cov);w=(vectors/np.sqrt(eigen)[None,:])@vectors.T
            dc=w@np.ones(c.samples);dc/=np.linalg.norm(dc);transform=(np.eye(c.samples)-np.outer(dc,dc))@w
            qs=[]
            for r in self.grid:
                phase=2*np.pi*2*c.slope_hz_s*r*self.base.t/299792458
                a=transform@np.column_stack((np.cos(phase),np.sin(phase)))
                q,s,_=np.linalg.svd(a,full_matrices=False);q*= (s>1e-8)[None,:];qs.append(q)
            self.transforms.append(transform);self.bases.append(qs)
        self.transforms=np.array(self.transforms);self.bases=np.array(self.bases)
        self.threshold=2*max(self.score(f)['score'] for f in empty[fit_frames:fit_frames+calibration_frames]);self.threshold=max(self.threshold,1e-9)
        self.hits=0;self.guard=Continuity(c);self.invalidated=False
    def score(self,frame):
        power(frame,self.c)
        x=traces(frame,self.c).reshape(-1,3,self.c.samples).mean(axis=0)-self.reference
        z=np.einsum('rnm,rm->rn',self.transforms,x)
        projections=np.einsum('rn,rgnk->rgk',z,self.bases,optimize=True)
        scores=np.sum(projections**2,axis=(0,2));k=int(np.argmax(scores));energy=float(np.sum(z*z))
        return dict(candidate_m=float(self.grid[k]),score=float(scores[k]),residual_fraction=float(max(0,1-scores[k]/max(energy,1e-20))),boundary=k in (0,len(self.grid)-1))
    def update(self,f):
        reason=self.guard.check(f)
        if reason=='restart_or_duplicate':self.invalidated=True
        if reason or self.invalidated:self.hits=0;return dict(range_m=None,reason=reason or 'invalidated',presence=False)
        result=self.score(f);self.hits=self.hits+1 if result['score']>self.threshold else 0
        result.update(threshold=self.threshold,presence=self.hits>=3,range_m=result['candidate_m'] if self.hits>=3 and not result['boundary'] else None)
        return result

def main():
    out=Path('evidence/whitened-range-1');out.mkdir(parents=True,exist_ok=True);report=[]
    setups=[]
    for run in ['350-a','100-a','350-b']:
        root=Path(f'recordings/hpf{run}-empty-before');setups.append((root,[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]))
    for session,cases in [('gui-20261101-144515-340260',[('live-003',None,0),('live-004',.3,0),('live-005',.5,0)]),('gui-20261101-153737-539230',[('empty-001',None,30),('live-002',None,0),('live-003',.3,0),('live-004',.4,0),('live-005',.5,0),('live-006',None,0)])]:
        root=Path('recordings')/session;setups.append((root/'empty-001',[(root/n,v,s) for n,v,s in cases]))
    with (out/'frames.jsonl').open('w') as log:
        for reference,cases in setups:
            c,e,_=read_recording(reference)
            for path,label,skip in cases:
                model=WhitenedRange(c,e[:30]);_,fs,_=read_recording(path,c);values=[];presence=0
                for f in fs[skip:]:
                    r=model.update(f);presence+=r['presence'];values.append(r['range_m']);log.write(json.dumps(dict(recording=str(path),sequence=f.sequence,**r))+'\n')
                row=dict(recording=str(path),label_m=label,threshold=model.threshold,presence=presence,metrics=measure(values,label));report.append(row);print(path.name,label,presence,row['metrics'],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
