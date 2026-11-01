"""Replay the frozen 350-a / 100-a / 350-b experiment without hardware."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.core import Baseline,Detector
from radar_min.__main__ import read_recording
from tools.analyze_distance_sweep import dense_power
from tools.fit_range_signal import ToneFit,traces,summarize


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output',type=Path)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    rows=[]
    with (args.output/'frames.jsonl').open('w') as stream:
        for run,profile in [('350-a',0x33514802),('100-a',0x33514801),('350-b',0x33514802)]:
            eroot=Path(f'recordings/hpf{run}-empty-before');c,empty,_=read_recording(eroot)
            if c.profile_id!=profile or len(empty)<=30:raise ValueError('Invalid reference')
            b=Baseline.fit(empty[:30],c)
            wave=np.mean([traces(f,c) for f in empty[:30]],axis=0)
            ref=np.median([dense_power(f,c) for f in empty[:30]],axis=0)
            axis=np.fft.rfftfreq(4096,1/c.sample_rate_hz)*299792458/(2*c.slope_hz_s)
            ids=np.flatnonzero((axis>=.15)&(axis<=1.5));fitter=ToneFit(c)
            cases=[('empty-before',None,30),('30cm',.3,0),('50cm',.5,0),('40cm',.4,0),('40cm-repeat',.4,0),('empty-after',None,0)]
            for suffix,label,skip in cases:
                path=Path(f'recordings/hpf{run}-{suffix}');_,frames,_=read_recording(path,c);frames=frames[skip:]
                detector=Detector(b);readings=[];fits=[];peaks=[]
                for i,f in enumerate(frames):
                    if f.flags!=(7 if run=='100-a' else 3):raise ValueError('Unexpected profile flags')
                    reading=detector.update(f)
                    if 'power' not in reading:raise ValueError('Invalid raw frame')
                    result=fitter.fit(traces(f,c)-wave)
                    peak=float(axis[ids[np.argmax((dense_power(f,c)-ref)[ids])]])
                    readings.append(reading);fits.append(result);peaks.append(peak)
                    stream.write(json.dumps(dict(recording=path.name,frame_index=i+skip,joint_fit=result,fft_peak_m=peak,native_detected=reading['target_detected'],reason=reading['reason']))+'\n')
                accepted=np.array([r['target_detected'] for r in readings])
                row=dict(run=run,recording=path.name,label_m=label,frames=len(frames),reference=eroot.name,reference_training_count=30,
                    raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),native_detections=int(accepted.sum()),
                    reasons=dict(Counter(r['reason'] for r in readings)),joint_fit=summarize(fits,label,accepted),
                    fft_median_m=float(np.median(peaks)),fft_mae_cm=float(np.mean(abs(np.array(peaks)-label))*100) if label is not None else None)
                rows.append(row)
                # Reproduce the already reported target results without retuning.
                if label is not None:
                    prior=json.loads(Path(f'evidence/hpf-pair-2/target-{run}-{suffix}.json').read_text())
                    if not np.isclose(row['joint_fit']['all_frame_errors']['mae_cm'],prior['joint_fit']['all_frame_errors']['mae_cm'],atol=1e-8):
                        raise ValueError('Replay differs from recorded result')
                    if row['native_detections']!=prior['native_detections']:raise ValueError('Detection replay mismatch')
                print(path.name,row['native_detections'],'/',row['frames'],flush=True)
    (args.output/'report.json').write_text(json.dumps(rows,indent=2))


if __name__=='__main__':main()
