"""Run from repository root; labels follow user's requested capture order."""
import hashlib,json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from tools.fit_range_signal import ToneFit,traces
root=Path('recordings/gui-20261101-144515-340260')
b=Baseline.load(root/'empty-001/baseline.json')
c,empty,_=read_recording(root/'empty-001',b.config)
ref=np.mean([traces(f,c) for f in empty[:b.training_frames]],axis=0)
fit=ToneFit(c);report=[]
for name,truth in [('live-003',None),('live-004',30),('live-005',50)]:
 p=root/name;_,frames,_=read_recording(p,c)
 saved=[json.loads(s) for s in (p/'readings.jsonl').read_text().splitlines()]
 assert len(frames)==len(saved)
 detector=Detector(b);values=[];accepted=[]
 for frame,row in zip(frames,saved):
  replay=detector.update(frame); result=fit.fit(traces(frame,c)-ref)
  assert replay['target_detected']==row['target_detected']
  assert abs(result['range_m']-row['experimental_range_m'])<1e-8
  values.append(result['range_m']*100);accepted.append(row['target_detected'])
 v=np.array(values);a=np.array(accepted);av=v[a]
 entry=dict(recording=str(p),label_cm=truth,label_basis='User followed requested order: empty, stationary 30 cm, stationary 50 cm; no per-frame external measurement',frames=len(v),accepted=int(a.sum()),accepted_fraction=float(a.mean()),accepted_range_min_median_max_cm=[float(z) for z in (av.min(),np.median(av),av.max())],accepted_boundary_15cm=int(np.sum(av<=15.001)),accepted_over_75cm=int(np.sum(av>75)),capture=json.loads((p/'capture-summary.json').read_text()),raw_sha256=hashlib.sha256((p/'frames.grd').read_bytes()).hexdigest(),raw_replay_matches_live=True)
 if truth is not None:
  entry.update(accepted_mae_cm=float(np.mean(abs(av-truth))),accepted_within_2cm=int(np.sum(abs(av-truth)<=2)),all_frames_within_2cm=int(np.sum(abs(v-truth)<=2)))
 report.append(entry)
out=Path('evidence/gui-static-1/report.json');out.write_text(json.dumps(report,indent=2)+'\n');print(out.read_text())
