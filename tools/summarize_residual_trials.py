"""Compare residual-driven development trials, including convergence failures."""
import hashlib,json
from pathlib import Path
import numpy as np
from tools.evaluate_association import measure

def main():
    out=Path('evidence/joint-residual-1')
    associated={r['recording']:r for r in json.loads(Path('evidence/associated-fit-3/report.json').read_text())}
    methods={}
    for label,folder in [('joint','joint-component-1'),('expanded_nuisance','supported-nuisance-1'),('three_components_8','multi-component-1'),('three_components_32','multi-component-2')]:
        p=Path('evidence')/folder
        reports={r['recording']:r for r in json.loads((p/'report.json').read_text())}
        frames=[json.loads(s) for s in (p/'frames.jsonl').read_text().splitlines()]
        methods[label]=(reports,frames)
    result=[]
    for name,baseline in associated.items():
        row=dict(recording=name,label_m=baseline['label_m'],raw_sha256=hashlib.sha256((Path(name)/'frames.grd').read_bytes()).hexdigest(),associated=baseline['methods']['associated'],trials={})
        for label,(reports,frames) in methods.items():
            selected=[x for x in frames if x['recording']==name];returned=[x['diagnostic'] for x in selected if x['range_m'] is not None]
            histories=[x['diagnostic']['objective_history'] for x in selected if len(x['diagnostic'].get('objective_history',[]))>1]
            decreases=int(sum(np.min(np.diff(h)) < -1e-8 for h in histories));assert not decreases
            row['trials'][label]=dict(metrics=reports[name]['metrics'],not_converged=sum(not x['converged'] for x in returned),median_returned_residual=float(np.median([x['residual_fraction'] for x in returned])) if returned else None,objective_decreases=decreases,converged_only=measure([x['range_m'] if x['diagnostic'].get('converged',False) else None for x in selected],baseline['label_m']))
        result.append(row)
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    for row in result:
        if '/live-' in row['recording']:
            print(row['recording'],{k:(v['metrics'].get('mae_cm'),v['metrics']['reported'],v['not_converged']) for k,v in row['trials'].items()})
if __name__=='__main__':main()
