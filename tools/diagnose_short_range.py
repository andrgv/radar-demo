"""Offline gate diagnosis. Never changes thresholds, recordings or firmware.

Run from repository root: python -m tools.diagnose_short_range OUTPUT_DIRECTORY
Local user captures required; filenames and hashes are included in the report.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types
import numpy as np
from radar_min.core import Baseline,Detector,db,power
from radar_min.__main__ import read_recording

BASELINE_COMMIT='4105345'


def median_experiment(excess,b):
    """Exploratory only: causal five-frame evidence median + raw-bin presence gate.

    Not installed. No state may be maintained when the selected raw bin fails.
    Input is already validated by the main detector for these continuous captures.
    """
    c=b.config;ids=np.arange(c.min_bin,c.max_bin+1);last=None;hits=0;count=0
    for i,raw in enumerate(excess):
        filtered=np.median(excess[max(0,i-4):i+1],axis=0)
        eligible=ids[(raw[ids]>=b.threshold_db[ids]) & (filtered[ids]>=b.threshold_db[ids])]
        if not len(eligible):last=None;hits=0;continue
        best=int(eligible[np.argmax(filtered[eligible])]);other=ids[abs(ids-best)>1]
        if len(other) and filtered[best]-max(filtered[other])<c.margin_db:
            last=None;hits=0;continue
        hits=hits+1 if best==last else 1;last=best
        count+=hits>=c.confirmation_frames
    return int(count)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    old=types.ModuleType('range_core_before');sys.modules[old.__name__]=old
    exec(subprocess.check_output(['git','show',BASELINE_COMMIT+':radar_min/core.py'],text=True),old.__dict__)
    report={'before_commit':BASELINE_COMMIT,'after_core_sha256':hashlib.sha256(Path('radar_min/core.py').read_bytes()).hexdigest(),
            'validation_status':'Retrospective development evidence; no new prospective validation. 1 m captures held by operator are confounded.',
            'policy':'Thresholds and ambiguity margin unchanged; qualify each bin before ranking. Median is exploratory only.', 'captures':{}}
    plot_data=[]
    groups=[('empty-50cm-1.json',[('empty-50cm-1',30),('target-50cm-1',0),('empty-after-50cm-1',0)]),
            ('empty-session-1.json',[('empty-session-1',30),('target-session-1',0),('target-1m-session-1',0),('empty-after-1m-session-1',0),('target-1m-repeat-1',0)])]
    for baseline,scenes in groups:
        path=Path('artifacts')/baseline;b=Baseline.load(path)
        for name,skip in scenes:
            root=Path('recordings')/name;_,frames,_=read_recording(root,b.config);frames=frames[skip:]
            previous=old.Detector(b);new=Detector(b)
            before=[previous.update(f) for f in frames];after=[new.update(f) for f in frames]
            e=np.array([db(power(f,b.config))-b.median_db for f in frames]);ids=np.arange(1,5)
            best=ids[np.argmax(e[:,ids],axis=1)];qualified=e[:,ids]>=b.threshold_db[ids]
            blocked=sum(e[i,k]<b.threshold_db[k] and qualified[i].any() for i,k in enumerate(best))
            def summarize(rows):
                return dict(detections=sum(r['target_detected'] for r in rows),bins=dict(Counter(r['range_bin'] for r in rows if r['target_detected'])),reasons=dict(Counter(r['reason'] for r in rows)))
            report['captures'][name]=dict(frames=len(frames),skip=skip,raw_sha256=hashlib.sha256((root/'frames.grd').read_bytes()).hexdigest(),baseline_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                threshold_db_bins1to4=b.threshold_db[1:5].tolist(),above_threshold_frames_bins1to4=qualified.sum(axis=0).tolist(),
                median_excess_bins1to4=np.median(e[:,1:5],axis=0).tolist(),bin1_excess_min_median_max=np.percentile(e[:,1],[0,50,100]).tolist(),
                frames_blocked_by_ineligible_winner=int(blocked),before=summarize(before),after=summarize(after),
                exploratory_median5_detections=median_experiment(e,b))
            if baseline=='empty-50cm-1.json':plot_data.append((name,e,b,before,after))
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(12,9),layout='constrained')
    for row,(name,e,b,before,after) in enumerate(plot_data):
        t=np.arange(len(e))*.1;ax=axes[row,0]
        ax.plot(t,e[:,1],label='Bin 1 excess',color='#136f63');ax.plot(t,e[:,2],label='Bin 2 excess',color='#b35c00',alpha=.75)
        ax.axhline(b.threshold_db[1],color='#136f63',ls='--',label='Bin 1 threshold');ax.axhline(b.threshold_db[2],color='#b35c00',ls='--',label='Bin 2 threshold')
        ax.set(title=name,ylabel='Excess over empty reference (dB)',xlabel='Nominal elapsed seconds');ax.legend(fontsize=8,ncol=2);ax.grid(alpha=.2)
        ax=axes[row,1]
        for offset,(label,rows,color) in enumerate([('Before',before,'#8b3a3a'),('Fixed selection',after,'#136f63')]):
            detected=np.array([r['target_detected'] for r in rows]);ax.scatter(t[detected],np.full(detected.sum(),offset),s=8,color=color)
        ax.set(yticks=[0,1],yticklabels=['Before','Fixed selection'],ylim=(-.5,1.5),xlim=(0,max(float(t[-1]),.1)),xlabel='Nominal elapsed seconds',title='Accepted frames (blank = no reading)');ax.grid(alpha=.2)
    fig.suptitle('50 cm experiment: stable bin 1 evidence was blocked by an unqualified neighbor\nNo threshold changes, range calibration, or temporal smoothing',fontsize=13)
    fig.savefig(args.output/'gate-diagnosis.png',dpi=150);plt.close(fig)
    for name,d in report['captures'].items():print(name,d['before']['detections'],'->',d['after']['detections'],'/',d['frames'],'median experiment',d['exploratory_median5_detections'])

if __name__=='__main__':main()
