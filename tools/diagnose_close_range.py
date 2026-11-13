"""Causal empty-reference freshness ablation; no target-label parameter fitting."""
import json,hashlib
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from radar_min.associated_fit import AssociatedFit
from tools.fit_range_signal import traces
from tools.evaluate_association import measure

OUT=Path('evidence/close-reference-1')
def main():
    OUT.mkdir(parents=True,exist_ok=True);report=[]
    setups=[]
    for run in ['350-a','100-a','350-b']:
        root=Path(f'recordings/hpf{run}-empty-before');c,e,_=read_recording(root)
        setups.append((root,c,e[:30],root,e[-30:],[(root,None,30,len(e)-30)]+[(Path(f'recordings/hpf{run}-{s}'),v,0,None) for s,v in [('30cm',.3),('40cm',.4),('40cm-repeat',.4),('50cm',.5),('empty-after',None)]]))
    g=Path('recordings/gui-20261101-144515-340260');c,e,_=read_recording(g/'empty-001');_,recent,_=read_recording(g/'live-003',c)
    setups.append((g/'empty-001',c,e[:30],g/'live-003',recent[:30],[(g/'live-003',None,30,None),(g/'live-004',.3,0,None),(g/'live-005',.5,0,None)]))
    with (OUT/'frames.jsonl').open('w') as log:
        for original,c,old,recent_path,recent,cases in setups:
            fit=AssociatedFit(c);oldref=np.mean([traces(f,c) for f in old],axis=0);newref=np.mean([traces(f,c) for f in recent],axis=0)
            baselines={'old':Baseline.fit(old,c),'new':Baseline.fit(recent,c)}
            refdiff=(newref-oldref).reshape(-1,3,c.samples);refdiff-=refdiff.mean(axis=2,keepdims=True)
            for path,label,start,stop in cases:
                _,frames,_=read_recording(path,c);frames=frames[start:stop];det={k:Detector(b) for k,b in baselines.items()};values={k:[] for k in ['original','wave_only','detector_only','refreshed','no_wave_subtraction','chirp_mean_reference']};loss=[]
                for frame in frames:
                    readings={k:d.update(frame) for k,d in det.items()};raw=traces(frame,c)
                    variants={'original':('old',raw-oldref),'wave_only':('old',raw-newref),'detector_only':('new',raw-oldref),'refreshed':('new',raw-newref),'no_wave_subtraction':('old',raw),'chirp_mean_reference':('old',raw-np.tile(oldref.reshape(-1,3,c.samples).mean(axis=0),(c.chirps-c.discard_chirps,1)))}
                    frameout={}
                    # Label appears only in evaluation: quantify score at actual vs winning grid frequency.
                    centered=raw-oldref;centered-=centered.mean(axis=1,keepdims=True)
                    scores=np.sum(np.einsum('ts,gsb->gtb',centered,fit.q,optimize=True)**2,axis=(1,2));energy=np.sum(centered**2)
                    if label is not None:loss.append(float((scores.max()-scores[np.argmin(abs(fit.grid-label))])/max(energy,1e-20)))
                    for name,(which,x) in variants.items():
                        r=readings[which];result=fit.fit_associated(x,r['candidate_bin'],r.get('qualified_bins'))
                        v=result['range_m'] if r['target_detected'] else None;values[name].append(v);frameout[name]=dict(range_m=v,reason=result['reason'],presence=r['target_detected'])
                    log.write(json.dumps(dict(recording=str(path),sequence=frame.sequence,methods=frameout))+'\n')
                row=dict(recording=str(path),label_m=label,start=start,stop=stop,original_reference=str(original),refreshed_reference=str(recent_path),reference_difference_rms_per_rx=np.sqrt(np.mean(refdiff**2,axis=(0,2))).tolist(),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),median_truth_objective_loss_fraction=float(np.median(loss)) if loss else None,methods={k:measure(v,label) for k,v in values.items()});report.append(row)
                print(path.name,{k:(v['reported'],round(v['mae_cm'],2) if v.get('mae_cm') is not None else None) for k,v in row['methods'].items()},flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
