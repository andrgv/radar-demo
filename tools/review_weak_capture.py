"""Audit a newly labeled weak-mode capture without modifying detector settings."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.core import db,range_spectrum
from tools.qualify_avg16_cfar import aligned_times
from tools.sweep_cfar import episodes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Existing evaluate_joint_results output for the recording')
    args=parser.parse_args();manifest=json.loads(args.manifest.read_text());case=manifest['cases'][0]
    path=Path(case['recording']);c,frames,_=read_recording(path)
    saved=[json.loads(x)for x in(path/'readings.jsonl').read_text().splitlines()]
    arrivals=[json.loads(x)for x in(path/'arrivals.jsonl').read_text().splitlines()]
    times=aligned_times(frames,arrivals)
    with gzip.open(args.output/'results.jsonl.gz','rt')as stream:replayed=[json.loads(x)for x in stream]
    if [r['frame_sequence']for r in saved]!=[f.sequence for f in frames]:raise ValueError('Saved sequence mismatch')
    if [r['frame_sequence']for r in replayed]!=[f.sequence for f in frames]:raise ValueError('Replay sequence mismatch')
    for old,new in zip(saved,replayed):
        for key in('results','association','motion_result','receiver_diagnostics','weak_motion_result','weak_feature_result'):
            if old.get(key)!=new.get(key):raise ValueError('Saved/live replay mismatch: '+key)
        for key in('selection','weak_selection','weak_phase_fit'):
            if old['clutter_comparison'][key]!=new['clutter_comparison'][key]:raise ValueError('OS/weak parity mismatch: '+key)
        for key in('target_detected','range_bin','experimental_range_m','reason'):
            if old['clutter_comparison']['os'][key]!=new['clutter_comparison']['os'][key]:raise ValueError('OS detector changed: '+key)
    windows=[];spectra=[]
    for w in case['windows']:
        ids=np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))
        if not len(ids):raise ValueError('Scene window has no saved frames: '+w['label'])
        channels={}
        methods={'baseline':lambda r:r['one_d'], 'os':lambda r:r['clutter_comparison']['os'],
            'os_rd':lambda r:r['clutter_comparison']['selection'],
            'weak':lambda r:r['clutter_comparison']['weak_selection'],
            'confirmed_weak':lambda r:r['weak_feature_result'],
            'motion':lambda r:r['motion_result']}
        for name,method in methods.items():
            rows=[method(saved[i])for i in ids];values=np.array([r['experimental_range_m']*100 for r in rows if r.get('experimental_range_m')is not None])
            fs=[SimpleNamespace(sequence=frames[i].sequence,timestamp_us=frames[i].timestamp_us)for i in ids]
            runs=episodes([r.get('experimental_range_m')is not None for r in rows],fs,c.frame_interval_s)
            channels[name]=dict(numeric_frames=len(values),frames=len(ids),
                presence_frames=sum(r.get('target_detected',False)for r in rows)if name in('baseline','os')else None,
                cm_p05_p50_p95=np.percentile(values,[5,50,95]).tolist()if len(values)else None,
                episodes=len(runs),longest_s=max((x['duration_s']for x in runs),default=0),
                reasons=dict(Counter(r['reason']for r in rows)))
        power=np.array([saved[i]['one_d']['power']for i in ids]);threshold=np.array([saved[i]['one_d']['threshold_power']for i in ids],float)
        item=dict(**w,channels=channels,
            ca_fine_reasons=dict(Counter(saved[i]['one_d']['fine_range']['reason']for i in ids if saved[i]['one_d']['fine_range'])),
            median_power_db_bins1_9=np.median(db(power[:,1:10]),axis=0).tolist(),
            median_ca_margin_db_bins1_9=np.median(db(power[:,1:10]/threshold[:,1:10]),axis=0).tolist(),
            current_rd_measured_bins=dict(Counter(str(t['measurement']['range_bin'])for i in ids for t in saved[i]['association']['tracks']if t['measurement_valid'])))
        if w['trim_s']==2:
            profiles=[np.mean(abs(range_spectrum(frames[i],c,nfft=4096))**2,axis=0)for i in ids[::5]]
            median=np.median(profiles,axis=0);axis=np.arange(len(median))*c.samples*c.spacing_m/4096
            spectra.append((w,axis,median))
            if w['state']=='hold':
                counts=[];locations=[]
                for i in ids[::5]:
                    baseline=saved[i]['one_d'];bins=baseline['selected_group_bins']
                    if not bins:continue
                    p=np.mean(abs(range_spectrum(frames[i],c,nfft=4096))**2,axis=(0,2))
                    support=np.flatnonzero((axis>=(min(bins)-.5)*c.spacing_m)&(axis<=(max(bins)+.5)*c.spacing_m))
                    k=support[np.argmax(p[support])]
                    peaks=[j for j in support[1:-1]if p[j]>=p[j-1]and p[j]>p[j+1]and p[j]>=.5*p[k]]
                    counts.append(len(peaks));locations.append([float(axis[j]*100)for j in peaks])
                item['fine_peak_diagnostic']=dict(sample_stride=5,counts=dict(Counter(counts)),locations_cm=locations)
        windows.append(item)
    frozen=[r['clock_sync']for r in saved if r['clock_sync']['state']=='frozen']
    metadata=json.loads((path/'metadata.json').read_text())
    report=dict(manifest=manifest,manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in
            ('tools/review_weak_capture.py','radar_min/core.py','radar_min/cfar_range.py')},
        upstream_report_sha256=hashlib.sha256((args.output/'report.json').read_bytes()).hexdigest(),
        raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
        arrivals_sha256=hashlib.sha256((path/'arrivals.jsonl').read_bytes()).hexdigest(),
        capture_metadata=metadata,capture_summary=json.loads((path/'capture-summary.json').read_text()),
        frames=len(frames),host_span_s=float(times[-1]),labeled_end_s=manifest['segments'][-1]['end_s'],
        unscored_tail_s=max(0,float(times[-1])-manifest['segments'][-1]['end_s']),
        clock_states=dict(Counter(r['clock_sync']['state']for r in saved)),
        fit_diagnostics=frozen[0]['fit_diagnostics']if frozen else None,
        frozen_error_ms_p95_max=np.percentile([abs(r['residual_s'])*1000 for r in frozen],[95,100]).tolist()if frozen else None,
        saved_replay_results_association_motion_rx_os_phase_weak_link_and_feature_match=True,
        windows=windows,interpretation='New capture evaluated with unchanged settings; labels used only for scoring. Empty silence is inherited through gated stages and does not compensate for missing target ranges. Peak locations and spectral contrasts are diagnostics, not accepted physical target distances.')
    (args.output/'capture-review.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True,layout='constrained')
    for key,name in [('baseline','Baseline'),('os_rd','Old OS + RD inspection'),('confirmed_weak','Confirmed weak feature')]:
        ys=[methods[key](r)['experimental_range_m']for r in saved]
        axes[0].plot(times,[v*100 if v is not None else np.nan for v in ys],'.',ms=2,label=name)
    for k in(1,2,3,4):
        p=np.array([r['one_d']['power'][k]for r in saved]);th=np.array([r['one_d']['threshold_power'][k]for r in saved])
        axes[1].plot(times,db(p/th),lw=.7,label=f'CA margin bin {k}')
    for w in case['windows']:
        if w['trim_s']!=2:continue
        lo,hi=w['window_host_s'];nominal=w.get('nominal_target_m')
        for ax in axes:ax.axvspan(lo,hi,color='teal'if nominal else'gray',alpha=.12)
        if nominal:axes[0].plot([lo,hi],[nominal*100]*2,'k--',lw=.8)
    axes[0].set(ylabel='Experimental cm',ylim=(0,170),title='New bare-box / operator-B run; handling excluded from scores')
    axes[1].axhline(0,color='black',ls='--');axes[1].set(xlabel='Host seconds from first saved frame',ylabel='dB above/below CA threshold')
    for ax in axes:ax.legend(fontsize=8)
    fig.savefig(args.output/'comparison.png',dpi=130);plt.close(fig)
    fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,layout='constrained')
    for w,axis,median in spectra:
        for rx,ax in enumerate(axes):ax.plot(axis,db(median[:,rx]),lw=.8,label=w['label'])
    for rx,ax in enumerate(axes):ax.set(ylabel=f'RX {rx+1} dB ADC units²',xlim=(0,2.8));ax.axvline(.5,color='gray',ls='--',lw=.7);ax.axvline(1.2,color='gray',ls='--',lw=.7)
    axes[0].legend(fontsize=7,ncol=2);axes[0].set_title('Median raw dense power per RX, fixed every-fifth-frame sampling')
    axes[-1].set_xlabel('Nominal range (m); dashed lines are reported target placements')
    fig.savefig(args.output/'spectra.png',dpi=130);plt.close(fig)
    for w in windows:
        if w['trim_s']==2:print(w['label'],{k:(v['presence_frames'],v['numeric_frames'],v['frames'],v['cm_p05_p50_p95'])for k,v in w['channels'].items()},flush=True)


if __name__=='__main__':main()
