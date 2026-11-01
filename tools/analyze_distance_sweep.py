"""Analyze fixed distance sweep without fitting to distance labels.

The fine FFT only samples the existing spectrum more densely. All estimates are
provisional. Empty scenes also have maxima: a maximum alone is not a detection.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.core import Baseline,Detector
from radar_min.__main__ import read_recording


def dense_power(frame,c,nfft=4096):
    x=frame.adc[c.discard_chirps:].astype(float)
    x-=x.mean(axis=1,keepdims=True)
    w=np.hanning(c.samples)
    return np.mean(abs(np.fft.rfft(x*w[None,:,None],n=nfft,axis=1)*(2/w.sum()))**2,axis=(0,2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('prefix',help='e.g. recordings/distance-sweep-1')
    ap.add_argument('output',type=Path)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    before=Path(a.prefix+'-empty-before');c,empty,_=read_recording(before)
    training=30
    if len(empty)<=training:raise ValueError('Need training and unused empty frames')
    b=Baseline.fit(empty[:training],c,{'recording':str(before),'training_frames':training})
    ref=np.median([dense_power(f,c) for f in empty[:training]],axis=0)
    ranges=np.fft.rfftfreq(4096,1/c.sample_rate_hz)*299792458/(2*c.slope_hz_s)
    ids=np.flatnonzero((ranges>=.15)&(ranges<=1.5))
    report={'method':'Median empty linear power subtracted from per-frame averaged Hann FFT power; maximum in fixed 0.15–1.50 m provisional search interval. No label-dependent fit, offset, threshold or search tuning.',
            'training_frames':training,'nfft':4096,'native_samples':c.samples,
            'fine_grid_m':float(ranges[1]),'native_spacing_m':c.spacing_m,
            'limits':'Exploratory provisional coordinates, not certified target association or calibrated distances. Detection gate is the unchanged native-bin detector. Ungated peaks include rejected frames.',
            'thresholds_bins1to4':b.threshold_db[1:5].tolist(),'captures':{}}
    data=[]
    for suffix,label in [('empty-before',None),('30cm',.3),('40cm',.4),('50cm',.5),('40cm-repeat',.4),('empty-after',None)]:
        root=Path(a.prefix+'-'+suffix);_,allframes,p=read_recording(root,c)
        frames=allframes[training:] if suffix=='empty-before' else allframes
        if not frames:raise ValueError('Empty evaluation set')
        powers=np.array([dense_power(f,c) for f in frames]);residual=powers-ref
        peakidx=ids[np.argmax(residual[:,ids],axis=1)];peaks=ranges[peakidx]
        med=np.median(residual,axis=0);medianidx=ids[np.argmax(med[ids])]
        d=Detector(b);readings=[d.update(f) for f in frames];accepted=np.array([r['target_detected'] for r in readings])
        row={'frames':len(frames),'reported_distance_m':label,
             'raw_sha256':hashlib.sha256((root/'frames.grd').read_bytes()).hexdigest(),
             'capture':json.loads((root/'capture-summary.json').read_text()),
             'native_gate_detections':int(accepted.sum()),'native_gate_bins':dict(Counter(r['range_bin'] for r in readings if r['target_detected'])),
             'native_gate_reasons':dict(Counter(r['reason'] for r in readings)),
             'ungated_peak_p05_median_p95_m':np.percentile(peaks,[5,50,95]).tolist(),
             'median_residual_profile_peak_m':float(ranges[medianidx]),
             'search_boundary_peak_frames':int(np.sum((peakidx==ids[0])|(peakidx==ids[-1]))),
             'accepted_peak_p05_median_p95_m':np.percentile(peaks[accepted],[5,50,95]).tolist() if accepted.any() else None}
        if label is not None:
            row['ungated_median_bias_m']=float(np.median(peaks)-label)
            row['ungated_nominal_mae_m']=float(np.mean(abs(peaks-label)))
        report['captures'][suffix]=row
        data.append((suffix,label,peaks,accepted,med))
    report['repeat_median_difference_m']=report['captures']['40cm-repeat']['ungated_peak_p05_median_p95_m'][1]-report['captures']['40cm']['ungated_peak_p05_median_p95_m'][1]
    (a.output/'report.json').write_text(json.dumps(report,indent=2))
    with (a.output/'per-frame.jsonl').open('w') as f:
        for suffix,label,peaks,accepted,med in data:
            for i,(estimate,gate) in enumerate(zip(peaks,accepted)):
                f.write(json.dumps(dict(capture=suffix,frame_index=i,provisional_peak_m=float(estimate),native_gate_detected=bool(gate)))+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
    for ax,(suffix,label,peaks,accepted,med) in zip(axes.flat,[d for d in data if d[1] is not None]):
        t=np.arange(len(peaks))*.1
        ax.plot(t,peaks*100,color='#777777',lw=1,label='All provisional peak estimates')
        ax.scatter(t[accepted],peaks[accepted]*100,s=10,color='#167d8d',label='Frames accepted by presence gate')
        ax.axhline(label*100,ls='--',color='#a94732',label='User-measured position')
        ax.set(title=suffix,xlabel='Nominal elapsed seconds',ylabel='Distance coordinate (cm)',ylim=(10,max(75,float(peaks.max()*100)+5)));ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle('Distance sweep: fine peak estimates without fitted distance correction\nZero padding adds spectral samples, not physical bandwidth',fontsize=12)
    fig.savefig(a.output/'distance-estimates.png',dpi=150);plt.close(fig)
    for name,row in report['captures'].items():
        print(name, 'gate',row['native_gate_detections'],'/',row['frames'],'p05/median/p95',row['ungated_peak_p05_median_p95_m'],'profile peak',row['median_residual_profile_peak_m'])
    print('40 cm repeat median difference:',report['repeat_median_difference_m'])

if __name__=='__main__':main()
