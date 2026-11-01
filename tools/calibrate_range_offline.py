"""Exploratory group-held-out distance calibration. Never changes live processing.

No random frame splits, label-dependent feature selection, clipping or smoothing.
Hyperparameters/features are fixed before examining benchmark results.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.core import Baseline,Detector,power
from radar_min.__main__ import read_recording
from tools.analyze_distance_sweep import dense_power

FEATURES=['fine_peak_m','positive_residual_centroid_m','positive_residual_width_m',
          'roi_power_ratio_db','residual_fraction_bin1','residual_fraction_bin2',
          'residual_fraction_bin3','residual_fraction_bin4']
ALPHA=0.1
# Session = one independently fitted empty reference / physical setup.
# Labels are user-reported, not hardware certified.
SETUPS=[
 ('early50','empty-50cm-1',[('target-50cm-1',.50)],['empty-after-50cm-1']),
 ('aligned','empty-50cm-v2-1',[('target-35cm-v2-1',.35),('target-50cm-v2-repeat-1',.50)],
  ['empty-after-50cm-v2-1','empty-after-35cm-v2-1']),
 ('sweep1','distance-sweep-1-empty-before',[
  ('distance-sweep-1-30cm',.30),('distance-sweep-1-40cm',.40),('distance-sweep-1-50cm',.50),
  ('distance-sweep-1-40cm-repeat',.40),('distance-sweep-1-40cm-repeat-2',.40),
  ('distance-sweep-1-40cm-untouched-1',.40)],['distance-sweep-1-empty-after']),
 ('sweep2','distance-sweep-2-empty-before',[
  ('distance-sweep-2-30cm',.30),('distance-sweep-2-40cm',.40),('distance-sweep-2-50cm',.50),
  ('distance-sweep-2-40cm-repeat',.40)],['distance-sweep-2-empty-after'])]
EXCLUDED={
 'target-1m-session-1':'User later reported holding target; also outside 30–50 cm benchmark.',
 'target-1m-repeat-1':'Hand-held/placement confounding; outside benchmark.',
 'target-session-1':'12 cm outside evaluated interval.',
 'target-50cm-v2-1':'User reported repositioning target during capture.',
 'October recordings':'Outside 30–50 cm label set; already reported failure/stress evidence retained separately.'}

@dataclass
class Record:
    name:str
    setup:str
    label:float|None
    x:np.ndarray
    accepted:np.ndarray
    raw_hash:str


def features(frame,c,reference):
    p=dense_power(frame,c)
    ranges=np.fft.rfftfreq(4096,1/c.sample_rate_hz)*299792458/(2*c.slope_hz_s)
    ids=np.flatnonzero((ranges>=.15)&(ranges<=1.5))
    residual=p-reference;selected=residual[ids];peak=ranges[ids[np.argmax(selected)]]
    positive=np.maximum(selected,0);total=positive.sum()
    if total>1e-12:
        center=float(np.sum(positive*ranges[ids])/total)
        width=float(np.sqrt(np.sum(positive*(ranges[ids]-center)**2)/total))
    else: center=0.;width=0.
    strength=10*np.log10(max(p[ids].sum(),1e-12)/max(reference[ids].sum(),1e-12))
    # Values exactly at native FFT bins, normalized positive power change.
    native=np.maximum(residual[np.arange(1,5)*64],0)
    fractions=native/max(native.sum(),1e-12)
    return np.array([peak,center,width,strength,*fractions])


def load_data(root):
    targets=[];empties=[];manifest=[];hashes=set()
    for setup,emptyname,names,emptychecks in SETUPS:
        emptyroot=root/emptyname;c,empty,_=read_recording(emptyroot)
        if len(empty)<=30:raise ValueError('Need unused empty frames')
        baseline=Baseline.fit(empty[:30],c)
        reference=np.median([dense_power(f,c) for f in empty[:30]],axis=0)
        for name,label,skip in [(n,d,0) for n,d in names]+[(emptyname,None,30)]+[(n,None,0) for n in emptychecks]:
            path=root/name;_,allframes,_=read_recording(path,c);frames=allframes[skip:]
            if not frames:raise ValueError('Empty capture')
            digest=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest()
            if digest in hashes:raise ValueError('Duplicate recording hash: '+name)
            hashes.add(digest)
            detector=Detector(baseline);readings=[detector.update(f) for f in frames]
            if any('power' not in r for r in readings):raise ValueError('Invalid/discontinuous raw frames: '+name)
            r=Record(name,setup,label,np.array([features(f,c,reference) for f in frames]),
                     np.array([x['target_detected'] for x in readings]),digest)
            (targets if label is not None else empties).append(r)
            manifest.append(dict(name=name,setup=setup,label_m=label,frames=len(frames),skip=skip,raw_sha256=digest,
                reference=emptyname,reference_raw_sha256=hashlib.sha256((emptyroot/'frames.grd').read_bytes()).hexdigest(),
                gate_reasons=dict(Counter(x['reason'] for x in readings))))
    return targets,empties,manifest


def fit_model(records,kind):
    if not records:raise ValueError('No training recordings')
    x=np.concatenate([r.x for r in records]);y=np.concatenate([np.full(len(r.x),r.label) for r in records])
    # Each recording contributes equal total weight, regardless of duration.
    w=np.concatenate([np.full(len(r.x),1/(len(records)*len(r.x))) for r in records])
    intercept=float(w@y)
    if kind in ('constant','raw_peak'):return {'kind':kind,'intercept':intercept}
    cols=[0] if kind=='linear_peak' else list(range(len(FEATURES)))
    x=x[:,cols];mean=w@x;scale=np.sqrt(w@((x-mean)**2));scale=np.where(scale<1e-9,1.,scale)
    z=(x-mean)/scale
    if kind=='linear_peak':
        den=float(w@(z[:,0]**2));coef=np.array([float(w@(z[:,0]*(y-intercept)))/den if den>1e-12 else 0])
    else:
        coef=np.linalg.solve(z.T@(w[:,None]*z)+ALPHA*np.eye(len(cols)),z.T@(w*(y-intercept)))
    return dict(kind=kind,intercept=intercept,columns=cols,mean=mean.tolist(),scale=scale.tolist(),coef=coef.tolist(),ridge_alpha=ALPHA if kind=='spectral_ridge' else 0)


def predict(model,x):
    if model['kind']=='raw_peak':return x[:,0].copy()
    if model['kind']=='constant':return np.full(len(x),model['intercept'])
    return ((x[:,model['columns']]-model['mean'])/model['scale'])@np.array(model['coef'])+model['intercept']


def metrics(pred,label,accepted):
    err=pred-label
    def subset(mask):
        if not np.any(mask):return None
        e=err[mask];p=pred[mask]
        return dict(frames=int(mask.sum()),mae_cm=float(np.mean(abs(e))*100),rmse_cm=float(np.sqrt(np.mean(e**2))*100),
            mean_bias_cm=float(np.mean(e)*100),within_1cm_fraction=float(np.mean(abs(e)<=.01)),within_2cm_fraction=float(np.mean(abs(e)<=.02)),
            prediction_p05_median_p95_cm=(np.percentile(p,[5,50,95])*100).tolist())
    return dict(all_frames=subset(np.ones(len(pred),bool)),accepted_frames=subset(accepted),
                native_acceptance_fraction=float(np.mean(accepted)),missed_frames=int((~accepted).sum()),
                outside_observed_training_interval_note='Predictions are never clipped to known labels or 30–50 cm.')


def splits(records,mode):
    if mode=='setup':
        for setup in sorted({r.setup for r in records}):
            yield setup,[r for r in records if r.setup!=setup],[r for r in records if r.setup==setup]
    else:
        for label in sorted({r.label for r in records}):
            yield str(label),[r for r in records if r.label!=label],[r for r in records if r.label==label]


def benchmark(records,mode):
    results=[]
    for fold,train,test in splits(records,mode):
        if {r.name for r in train}&{r.name for r in test}:raise ValueError('Train/test recording overlap')
        for kind in ['raw_peak','constant','linear_peak','spectral_ridge']:
            model=fit_model(train,kind)
            for r in test:
                pred=predict(model,r.x)
                results.append(dict(fold=fold,recording=r.name,setup=r.setup,label_m=r.label,model=kind,
                    training_recordings=[t.name for t in train],training_label_range_m=[min(t.label for t in train),max(t.label for t in train)],
                    extrapolation=r.label<min(t.label for t in train) or r.label>max(t.label for t in train),
                    fit=model,**metrics(pred,r.label,r.accepted)))
    summary={}
    for kind in ['raw_peak','constant','linear_peak','spectral_ridge']:
        rows=[x for x in results if x['model']==kind]
        label_mae={str(label):float(np.mean([r['all_frames']['mae_cm'] for r in rows if r['label_m']==label])) for label in sorted({r['label_m'] for r in rows})}
        summary[kind]=dict(recording_macro_mae_cm=float(np.mean([r['all_frames']['mae_cm'] for r in rows])),
            distance_balanced_mae_cm=float(np.mean(list(label_mae.values()))),mae_by_distance_cm=label_mae,
            recording_macro_within_1cm=float(np.mean([r['all_frames']['within_1cm_fraction'] for r in rows])),
            worst_recording_mae_cm=max(r['all_frames']['mae_cm'] for r in rows))
    return dict(summary=summary,results=results)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('recordings',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    targets,empties,manifest=load_data(a.recordings)
    report=dict(features=FEATURES,ridge_alpha=ALPHA,exclusions=EXCLUDED,manifest=manifest,
        protocol='Fixed models/features; equal recording training weights; fit scaling only to training. Leave entire background setups out (primary), leave entire distance labels out (secondary). No frame splits. Fixed native presence gate evaluated separately.',
        limits='Previously inspected captures: retrospective development, not prospective validation. Same-room same-day setups are not independent rooms. Distance 35 cm has one recording. Endpoint distance holdouts require extrapolation. No centimeter accuracy claim.',
        by_setup=benchmark(targets,'setup'),by_distance=benchmark(targets,'distance'))
    # Freeze both candidate calibrations for possible later prospective tests.
    frozen={kind:fit_model(targets,kind) for kind in ['constant','linear_peak','spectral_ridge']}
    artifact=dict(status='EXPERIMENTAL_NOT_LIVE_NOT_VALIDATED',features=FEATURES,models=frozen,
        training_recordings=[r.name for r in targets],training_raw_sha256=[r.raw_hash for r in targets],
        label_range_m=[.3,.5],native_gate_required=True,centimeter_accuracy_validated=False)
    (a.output/'frozen-models.json').write_text(json.dumps(artifact,indent=2))
    report['empty_checks']=[dict(recording=r.name,setup=r.setup,frames=len(r.x),false_detections=int(r.accepted.sum()),
        ungated_model_prediction_medians_cm={kind:float(np.median(predict(m,r.x))*100) for kind,m in frozen.items()},
        caution='Regressors always output a number for empty data. Only the unchanged native detector rejects it.') for r in empties]
    report['existing_background_transfer_failure']='The earlier box_range_02 reference produced 35/61 false alarms on box_range_20261028_002954 empty. This calibration changes no presence gate and does not resolve that failure.'
    (a.output/'report.json').write_text(json.dumps(report,indent=2))
    for mode in ('by_setup','by_distance'):
        print(mode,json.dumps(report[mode]['summary'],indent=2))
    print('Empty checks:',sum(x['false_detections'] for x in report['empty_checks']),'/',sum(x['frames'] for x in report['empty_checks']))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    for ax,kind in zip(axes,['raw_peak','linear_peak','spectral_ridge']):
        rows=[r for r in report['by_setup']['results'] if r['model']==kind]
        for r in rows:
            lo,med,hi=r['all_frames']['prediction_p05_median_p95_cm']
            ax.errorbar(r['label_m']*100,med,yerr=[[med-lo],[hi-med]],fmt='o',alpha=.6,capsize=3)
        ax.plot([20,60],[20,60],'k--',lw=1)
        ax.set(title=kind,xlabel='User-measured distance (cm)',ylabel='Held-out prediction (cm)');ax.grid(alpha=.2)
    fig.suptitle('Entire background setups held out: each point is one recording\nBars show per-frame 5th–95th percentiles, not confidence intervals',fontsize=12)
    fig.savefig(a.output/'held-out-predictions.png',dpi=150);plt.close(fig)

if __name__=='__main__':main()
