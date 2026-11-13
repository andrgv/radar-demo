"""Offline channel and empty-waveform sensitivity; no label-based selection."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from tools.fit_range_signal import ToneFit


def cube(frame,c):
    return frame.adc[c.discard_chirps:].astype(float).transpose(0,2,1)


def stats(results,label):
    r=np.array([v['range_m'] if v['range_m'] is not None else np.nan for v in results])
    valid=np.isfinite(r)
    return dict(valid=int(valid.sum()),median_m=float(np.nanmedian(r)) if valid.any() else None,
        p05_p95_m=np.nanpercentile(r,[5,95]).tolist() if valid.any() else None,
        mae_cm=float(np.nanmean(abs(r-label))*100) if label is not None and valid.any() else None,
        boundary_fits=sum(v['boundary'] for v in results),
        median_residual=float(np.median([v['residual_fraction'] for v in results if v['range_m'] is not None])) if valid.any() else None)


def plot_report(report,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,3,figsize=(12,4),layout='constrained')
    rows=[r for r in report['rows'] if r['run']=='100-a' and r['reference']=='first30' and r['label_m'] is not None]
    for ax,suffix in zip(axes,['30cm','40cm','50cm']):
        row=next(r for r in rows if r['recording']==f'hpf100-a-{suffix}')
        for i,name in enumerate(['rx0','rx1','rx2','all']):
            s=row['channels'][name];lo,hi=np.array(s['p05_p95_m'])*100;med=s['median_m']*100
            ax.errorbar(i,med,yerr=[[med-lo],[hi-med]],fmt='o',capsize=4,color='#167d8d' if name=='all' else '#737373')
        ax.axhline(row['label_m']*100,color='#ba6638',ls='--',label='Measured box position')
        ax.set(xticks=range(4),xticklabels=['RX0','RX1','RX2','Combined'],title=suffix,ylabel='Nominal estimated distance (cm)')
        ax.grid(axis='y',alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle('100 kHz: receiver medians and frame 5th–95th percentiles\nWire indices; physical antenna mapping unverified')
    fig.savefig(output/'channels.png',dpi=150);plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('output',type=Path)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    report=dict(protocol='Fixed comparisons, no channel chosen, labels used only for error scoring. Wire channel indices do not establish physical antenna order. Four equal-size empty references; late-reference result is retrospective, not causal. No new gate or calibration.',rows=[],drift=[],manifest=[])
    with (args.output/'frames.jsonl').open('w') as stream:
        for run in ['350-a','100-a','350-b']:
            before=Path(f'recordings/hpf{run}-empty-before');after=Path(f'recordings/hpf{run}-empty-after')
            c,empty,_=read_recording(before);_,late,_=read_recording(after,c);fitter=ToneFit(c)
            if len(empty)<91 or len(late)<31:raise ValueError('Insufficient independent evaluation frames')
            sources={'first30':(before,empty,0,30),'next30':(before,empty,30,60),
                     'third30':(before,empty,60,90),'after30':(after,late,0,30)}
            refs={k:np.mean([cube(f,c) for f in fs[start:end]],axis=0) for k,(_,fs,start,end) in sources.items()}
            for name,(path,fs,start,end) in sources.items():
                report['manifest'].append(dict(run=run,reference=name,recording=path.name,start=start,end_exclusive=end,raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest()))
                delta=refs[name]-refs['first30'];delta-=delta.mean(axis=2,keepdims=True)
                report['drift'].append(dict(run=run,reference=name,centered_reference_difference_rms_per_rx=np.sqrt(np.mean(delta**2,axis=(0,2))).tolist()))
            cases=[('30cm',.3,0),('50cm',.5,0),('40cm',.4,0),('40cm-repeat',.4,0),('empty-before',None,90),('empty-after',None,30)]
            for suffix,label,skip in cases:
                path=Path(f'recordings/hpf{run}-{suffix}');_,frames,_=read_recording(path,c);frames=frames[skip:]
                primary=None
                for refname,reference in refs.items():
                    collected={name:[] for name in ['all','rx0','rx1','rx2']};energies=[]
                    for i,f in enumerate(frames):
                        x=cube(f,c)-reference
                        centered=x-x.mean(axis=2,keepdims=True)
                        e=np.sum(centered**2,axis=(0,2));energies.append(e/max(float(e.sum()),1e-20))
                        for name,rx in [('all',None),('rx0',0),('rx1',1),('rx2',2)]:
                            traces=x.reshape(-1,c.samples) if rx is None else x[:,rx,:]
                            result=fitter.fit(traces);collected[name].append(result)
                            stream.write(json.dumps(dict(run=run,recording=path.name,index=i+skip,reference=refname,channel=name,**result))+'\n')
                    estimates={k:np.array([v['range_m'] if v['range_m'] is not None else np.nan for v in vs]) for k,vs in collected.items()}
                    if primary is None:primary=estimates
                    row=dict(run=run,recording=path.name,label_m=label,frames=len(frames),skip=skip,reference=refname,
                        raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                        channels={k:stats(v,label) for k,v in collected.items()},
                        median_rx_energy_fraction=np.median(energies,axis=0).tolist(),
                        median_frame_rx_spread_cm=float(np.nanmedian(np.nanmax(np.stack([estimates[k] for k in ['rx0','rx1','rx2']]),axis=0)-np.nanmin(np.stack([estimates[k] for k in ['rx0','rx1','rx2']]),axis=0))*100),
                        reference_shift={k:dict(median_signed_cm=float(np.nanmedian(estimates[k]-primary[k])*100),median_absolute_cm=float(np.nanmedian(abs(estimates[k]-primary[k]))*100),p95_absolute_cm=float(np.nanpercentile(abs(estimates[k]-primary[k]),95)*100)) for k in estimates})
                    report['rows'].append(row)
                    if label is not None and refname=='first30':
                        prior=json.loads(Path(f'evidence/hpf-pair-2/target-{run}-{suffix}.json').read_text())
                        if not np.isclose(row['channels']['all']['mae_cm'],prior['joint_fit']['all_frame_errors']['mae_cm'],atol=1e-8):raise ValueError('Primary fit changed')
                print(run,suffix,'complete',flush=True)
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    plot_report(report,args.output)


if __name__=='__main__':main()
