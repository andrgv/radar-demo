"""Exploratory reference-free multi-tone separation of static FMCW returns.

Uses real-trace Hankel smoothing and shared receiver subspace. No ground-truth
range/door state enters order selection. BIC is heuristic under colored radar
noise; this is a signal-model audit, not a validated obstacle detector.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from radar.config import Config
from radar.storage import replay
from radar.door_check import _session


def estimate(traces):
    # Input RX x fast-time, averaged within one stationary acquisition window.
    traces=np.asarray(traces,dtype=float)
    if traces.ndim != 2 or traces.shape[1] < 32 or not np.isfinite(traces).all():
        raise ValueError('Expected finite RX by fast-time traces with at least 32 samples')
    traces = traces-traces.mean(axis=1,keepdims=True)
    if float(np.sum(traces**2)) <= 1e-20:
        raise ValueError('No AC energy for subspace estimation')
    channels, samples = traces.shape
    length = samples//2
    hankels = np.concatenate([np.lib.stride_tricks.sliding_window_view(t, length).T for t in traces],axis=1)
    u,s,_ = np.linalg.svd(hankels,full_matrices=False)
    fits=[]
    axis=np.arange(samples)
    for order in (2,4,6,8,10,12,14,16):
        modes=u[:,:order]
        roots=np.linalg.eigvals(np.linalg.lstsq(modes[:-1],modes[1:],rcond=None)[0])
        poles=[z for z in roots if np.angle(z)>1e-5 and .85<abs(z)<1.15]
        frequencies=sorted(float(np.angle(z)*samples/(2*np.pi)) for z in poles)
        if not frequencies:
            continue
        design=np.stack([np.ones(samples)]+[func(2*np.pi*f*axis/samples) for f in frequencies for func in (np.cos,np.sin)],axis=1)
        coefficients=np.linalg.lstsq(design,traces.T,rcond=None)[0]
        residual=traces.T-design@coefficients
        rss=float(np.sum(residual**2))
        n=traces.size
        parameters=channels*(1+2*len(frequencies))+len(frequencies)
        bic=float(n*np.log(max(rss/n,1e-20))+parameters*np.log(n))
        amplitude=np.sqrt(coefficients[1::2]**2+coefficients[2::2]**2).T
        fits.append(dict(order=order,bic=bic,frequencies_native_bins=frequencies,
                         amplitudes_per_rx=amplitude.tolist(), residual_fraction=rss/float(np.sum(traces**2))))
    return dict(best=min(fits,key=lambda f:f['bic']),orders=fits,
                singular_values=s.tolist())


def audit(root,output):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    result={}
    for manifest_path in sorted(Path(root).glob('*/door-check.json')):
        manifest=json.loads(manifest_path.read_text())
        if not manifest.get('complete'):continue
        experiment=manifest_path.parent
        config=Config.load(experiment/'config.json')
        spacing=299792458*config.sample_rate_hz/(2*config.slope_hz_s*config.samples)
        target=manifest['measured_glass_distance_m']/spacing
        n=max(1,int(np.ceil(1/config.frame_interval_s)))
        for i in range(1,manifest['repeats']+1):
            for state in ('open','closed'):
                path=experiment/f'{state}-{i:02d}'
                _session(path,config)
                adc=np.array([np.mean(f.adc[config.discard_chirps:].astype(float),axis=0).T for f in replay(path)])
                windows=[]
                for start in range(0,len(adc)-n+1,n):
                    fit=estimate(np.median(adc[start:start+n],axis=0))
                    fit['start_frame']=start
                    fit['near_measured_pane']=[f for f in fit['best']['frequencies_native_bins'] if abs(f-target)<=1]
                    windows.append(fit)
                result[f'{experiment.name}/{path.name}']=dict(expected_fractional_bin=target,
                    windows=windows,near_pane_windows=sum(bool(w['near_measured_pane']) for w in windows))
                print(experiment.name,path.name,'near',result[f'{experiment.name}/{path.name}']['near_pane_windows'],
                      '/',len(windows),'first',np.round(windows[0]['best']['frequencies_native_bins'],3).tolist(),flush=True)
    (output/'audit.json').write_text(json.dumps(dict(method=__doc__,sessions=result),indent=2,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('output');a=p.parse_args();audit(a.root,a.output)
