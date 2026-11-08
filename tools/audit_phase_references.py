"""Check saved, non-door phase references without installing a calibration.

Distances below are filename/conversation hypotheses. Missing surveyed pose
metadata is not filled in from an algorithm's estimated direction.
"""
import argparse
import json
from pathlib import Path
import numpy as np
from radar.calibration import calibrate_channels
from radar.config import Config
from radar.processing import range_fft
from radar.protocol import Parser
from radar.storage import replay


def audit(root,output):
    root,output=Path(root),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    config=Config.load(Path(__file__).resolve().parents[1]/'configs/range-source-derived.json')
    references=[]
    for name,distance in [('plate_0_6m',.6),('plate_1_3m',1.3),('plate_2m',2.),('phase_center',1.3)]:
        path=root/name;metadata=json.loads((path/'metadata.json').read_text())
        parser=Parser();frames=list(replay(path,parser))
        if parser.bad_crc or parser.bad_headers or parser.gaps or parser.restarts or len(frames)<20:
            raise ValueError(f'{name}: raw reference quality failed')
        if any(f.profile_id!=config.profile_id or f.adc.shape!=(config.chirps,config.samples,3) for f in frames):
            raise ValueError(f'{name}: reference/config mismatch')
        count=min(100,len(frames));b=int(np.argmin(abs(config.ranges-distance)))
        spectrum=np.concatenate([range_fft(f.adc,config) for f in frames[:count]])[:,b]
        relative=np.mean(spectrum*spectrum[:,:1].conj(),axis=0)
        row=dict(recording=name,assumed_range_m=distance,assumed_range_source='Filename/conversation, not populated survey metadata',
                 frames=len(frames),frames_used=count,nominal_bin=b,
                 relative_phase_deg=np.degrees(np.angle(relative)).tolist(),
                 metadata=metadata,profile_id=config.profile_id,calibration_promoted=False)
        try:
            calibrate_channels(frames[:count],config,distance)
            row['signal_quality_gate']='passed'
        except ValueError as error:
            row['signal_quality_gate']='refused';row['reason']=str(error)
        row['independent_surveyed_pose_available']=bool(metadata.get('surveyed_range_m') is not None
            and metadata.get('surveyed_azimuth_deg') is not None and metadata.get('surveyed_elevation_deg') is not None)
        references.append(row)
    result=dict(references=references,
        conclusion='No validated independent angular calibration is installed. Signal isolation alone does not '
                   'identify a centered target or verify cross-profile phase transfer. Pose metadata and '
                   'independent held-out positions are missing in these candidate reference recordings.')
    (output/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root');p.add_argument('output');a=p.parse_args();audit(a.root,a.output)
