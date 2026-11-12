"""Offline model check: windowed peak versus raw sinusoid/DC fit; no live change."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from tools.fit_range_signal import ToneFit,traces
from tools.qualify_avg16_cfar import aligned_times


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('configs/foil-box-live-20261111.json'))
    parser.add_argument('--output',type=Path,default=Path('evidence/foil-box-live-20261111'))
    args=parser.parse_args();manifest=json.loads(args.manifest.read_text());case=manifest['cases'][0]
    source=Path(case['recording']);config,frames,_=read_recording(source)
    arrivals=[json.loads(x)for x in (source/'arrivals.jsonl').read_text().splitlines()]
    saved=[json.loads(x)for x in (source/'readings.jsonl').read_text().splitlines()]
    if [r['frame_sequence'] for r in saved]!=[f.sequence for f in frames]:raise ValueError('Frame/output mismatch')
    times=aligned_times(frames,arrivals);fitter=ToneFit(config);windows=[]
    for w in case['windows']:
        if w['trim_s']!=2 or w['state']!='hold':continue
        ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))[::5]
        results=[fitter.fit(traces(frames[i],config)) for i in ids]
        recorded=[saved[i]['one_d']['experimental_range_m']*100 for i in ids if saved[i]['one_d']['experimental_range_m'] is not None]
        windows.append(dict(label=w['label'],fixed_frame_stride=5,samples=len(ids),
            recorded_peak_cm_p05_p50_p95=np.percentile(recorded,[5,50,95]).tolist() if recorded else None,
            diagnostic_fit_cm_p05_p50_p95=np.percentile([r['range_m']*100 for r in results],[5,50,95]).tolist(),
            residual_fraction_p05_p50_p95=np.percentile([r['residual_fraction']for r in results],[5,50,95]).tolist(),
            boundary_fits=sum(r['boundary']for r in results)))
    phase_test=[];n=np.arange(config.samples);axis=np.arange(2049)*config.spacing_m*config.samples/4096
    band=np.flatnonzero((axis>=.15)&(axis<=1.7))
    for distance in (.47,.5,.53,1.2):
        peaks=[]
        for phase in np.linspace(0,2*np.pi,361):
            x=np.cos(2*np.pi*(distance/config.spacing_m)*n/config.samples+phase)
            x-=x.mean();power=abs(np.fft.rfft(x*np.hanning(config.samples),n=4096))**2
            peaks.append(float(axis[band[np.argmax(power[band])]]))
        phase_test.append(dict(true_distance_m=distance,phases=361,
                               raw_hann_peak_m_min_max=[min(peaks),max(peaks)]))
    report=dict(manifest=manifest,raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in
            ('tools/diagnose_foil_range.py','tools/fit_range_signal.py','radar_min/core.py')},
        diagnostic_model='Raw shared-frequency real sinusoid plus separate DC/sine/cosine amplitudes per chirp/RX; no empty subtraction, no window, fixed 0.15–1.5m pre-existing grid',
        interpretation='Diagnostic only. Large residuals mean the single-tone model does not explain all the waveform. Fitted frequency is not verified target identity or calibrated range, and no distance labels were fitted. Synthetic isolated-tone phase sweeps show a possible estimator contribution but do not model the full hardware scene.',
        windows=windows,synthetic_phase_test=phase_test)
    (args.output/'model-check.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    for w in windows:print(w)


if __name__=='__main__':main()
