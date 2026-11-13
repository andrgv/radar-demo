"""Compare frozen joint-fit outputs with saved baselines and check convergence."""
import hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np

def main():
    p=Path('evidence/joint-component-1')
    old={r['recording']:r['methods']['associated'] for r in json.loads(Path('evidence/associated-fit-3/report.json').read_text())}
    one={r['recording']:r['metrics'] for r in json.loads(Path('evidence/far-component-2/report.json').read_text())}
    new=json.loads((p/'report.json').read_text());frames=[json.loads(s) for s in (p/'frames.jsonl').read_text().splitlines()]
    comparison=[]
    for r in new:
        name=r['recording'];diagnostics=[x['diagnostic'] for x in frames if x['recording']==name]
        histories=[x['objective_history'] for x in diagnostics if len(x.get('objective_history',[]))>1]
        decreases=int(sum(min(np.diff(h)) < -1e-8 for h in histories))
        assert decreases==0
        comparison.append(dict(recording=name,label_m=r['label_m'],raw_sha256=hashlib.sha256((Path(name)/'frames.grd').read_bytes()).hexdigest(),associated=old[name],one_pass=one[name],joint=r['metrics'],reasons=dict(Counter(x['reason'] for x in diagnostics)),converged=sum(x.get('converged',False) for x in diagnostics),objective_decreases=decreases))
    (p/'comparison.json').write_text(json.dumps(comparison,indent=2)+'\n')
    print('Compared',sum(r['metrics']['frames'] for r in new),'frames; empty false detections:',sum(r['metrics'].get('false_detections',0) for r in new))
if __name__=='__main__':main()
