"""Frozen cwm algorithms versus current GUI on common static GUI captures.
Run: python -m tools.compare_cwm_gui
"""
import hashlib, json, subprocess, sys, types
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Baseline, Detector
from tools.fit_range_signal import ToneFit, traces

REPO=Path('/Users/chekaylimeyer/radar-work/radar-demo')
REV='a6d7a089d9a44814d4258b3593a28b9daffbd8ae'
ROOT=Path('recordings/gui-20261101-144515-340260')
OUT=Path('evidence/cwm-gui-comparison-1')

def old_modules():
    package=types.ModuleType('frozen_cwm');package.__path__=[];sys.modules[package.__name__]=package
    modules={};hashes={}
    for name in ['config','processing','tracking','wavvy_range_filter']:
        source=subprocess.check_output(['git','-C',str(REPO),'show',f'{REV}:radar/{name}.py'])
        hashes[name]=hashlib.sha256(source).hexdigest()
        mod=types.ModuleType('frozen_cwm.'+name);mod.__package__='frozen_cwm';sys.modules[mod.__name__]=mod
        exec(compile(source,f'cwm@{REV}/radar/{name}.py','exec'),mod.__dict__);modules[name]=mod
    return modules,hashes

def summary(rows,truth,key):
    values=np.array([r[key] if r[key] is not None else np.nan for r in rows])*100
    valid=np.isfinite(values);v=values[valid]
    jumps=np.abs(np.diff(values)); jumps=jumps[np.isfinite(jumps)]
    result=dict(total=len(rows),reported=int(valid.sum()),availability=float(valid.mean()),median_cm=float(np.median(v)) if len(v) else None,
        min_cm=float(v.min()) if len(v) else None,max_cm=float(v.max()) if len(v) else None,
        adjacent_reported_pairs=len(jumps),jumps_over_20cm=int(np.sum(jumps>20)))
    if truth is None:result['false_positive_frames']=len(v)
    else:result.update(mae_cm=float(np.mean(abs(v-truth))) if len(v) else None,
        errors_over_10cm=int(np.sum(abs(v-truth)>10)),within_2cm=int(np.sum(abs(v-truth)<=2)),
        within_2cm_over_all_frames=float(np.sum(abs(v-truth)<=2)/len(rows)))
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=True);old,hashes=old_modules()
    b=Baseline.load(ROOT/'empty-001/baseline.json');c,empty,_=read_recording(ROOT/'empty-001',b.config);training=empty[:b.training_frames]
    oc=old['config'].Config(**{k:getattr(c,k) for k in ['profile_id','samples','chirps','sample_rate_hz','slope_hz_s','discard_chirps','frame_interval_s']})
    assert np.allclose(oc.ranges,np.arange(c.samples//2+1)*c.spacing_m)
    def magnitude(f):
        # Example tracker's 4x FFT padding, actual sampled sweep bandwidth S*N/Fs.
        adc=f.adc[c.discard_chirps:].transpose(0,2,1).reshape(-1,c.samples)
        return old['wavvy_range_filter'].range_profile_from_chirps(adc,c.slope_hz_s*c.samples/c.sample_rate_hz,nfft=4*c.samples)
    reference=np.mean([traces(f,c) for f in training],axis=0);fitter=ToneFit(c)
    report=dict(cwm_revision=REV,source_sha256=hashes,training_frames=len(training),nominal_spacing_m=c.spacing_m,recordings=[])
    with (OUT/'frames.jsonl').open('w') as log:
        for name,truth in [('live-003',None),('live-004',30),('live-005',50)]:
            path=ROOT/name;_,frames,_=read_recording(path,c)
            native=old['tracking'].ShortRangeAmplitudeTracker(oc);native.fit(training)
            current=Detector(b)
            stable={mode:old['wavvy_range_filter'].StableRangeTracker() for mode in ['stationary_default','empty_difference']}
            for tracker in stable.values():tracker.calibrate_empty_scene([magnitude(f)[0] for f in training])
            rows={k:[] for k in ['cwm_gui','current_gui',*stable]}
            for f in frames:
                track,_=native.update(f)
                accepted=track.state=='confirmed' and track.observed_range_m is not None
                entries={'cwm_gui':dict(raw=track.observed_range_m if accepted else None,smooth=track.range_m if accepted else None,status=track.state)}
                det=current.update(f);fit=fitter.fit(traces(f,c)-reference)
                entries['current_gui']=dict(raw=fit['range_m'] if det['target_detected'] else None,smooth=None,status=det['reason'])
                mag,ranges=magnitude(f)
                for mode,tracker in stable.items():
                    reading=tracker.update(mag,ranges,subtract_background=mode=='empty_difference')
                    entries[mode]=dict(raw=reading.raw_peak_m,smooth=reading.distance_m,status=reading.status)
                for pipeline,entry in entries.items():
                    rows[pipeline].append(entry);log.write(json.dumps(dict(recording=name,sequence=f.sequence,pipeline=pipeline,**entry))+'\n')
            saved=[json.loads(s) for s in (path/'readings.jsonl').read_text().splitlines()]
            for row,s in zip(rows['current_gui'],saved):
                expected=s['experimental_range_m'] if s['target_detected'] else None
                assert (row['raw'] is None)==(expected is None)
                if expected is not None:assert abs(row['raw']-expected)<1e-8
            entry=dict(recording=str(path),label_cm=truth,raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),pipelines={})
            for pipeline,data in rows.items():
                entry['pipelines'][pipeline]={'raw':summary(data,truth,'raw')}
                if pipeline!='current_gui':entry['pipelines'][pipeline]['smooth']=summary(data,truth,'smooth')
            report['recordings'].append(entry)
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    for record in report['recordings']:
        print('\nSCENE',record['label_cm'])
        for name,variants in record['pipelines'].items():
            for variant,result in variants.items():print(name,variant,json.dumps(result))

if __name__=='__main__':main()
