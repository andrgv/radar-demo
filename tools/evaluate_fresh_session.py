"""Frozen-method evaluation of the user's new five-run sequence; no tuning."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline,Detector
from radar_min.gui import Estimate,range_displayable
from tools.fit_range_signal import traces
from tools.evaluate_far_component import FarComponentFit
from tools.joint_component_fit import JointComponentFit
from tools.multi_component_fit import MultiComponentFit
from tools.evaluate_association import measure

ROOT=Path('recordings/gui-20261101-153737-539230')
OUT=Path('evidence/fresh-session-1')
def main():
    OUT.mkdir(parents=True,exist_ok=True);baseline=Baseline.load(ROOT/'empty-001/baseline.json');c,empty,_=read_recording(ROOT/'empty-001',baseline.config)
    ref=np.mean([traces(f,c) for f in empty[:30]],axis=0)
    report=dict(source_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),session=str(ROOT),label_basis='Requested order: empty, 30 cm, 40 cm, 50 cm, empty; inferred from user done; no external synchronized truth',training_raw_sha256=hashlib.sha256((ROOT/'empty-001/frames.grd').read_bytes()).hexdigest(),recordings=[])
    with (OUT/'frames.jsonl').open('w') as log:
        for name,label in [('live-002',None),('live-003',.3),('live-004',.4),('live-005',.5),('live-006',None)]:
            p=ROOT/name;_,frames,_=read_recording(p,c);d=Detector(baseline);associated=Estimate(baseline,'associated')
            others={'one_pass':FarComponentFit(c),'joint':JointComponentFit(c),'three_component':MultiComponentFit(c)}
            saved=[json.loads(s) for s in (p/'readings.jsonl').read_text().splitlines()];assert len(saved)==len(frames)
            values={k:[] for k in ['associated',*others]};presence=0;nonconverged={k:0 for k in others}
            for f,live in zip(frames,saved):
                r=d.update(f);associated.enrich(f,r);presence+=r['target_detected'];v=r['experimental_range_m'] if range_displayable(r) else None
                assert live['target_detected']==r['target_detected']
                actual=live['experimental_range_m'] if range_displayable(live) else None
                assert (actual is None)==(v is None)
                if v is not None:assert abs(actual-v)<1e-8
                row=dict(recording=name,sequence=f.sequence,presence=r['target_detected'],associated=v);values['associated'].append(v)
                for method,model in others.items():
                    if r['target_detected']:
                        kwargs=dict(max_iterations=32) if method=='three_component' else {}
                        result=model.fit_associated(traces(f,c)-ref,r['candidate_bin'],r.get('qualified_bins'),**kwargs)
                    else:result=dict(range_m=None,reason='presence_rejected')
                    v=result['range_m'];values[method].append(v);row[method]=dict(range_m=v,reason=result['reason'],converged=result.get('converged'))
                    if v is not None and result.get('converged') is False:nonconverged[method]+=1
                log.write(json.dumps(row)+'\n')
            entry=dict(recording=str(p),label_m=label,raw_sha256=hashlib.sha256((p/'frames.grd').read_bytes()).hexdigest(),capture=json.loads((p/'capture-summary.json').read_text()),presence_frames=presence,live_replay_matches=True,nonconverged=nonconverged,methods={k:measure(v,label) for k,v in values.items()});report['recordings'].append(entry)
            print(name,label,{k:(m['reported'],round(m['mae_cm'],2) if m.get('mae_cm') is not None else None) for k,m in entry['methods'].items()},flush=True)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
