"""Longer confirmed-empty calibration; not comparable holdout denominators."""
import json
from pathlib import Path
from radar_min.__main__ import read_recording
from tools.evaluate_whitened_range import WhitenedRange
from tools.evaluate_association import measure

def main():
    out=Path('evidence/whitened-long-1');out.mkdir(parents=True,exist_ok=True);report=[]
    setups=[]
    for run in ['350-a','100-a','350-b']:
        root=Path(f'recordings/hpf{run}-empty-before');setups.append((root,[(Path(f'recordings/hpf{run}-{s}'),v,skip) for s,v,skip in [('empty-before',None,90),('30cm',.3,0),('40cm',.4,0),('40cm-repeat',.4,0),('50cm',.5,0),('empty-after',None,0)]]))
    for session,cases in [('gui-20261101-144515-340260',[('live-003',None,90),('live-004',.3,0),('live-005',.5,0)]),('gui-20261101-153737-539230',[('live-002',None,90),('live-003',.3,0),('live-004',.4,0),('live-005',.5,0),('live-006',None,0)])]:
        root=Path('recordings')/session;setups.append((root/('live-003' if '144515' in session else 'live-002'),[(root/n,v,s) for n,v,s in cases]))
    with (out/'frames.jsonl').open('w') as log:
        for reference,cases in setups:
            c,e,_=read_recording(reference)
            for path,label,skip in cases:
                model=WhitenedRange(c,e[:90],fit_frames=60,calibration_frames=30);_,fs,_=read_recording(path,c);values=[];presence=0
                for f in fs[skip:]:
                    r=model.update(f);presence+=r['presence'];values.append(r['range_m']);log.write(json.dumps(dict(recording=str(path),sequence=f.sequence,**r))+'\n')
                row=dict(recording=str(path),label_m=label,reference=str(reference),evaluation_skip=skip,threshold=model.threshold,presence=presence,metrics=measure(values,label));report.append(row);print(path.name,label,presence,row['metrics'],flush=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
