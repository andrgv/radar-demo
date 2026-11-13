"""Frozen component association and optional causal median; raw replay only."""
import argparse,json,hashlib
from collections import deque
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from radar_min.associated_fit import AssociatedFit
from tools.fit_range_signal import ToneFit,traces

def measure(values,label):
    v=np.array([np.nan if x is None else x for x in values]);valid=np.isfinite(v);a=v[valid];j=np.abs(np.diff(v));j=j[np.isfinite(j)]
    result=dict(frames=len(v),reported=len(a),misses=int((~valid).sum()),adjacent_pairs=len(j),jumps_over_20cm=int(np.sum(j>.2)),median_cm=float(np.median(a)*100) if len(a) else None)
    if label is None:result['false_detections']=len(a)
    else:result.update(mae_cm=float(np.mean(abs(a-label))*100) if len(a) else None,p95_error_cm=float(np.percentile(abs(a-label),95)*100) if len(a) else None,within_2cm=int(np.sum(abs(a-label)<=.02)),errors_over_10cm=int(np.sum(abs(a-label)>.1)))
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--variant',type=int,choices=[1,2,3],default=3);args=parser.parse_args()
    OUT=Path(f'evidence/associated-fit-{args.variant}');OUT.mkdir(parents=True,exist_ok=True);report=[]
    roots=[(Path(f'recordings/hpf{run}-empty-before'),[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,30),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]) for run in ['350-a','100-a','350-b']]
    g=Path('recordings/gui-20261101-144515-340260');roots.append((g/'empty-001',[(g/n,v,0) for n,v in [('live-003',None),('live-004',.3),('live-005',.5)]]))
    with (OUT/'frames.jsonl').open('w') as stream:
        for root,cases in roots:
            c,empty,_=read_recording(root);empty=empty[:30];ref=np.mean([traces(f,c) for f in empty],axis=0);b=Baseline.fit(empty,c);fitter=AssociatedFit(c);old=ToneFit(c)
            for path,label,skip in cases:
                _,frames,_=read_recording(path,c);frames=frames[skip:];d=Detector(b);history=deque(maxlen=5);values={k:[] for k in ['current','associated','associated_median5']};counts={}
                for frame in frames:
                    reading=d.update(frame);x=traces(frame,c)-ref
                    previous=old.fit(x);result=fitter.fit_associated(x,reading['candidate_bin'],reading.get('qualified_bins') if args.variant>=2 else None,allow_boundary=args.variant<3) if reading['candidate_bin'] is not None else dict(range_m=None,reason='invalid_frame')
                    a=result['range_m'] if reading['target_detected'] else None
                    if a is None:history.clear();smooth=None
                    else:history.append(a);smooth=float(np.median(history))
                    row=dict(recording=str(path),sequence=frame.sequence,presence=reading['target_detected'],candidate_bin=reading['candidate_bin'],current=previous['range_m'] if reading['target_detected'] and not previous['boundary'] else None,associated=a,associated_median5=smooth,diagnostic=result)
                    for k in values:values[k].append(row[k])
                    counts[result['reason']]=counts.get(result['reason'],0)+1;stream.write(json.dumps(row)+'\n')
                record=dict(recording=str(path),label_m=label,reference=str(root),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),methods={k:measure(v,label) for k,v in values.items()},fit_reasons=counts);report.append(record)
                print(path.name,{k:(m['reported'],round(m['mae_cm'],2) if m.get('mae_cm') is not None else None) for k,m in record['methods'].items()},flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
