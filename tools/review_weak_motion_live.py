"""Audit the optional live motion-link inspection against frozen cached readings."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline',type=Path,default=Path('evidence/weak-motion-20261111'))
    parser.add_argument('--live',type=Path,default=Path('evidence/weak-motion-live-20261111'))
    args=parser.parse_args();offline_report=json.loads((args.offline/'report.json').read_text())
    reference_path=Path(offline_report['input']);counts={}
    with gzip.open(reference_path,'rt')as reference,gzip.open(args.offline/'frames.jsonl.gz','rt')as expected,gzip.open(args.live/'results.jsonl.gz','rt')as actual:
        for a,b,c in zip(reference,expected,actual,strict=True):
            old=json.loads(a);e=json.loads(b);r=json.loads(c)
            keys=[(x['recording'],x['frame_sequence'])for x in(old,e,r)]
            if len(set(keys))!=1:raise ValueError('Frame/recording mismatch')
            for key in('results','association','motion_result'):
                if r[key]!=old[key]:raise ValueError('Existing output changed: '+key)
            if r['clutter_comparison']['weak_selection']!=old['clutter_comparison']['weak_selection']:
                raise ValueError('Weak selector changed')
            if r['weak_motion_result']!=e['weak_motion_result']:raise ValueError('Live/offline link differs')
            result=r['weak_motion_result']
            if result['primary_eligible']or result['predicted']or not result['inspection_only']:
                raise ValueError('Link promoted or predicted')
            count=counts.setdefault(r['recording'],Counter());count['frames']+=1
            point=result['experimental_range_m']is not None
            count['linked_inspection_frames']+=point
            count['new_when_baseline_and_motion_blank']+=point and e['baseline_m']is None and e['reference_motion_m']is None
    sources=['tools/review_weak_motion_live.py','radar_min/weak_motion.py','radar_min/rd_live.py','radar_min/rd_gui.py']
    inputs=[reference_path,args.offline/'report.json',args.offline/'frames.jsonl.gz',args.live/'report.json',args.live/'results.jsonl.gz']
    report=dict(sessions=[dict(recording=k,counts=dict(v))for k,v in counts.items()],
        original_results_association_motion_and_weak_selection_unchanged=True,framewise_link_parity=True,
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in sources},
        inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in inputs},
        interpretation='Live adapter replay, not new physical identity/accuracy or live serial timing qualification. Link remains inspection-only; no primary or motion policy is changed.')
    (args.live/'live-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(sum(v['frames']for v in counts.values()),'frames preserve prior outputs; motion-link parity matches')


if __name__=='__main__':main()
