"""Test multi-tone returns against independent fast-time aperture truncations.

No state labels or measured distances enter extraction/stability selection.
Frequency agreement is an engineering consistency test, not calibrated accuracy.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from radar.config import Config
from radar.storage import replay
from radar.door_check import _session
from tools.audit_subspace_returns import estimate


def stable_components(traces, agreement=.25):
    full=estimate(traces)['best']
    samples=traces.shape[1]
    length=3*samples//4
    left=estimate(traces[:,:length])['best']
    right=estimate(traces[:,-length:])['best']
    f=np.array(full['frequencies_native_bins'])
    l=np.array(left['frequencies_native_bins'])*samples/length
    r=np.array(right['frequencies_native_bins'])*samples/length
    stable=[]
    for i,frequency in enumerate(f):
        error=max(float(np.min(abs(l-frequency))),float(np.min(abs(r-frequency))))
        if error<=agreement:
            stable.append(dict(native_bin=float(frequency),max_subset_difference_bins=error,
                               amplitude_per_rx=[a[i] for a in full['amplitudes_per_rx']]))
    return dict(components=stable,full=full,left_frequencies=l.tolist(),right_frequencies=r.tolist())


def audit(root,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    result={}
    for manifest_path in sorted(Path(root).glob('*/door-check.json')):
        manifest=json.loads(manifest_path.read_text())
        if not manifest.get('complete'):continue
        experiment=manifest_path.parent;config=Config.load(experiment/'config.json')
        spacing=299792458*config.sample_rate_hz/(2*config.slope_hz_s*config.samples)
        expected=manifest['measured_glass_distance_m']/spacing
        n=max(1,int(np.ceil(1/config.frame_interval_s)))
        for i in range(1,manifest['repeats']+1):
            for state in ('open','closed'):
                path=experiment/f'{state}-{i:02d}';_session(path,config)
                adc=np.array([np.mean(f.adc[config.discard_chirps:].astype(float),axis=0).T for f in replay(path)])
                windows=[stable_components(np.median(adc[j:j+n],axis=0)) for j in range(0,len(adc)-n+1,n)]
                counts={str(tolerance):sum(any(abs(c['native_bin']-expected)<=tolerance for c in w['components'])
                                         for w in windows) for tolerance in (.25,.5,1.)}
                result[f'{experiment.name}/{path.name}']=dict(windows=windows,
                    expected_fractional_bin=expected,near_pane_windows_by_tolerance=counts)
                print(experiment.name,path.name,len(windows),counts,flush=True)
    (output/'audit.json').write_text(json.dumps(dict(method=__doc__,sessions=result),indent=2,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('output');a=p.parse_args();audit(a.root,a.output)
