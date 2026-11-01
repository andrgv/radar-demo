"""Offline correlated-spectrum presence trial; no claimed calibrated PFA.

Fixed chi-square-derived engineering cutoffs, shrinkage covariance learned only
from 30 empty frames. Target labels score outcomes, never define acceptance.
"""
import json,hashlib
from pathlib import Path
import numpy as np
from radar_min.core import Baseline,Detector,Continuity,power,db
from radar_min.__main__ import read_recording
from radar_min.associated_fit import AssociatedFit
from tools.fit_range_signal import traces
from tools.evaluate_association import measure

class JointPresence:
    def __init__(self,c,empty,receiver_features=False):
        self.c=c;self.receivers=receiver_features
        self.threshold=37.6972982184 if receiver_features else 20.5150056524 # chi2 .999, df15 or5; not a calibrated PFA
        features=np.array([self.features(f) for f in empty]);self.center=np.median(features,axis=0)
        z=features-self.center;cov=z.T@z/(len(z)-1)
        cov=.5*cov+.5*np.diag(np.diag(cov));cov+=np.eye(len(cov))*max(np.trace(cov)/len(cov)*1e-6,1e-9)
        self.inverse=np.linalg.inv(cov);self.guard=Continuity(c);self.hits=0;self.invalidated=False
    def features(self,f):
        if not self.receivers:return db(power(f,self.c))[:5]
        power(f,self.c) # same frame validation
        x=f.adc[self.c.discard_chirps:].astype(float);x-=x.mean(axis=1,keepdims=True)
        w=np.hanning(self.c.samples);spec=np.fft.rfft(x*w[None,:,None],axis=1)*(2/w.sum())
        return db(np.mean(abs(spec)**2,axis=0)[:5]).reshape(-1)
    def update(self,f):
        reason=self.guard.check(f)
        if reason=='restart_or_duplicate':self.invalidated=True
        if reason or self.invalidated:self.hits=0;return False,None
        z=self.features(f)-self.center;score=float(z@self.inverse@z)
        self.hits=self.hits+1 if score>self.threshold else 0
        return self.hits>=3,score

def main():
    out=Path('evidence/joint-presence-1');out.mkdir(parents=True,exist_ok=True);report=[]
    setups=[]
    for run in ['350-a','100-a','350-b']:
        root=Path(f'recordings/hpf{run}-empty-before')
        setups.append((root,[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]))
    for session,cases in [('gui-20261101-144515-340260',[('live-003',None,0),('live-004',.3,0),('live-005',.5,0)]),('gui-20261101-153737-539230',[('empty-001',None,30),('live-002',None,0),('live-003',.3,0),('live-004',.4,0),('live-005',.5,0),('live-006',None,0)])]:
        root=Path('recordings')/session;setups.append((root/'empty-001',[(root/n,v,s) for n,v,s in cases]))
    with (out/'frames.jsonl').open('w') as log:
        for reference,cases in setups:
            c,e,_=read_recording(reference);e=e[:30];b=Baseline.fit(e,c);wave=np.mean([traces(f,c) for f in e],axis=0);fit=AssociatedFit(c)
            for path,label,skip in cases:
                _,frames,_=read_recording(path,c);frames=frames[skip:];old=Detector(b);models={name:JointPresence(c,e,rx) for name,rx in [('pooled',False),('per_rx',True)]};values={k:[] for k in ['existing',*models]};presence={k:0 for k in values}
                for f in frames:
                    r=old.update(f);gates={'existing':(r['target_detected'],None),**{k:m.update(f) for k,m in models.items()}}
                    candidate=fit.fit_associated(traces(f,c)-wave,r['candidate_bin'],r.get('qualified_bins')) if any(a for a,_ in gates.values()) else dict(range_m=None,reason='all_presence_rejected')
                    row=dict(recording=str(path),sequence=f.sequence,range_candidate=candidate,methods={})
                    for k,(accepted,score) in gates.items():
                        presence[k]+=int(accepted);v=candidate['range_m'] if accepted else None;values[k].append(v);row['methods'][k]=dict(presence=bool(accepted),score=score,range_m=v)
                    log.write(json.dumps(row)+'\n')
                row=dict(recording=str(path),label_m=label,reference=str(reference),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),presence=presence,methods={k:measure(v,label) for k,v in values.items()});report.append(row)
                print(path.name,label,{k:(presence[k],v['reported'],round(v['mae_cm'],2) if v.get('mae_cm') is not None else None) for k,v in row['methods'].items()},flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
