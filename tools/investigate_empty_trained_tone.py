"""Fixed one-tone/RX empty-trained nuisance model; offline diagnostics only."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from radar_min.__main__ import read_recording
from tools.evaluate_tone_background import JointBackground
from tools.fit_range_signal import traces
from tools.qualify_avg16_cfar import aligned_times


class EmptyTrainedTone:
    """Fixed nuisance frequency; independent current sin/cos coefficients per trace.

    Background frequencies are fitted only to empty frames, not re-estimated
    on a target. A conditional peak is a probe, not a presence decision.
    """
    def __init__(self, config, empty):
        if not empty:
            raise ValueError('Empty training frames required')
        self.c = config
        self.background = JointBackground(config, empty, 1)
        lo, hi = config.min_bin-.5, config.max_bin+.5
        self.grid = np.linspace(lo, hi, 64*(config.max_bin-config.min_bin+1)+1)*config.spacing_m
        bases = np.array([self.background.target.basis(r) for r in self.grid])
        self.q = []; self.singular = []
        for nuisance in self.background.nuisance:
            z = bases - np.einsum('ni,mi,gmk->gnk', nuisance, nuisance, bases, optimize=True)
            u, s, _ = np.linalg.svd(z, full_matrices=False)
            self.q.append(u * (s > 1e-6)[:,None,:])
            self.singular.append(s[:, -1])
        self.q = np.array(self.q); self.singular = np.array(self.singular)

    def fit(self, frame):
        c = self.c
        if frame.profile_id != c.profile_id or frame.adc.shape != (c.chirps,c.samples,3):
            raise ValueError('Frame/config mismatch')
        if not np.isfinite(frame.adc).all() or np.any((frame.adc<=0)|(frame.adc>=65535)):
            raise ValueError('Invalid ADC input')
        x = traces(frame, c).reshape(-1,3,c.samples)
        x -= x.mean(axis=2, keepdims=True)
        raw_rx = np.sum(x*x, axis=(0,2))
        after = x.copy()
        for rx, u in enumerate(self.background.nuisance):
            after[:,rx] -= (x[:,rx]@u)@u.T
        energy_rx = np.sum(after*after, axis=(0,2)); energy = float(energy_rx.sum())
        projection = np.einsum('crn,rgnk->rgck', after, self.q, optimize=True)
        score_rx = np.sum(projection**2, axis=(2,3)); scores = score_rx.sum(axis=0)
        k = int(np.argmax(scores)); best = float(scores[k])
        rxk = np.argmax(score_rx, axis=1)
        residual_rx = np.maximum(0, energy_rx-score_rx[:,k])
        fraction_rx = np.divide(residual_rx, energy_rx, out=np.ones(3), where=energy_rx>1e-12)
        width = float(np.ptp(self.grid[best-scores<=.01*energy]))
        near = abs(self.grid[rxk]-self.grid[k]) <= .25*c.spacing_m
        supported = near & (fraction_rx <= .5) & (rxk>0) & (rxk<len(self.grid)-1) & (self.singular[:,k]>1e-6)
        maxima = np.flatnonzero((scores[1:-1]>=scores[:-2]) & (scores[1:-1]>scores[2:]))+1
        comparable = int(np.sum(best-scores[maxima] <= .01*energy))
        failures = []
        if energy <= 1e-12*max(1, float(raw_rx.sum())): failures.append('no_unique_energy')
        if k in (0,len(self.grid)-1): failures.append('scan_boundary')
        if comparable>1: failures.append('competing_optima')
        if width>.5*c.spacing_m: failures.append('broad_fit')
        residual = float(max(0,energy-best)/energy) if energy>1e-12 else 1.
        if residual>.5: failures.append('poor_conditional_tone_model')
        if int(supported.sum())<2: failures.append('insufficient_consistent_rx')
        return dict(diagnostic_range_m=float(self.grid[k]),
                    quality_range_m=None if failures else float(self.grid[k]),
                    reason=';'.join(failures) if failures else 'conditional_quality_only',
                    failures=failures, raw_energy=float(raw_rx.sum()),
                    background_residual_fraction=float(energy/max(float(raw_rx.sum()),1e-12)),
                    joint_raw_residual_fraction=float(max(0,energy-best)/max(float(raw_rx.sum()),1e-12)),
                    conditional_residual_fraction=residual,
                    unique_energy_per_trace=best/(len(x)*3),
                    width_m=width, comparable_optima=comparable,
                    rx_ranges_m=self.grid[rxk].tolist(), rx_spread_m=float(np.ptp(self.grid[rxk])),
                    rx_conditional_residual_fraction=fraction_rx.tolist(), supported_rx=int(supported.sum()),
                    candidate_basis_min_singular_rx=self.singular[:,k].tolist(),
                    scan_boundary=bool(k in (0,len(self.grid)-1)))


def quantiles(values):
    return np.percentile(values,[5,50,95]).tolist() if len(values) else None


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); manifest=json.loads(a.manifest.read_text())
    if len(manifest['cases'])!=1: raise ValueError('Exactly one matched recording required')
    case=manifest['cases'][0]; path=Path(case['recording']); c,frames,parser=read_recording(path)
    if any((parser.bad_crc,parser.bad_headers,parser.gaps,parser.restarts)): raise ValueError('Raw integrity failure')
    times=aligned_times(frames,[json.loads(x) for x in (path/'arrivals.jsonl').read_text().splitlines()])
    windows=[w for w in case['windows'] if w.get('trim_s')==2 and w['state'] in ('target_absent','hold')]
    ids=[np.flatnonzero((times>=w['window_host_s'][0])&(times<w['window_host_s'][1])) for w in windows]
    if not windows or windows[0]['state']!='target_absent' or any(len(v)<4 for v in ids):
        raise ValueError('Need initial empty and populated quiet windows')
    train=ids[0][:len(ids[0])//2]
    model=EmptyTrainedTone(c,[frames[i] for i in train])
    chosen=sorted(set(int(i) for subset in ids for i in subset))
    rows={i:model.fit(frames[i]) for i in chosen}
    # Empirical candidate-energy gate learned from the same frozen training empty.
    threshold=float(np.percentile([rows[int(i)]['unique_energy_per_trace'] for i in train],99))
    for i,r in rows.items():
        r.update(sequence=frames[i].sequence,host_s=float(times[i]),training=i in train)
        r['energy_changed']=bool(r['unique_energy_per_trace']>threshold)
        r['inspection_range_m']=r['quality_range_m'] if r['energy_changed'] else None
    groups=[(windows[0],train,'training only'),(windows[0],ids[0][len(train):],'held-out same-empty half')]
    groups += [(w,subset,'held-out interval') for w,subset in zip(windows[1:],ids[1:])]
    summaries=[]
    for w,subset,role in groups:
        selected=[rows[int(i)] for i in subset]
        summary=dict(**w,role=role,frames=len(subset),
            reasons=dict(Counter(r['reason'] for r in selected)),
            failure_counts=dict(Counter(f for r in selected for f in r['failures'])),
            energy_changed_frames=sum(r['energy_changed'] for r in selected),
            quality_frames=sum(r['quality_range_m'] is not None for r in selected),
            inspection_frames=sum(r['inspection_range_m'] is not None for r in selected),channels={})
        for name in ('diagnostic_range_m','quality_range_m','inspection_range_m'):
            values=[r[name] for r in selected if r[name] is not None]
            ch=dict(frames=len(values),cm_p05_p50_p95=quantiles(np.array(values)*100))
            if 'nominal_target_m' in w and values:
                dif=np.abs(np.array(values)-w['nominal_target_m'])
                ch.update(nominal_difference_mae_cm=float(np.mean(dif)*100),within_half_native_bin=int(np.sum(dif<=.5*c.spacing_m)))
            summary['channels'][name]=ch
        for name in ('background_residual_fraction','joint_raw_residual_fraction','conditional_residual_fraction',
                     'unique_energy_per_trace','rx_spread_m','width_m','supported_rx'):
            summary[name+'_p05_p50_p95']=quantiles([r[name] for r in selected])
        summaries.append(summary)
    sources=[str(a.manifest),str(path/'frames.grd'),str(path/'arrivals.jsonl'),str(path/'config.json'),
             'tools/investigate_empty_trained_tone.py','tools/evaluate_tone_background.py','tools/fit_range_signal.py',
             'tools/evaluate_power_fit.py','radar_min/core.py']
    report=dict(protocol='First half of first trim-2 empty fits exactly one nuisance tone/RX from empty covariance, fixed 0.05–5m grid at 5mm. No target-label fit or nuisance-rank sweep; nuisance frequency frozen afterward. Current independent sin/cos coefficients per chirp/RX permit background phase/amplitude changes. Raw DC-centered data; no fixed waveform subtraction. Conditional candidate grid is saved acquisition half-bin bounds at 1/64 native bin. Every quiet frame used. A probe exists even without CFAR; never a primary or confirmed object.',
        quality_rules=dict(conditional_max_residual=.5,max_width_native_bins=.5,rx_gate_native_bins=.25,
                           min_supported_rx=2,near_energy_fraction=.01,min_basis_singular=1e-6,
                           scan_boundary_rejected=True,competing_optima_rejected=True,
                           note='Borrowed fixed geometry/residual conventions from prior phase diagnostics, applied to post-nuisance energy. New diagnostic policy, not calibrated detection or independent validation.'),
        candidate_energy_threshold=threshold,energy_gate='Training-99th-percentile conditional explained energy per retained chirp/RX; empirical, no false-alarm calibration.',
        background_nominal_tone_m_rx=model.background.frequencies,
        background_search_bounds_m=[.05,5.],
        background_search_boundary_rx=[bool(r[0]<=.050000001 or r[0]>=4.999999999) for r in model.background.frequencies],
        background_boundary_policy='Retained as an explicit diagnostic warning; not hidden or used to retune the model. Quality-only outputs do not certify nuisance-frequency identification.',
        training_sequences=[frames[i].sequence for i in train],
        candidate_grid_m=model.grid.tolist(),spacing_m=c.spacing_m,manifest=manifest,windows=summaries,
        hashes={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in sources})
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with gzip.open(a.output/'frames.jsonl.gz','wt') as stream:
        for r in rows.values(): stream.write(json.dumps(r,allow_nan=False)+'\n')
    np.savez_compressed(a.output/'background.npz',grid_m=model.grid,conditional_basis=model.q,
                       **{f'nuisance_rx{rx}':v for rx,v in enumerate(model.background.nuisance)})
    plot(a.output, times, groups, rows, threshold)
    print('Frozen nuisance ranges',model.background.frequencies,'energy threshold',threshold,flush=True)
    for w in summaries:
        print(w['label'],w['role'],w['frames'],'quality',w['quality_frames'],'changed',w['energy_changed_frames'],
              'inspection',w['inspection_frames'],w['channels']['diagnostic_range_m'],w['failure_counts'],flush=True)


def plot(output,times,groups,rows,threshold):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(13,9),sharex=True,layout='constrained')
    ix=sorted(rows);t=times[ix]
    for key,label,color in [('diagnostic_range_m','Blind conditional probe','gray'),('inspection_range_m','Quality + energy inspection','teal')]:
        axes[0].plot(t,[rows[i][key]*100 if rows[i][key] is not None else np.nan for i in ix],'.',ms=2,label=label,color=color)
    axes[1].plot(t,[rows[i]['unique_energy_per_trace'] for i in ix],'.',ms=2)
    axes[1].axhline(threshold,color='black',ls='--',label='Training q99 energy')
    for key,label in [('conditional_residual_fraction','Residual after nuisance + candidate / post-nuisance energy'),('joint_raw_residual_fraction','Residual after joint fit / raw AC energy')]:
        axes[2].plot(t,[rows[i][key] for i in ix],'.',ms=2,label=label)
    axes[2].axhline(.5,color='gray',ls='--')
    for w,subset,role in groups:
        lo,hi=times[subset[0]],times[subset[-1]]
        for ax in axes: ax.axvspan(lo,hi,color='teal' if w['state']=='hold' else 'gray',alpha=.1)
        if 'nominal_target_m' in w: axes[0].plot([lo,hi],[w['nominal_target_m']*100]*2,'k--',lw=.8)
    axes[0].set(ylabel='Diagnostic cm',title='One empty-trained nuisance tone/RX; no live range changes')
    axes[1].set(ylabel='Conditional energy / trace',yscale='log')
    axes[2].set(ylabel='Residual fraction',xlabel='Host seconds from first saved frame',ylim=(0,1))
    for ax in axes:ax.legend(fontsize=7)
    fig.savefig(output/'comparison.png',dpi=130);plt.close(fig)


if __name__=='__main__':main()
