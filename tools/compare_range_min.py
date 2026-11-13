"""Read original recordings without mutation; write comparison to stdout."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from radar_min.core import Config,Baseline,Detector
from radar_min.__main__ import read_recording
from radar.config import Config as LegacyConfig
from radar.tracking import ShortRangeAmplitudeTracker


def compare(root):
    root=Path(root);c,empty,_=read_recording(root/'empty');training=len(empty)//2
    b=Baseline.fit(empty[:training],c,dict(training_recording=str(root/'empty'),training_count=training))
    report=dict(training_frames=training,config_fingerprint=c.fingerprint,threshold_db=b.threshold_db.tolist(),
                policy='Fixed defaults; no holdout tuning. Track state reset for each stage.',stages={})
    for stage in ('empty','near','far'):
        if not (root/stage/'frames.grd').exists():continue
        _,frames,parser=read_recording(root/stage,c)
        if stage=='empty':frames=frames[training:]
        d=Detector(b);old=ShortRangeAmplitudeTracker(LegacyConfig.load(root/'config.json'));old.fit(empty[:training])
        results=[d.update(f) for f in frames]
        old_results=[old.update(f)[0] for f in frames]
        count=Counter(r['range_bin'] for r in results if r['target_detected'])
        old_count=Counter(r.bin_index for r in old_results if r.state=='confirmed')
        meta=json.loads((root/stage/'metadata.json').read_text())
        report['stages'][stage]=dict(frames=len(frames),measured_distance_m=meta.get('measured_distance_m'),
            raw_sha256=hashlib.sha256((root/stage/'frames.grd').read_bytes()).hexdigest(),
            cwm_detected=sum(old_count.values()),cwm_bins=dict(old_count),mvp_detected=sum(count.values()),mvp_bins=dict(count),
            mvp_detection_fraction=sum(count.values())/len(frames),
            mvp_reasons=dict(Counter(r['reason'] for r in results)),
            candidate_bins=dict(Counter(r['candidate_bin'] for r in results)),
            interpretation='false alarms' if stage=='empty' else 'spectral-change detections; object association unverified')
    # Separate acquisition sessions: stress test, not evidence of unchanged sensor pose.
    report['separate_session_empty_stress']={}
    for other in sorted(root.parent.glob('box_range_*')):
        if other==root or not (other/'empty/frames.grd').exists():continue
        _,held,_=read_recording(other/'empty',c)
        d=Detector(b);hits=sum(d.update(f)['target_detected'] for f in held)
        report['separate_session_empty_stress'][other.name]=dict(frames=len(held),false_alarms=hits,
            caveat='Separate capture; unchanged scene/pose not certified. Never used for fitting.')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('recordings');a=p.parse_args()
    print(json.dumps({r.name:compare(r) for r in sorted(Path(a.recordings).glob('box_range_*')) if (r/'empty/frames.grd').exists()},indent=2))
