"""Experimental single-tone variable-projection fit; never used by live code.

For each chirp/RX: x[n] = d + a*cos(2*pi*f*t[n]) + b*sin(2*pi*f*t[n]).
Frequency is shared; d/a/b are independent per trace. No window or fitted labels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.core import Baseline, Detector, Config
from radar_min.__main__ import read_recording
from tools.analyze_distance_sweep import dense_power
from tools.calibrate_range_offline import SETUPS, EXCLUDED


class ToneFit:
    def __init__(self, config):
        self.c = config
        self.t = np.arange(config.samples)/config.sample_rate_hz
        self.grid = np.linspace(.15, 1.5, 271)  # fixed 5 mm scan; not physical resolution
        self.q = np.array([self.basis(r) for r in self.grid])

    def basis(self, distance):
        phase = 2*np.pi*(2*self.c.slope_hz_s*distance/299792458)*self.t
        a = np.column_stack((np.cos(phase), np.sin(phase)))
        # Residualize BOTH data and basis against constant: equivalent to joint DC fit.
        a -= a.mean(axis=0)
        return np.linalg.qr(a)[0]

    def fit(self, traces):
        x = np.asarray(traces, dtype=float)
        if x.ndim != 2 or x.shape[1] != self.c.samples or not np.isfinite(x).all():
            raise ValueError('Expected finite traces x samples')
        x = x-x.mean(axis=1, keepdims=True)
        energy = float(np.sum(x*x))
        if energy <= 1e-20:
            return dict(range_m=None, reason='no_ac_energy', residual_fraction=None,
                        near_optimal_width_m=None, boundary=False)
        projection = np.einsum('ts,gsb->gtb', x, self.q, optimize=True)
        scores = np.sum(projection**2,axis=(1,2))
        k = int(np.argmax(scores))
        def score(r): return float(np.sum((x@self.basis(r))**2))
        lo,hi = self.grid[max(0,k-1)],self.grid[min(len(self.grid)-1,k+1)]
        # Golden-section refinement inside the winning scan cell; NumPy only.
        ratio=(np.sqrt(5)-1)/2
        left=hi-ratio*(hi-lo);right=lo+ratio*(hi-lo)
        sl,sr=score(left),score(right)
        for _ in range(40):
            if sl>sr:
                hi,right,sr=right,left,sl
                left=hi-ratio*(hi-lo);sl=score(left)
            else:
                lo,left,sl=left,right,sr
                right=lo+ratio*(hi-lo);sr=score(right)
        candidates = [(float(self.grid[k]),float(scores[k])),(float(left),sl),(float(right),sr)]
        estimate,best = max(candidates,key=lambda v:v[1])
        # Diagnostic width of grid fits within 1% of total centered signal energy.
        # Not a calibrated confidence interval, nor a detection/rejection threshold.
        near = self.grid[(best-scores)<=.01*energy]
        return dict(range_m=estimate,reason='experimental_fit_not_detection',
                    residual_fraction=float(max(0,1-best/energy)),
                    near_optimal_width_m=float(np.ptp(near)) if len(near) else 0.,
                    boundary=bool(estimate<=.15001 or estimate>=1.49999))


def traces(frame,c):
    return frame.adc[c.discard_chirps:].transpose(0,2,1).reshape(-1,c.samples).astype(float)


def summarize(results,label,accepted):
    valid=np.array([r['range_m'] is not None for r in results])
    values=np.array([r['range_m'] if r['range_m'] is not None else np.nan for r in results])
    def errors(mask):
        selected=values[mask&valid]
        if label is None or not len(selected): return None
        return dict(frames=len(selected),mae_cm=float(np.mean(abs(selected-label))*100),
                    bias_cm=float(np.mean(selected-label)*100),within_1cm=float(np.mean(abs(selected-label)<=.01)))
    return dict(valid_fits=int(valid.sum()),boundary_fits=sum(r['boundary'] for r in results),
        range_p05_median_p95_m=np.nanpercentile(values,[5,50,95]).tolist() if valid.any() else None,
        all_frame_errors=errors(np.ones(len(values),bool)),gated_errors=errors(accepted),
        residual_fraction_median=float(np.median([r['residual_fraction'] for r in results if r['range_m'] is not None])) if valid.any() else None,
        near_optimal_width_median_m=float(np.median([r['near_optimal_width_m'] for r in results if r['range_m'] is not None])) if valid.any() else None)


def plot_report(report,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[r for r in report['recordings'] if r['label_m'] is not None]
    fig,ax=plt.subplots(figsize=(10,7),layout='constrained')
    y=np.arange(len(rows))
    ax.barh(y-.17,[r['peak_mae_cm'] for r in rows],height=.32,label='Existing fine FFT peak',color='#9b9b9b')
    ax.barh(y+.17,[r['subtracted']['all_frame_errors']['mae_cm'] for r in rows],height=.32,label='Joint tone fit after empty waveform subtraction',color='#247b91')
    ax.set(yticks=y,yticklabels=[r['recording'] for r in rows],xlabel='Mean absolute error (cm), all target frames',
           title='Saved recordings: no distance-label training or smoothing')
    ax.invert_yaxis();ax.legend(fontsize=8);ax.grid(axis='x',alpha=.2)
    fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)


def synthetic_checks():
    fitter=ToneFit(Config());rows=[]
    for distance in [.15,.1837,.3,.35,.4,.5,.8732,1.5]:
        errors=[]
        for phase in np.arange(360)*2*np.pi/360:
            signal=17000+730*np.cos(2*np.pi*(2*fitter.c.slope_hz_s*distance/299792458)*fitter.t+phase)
            result=fitter.fit(signal[None,:]);errors.append(abs(result['range_m']-distance))
        rows.append(dict(distance_m=distance,phases=360,max_absolute_error_m=max(errors)))
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('output',type=Path);args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'synthetic.json').write_text(json.dumps(synthetic_checks(),indent=2))
    report=dict(method=__doc__,search_interval_m=[.15,1.5],grid_step_m=.005,
        variants=['raw_single_tone','empty_waveform_subtracted'],exclusions=EXCLUDED,
        protocol='No target labels fitted or search bounds tuned. All entire recordings scored. Empty reference first 30 frames only; holdouts excluded. Retrospective evaluation, not new prospective validation.',
        limits='Shared frequency assumes one static tone across RX/chirps. Empty waveform subtraction assumes sample/phase alignment, not proven on hardware. Near-optimal width is a sensitivity diagnostic, not confidence. Neither fit detects presence.',recordings=[])
    with (args.output/'frames.jsonl').open('w') as out:
        for setup,emptyname,targets,emptychecks in SETUPS:
            c,empty,_=read_recording(Path('recordings')/emptyname)
            fitter=ToneFit(c);baseline=Baseline.fit(empty[:30],c)
            ref_wave=np.mean([traces(f,c) for f in empty[:30]],axis=0)
            ref_power=np.median([dense_power(f,c) for f in empty[:30]],axis=0)
            axis=np.fft.rfftfreq(4096,1/c.sample_rate_hz)*299792458/(2*c.slope_hz_s)
            ids=np.flatnonzero((axis>=.15)&(axis<=1.5))
            for name,label,skip in [(n,d,0) for n,d in targets]+[(emptyname,None,30)]+[(n,None,0) for n in emptychecks]:
                path=Path('recordings')/name;_,frames,_=read_recording(path,c);frames=frames[skip:]
                detector=Detector(baseline);accepted=[];raw=[];sub=[];peaks=[]
                for i,f in enumerate(frames):
                    reading=detector.update(f)
                    if 'power' not in reading: raise ValueError('Invalid frame '+name)
                    accepted.append(reading['target_detected'])
                    x=traces(f,c);a=fitter.fit(x);b=fitter.fit(x-ref_wave)
                    raw.append(a);sub.append(b)
                    peak=float(axis[ids[np.argmax((dense_power(f,c)-ref_power)[ids])]])
                    peaks.append(peak)
                    out.write(json.dumps(dict(recording=name,index=i,raw=a,subtracted=b,peak_m=peak,native_accepted=accepted[-1]))+'\n')
                accepted=np.array(accepted)
                row=dict(recording=name,setup=setup,label_m=label,frames=len(frames),skip=skip,
                    reference=emptyname,reference_training_frames=30,
                    raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                    native_accepted=int(accepted.sum()),raw=summarize(raw,label,accepted),
                    subtracted=summarize(sub,label,accepted),
                    peak_mae_cm=float(np.mean(abs(np.array(peaks)-label))*100) if label is not None else None)
                report['recordings'].append(row)
                print(name, 'raw/sub/peak MAE',*[round(row[k]['all_frame_errors']['mae_cm'],2) if label is not None else None for k in ['raw','subtracted']],row['peak_mae_cm'],flush=True)
    targets=[r for r in report['recordings'] if r['label_m'] is not None]
    report['recording_macro_mae_cm']={k:float(np.mean([r[k]['all_frame_errors']['mae_cm'] for r in targets])) for k in ['raw','subtracted']}
    report['recording_macro_mae_cm']['peak']=float(np.mean([r['peak_mae_cm'] for r in targets]))
    report['distance_balanced_mae_cm']={k:float(np.mean([np.mean([r[k]['all_frame_errors']['mae_cm'] for r in targets if r['label_m']==d]) for d in sorted({r['label_m'] for r in targets})])) for k in ['raw','subtracted']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2))
    plot_report(report,args.output)
    print(report['recording_macro_mae_cm'])


if __name__=='__main__': main()
