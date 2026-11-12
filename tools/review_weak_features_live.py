"""Audit separate weak feature confirmation without changing existing outputs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',type=Path,default=Path('evidence/weak-features-20261111'))
    parser.add_argument('--live',type=Path,default=Path('evidence/weak-features-live-20261111'))
    args=parser.parse_args();offline=json.loads((args.offline/'report.json').read_text())
    reference=Path(offline['input']);counts={}
    with gzip.open(reference,'rt')as old,gzip.open(args.offline/'frames.jsonl.gz','rt')as expected,gzip.open(args.live/'results.jsonl.gz','rt')as actual:
        for a,b,c in zip(old,expected,actual,strict=True):
            before=json.loads(a);e=json.loads(b);r=json.loads(c)
            if len({(v['recording'],v['frame_sequence'])for v in(before,e,r)})!=1:raise ValueError('Sequence mismatch')
            for key in('results','association','motion_result','weak_motion_result','receiver_diagnostics'):
                if r[key]!=before[key]:raise ValueError('Existing output changed: '+key)
            if r['clutter_comparison']['weak_selection']!=before['clutter_comparison']['weak_selection']:
                raise ValueError('Weak selection changed')
            feature=r['weak_feature_result']
            if feature!=e['weak_feature_result']:raise ValueError('Offline/live weak feature mismatch')
            if feature['primary_eligible']or feature['predicted']or not feature['inspection_only']:
                raise ValueError('Weak feature promoted or predicted')
            point=feature['experimental_range_m']is not None
            if point and(not feature['confirmed']or feature['measurement_sequence']!=r['frame_sequence']):
                raise ValueError('Unconfirmed or held feature range')
            n=counts.setdefault(r['recording'],Counter());n['frames']+=1;n['confirmed_weak_frames']+=point
            n['confirmed_with_blank_baseline']+=point and e['baseline_m']is None
            n['confirmed_without_original_rd_track']+=point and feature['strong_rd_track_id']is None
    paths=[reference,args.offline/'report.json',args.offline/'frames.jsonl.gz',args.live/'report.json',args.live/'results.jsonl.gz']
    sources=['tools/review_weak_features_live.py','radar_min/weak_features.py','radar_min/rd_live.py','radar_min/rd_gui.py']
    report=dict(sessions=[dict(recording=k,counts=dict(v))for k,v in counts.items()],
        previous_primary_association_motion_rx_and_weak_selection_unchanged=True,framewise_feature_parity=True,
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in sources},
        interpretation='Live adapter on saved frames, not live serial timing or independent object/distance acceptance. Confirmed weak scene features remain inspection-only and preserve the known wrong-range case.')
    (args.live/'live-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(sum(v['frames']for v in counts.values()),'frames preserve prior outputs and match independent weak confirmation')


if __name__=='__main__':main()
