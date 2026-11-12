"""Check optional live weak-candidate results against the independent offline review."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',type=Path,default=Path('evidence/weak-candidates-20261111'))
    parser.add_argument('--live',type=Path,default=Path('evidence/weak-candidates-live-20261111'))
    args=parser.parse_args();counts={}
    with gzip.open(args.offline/'frames.jsonl.gz','rt')as offline,gzip.open(args.live/'results.jsonl.gz','rt')as live:
        for a,b in zip(offline,live,strict=True):
            expected=json.loads(a);actual=json.loads(b)
            if (expected['recording'],expected['frame_sequence'])!=(actual['recording'],actual['frame_sequence']):
                raise ValueError('Live/offline sequence mismatch')
            weak=actual.get('clutter_comparison',{}).get('weak_selection')
            if weak!=expected['weak_selection']:raise ValueError('Live/offline weak selection changed')
            primary=actual.get('results',{}).get('primary')
            value=primary['experimental_range_m']if primary else None
            if value!=expected['baseline_m']:raise ValueError('Weak inspection changed primary')
            c=counts.setdefault(actual['recording'],Counter());c['frames']+=1
            c['weak_frames']+=weak['experimental_range_m']is not None
            c['recovery_inspection_frames']+=value is None and weak['experimental_range_m']is not None
            c['weak_model_withheld_frames']+=weak['experimental_range_m']is not None and not weak['phase_model_accepted']
            if not weak['inspection_only']or weak['primary_eligible']:raise ValueError('Weak candidate promoted')
    files=[args.offline/'report.json',args.offline/'frames.jsonl.gz',args.live/'report.json',args.live/'results.jsonl.gz']
    sources=['tools/review_weak_live.py','radar_min/rd_live.py','radar_min/rd_gui.py','radar_min/weak_candidate.py','radar_min/__main__.py']
    report=dict(sessions=[dict(recording=k,counts=dict(v))for k,v in counts.items()],
        framewise_live_offline_selection_equal=True,primary_unchanged=True,
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in files},
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in sources},
        interpretation='Live processing adapter tested on saved frames, not a new serial/hardware timing qualification. Inspection does not identify the labeled target or accept a rejected range model. Motion policy and RD masks/association are independently checked by evaluate_joint_results.')
    (args.live/'live-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(sum(v['frames']for v in counts.values()),'live/offline selections match; primary unchanged')


if __name__=='__main__':main()
