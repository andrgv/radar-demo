"""Glass-blocking scene transfer probe, without XYZ or oracle pane locations.

This is an offline experiment, NOT an integrated detector or glass-identity proof.
Operational labels are closed glass in beam vs open door / drywall-facing view.
Open controls are not certified glass-free elsewhere. Door03/door04 are grouped
as the same physical door. Cross-study physical novelty is not independently
verified. Thresholds and model settings are frozen before inspecting results.
"""
from pathlib import Path
from dataclasses import asdict
from collections import Counter
import argparse,json,sys,hashlib
import numpy as np
sys.path.insert(0,str(Path.cwd()))
from radar.config import Config
from radar.material import PARAMETERS, ROUNDS, _check_frame
from radar.storage import replay
from radar.protocol import Parser
import xgboost as xgb

def features(path):
    config=Config.load(path/'config.json'); parser=Parser(); previous=None; values=[]
    window=np.hanning(config.samples)
    frame_hashes=[]
    for frame in replay(path,parser):
        _check_frame(frame,config,previous);previous=frame
        frame_hashes.append(hashlib.sha256(frame.adc.tobytes()).hexdigest())
        raw=frame.adc[config.discard_chirps:].astype(float)
        raw-=raw.mean(axis=1,keepdims=True)
        fft=np.fft.rfft(raw*window[None,:,None],axis=1)*(2/window.sum())
        cov=np.einsum('cfa,cfb->fab',fft,fft.conj())/len(fft)
        power=np.diagonal(cov,axis1=1,axis2=2).real[1:-1]
        db=10*np.log10(np.maximum(power,1e-12))
        cross=np.stack([cov[1:-1,rx,0]/np.sqrt(np.maximum(power[:,rx]*power[:,0],1e-24)) for rx in (1,2)],axis=1)
        # Absolute levels removed per frame; preserve spectral/RX shape.
        normalized=db-db.mean()
        values.append(np.r_[normalized.T.reshape(-1),cross.real.T.reshape(-1),cross.imag.T.reshape(-1)])
    assert not any(getattr(parser,k) for k in ('bad_crc','bad_headers','gaps','restarts','discarded_bytes')) and not parser.buffer
    arrivals=[json.loads(line) for line in (path/'arrivals.jsonl').read_text().splitlines()]
    assert len(arrivals)==len(values)
    windows=np.array([np.median(values[i:i+10],axis=0) for i in range(10,len(values)-9,10)],np.float32)
    assert len(windows)>0 and np.isfinite(windows).all()
    return dict(x=windows,profile_id=config.profile_id,frames=len(values),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),frame_hashes=frame_hashes)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings',type=Path,default=Path('recordings'))
    parser.add_argument('--archive-recordings',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a new report path')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    sessions=[]
    for door,group in [('door03','first-door'),('door04','first-door'),('door07','second-door')]:
        manifest=json.loads((args.recordings/door/'door-check.json').read_text());assert manifest['complete']
        for state in ('open','closed'):
            for pair in range(1,manifest['repeats']+1):
                path=args.recordings/door/f'{state}-{pair:02d}'
                sessions.append(dict(path=str(path),group=group,label=int(state=='closed'),label_source='complete_door_state_manifest',**features(path)))
    archive=args.archive_recordings
    manifest=json.loads(Path('experiments/materials/window-drywall-repeat.json').read_text())
    for row in manifest['recordings']:
        path=archive/'glass-pane-100cm-01'/Path(row['path']).name
        sessions.append(dict(path=str(path),group='window-study',label=int(row['label']=='glass'),label_source='corrected_material_manifest',**features(path)))
    for row in json.loads(Path('evidence/material-transfer-check/report.json').read_text())['sessions']:
        path=archive/Path(row['recording']).name
        sessions.append(dict(path=str(path),group='later-controls',label=int(row['user_reported_target']=='glass'),label_source='user_reported_material; novelty_unknown',**features(path)))
    assert len({s['profile_id'] for s in sessions})==1
    assert len({s['raw_sha256'] for s in sessions})==len(sessions)
    assert len(set.intersection(*(set(s['frame_hashes']) for s in sessions)))==0
    report=dict(description=__doc__,parameters=PARAMETERS,rounds=ROUNDS,window_frames=10,skip_frames=10,
                features='93 relative power; optionally 124 normalized cross-RX real/imag covariance values; bins 1..31',folds=[])
    for phase in (False,True):
        for heldout in ('first-door','second-door','window-study'):
            train=[s for s in sessions if s['group'] not in (heldout,'later-controls')]
            test=[s for s in sessions if s['group'] in (heldout,'later-controls')]
            train_hashes={h for s in train for h in s['frame_hashes']}
            assert not train_hashes.intersection(h for s in test for h in s['frame_hashes'])
            def select(x):return x if phase else x[:,:93]
            x=np.vstack([select(s['x']) for s in train])
            y=np.concatenate([np.full(len(s['x']),s['label']) for s in train])
            weights=np.concatenate([np.full(len(s['x']),len(x)/(len(train)*len(s['x']))) for s in train])
            booster=xgb.train(PARAMETERS,xgb.DMatrix(x,label=y,weight=weights,nthread=1),num_boost_round=ROUNDS)
            rows=[]
            for s in test:
                score=booster.predict(xgb.DMatrix(select(s['x']),nthread=1))
                median=float(np.median(score))
                prediction='control' if median<=.35 else 'glass_blocking' if median>=.65 else 'uncertain'
                correct=(prediction=='glass_blocking') if s['label'] else (prediction=='control')
                rows.append({k:v for k,v in s.items() if k not in ('x','frame_hashes')}|dict(score=median,prediction=prediction,correct=correct,window_counts=dict(Counter('control' if p<=.35 else 'glass_blocking' if p>=.65 else 'uncertain' for p in score)),scores=score.tolist()))
            fold=dict(phase_features=phase,heldout=heldout,training=[s['path'] for s in train],results=rows)
            report['folds'].append(fold)
            held=[r for r in rows if r['group']==heldout]
            print('phase',phase,'heldout',heldout,[(Path(r['path']).parent.name+'/'+Path(r['path']).name,r['prediction'],round(r['score'],3)) for r in held],flush=True)
    with args.output.open('x') as destination:
        json.dump(report,destination,indent=2,allow_nan=False)


if __name__=='__main__':
    main()
