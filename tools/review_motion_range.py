"""Explain motion-frame dropouts and audit measured-only RD selection on replays."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.motion_range import MotionRangePolicy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('evidence/motion-aware-joint-20261111'))
    parser.add_argument('--manifest',type=Path,nargs='+',help='Explicit labeled manifests; default is the four development controls')
    parser.add_argument('--hold-spectra',action='store_true',help='Inspect raw median near-band spectra every fifth hold frame')
    args=parser.parse_args()
    regression=json.loads((args.output/'report.json').read_text())
    policy_settings={s['recording']:s['settings'].get('motion_policy_settings',
        dict(motion_confirmation_frames=2,stationary_support_required=False)) for s in regression['sessions']}
    grouped={}
    with gzip.open(args.output/'results.jsonl.gz','rt') as stream:
        for line in stream:
            row=json.loads(line);grouped.setdefault(row['recording'],[]).append(row)
    manifests=['avg16-repeat50-20261111.json','avg16-operator-abab-20261111.json',
               'avg16-operator-empty-abab-20261111.json','avg16-motion-20261111.json']
    manifest_paths=args.manifest or [Path('configs')/name for name in manifests]
    cases=[case for path in manifest_paths for case in json.loads(path.read_text())['cases']]
    sessions=[];plot_data=[]
    for case in cases:
        rows=grouped[case['recording']]
        arrivals=[json.loads(x) for x in (Path(case['recording'])/'arrivals.jsonl').read_text().splitlines()]
        if [r['frame_sequence'] for r in rows]!=[a['sequence'] for a in arrivals]:raise ValueError('Arrival mismatch')
        times=np.array([(a['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9 for a in arrivals])
        policy=MotionRangePolicy(**policy_settings[case['recording']])
        for r in rows:
            if policy.update(r)!=r['motion_result']:raise ValueError('Motion selection does not reproduce')
        original=[json.loads(x) for x in (Path(case['recording'])/'readings.jsonl').read_text().splitlines()]
        windows=[]
        if args.hold_spectra:
            from radar_min.__main__ import read_recording
            from radar_min.core import range_spectrum,db
            config,frames,_=read_recording(case['recording'])
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
            selected=[rows[i]['motion_result'] for i in ids]
            values=[r['experimental_range_m']*100 for r in selected if r['experimental_range_m'] is not None]
            baseline_values=[rows[i]['one_d']['experimental_range_m']*100 for i in ids if rows[i]['one_d']['experimental_range_m'] is not None]
            item=dict(label=w['label'],state=w['state'],frames=len(ids),window_host_s=w['window_host_s'],
                baseline_frames=sum(rows[i]['one_d']['experimental_range_m'] is not None for i in ids),
                motion_policy_frames=len(values),
                motion_policy_cm_p05_p50_p95=np.percentile(values,[5,50,95]).tolist() if values else None,
                baseline_cm_p05_p50_p95=np.percentile(baseline_values,[5,50,95]).tolist() if baseline_values else None,
                selected_feature_counts=dict(Counter(str(r['track_id']) for r in selected)),
                source_counts=dict(Counter(str(r['source']) for r in selected)),
                selection_reasons=dict(Counter(r['reason'] for r in selected)),
                baseline_reasons=dict(Counter(rows[i]['one_d']['reason'] for i in ids)))
            if all('motion_result' in original[i] for i in ids):
                recorded=[original[i]['motion_result'] for i in ids]
                v=[r['experimental_range_m']*100 for r in recorded if r['experimental_range_m'] is not None]
                item.update(recorded_motion_frames=len(v),
                    recorded_motion_cm_p05_p50_p95=np.percentile(v,[5,50,95]).tolist() if v else None)
            if w['state']=='motion':
                sign=w['expected_phase_sign']
                def matches(p):return 1<=p['range_bin']<=4 and p['cycles_per_saved_block']*sign>0
                item.update(expected_phase_sign=sign,
                    raw_expected_sign_peak_frames=sum(any(matches(p) for c in rows[i]['cfar_clusters'] for p in c['local_maxima']) for i in ids),
                    confirmed_expected_sign_frames=sum(any(t['measurement_valid'] and matches(t['measurement']) for t in rows[i]['association']['tracks']) for i in ids),
                    refined_expected_sign_frames=sum(any(c.get('rd_confirmed') and c.get('rd_range_m') is not None and matches(c) for c in rows[i]['results']['candidates']) for i in ids))
            elif args.hold_spectra and w['state']=='hold':
                profiles=[np.mean(abs(range_spectrum(frames[i],config,nfft=4096))**2,axis=0) for i in ids[::5]]
                median=np.median(profiles,axis=0);axis=np.arange(len(median))*config.spacing_m*config.samples/4096
                band=np.flatnonzero((axis>=.15)&(axis<=1.7))
                p=np.array([rows[i]['one_d']['power'] for i in ids]);th=np.array([rows[i]['one_d']['threshold_power'] for i in ids],dtype=float)
                item['raw_spectrum']=dict(sample_stride=5,frames_used=len(profiles),diagnostic_band_m=[.15,1.7],
                    raw_near_peak_m=float(axis[band[np.argmax(median[band].mean(axis=1))]]),
                    per_rx_near_peak_m=[float(axis[band[np.argmax(median[band,rx])]]) for rx in range(3)],
                    median_ca_margin_db_bins1_6=np.median(db(p[:,1:7]/th[:,1:7]),axis=0).tolist())
            windows.append(item)
        frozen=[r for r in original if r.get('clock_sync',{}).get('state')=='frozen']
        sessions.append(dict(recording=case['recording'],windows=windows,
            capture_summary=json.loads((Path(case['recording'])/'capture-summary.json').read_text()),
            saved_clock_states=dict(Counter(r.get('clock_sync',{}).get('state') for r in original)),
            fit_diagnostics=frozen[0]['clock_sync'].get('fit_diagnostics') if frozen else None,
            frozen_error_ms_p95_max=np.percentile([abs(r['clock_sync']['residual_s'])*1000 for r in frozen],[95,100]).tolist() if frozen else None))
        plot_data.append((case,rows,times,original))
    report=dict(source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
            ('tools/review_motion_range.py','radar_min/motion_range.py','radar_min/joint_results.py')},
        regression_report_sha256=hashlib.sha256((args.output/'report.json').read_bytes()).hexdigest(),
        manifests={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in manifest_paths},
        sessions=sessions,
            interpretation='Current-frame numeric coverage, not verified target-identity accuracy. Recorded motion output and current-policy replay can differ; policy settings are in the regression metadata. Manual/operator motion can seed episodes. No predictions or smoothing. Frozen baseline retained.')
    (args.output/'motion-review.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plot_data),1,figsize=(13,3*len(plot_data)),layout='constrained')
    for ax,(case,rows,times,original) in zip(np.atleast_1d(axes),plot_data):
        if all('motion_result' in r for r in original):
            recorded=[r['motion_result']['experimental_range_m']*100 if r['motion_result']['experimental_range_m'] is not None else np.nan for r in original]
            ax.plot(times,recorded,'--',color='gray',lw=1,label='Recorded motion-aware')
        for key,label in [('one_d','Frozen 1D'),('motion_result','Experimental motion-aware')]:
            y=[r[key]['experimental_range_m']*100 if r[key]['experimental_range_m'] is not None else np.nan for r in rows]
            ax.plot(times,y,'.-',ms=2,lw=.5,label=label)
        for w in case['windows']:
            if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
            left,right=w['window_host_s']
            if w['state']=='motion':ax.axvspan(left,right,color='orange',alpha=.2)
            elif w['state']=='target_absent':ax.axvspan(left,right,color='gray',alpha=.15)
            elif w.get('nominal_target_m'):ax.plot([left,right],[w['nominal_target_m']*100]*2,'k--',lw=1)
        ax.set(title=case['recording'],ylabel='Experimental cm',ylim=(0,180));ax.legend(fontsize=8)
    np.atleast_1d(axes)[-1].set_xlabel('Host seconds from first saved frame; gray = target absent, orange = motion')
    fig.savefig(args.output/'motion-comparison.png',dpi=150);plt.close(fig)
    for s in sessions:
        print(s['recording'])
        for w in s['windows']:
            print(w['label'],w['frames'],w['baseline_frames'],w['motion_policy_frames'],w['selection_reasons'])


if __name__=='__main__':main()
