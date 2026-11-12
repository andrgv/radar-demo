"""Check live-adapter parity with both association replays without serial access."""
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.storage import replay
from radar_min.core import Config
from radar_min.rd_live import LiveRangeDoppler, feature_table_rows

ROOT=Path(__file__).resolve().parents[1]
DATASETS=[('first','recordings/avg16-motion-01'),
          ('followup','recordings/gui-20261110-221227-169414/live-001')]


def main():
    output=ROOT/'evidence/rd-live-gui-20261110';output.mkdir(parents=True,exist_ok=True)
    report=dict(hardware_serial_access=False,clock_backlog_timeout_gates='Covered by simulated serial tests; original replay host timing is not applied in parity check',
        source_sha256={name:hashlib.sha256((ROOT/'radar_min'/name).read_bytes()).hexdigest()
                       for name in('rd_live.py','rd_gui.py','__main__.py','rd_association.py')},datasets={})
    for name,source_path in DATASETS:
        source=ROOT/source_path;exported=ROOT/'evidence/rd-association-20261110'/name
        baseline=[json.loads(x)for x in(exported/'tracks.jsonl').read_text().splitlines()]
        frames=list(replay(source));config=Config.load(source/'config.json');processor=LiveRangeDoppler(config)
        times=[]
        with np.load(exported/'maps.npz')as maps,np.load(exported/'cfar.npz')as cfar:
            full_power=maps['full_power'];threshold_power=cfar['threshold_power'];accepted=cfar['accepted']
            for index,(frame,expected)in enumerate(zip(frames,baseline,strict=True)):
                reading=processor.update(frame)
                assert reading['association']==expected
                assert reading['valid']
                np.testing.assert_array_equal(processor.snapshot.full_power,full_power[index])
                np.testing.assert_allclose(processor.snapshot.threshold_power,threshold_power[index],rtol=0,atol=0,equal_nan=True)
                np.testing.assert_array_equal(processor.snapshot.accepted,accepted[index])
                assert processor.snapshot.sequence==frame.sequence
                assert not processor.snapshot.full_power.flags.writeable
                json.dumps(reading,allow_nan=False)
                rows=feature_table_rows(reading,config)
                for track,(_,values)in zip(expected['tracks'],rows,strict=True):
                    assert(values[2]!='—')==track['measurement_valid']
                    if track['measurement_valid']:assert track['last_peak_sequence']==frame.sequence
                times.append(reading['processing_ms'])
        item=dict(recording=source_path,frames=len(frames),association_reports_equal=True,
            full_power_threshold_and_accepted_arrays_equal=True,table_freshness_invariant_violations=0,
            processing_ms_p05_p50_p95_max=np.percentile(times,[5,50,95,100]).tolist(),metadata=processor.metadata)
        if name=='followup':
            arrivals=[json.loads(x)for x in(source/'arrivals.jsonl').read_text().splitlines()]
            t=(np.array([x['host_unix_ns']for x in arrivals])-arrivals[0]['host_unix_ns'])/1e9
            measured=[i for i,row in enumerate(baseline)if 48.78<=t[i]<=50.63 and any(
                x['measurement_valid']and x['measurement']['doppler_bin']!=8 and 1<=x['measurement']['range_bin']<=4 for x in row['tracks'])]
            i=min(measured,key=lambda i:abs(t[i]-(48.78+50.63)/2))
            item['measured_snapshot_frame']=i;item['measured_snapshot_host_s']=float(t[i])
        report['datasets'][name]=item
    report['review_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output/'summary.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({name:{k:r[k]for k in('frames','association_reports_equal','processing_ms_p05_p50_p95_max')}
                      for name,r in report['datasets'].items()},indent=2))
    print('Measured snapshot frame:',report['datasets']['followup']['measured_snapshot_frame'])


if __name__=='__main__':main()
