"""Export joint results and audit unchanged 1D/RD behavior on regression captures."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig, CfarDetector
from radar_min.cfar_2d import CaCfar2D,Cfar2DConfig
from radar_min.range_doppler import RangeDoppler
from radar_min.rd_association import CandidateAssociator,AssociationConfig
from radar_min.rd_live import LiveRangeDoppler
from radar_min.motion_range import MotionRangePolicy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--experimental-weak',action='store_true',help='Audit the optional weak-candidate branch beside the unchanged primary')
    parser.add_argument('--recordings', nargs='+', type=Path, default=[
        Path(f'recordings/gui-20261111-093723-246315/live-{i:03d}') for i in range(3,7)])
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    sessions = []
    with gzip.open(args.output/'results.jsonl.gz','wt') as stream:
        for path in args.recordings:
            config,frames,_ = read_recording(path)
            saved_metadata=json.loads((path/'metadata.json').read_text()).get('detector') or {}
            settings = CfarConfig(**saved_metadata.get('one_d_cfar',
                saved_metadata.get('cfar',{}) if saved_metadata.get('algorithm')=='range-ca-cfar-v2' else dict(guard_cells=1,training_cells=4,min_training_cells=4,factor=2)))
            rd_settings=Cfar2DConfig(**(saved_metadata.get('cfar',{}) if 'guard_range' in saved_metadata.get('cfar',{}) else {}))
            association_settings=AssociationConfig(**saved_metadata.get('association',{}))
            processor = LiveRangeDoppler(config,rd_settings,association_settings,one_d_settings=settings,experimental_weak=args.experimental_weak)
            baseline = CfarDetector(config, settings)
            rd = RangeDoppler(config)
            cfar = CaCfar2D((rd.count,config.samples//2+1),rd_settings)
            association = CandidateAssociator(config,association_settings,rd_settings.doppler_edge)
            motion_reference = MotionRangePolicy()
            saved_motion_reference=MotionRangePolicy(**saved_metadata.get('motion_policy_settings',
                dict(motion_confirmation_frames=2,stationary_support_required=False)))
            saved = [json.loads(x) for x in (path/'readings.jsonl').read_text().splitlines()]
            if [r['frame_sequence'] for r in saved] != [f.sequence for f in frames]:
                raise ValueError('Saved/frame sequence mismatch')
            counts = Counter(); reasons = Counter();elapsed=[]
            for frame,original in zip(frames,saved):
                reading = processor.update(frame)
                expected = baseline.update(frame)
                saved_baseline = original.get('one_d', original)
                for key in ('target_detected','range_bin','experimental_range_m','reason'):
                    if reading['one_d'][key]!=expected[key] or expected[key]!=saved_baseline[key]:
                        raise ValueError(f'1D baseline parity failed: {path} {frame.sequence} {key}')
                full,_,info = rd.update(frame)
                if info['valid']:
                    _,threshold,accepted,clusters = cfar.detect(full)
                    reference = association.update(frame,full,threshold,accepted,clusters)
                    if not np.array_equal(processor.snapshot.accepted,accepted):
                        raise ValueError('RD CFAR mask changed')
                else:reference = association.update(frame,None,None,None,[],valid=False,reason=info['reason'])
                if reading['association']!=reference:
                    raise ValueError('RD association changed')
                result=reading.get('results',{})
                primary=result.get('primary')
                if (primary['experimental_range_m'] if primary else None)!=expected['experimental_range_m']:
                    raise ValueError('Primary differs from frozen baseline')
                if 'results'in original and result!=original['results']:
                    raise ValueError('Previously saved joint results changed')
                counts['frames']+=1
                counts['primary_frames']+=bool(primary)
                weak=reading.get('clutter_comparison',{}).get('weak_selection')
                if weak:
                    counts['weak_candidate_frames']+=weak['experimental_range_m']is not None
                    counts['weak_candidate_rejected_model_frames']+=weak['experimental_range_m']is not None and not weak['phase_model_accepted']
                    if weak['primary_eligible']:raise ValueError('Weak candidate promoted')
                motion=reading['motion_result']
                if motion_reference.update(reading)!=motion:
                    raise ValueError('Motion policy replay mismatch')
                saved_policy=saved_motion_reference.update(reading)
                if 'motion_result' in original:
                    if original['motion_result']!=saved_policy:raise ValueError('Recorded motion policy does not reproduce')
                    counts['motion_policy_changed_frames']+=motion!=saved_policy
                counts['motion_policy_range_frames']+=motion['experimental_range_m'] is not None
                counts['rd_motion_range_frames']+=motion['source']=='RD motion'
                counts['rd_stopped_range_frames']+=motion['source']=='RD stopped'
                if motion['predicted']:raise ValueError('Motion policy published a prediction')
                rows=result.get('candidates',[])
                counts['rd_only_feature_frames']+=any(r['sources']==['RD'] for r in rows)
                counts['rd_only_fine_frames']+=any(r['sources']==['RD'] and r.get('rd_range_m') is not None for r in rows)
                counts['merged_source_frames']+=any(r['sources']==['1D','RD'] for r in rows)
                counts['rd_fine_frames']+=any(r.get('rd_range_m') is not None for r in rows)
                counts['range_disagreement_frames']+=any(r.get('range_agreement')=='disagree' for r in rows)
                for row in rows:
                    fine=row.get('rd_fine_range')
                    if fine:reasons[fine['reason']]+=1
                    if row['primary_eligible'] and '1D' not in row['sources']:
                        raise ValueError('RD-only feature promoted')
                elapsed.append(reading['processing_ms'])
                stream.write(json.dumps(dict(recording=str(path),**reading),allow_nan=False)+'\n')
            sessions.append(dict(recording=str(path),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
                config_fingerprint=config.fingerprint,settings=processor.metadata,
                counts=dict(counts),rd_fine_reasons=dict(reasons),
                processing_ms_p50_p95_max=np.percentile(elapsed,[50,95,100]).tolist(),
                baseline_matches_saved_and_independent=True,rd_masks_and_association_unchanged=True))
            print(str(path),dict(counts),flush=True)
    report=dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),sessions=sessions,
        interpretation='Development regression; no independent physical accuracy acceptance. Every primary exactly reproduces the frozen 1D distance, every RD mask and association matches the standalone algorithms. RD-only refinements are inspection values, not target identities or automatic primary measurements. Saved host freshness is not re-certified.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
