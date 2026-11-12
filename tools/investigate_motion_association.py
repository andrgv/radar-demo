"""Compare native and sub-bin association, and inspect biased hold spectra."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.core import range_spectrum,db
from radar_min.rd_association import AssociationConfig
from radar_min.rd_live import LiveRangeDoppler
from tools.qualify_avg16_cfar import aligned_times


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    names=['avg16-repeat50-20261111.json','avg16-operator-abab-20261111.json',
           'avg16-operator-empty-abab-20261111.json','avg16-motion-20261111.json','motion-aware-live-20261111.json']
    cases=[c for name in names for c in json.loads((Path('configs')/name).read_text())['cases']]
    sessions=[];spectra=[]
    for case in cases:
        source=Path(case['recording']);config,frames,_=read_recording(source)
        saved=[json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
        arrivals=[json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
        if [r['frame_sequence'] for r in saved]!=[f.sequence for f in frames]:raise ValueError('Saved sequence mismatch')
        times=aligned_times(frames,arrivals)
        processors={name:LiveRangeDoppler(config,association_settings=AssociationConfig(range_metric=name)) for name in ('native','quadratic')}
        outputs={name:[] for name in processors}
        for frame,original in zip(frames,saved):
            readings={name:p.update(frame) for name,p in processors.items()}
            if not np.array_equal(processors['native'].snapshot.accepted,processors['quadratic'].snapshot.accepted):
                raise ValueError('CFAR mask changed')
            if 'association' in original and original['association']!=readings['native']['association']:
                raise ValueError('Native association differs from saved live')
            for name,r in readings.items():
                expected=original.get('one_d',original)
                for key in ('target_detected','range_bin','experimental_range_m','reason'):
                    if r['one_d'][key]!=expected[key]:raise ValueError('Baseline changed')
                outputs[name].append(dict(motion=r['motion_result'],ended=len(r['association']['ended_tracks'])))
        windows=[]
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
            methods={}
            for name,rows in outputs.items():
                points=[rows[i]['motion']['experimental_range_m']*100 for i in ids if rows[i]['motion']['experimental_range_m'] is not None]
                methods[name]=dict(numeric_frames=len(points),
                    median_cm=float(np.median(points)) if points else None,
                    reasons=dict(Counter(rows[i]['motion']['reason'] for i in ids)),
                    feature_ids=dict(Counter(str(rows[i]['motion']['track_id']) for i in ids)))
            windows.append(dict(label=w['label'],state=w['state'],frames=len(ids),methods=methods))
            if source.name=='live-002' and w['state']=='hold':
                # Fixed temporal subsampling, no strongest-frame selection.
                profiles=[np.mean(abs(range_spectrum(frames[i],config,nfft=4096))**2,axis=0) for i in ids[::5]]
                median=np.median(profiles,axis=0)
                axis=np.arange(len(median))*config.spacing_m*config.samples/4096
                use=np.flatnonzero((axis>=.15)&(axis<=1.7))
                per_rx=[float(axis[use[np.argmax(median[use,rx])]]) for rx in range(3)]
                dominant=float(axis[use[np.argmax(median[use].mean(axis=1))]])
                spectra.append(dict(label=w['label'],frames_used=len(profiles),raw_near_peak_m=dominant,
                    per_rx_raw_near_peak_m=per_rx,coordinates_m=axis[use].tolist(),power_db=db(median[use].mean(axis=1)).tolist()))
        sessions.append(dict(recording=str(source),raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
            frames=len(frames),masks_unchanged=True,baseline_matches_saved=True,windows=windows))
        print(str(source),[(w['label'],w['methods']['native']['numeric_frames'],w['methods']['quadratic']['numeric_frames']) for w in windows],flush=True)
    report=dict(sessions=sessions,hold_spectra=spectra,
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ('radar_min/rd_association.py','radar_min/joint_results.py','radar_min/motion_range.py','tools/investigate_motion_association.py')},
        interpretation='Development comparison; native gates/ambiguity gap/confirmation unchanged. Sub-bin coordinates affect cost only, not published distance. Hold spectra are raw median power in a declared near-range diagnostic band, not identified-object truth. No distance offset or label fit.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    for s in spectra:ax.plot(np.array(s['coordinates_m'])*100,s['power_db'],label=s['label'])
    ax.set(xlabel='Nominal range (cm)',ylabel='Median raw dB ADC units²',title='Biased holds: raw near-range spectra before association or display policy')
    ax.legend(fontsize=8);fig.savefig(args.output/'hold-spectra.png',dpi=150);plt.close(fig)


if __name__=='__main__':main()
