"""Audit and summarize an explicitly labeled live CA/OS comparison capture."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_os import OsConfig,OsCfarDetector,select_os_candidate
from radar_min.core import db
from tools.qualify_avg16_cfar import aligned_times,summarize


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text());source=Path(manifest['recording'])
    config,frames,_=read_recording(source)
    rows=[json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
    arrivals=[json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
    if [r['frame_sequence'] for r in rows]!=[f.sequence for f in frames]:
        raise ValueError('Saved reading/frame sequence mismatch')
    times=aligned_times(frames,arrivals)
    metadata=json.loads((source/'metadata.json').read_text())
    settings=CfarConfig(**metadata['detector']['one_d_cfar'])
    os_settings=OsConfig(**metadata['detector']['experimental_os']['os'])
    ca=CfarDetector(config,settings);os=OsCfarDetector(config,settings,os_settings)
    channels={'ca':[],'os':[],'selected':[]}
    for frame,row in zip(frames,rows):
        for detector,saved in [(ca,row['one_d']),(os,row['clutter_comparison']['os'])]:
            replay=detector.update(frame)
            for key in ('target_detected','range_bin','experimental_range_m','reason'):
                if replay[key]!=saved[key]:raise ValueError(f'Live/replay mismatch: {frame.sequence} {key}')
        selected=select_os_candidate(row['clutter_comparison']['os'],row['cfar_clusters'])
        if selected!=row['clutter_comparison']['selection']:raise ValueError('Selection mismatch')
        channels['ca'].append(row['one_d']);channels['os'].append(row['clutter_comparison']['os'])
        value=selected['experimental_range_m']
        channels['selected'].append(dict(target_detected=value is not None,experimental_range_m=value,
            reason=selected['reason'],range_bin=selected.get('rd_range_bin'),fine_range=None))
    windows=[]
    for w in manifest['windows']:
        ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
        p=np.array([rows[i]['one_d']['power'] for i in ids])
        t=np.array([rows[i]['one_d']['threshold_power'] for i in ids],dtype=float)
        windows.append(dict(**w,channels={name:summarize(values,frames,config,times,w) for name,values in channels.items()},
            median_power_db_bins1_9=np.median(db(p[:,1:10]),axis=0).tolist(),
            median_threshold_db_bins1_9=np.median(db(t[:,1:10]),axis=0).tolist(),
            median_margin_db_bins1_9=np.median(db(p[:,1:10]/t[:,1:10]),axis=0).tolist(),
            rd_confirmed_bin_counts=dict(Counter(str(track['measurement']['range_bin']) for i in ids
                for track in rows[i]['association']['tracks'] if track['measurement_valid']))))
    frozen=[r for r in rows if r['clock_sync']['state']=='frozen']
    report=dict(manifest=manifest,manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ('tools/review_live_clutter.py','tools/qualify_avg16_cfar.py','radar_min/cfar.py','radar_min/cfar_os.py','radar_min/cfar_range.py')},
        raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
        metadata=metadata,capture_summary=json.loads((source/'capture-summary.json').read_text()),
        frames=len(frames),host_span_s=float(times[-1]),
        clock_states=dict(Counter(r['clock_sync']['state'] for r in rows)),
        fit_diagnostics=frozen[0]['clock_sync']['fit_diagnostics'] if frozen else None,
        frozen_error_ms_p95_max=np.percentile([abs(r['clock_sync']['residual_s'])*1000 for r in frozen],[95,100]).tolist() if frozen else None,
        live_replay_ca_os_and_selection_match=True,windows=windows,
        interpretation='Live check of existing experimental settings; approximate scene durations and target placement. Conditional placement differences do not certify reflector identity. Shared CA/OS fine values do not demonstrate OS improvement or erase prior empty-control failures.')
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
    for mode,values in channels.items():
        y=[r['experimental_range_m']*100 if r['experimental_range_m'] is not None else np.nan for r in values]
        axes[0].plot(times,y,'.',ms=2,label=mode.upper())
    axes[0].set(ylabel='Experimental cm',ylim=(0,170),title='CA, OS and unique-support selection; coincident values overlap')
    axes[0].legend()
    power=np.array([r['one_d']['power'] for r in rows]);threshold=np.array([r['one_d']['threshold_power'] for r in rows],dtype=float)
    for k in (1,2,3):axes[1].plot(times,db(power[:,k]/threshold[:,k]),lw=.7,label=f'CA margin bin {k}')
    axes[1].axhline(0,color='black',ls='--');axes[1].legend(fontsize=8)
    axes[1].set(xlabel='Host seconds from first saved frame',ylabel='dB above/below CA threshold')
    for w in manifest['windows']:
        if w['trim_s']!=2:continue
        lo,hi=w['window_host_s'];target=w.get('nominal_target_m')
        for ax in axes:ax.axvspan(lo,hi,color='teal' if target else 'gray',alpha=.12)
        if target:axes[0].plot([lo,hi],[target*100]*2,'k--',lw=1)
    fig.savefig(args.output/'comparison.png',dpi=150);plt.close(fig)
    for w in windows:
        if w['trim_s']==2:
            print(w['label'],{k:(v['numeric_frames'],v['frames'],v['range_cm_p05_p50_p95']) for k,v in w['channels'].items()})


if __name__=='__main__':main()
