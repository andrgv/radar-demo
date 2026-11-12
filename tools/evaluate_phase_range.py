"""Frozen candidate-constrained phase-fit comparison on target and empty captures."""
import argparse
from collections import Counter
from dataclasses import asdict
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_os import OsCfarDetector
from radar_min.phase_range import CandidatePhaseRange
from tools.qualify_avg16_cfar import aligned_times
from tools.sweep_cfar import episodes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,nargs='+',help='Explicit scene manifests; default is the preserved development comparison')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    names=['avg16-placements-20261111.json','avg16-repeat50-20261111.json',
        'avg16-operator-abab-20261111.json','avg16-operator-empty-abab-20261111.json',
        'avg16-motion-20261111.json','motion-aware-live-20261111.json',
        'reflector-live-20261111.json','foil-box-live-20261111.json']
    manifest_paths=args.manifest or [Path('configs')/name for name in names]
    cases=[c for path in manifest_paths for c in json.loads(path.read_text())['cases']]
    if not args.manifest:
        cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',
            windows=[dict(label='80 cm stationary',state='hold',nominal_target_m=.8,trim_s=2,window_host_s=[2,73])]))
    settings=CfarConfig(1,4,4,2);sessions=[];plot_data=[]
    with gzip.open(args.output/'frames.jsonl.gz','wt') as stream:
        for case in cases:
            source=Path(case['recording']);config,frames,_=read_recording(source)
            original=[json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
            arrivals=[json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
            if [r['frame_sequence']for r in original]!=[f.sequence for f in frames]:raise ValueError('Saved sequence mismatch')
            times=aligned_times(frames,arrivals);ca=CfarDetector(config,settings);os=OsCfarDetector(config,settings)
            fitter=CandidatePhaseRange(config);results={'ca':[],'os':[]};elapsed=[]
            import time
            for frame,saved,t in zip(frames,original,times):
                readings={'ca':ca.update(frame),'os':os.update(frame)}
                baseline=saved.get('one_d',saved)
                for k in ('target_detected','range_bin','experimental_range_m','reason'):
                    if readings['ca'][k]!=baseline[k]:raise ValueError('CA baseline changed: '+k)
                output=dict(recording=str(source),frame_sequence=frame.sequence,host_time_s=float(t))
                # Reuse a current fit when CA/OS happen to select identical support.
                cache={}
                for mode,reading in readings.items():
                    fit=None
                    if reading['target_detected']:
                        bins=tuple(reading['selected_group_bins'])
                        if bins not in cache:
                            start=time.perf_counter();cache[bins]=fitter.fit(frame,list(bins))
                            elapsed.append((time.perf_counter()-start)*1000)
                        fit=cache[bins]
                    row=dict(presence=reading['target_detected'],support_bins=reading['selected_group_bins'],
                        peak_m=reading['experimental_range_m'],phase_m=fit['range_m'] if fit else None,
                        phase_fit=fit,reason=fit['reason'] if fit else reading['reason'])
                    results[mode].append(row);output[mode]=row
                stream.write(json.dumps(output,allow_nan=False)+'\n')
            windows=[]
            for w in case['windows']:
                if w.get('trim_s')==1 or w.get('operator_split_approximate'):continue
                ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
                variants={}
                for mode,rows in results.items():
                    target=w.get('nominal_target_m');channels={}
                    for key in ('peak_m','phase_m'):
                        selected=[rows[i][key] for i in ids if rows[i][key]is not None]
                        runs=episodes([rows[i][key]is not None for i in ids],[frames[i]for i in ids],config.frame_interval_s)
                        values=np.array(selected)
                        channels[key]=dict(numeric_frames=len(values),frames=len(ids),
                            cm_p05_p50_p95=np.percentile(values*100,[5,50,95]).tolist() if len(values) else None,
                            conditional_placement_mae_cm=float(np.mean(abs(values-target))*100) if target is not None and len(values) else None,
                            output_episodes=len(runs),longest_output_s=max((r['duration_s']for r in runs),default=0))
                    variants[mode]=dict(channels=channels,phase_reasons=dict(Counter(rows[i]['reason']for i in ids)))
                windows.append(dict(label=w['label'],state=w['state'],target_m=w.get('nominal_target_m'),
                    window_host_s=w['window_host_s'],variants=variants))
            sessions.append(dict(recording=str(source),frames=len(frames),raw_sha256=hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest(),
                config_fingerprint=config.fingerprint,ca_matches_saved=True,windows=windows,
                fit_processing_ms_p50_p95_max=np.percentile(elapsed,[50,95,100]).tolist() if elapsed else None))
            plot_data.append((case,times,results))
            print(str(source),{m:dict(Counter(r['reason']for r in rows))for m,rows in results.items()},flush=True)
    paths=['radar_min/phase_range.py','radar_min/cfar.py','radar_min/cfar_os.py','radar_min/core.py','tools/evaluate_phase_range.py']
    report=dict(estimator=fitter.metadata,detector_settings=asdict(settings),sessions=sessions,
        sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in paths},
        manifests={str(path):hashlib.sha256(path.read_bytes()).hexdigest()for path in manifest_paths},
        interpretation='Development comparison, no label fit or threshold sweep. Phase estimates require existing confirmed candidate support; rejected fits remain null. CA/OS settings unchanged. Conditional placement error does not establish physical identity or independent calibrated accuracy; read with coverage and empty outputs.')
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(plot_data),1,figsize=(13,2.6*len(plot_data)),layout='constrained')
    axes=np.atleast_1d(axes)
    for ax,(case,times,results) in zip(axes,plot_data):
        for key,label in [('peak_m','CA peak'),('phase_m','CA phase fit')]:
            y=[r[key]*100 if r[key]is not None else np.nan for r in results['ca']]
            ax.plot(times,y,'.',ms=2,label=label)
        for w in case['windows']:
            if w.get('trim_s')!=2 or w.get('operator_split_approximate'):continue
            lo,hi=w['window_host_s'];target=w.get('nominal_target_m')
            ax.axvspan(lo,hi,color='teal'if target else'gray',alpha=.1)
            if target:ax.plot([lo,hi],[target*100]*2,'k--',lw=.7)
        ax.set(title=case['recording'],ylabel='Experimental cm',ylim=(0,170));ax.legend(fontsize=7)
    axes[-1].set_xlabel('Host seconds from first saved frame')
    fig.savefig(args.output/'comparison.png',dpi=130);plt.close(fig)
    lines=['# Candidate-constrained phase-aware range comparison','',report['interpretation'],'',
        '| Recording / window | CA peak frames | CA phase frames | Phase median cm | Phase placement MAE cm* |',
        '|---|---:|---:|---:|---:|']
    for s in sessions:
        for w in s['windows']:
            a=w['variants']['ca']['channels']['peak_m'];b=w['variants']['ca']['channels']['phase_m'];q=b['cm_p05_p50_p95'];mae=b['conditional_placement_mae_cm']
            lines.append(f"| {s['recording']} / {w['label']} | {a['numeric_frames']}/{a['frames']} | {b['numeric_frames']}/{b['frames']} | {f'{q[1]:.1f}'if q else'—'} | {f'{mae:.1f}'if mae is not None else'—'} |")
    lines+=['','*Conditional placement differences are not identity-verified range error.',
        '', '[Full CA/OS metrics and hashes](report.json) · [CA timeline comparison](comparison.png) · [Frame decisions (gzip)](frames.jsonl.gz)']
    (args.output/'README.md').write_text('\n'.join(lines)+'\n')


if __name__=='__main__':main()
