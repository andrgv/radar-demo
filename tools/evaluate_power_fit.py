"""Offline phase-insensitive background experiment; never alters live estimator.
Labels score errors only. Existing presence gate is unchanged.
"""
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from tools.fit_range_signal import ToneFit,traces

OUT=Path('evidence/power-fit-1')

def covariance(frame,c):
    x=traces(frame,c).reshape(-1,3,c.samples)
    x=x-x.mean(axis=-1,keepdims=True)
    return np.einsum('crn,crm->rnm',x,x)/len(x)

class PowerFit:
    def __init__(self,c,empty):
        self.fit=ToneFit(c);self.reference=np.mean([covariance(f,c) for f in empty],axis=0)
        self.projectors=np.einsum('gnk,gmk->gnm',self.fit.q,self.fit.q)
    def estimate(self,frame,c):
        delta=covariance(frame,c)-self.reference
        scores=np.einsum('rnm,gnm->rg',delta,self.projectors)
        per_rx=self.fit.grid[np.argmax(scores,axis=1)]
        combined=scores.sum(axis=0);k=int(np.argmax(combined))
        return dict(range_m=float(self.fit.grid[k]),rx_ranges_m=per_rx.tolist(),boundary=k in (0,len(self.fit.grid)-1),score=float(combined[k]))

def metrics(values,accepted,label):
    v=np.asarray(values);a=np.asarray(accepted);av=v[a]
    out=dict(frames=len(v),accepted=int(a.sum()),all_median_cm=float(np.median(v)*100),accepted_median_cm=float(np.median(av)*100) if len(av) else None,
             boundary_frames=int(np.sum((v<=.15001)|(v>=1.49999))))
    if label is not None:
        out.update(all_mae_cm=float(np.mean(abs(v-label))*100),accepted_mae_cm=float(np.mean(abs(av-label))*100) if len(av) else None,
                   accepted_within_2cm=int(np.sum(abs(av-label)<=.02)),accepted_errors_over_10cm=int(np.sum(abs(av-label)>.1)))
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=True);report=[]
    cases=[]
    for run in ['350-a','100-a','350-b']:
        base=Path(f'recordings/hpf{run}-empty-before')
        cases.append((base,[(Path(f'recordings/hpf{run}-{suffix}'),label,skip) for suffix,label,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]))
    gui=Path('recordings/gui-20261101-144515-340260')
    cases.append((gui/'empty-001',[(gui/name,label,0) for name,label in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (OUT/'frames.jsonl').open('w') as stream:
        for reference,recordings in cases:
            c,empty,_=read_recording(reference);training=empty[:30];b=Baseline.fit(training,c)
            pf=PowerFit(c,training);tf=ToneFit(c);wave=np.mean([traces(f,c) for f in training],axis=0)
            for path,label,skip in recordings:
                _,frames,_=read_recording(path,c);frames=frames[skip:];d=Detector(b)
                values={k:[] for k in ['fixed','power','power_rx_median','fixed_rx_median']};accepted=[];spreads=[]
                for f in frames:
                    det=d.update(f);accepted.append(det['target_detected']);x=(traces(f,c)-wave).reshape(-1,3,c.samples)
                    fixed=tf.fit(x.reshape(-1,c.samples));rx=[tf.fit(x[:,i,:])['range_m'] for i in range(3)]
                    result=pf.estimate(f,c)
                    row=dict(recording=str(path),sequence=f.sequence,accepted=det['target_detected'],fixed=fixed['range_m'],power=result['range_m'],power_rx_median=float(np.median(result['rx_ranges_m'])),fixed_rx_median=float(np.median(rx)),fixed_rx=rx,power_rx=result['rx_ranges_m'])
                    for k in values:values[k].append(row[k])
                    spreads.append(max(rx)-min(rx));stream.write(json.dumps(row)+'\n')
                record=dict(recording=str(path),label_m=label,reference=str(reference),median_fixed_rx_spread_cm=float(np.median(spreads)*100),methods={k:metrics(v,accepted,label) for k,v in values.items()})
                report.append(record);print(path.name,{k:round(v['all_mae_cm'],2) for k,v in record['methods'].items() if 'all_mae_cm' in v},flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
