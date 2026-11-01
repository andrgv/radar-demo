"""Evaluate four new captures without tuning the preselected fit-gate trial."""
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline, Detector, Continuity
from radar_min.gui import Estimate, range_displayable
from tools.evaluate_fit_gate import FitEvidence, gate
from tools.evaluate_association import measure


def main():
    root=Path('recordings/gui-20261101-155623-972019')
    out=Path('evidence/frozen-fit-followup-1');out.mkdir(exist_ok=True)
    selection=Path('evidence/fit-gate-1/balanced-latest-tradeoff.json')
    thresholds=json.loads(selection.read_text())['thresholds']
    if thresholds != [2.,0.,999.,.1]:
        raise ValueError('Frozen threshold artifact changed')
    baseline=Baseline.load(root/'empty-001/baseline.json')
    c,empty,_=read_recording(root/'empty-001',baseline.config)
    model=FitEvidence(c,empty[:30])
    report=dict(thresholds=thresholds,median_window=5,
        selection_sha256=hashlib.sha256(selection.read_bytes()).hexdigest(),
        reference_sha256=hashlib.sha256((root/'empty-001/frames.grd').read_bytes()).hexdigest(),
        protocol='Prospective follow-up of locally selected trial; same acquisition session and background. All frames scored, no threshold tuning or trimming.',
        truth_limit='User states 40, 50, 20 cm, empty in order. Box shifted right during 50 and 20 cm; no synchronized pose or exact movement times. Their errors are relative to nominal placement, not certified instantaneous radial distance.',
        recordings=[])
    with (out/'frames.jsonl').open('w') as log:
        for name,label,moved in [('live-006',.4,False),('live-007',.5,True),('live-008',.2,True),('live-009',None,False)]:
            p=root/name;_,fs,_=read_recording(p,c)
            saved=[json.loads(s) for s in (p/'readings.jsonl').read_text().splitlines()]
            if len(saved)!=len(fs):raise ValueError('Live log frame count mismatch')
            detector=Detector(baseline);estimator=Estimate(baseline,'associated')
            guard=Continuity(c);invalidated=False;features=[];old=[]
            for f,s in zip(fs,saved):
                reason=guard.check(f);invalidated |= reason=='restart_or_duplicate'
                r=detector.update(f);estimator.enrich(f,r)
                value=r['experimental_range_m'] if range_displayable(r) else None
                saved_value=s['experimental_range_m'] if range_displayable(s) else None
                if r['target_detected']!=s['target_detected'] or ((value is None)!=(saved_value is None)) or (value is not None and abs(value-saved_value)>1e-8):
                    raise ValueError('Live replay mismatch')
                old.append(value)
                valid=not reason and not invalidated and r['candidate_bin'] is not None
                feature=model.features(f,r['candidate_bin'],r.get('qualified_bins')) if valid else dict(candidate=None,gain=0.,purity=0.,rx_spread=999.)
                feature.update(valid=valid,sequence=f.sequence);features.append(feature)
            raw=gate(features,thresholds,1);smooth=gate(features,thresholds,5)
            for f,feature,a,b,v in zip(fs,features,raw,smooth,old):
                log.write(json.dumps(dict(recording=name,sequence=f.sequence,features=feature,trial_raw_m=a,trial_median_m=b,existing_m=v))+'\n')
            methods={k:measure(v,label) for k,v in [('existing',old),('trial_raw',raw),('trial_median5',smooth)]}
            valid_values=[v*100 for v in smooth if v is not None]
            row=dict(recording=str(p),nominal_label_m=label,repositioned=moved,
                raw_sha256=hashlib.sha256((p/'frames.grd').read_bytes()).hexdigest(),live_replay_matches=True,
                capture=json.loads((p/'capture-summary.json').read_text()),methods=methods,
                trial_percentiles_cm=np.percentile(valid_values,[5,50,95]).tolist() if valid_values else None,
                chronological_quarters=[measure([smooth[i] for i in indices],label) for indices in np.array_split(np.arange(len(fs)),4)])
            report['recordings'].append(row)
            print(name,label,'moved',moved,'trial',methods['trial_median5'],'existing',methods['existing'],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
