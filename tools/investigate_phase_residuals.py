"""Fixed-stride residual/RX investigation; diagnostic models never publish live ranges."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from radar_min.__main__ import read_recording
from radar_min.cfar import CfarConfig,CfarDetector
from radar_min.cfar_os import OsCfarDetector
from tools.phase_residual_model import ResidualRangeModel
from tools.qualify_avg16_cfar import aligned_times


MANIFESTS=['avg16-placements-20261111.json','avg16-repeat50-20261111.json',
    'avg16-operator-abab-20261111.json','avg16-operator-empty-abab-20261111.json',
    'avg16-motion-20261111.json','motion-aware-live-20261111.json',
    'reflector-live-20261111.json','foil-box-live-20261111.json','foil-box-repeat-20261111.json']


def quantiles(values):
    values=[v for v in values if v is not None]
    return np.percentile(values,[5,50,95]).tolist() if values else None


def summarize(rows,target):
    result=dict(samples=len(rows),models=len([r for r in rows if r]),
        reasons=dict(Counter(r['reason']if r else'no_confirmed_candidate'for r in rows)))
    selected=[r for r in rows if r]
    result['single_accepted_samples']=sum(r['single']['range_m']is not None for r in selected)
    for key in ('diagnostic_range_m','residual_fraction','candidate_unique_energy_fraction',
                'nuisance_unique_energy_fraction','conditional_rx_spread_m','residual_peak_m','conditional_width_m'):
        result[key+'_p05_p50_p95']=quantiles([r.get(key)for r in selected])
    result['single_residual_fraction_p05_p50_p95']=quantiles([r['single']['residual_fraction']for r in selected])
    result['single_provisional_range_m_p05_p50_p95']=quantiles([r['single']['provisional_range_m']for r in selected])
    for key in ('nuisance_m','conditional_rx_range_m'):
        values=[r[key]for r in selected if key in r]
        result[key+'_median']=np.median(values,axis=0).tolist() if values else None
    result['grid_not_converged_samples']=sum(not r.get('grid_converged',True)for r in selected)
    result['nuisance_boundary_samples']=sum(r.get('nuisance_boundary',False)for r in selected)
    result['competing_candidate_samples']=sum(r.get('comparable_candidate_optima',0)>1 for r in selected)
    result['rx_boundary_samples']=sum(any(r.get('conditional_rx_boundary',[]))for r in selected)
    if target is not None:
        differences=[abs(r['diagnostic_range_m']-target)*100 for r in selected if r['diagnostic_range_m']is not None]
        result['diagnostic_conditional_placement_mae_cm']=float(np.mean(differences))if differences else None
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    cases=[case for name in MANIFESTS for case in json.loads((Path('configs')/name).read_text())['cases']]
    cases.append(dict(recording='recordings/rd-gui-20261111-133435-428121/live-001',
        windows=[dict(label='80 cm stationary (approximate)',state='hold',nominal_target_m=.8,window_host_s=[2,73])]))
    sessions=[];snapshots=[]
    with gzip.open(args.output/'frames.jsonl.gz','wt')as log:
        for case in cases:
            path=Path(case['recording']);c,frames,_=read_recording(path)
            saved=[json.loads(x)for x in (path/'readings.jsonl').read_text().splitlines()]
            arrivals=[json.loads(x)for x in (path/'arrivals.jsonl').read_text().splitlines()]
            times=aligned_times(frames,arrivals)
            if [f.sequence for f in frames]!=[r['frame_sequence']for r in saved]:raise ValueError('Saved sequence mismatch')
            windows=[w for w in case['windows']if w.get('trim_s')!=1 and not w.get('operator_split_approximate') and w['state']in('hold','target_absent')]
            indices={w['label']:np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1]))[::10]for w in windows}
            chosen=set(int(i)for ids in indices.values()for i in ids)
            ca=CfarDetector(c,CfarConfig(1,4,4,2));os=OsCfarDetector(c,CfarConfig(1,4,4,2));model=ResidualRangeModel(c);rows={}
            for i,(f,old)in enumerate(zip(frames,saved)):
                readings={'ca':ca.update(f),'os':os.update(f)};baseline=old.get('one_d',old)
                for k in ('target_detected','range_bin','experimental_range_m','reason'):
                    if readings['ca'][k]!=baseline[k]:raise ValueError('CA changed '+k)
                if i not in chosen:continue
                cache={};result=dict(recording=str(path),frame_sequence=f.sequence,host_time_s=float(times[i]))
                # A fixed acquisition-mask probe runs even with no detection. It is
                # deliberately diagnostic and cannot become a presence decision.
                supports={name:tuple(r['selected_group_bins'])if r['target_detected']else None for name,r in readings.items()}
                supports['probe']=tuple(range(c.min_bin,c.max_bin+1))
                for name,bins in supports.items():
                    if bins is not None and bins not in cache:cache[bins]=model.fit(f,list(bins))
                    result[name]=cache[bins]if bins else None
                result['baseline_peak_m']=readings['ca']['experimental_range_m'];rows[i]=result
                log.write(json.dumps(result,allow_nan=False)+'\n')
            summaries=[]
            for w in windows:
                ids=indices[w['label']];subset=[rows[int(i)]for i in ids]
                item=dict(**w,sampled_frames=len(subset),variants={name:summarize([r[name]for r in subset],w.get('nominal_target_m'))for name in('ca','os','probe')},
                    baseline_peak_m_p05_p50_p95=quantiles([r['baseline_peak_m']for r in subset]))
                summaries.append(item)
                if len(ids):
                    # Snapshot at the middle of the fixed sampled set, not the best fit.
                    i=int(ids[len(ids)//2]);snapshots.append((case['recording'],w,frames[i],c,rows[i]))
            sessions.append(dict(recording=str(path),frames=len(frames),sampled_frames=len(chosen),
                raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),config_fingerprint=c.fingerprint,
                ca_matches_saved=True,windows=summaries))
            print(str(path),len(chosen),'samples',flush=True)
    paths=['tools/investigate_phase_residuals.py','tools/phase_residual_model.py','radar_min/phase_range.py','radar_min/cfar.py','radar_min/cfar_os.py','radar_min/core.py']
    report=dict(method=model.metadata,stride=10,snapshot='Middle of each fixed sampled set',
        protocol='All frames replayed; CA decisions match saved readings. Every tenth frame inside existing quiet windows, anchored at window start. No labels fitted; CA/OS candidate bounds unchanged. Probe uses fixed saved acquisition mask without requiring detection. Extra nuisance fits are diagnostic only, not accepted ranges or independent validation.',
        sessions=sessions,sources={p:hashlib.sha256(Path(p).read_bytes()).hexdigest()for p in paths},
        manifests={name:hashlib.sha256((Path('configs')/name).read_bytes()).hexdigest()for name in MANIFESTS})
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    make_plots(snapshots,args.output)


def make_plots(snapshots,output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(output/'rx-residual-snapshots.pdf')as pdf:
        for recording,w,frame,c,row in snapshots:
            result=row['ca']or row['probe'];x=frame.adc[c.discard_chirps:].transpose(0,2,1).astype(float);x-=x.mean(axis=2,keepdims=True)
            basis=ResidualRangeModel(c).single;near=result['single']['provisional_range_m']
            if near is None:continue
            q=basis._basis(near/c.spacing_m);single=x-np.einsum('crn,nk,mk->crm',x,q,q)
            two=x.copy()
            if 'nuisance_m'in result:
                q=basis._basis(result['diagnostic_range_m']/c.spacing_m)
                for rx,far in enumerate(result['nuisance_m']):
                    a=np.column_stack((q,basis._basis(far/c.spacing_m)));u,s,_=np.linalg.svd(a,full_matrices=False);u=u[:,s>1e-8]
                    two[:,rx]=x[:,rx]-(x[:,rx]@u)@u.T
            fig,axes=plt.subplots(3,1,figsize=(11,8),sharex=True,sharey=True,layout='constrained')
            axis=np.arange(2049)*c.samples*c.spacing_m/4096
            for rx,ax in enumerate(axes):
                for traces,label in ((x,'Raw'),(single,'After candidate tone'),(two,'After candidate + nuisance')):
                    power=np.mean(abs(np.fft.rfft(traces[:,rx]*np.hanning(c.samples),n=4096,axis=1))**2,axis=0)
                    ax.plot(axis,10*np.log10(np.maximum(power,1e-12)),lw=.8,label=label)
                if w.get('nominal_target_m')is not None:ax.axvline(w['nominal_target_m'],color='black',ls='--',label='Reported placement')
                ax.axvspan(*result['single']['support_m'],alpha=.1,color='teal');ax.set(ylabel=f'RX {rx+1} dB',xlim=(0,4))
            axes[0].legend(fontsize=8);axes[-1].set_xlabel('Nominal range (m); FFT power in arbitrary dB, common scale per page')
            fig.suptitle(f"{recording}\n{w['label']}; host {row['host_time_s']:.2f}s; {'CA support'if row['ca']else'undetected fixed-mask probe'}",fontsize=10)
            pdf.savefig(fig)
            if recording.endswith('live-004')and w['label'].startswith('A1'):fig.savefig(output/'fixed-target-rx-residuals.png',dpi=130)
            plt.close(fig)


if __name__=='__main__':main()
