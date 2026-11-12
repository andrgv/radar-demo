"""Summarize current RX inspection and audit unchanged saved joint results."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True,help='Existing evaluate_joint_results output')
    args=parser.parse_args();regression=json.loads((args.output/'report.json').read_text())
    names=['avg16-placements-20261111.json','avg16-repeat50-20261111.json','avg16-operator-abab-20261111.json',
        'avg16-operator-empty-abab-20261111.json','avg16-motion-20261111.json','motion-aware-live-20261111.json',
        'reflector-live-20261111.json','foil-box-live-20261111.json','foil-box-repeat-20261111.json']
    cases=[case for name in names for case in json.loads((Path('configs')/name).read_text())['cases']]
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',windows=[
        dict(label='80 cm stationary (approximate)',state='hold',window_host_s=[2,73])]))
    grouped={}
    with gzip.open(args.output/'results.jsonl.gz','rt')as stream:
        for line in stream:
            row=json.loads(line);grouped.setdefault(row['recording'],[]).append(row)
    sessions=[]
    for case in cases:
        source=Path(case['recording']);rows=grouped[str(source)]
        saved=[json.loads(x)for x in(source/'readings.jsonl').read_text().splitlines()]
        arrivals=[json.loads(x)for x in(source/'arrivals.jsonl').read_text().splitlines()]
        assert [r['frame_sequence']for r in rows]==[r['frame_sequence']for r in saved]==[a['sequence']for a in arrivals]
        times=np.array([(a['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9 for a in arrivals])
        for row,old in zip(rows,saved):
            if 'results'in old and row.get('results')!=old['results']:raise ValueError('Existing joint results changed')
            diagnostic=row.get('receiver_diagnostics')
            if not row['valid']:
                if diagnostic is not None:raise ValueError('Rejected frame retains RX diagnostics')
                continue
            if diagnostic['frame_sequence']!=row['frame_sequence']:raise ValueError('Mismatched RX sequence')
            for g in diagnostic['groups']:
                if g['frame_sequence']!=row['frame_sequence']or not g['inspection_only']:raise ValueError('Stale or promoted group')
                candidates=[c for c in row['results']['candidates']if c.get('group_id')==g['group_id']and c.get('one_d_confirmed')]
                if len(candidates)!=1 or candidates[0]['support_bins']!=g['support_bins']:raise ValueError('Group support changed')
        windows=[]
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate')or w['state']=='motion':continue
            ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
            diagnostics=[rows[i].get('receiver_diagnostics',{}).get('nearest_confirmed_group')for i in ids]
            ds=[d for d in diagnostics if d is not None]
            def percentiles(key):
                values=[d[key]for d in ds if d[key]is not None]
                return np.percentile(values,[5,50,95]).tolist()if values else None
            windows.append(dict(label=w['label'],state=w['state'],frames=len(ids),diagnostic_frames=len(ds),
                numeric_baseline_frames=sum(rows[i].get('experimental_range_m')is not None for i in ids),
                flags=dict(Counter(f for d in ds for f in d['flags'])),no_flag_frames=sum(not d['flags']for d in ds),
                resolved_rx_counts=dict(Counter(d['resolved_rx']for d in ds)),
                residual_p05_p50_p95=percentiles('single_tone_residual_fraction'),spread_m_p05_p50_p95=percentiles('spread_m')))
        sessions.append(dict(recording=str(source),frames=len(rows),
            saved_joint_results_compared_frames=sum('results'in old for old in saved),
            existing_saved_joint_results_unchanged=True,windows=windows))
        print(str(source),[(w['label'],w['diagnostic_frames'],w['flags'])for w in windows],flush=True)
    paths=['tools/review_rx_diagnostics.py','radar_min/rx_diagnostics.py','radar_min/rd_gui.py']
    result=dict(sessions=sessions,regression_sha256=hashlib.sha256((args.output/'report.json').read_bytes()).hexdigest(),
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in paths},
        interpretation='Inspection flags, not new detector/accuracy performance. Unresolved RX omitted from spread, so read resolved_rx_counts too. A quiet diagnostic is not verified reflector identity; pooled-FFT residual is not the optimized phase fit.')
    (args.output/'receiver-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':main()
