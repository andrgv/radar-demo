"""Evaluate a causal five-frame average without bridging rejected frames.

Offline only. Native presence-gate acceptance does not certify fine-peak identity.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import numpy as np


def rolling_average(values,accepted,window=5):
    result=np.full(len(values),np.nan);history=deque(maxlen=window)
    for i,(value,valid) in enumerate(zip(values,accepted)):
        if not valid or not np.isfinite(value):
            history.clear();continue
        history.append(float(value))
        if len(history)==window:result[i]=np.mean(history)
    return result


def summarize(values,truth):
    values=np.asarray(values);values=values[np.isfinite(values)]
    if not len(values):return {'frames':0}
    d=dict(frames=len(values),p05_median_p95_cm=(100*np.percentile(values,[5,50,95])).tolist(),std_cm=float(100*np.std(values)))
    if truth is not None:
        d.update(mae_cm=float(100*np.mean(abs(values-truth))),mean_bias_cm=float(100*np.mean(values-truth)))
    return d


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('analysis',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    source=json.loads((a.analysis/'report.json').read_text());rows=[json.loads(x) for x in (a.analysis/'per-frame.jsonl').read_text().splitlines()]
    result={'policy':'Fixed causal arithmetic mean of 5 consecutive accepted estimates; full window required, clear immediately on rejected/nonfinite frame, reset between captures. No live change.',
            'limits':'No range calibration. Accuracy metrics use user labels only for evaluation. Raw versus smoothed comparisons on matched frames prevent apparent improvement from discarding misses.',
            'captures':{}}
    traces=[]
    for name,capture in source['captures'].items():
        r=[x for x in rows if x['capture']==name];x=np.array([x['provisional_peak_m'] for x in r]);gate=np.array([x['native_gate_detected'] for x in r]);truth=capture['reported_distance_m']
        y=rolling_average(x,gate);mask=np.isfinite(y)
        result['captures'][name]={'total_frames':len(x),'native_accepted_frames':int(gate.sum()),'average_output_frames':int(mask.sum()),'no_average_output_frames':int((~mask).sum()),
            'raw_all':summarize(x,truth),'raw_accepted':summarize(x[gate],truth),'raw_on_average_output_frames':summarize(x[mask],truth),'average':summarize(y,truth)}
        if truth is not None:traces.append((name,x,gate,y,truth))
    (a.output/'report.json').write_text(json.dumps(result,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,(name,x,gate,y,truth) in zip(axes.flat,traces):
        t=np.arange(len(x))*.1
        ax.plot(t,x*100,color='#bbbbbb',lw=1,label='All exploratory peaks')
        ax.scatter(t[gate],x[gate]*100,s=9,color='#166d91',label='Native gate accepted')
        ax.plot(t,y*100,color='#d65a16',lw=2,label='5-frame average (gaps preserved)')
        ax.axhline(truth*100,color='#333333',ls='--',label='User-measured distance')
        ax.set(title=name,xlabel='Nominal seconds',ylabel='Provisional distance (cm)',ylim=(10,max(75,float(x.max()*100)+5)))
        ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('Sweep 2: smoother output is not necessarily accurate\nNo fitted offset; averaging requires five accepted frames and clears on every rejection',fontsize=12)
    fig.savefig(a.output/'rolling-average.png',dpi=150);plt.close(fig)
    for name,d in result['captures'].items():print(name,json.dumps(d))

if __name__=='__main__':main()
