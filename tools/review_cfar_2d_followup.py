"""Frozen 2D CFAR review: empty controls and fast/slow 120↔30 cm motion."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from radar.paired import audit_wire
from radar.protocol import Parser
from radar.storage import replay
from radar_min.core import Config, db, range_spectrum

ROOT = Path(__file__).resolve().parents[1]
MOTIONS = [('fast approach',31.11,32.82,-1), ('fast retreat',48.78,50.63,1),
           ('slow approach',64.18,67.45,-1), ('slow retreat',81.14,84.70,1)]
HOLDS = [('120 cm A',18.99,31.11,120), ('30 cm A',32.82,48.78,30),
         ('120 cm B',50.63,64.18,120), ('30 cm B',67.45,81.14,30),
         ('120 cm C',84.70,95.39,120)]
TRANSITIONS = [('placing',13.99,18.99), ('removing',95.39,100.39)]


def main():
    source = ROOT/'recordings/gui-20261110-221227-169414/live-001'
    output = ROOT/'evidence/rd-cfar2d-followup-20261110'
    exported = output/'replay'
    meta = json.loads((exported/'metadata.json').read_text())
    original = json.loads((ROOT/'evidence/rd-cfar2d-20261110/replay/metadata.json').read_text())
    if meta['cfar'] != original['cfar'] or meta['cfar_source_sha256'] != original['cfar_source_sha256']:
        raise ValueError('Follow-up must use the same detector source and settings')
    if meta['raw_sha256'] != hashlib.sha256((source/'frames.grd').read_bytes()).hexdigest():
        raise ValueError('Replay/input mismatch')
    parser = Parser(); frames = list(replay(source,parser))
    arrivals = [json.loads(x) for x in (source/'arrivals.jsonl').read_text().splitlines()]
    readings = [json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
    candidates = [json.loads(x) for x in (exported/'candidates.jsonl').read_text().splitlines()]
    if not ([f.sequence for f in frames] == [r['sequence'] for r in arrivals] ==
            [r['sequence'] for r in candidates] == [r['frame_sequence'] for r in readings]):
        raise ValueError('Frame/arrival/output alignment mismatch')
    times = (np.array([r['host_unix_ns'] for r in arrivals])-arrivals[0]['host_unix_ns'])/1e9
    config = Config.load(source/'config.json')
    spectra = np.stack([range_spectrum(f,config) for f in frames])
    increments = spectra[:,1:]*spectra[:,:-1].conj()
    pooled = np.mean(increments/np.maximum(abs(increments),1e-20),axis=(1,3))
    phase = np.angle(pooled)/(2*np.pi)
    native_power = np.mean(abs(spectra)**2,axis=(1,3))
    maxima = [[p for g in r['clusters'] for p in g['local_maxima']] for r in candidates]
    with np.load(exported/'maps.npz') as a:
        full = a['full_power']; frequencies = a['cycles_per_saved_block']; valid = a['valid']
    with np.load(exported/'cfar.npz') as a:
        threshold = a['threshold_power']; accepted = a['accepted']
    detected = np.array([r['target_detected'] for r in readings])
    distance_cm = np.array([r.get('experimental_range_m')*100
                           if r.get('experimental_range_m') is not None else np.nan for r in readings])
    dt = float(np.median(np.diff(times)))

    def summarize(label,left,right):
        ids = np.flatnonzero((times>=left)&(times<=right)&valid)
        roi = [[p for p in maxima[i] if 1<=p['range_bin']<=4] for i in ids]
        numeric = distance_cm[ids][np.isfinite(distance_cm[ids])]
        hit_ids = ids[detected[ids]]
        episodes = []
        for group in np.split(hit_ids,np.flatnonzero(np.diff(hit_ids)>1)+1):
            if len(group):
                episodes.append(dict(start_host_s=float(times[group[0]]),end_host_s=float(times[group[-1]]),
                                     approximate_duration_s=float(times[group[-1]]-times[group[0]]+dt)))
        return dict(label=label,window_host_s=[left,right],frames=len(ids),
            roi_zero_local_maximum_frames=sum(any(p['doppler_bin']==8 for p in row) for row in roi),
            roi_nonzero_local_maximum_frames=sum(any(p['doppler_bin']!=8 for p in row) for row in roi),
            roi_negative_local_maximum_frames=sum(any(p['doppler_bin']<8 for p in row) for row in roi),
            roi_positive_local_maximum_frames=sum(any(p['doppler_bin']>8 for p in row) for row in roi),
            zero_peak_range_bins1_4_counts=dict(Counter(p['range_bin'] for row in roi for p in row if p['doppler_bin']==8)),
            roi_peak_doppler_offset_counts=dict(Counter(p['doppler_bin']-8 for row in roi for p in row)),
            all_range_zero_local_maximum_frames=sum(any(p['doppler_bin']==8 for p in maxima[i]) for i in ids),
            all_range_nonzero_local_maximum_frames=sum(any(p['doppler_bin']!=8 for p in maxima[i]) for i in ids),
            recorded_1d_output_frames=int(detected[ids].sum()),
            recorded_1d_numeric_distance_frames=len(numeric),
            recorded_1d_conditional_range_cm_p05_p50_p95=np.percentile(numeric,[5,50,95]).tolist() if len(numeric) else None,
            recorded_1d_output_episodes=episodes,
            phase_median_cycles_per_saved_block_bins1_8=np.median(phase[ids,1:9],axis=0).tolist(),
            zero_doppler_threshold_margin_median_db_bins1_8=np.median(db(full[ids,8,1:9]/threshold[ids,8,1:9]),axis=0).tolist(),
            native_range_power_median_db_bins1_8=db(np.median(native_power[ids,1:9],axis=0)).tolist())

    motions = []
    for label,left,right,sign in MOTIONS:
        motions.append(dict(**summarize(label,left+.2,right-.2),video_window_s=[left,right],
            expected_sign=sign, nominal_travel_average_m_s=.9/(right-left),
            offset_sensitivity=[dict(offset_s=offset,**summarize(label,left+.2+offset,right-.2+offset))
                                for offset in (-.5,-.25,0,.25,.5)]))
    holds = []
    for label,left,right,distance in HOLDS:
        item = dict(**summarize(label,left+2,right-2),nominal_target_cm=distance)
        coordinate = distance/100/config.spacing_m
        bins = sorted({int(x) for x in (np.floor(coordinate),np.ceil(coordinate)) if 1<=x<=31})
        ids = np.flatnonzero((times>=left+2)&(times<=right-2)&valid)
        item.update(nominal_endpoint_bins=bins,
            nominal_endpoint_zero_local_maximum_frames=sum(any(p['doppler_bin']==8 and p['range_bin'] in bins
                for p in maxima[i]) for i in ids),
            nominal_endpoint_zero_accepted_cell_frames=int(np.sum(np.any(accepted[ids,8][:,bins],axis=1))))
        holds.append(item)
    controls = [summarize('initial target absent',2,13.99),
                summarize('post-removal quiet',102.39,106.12),
                summarize('target absent, possible operator motion',106.62,float(times[-1]))]
    edge_period = [(f.edge_times_us[256]-f.edge_times_us[0])/16 for f in frames]
    report = dict(recording=str(source.relative_to(ROOT)),raw_sha256=meta['raw_sha256'],
        review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        cfar_source_sha256=meta['cfar_source_sha256'],settings=meta['cfar'],settings_and_source_unchanged=True,
        frames=len(frames),valid_frames=int(valid.sum()),first_last_sequence=[frames[0].sequence,frames[-1].sequence],
        host_span_s=float(times[-1]),wire_integrity=audit_wire(source),
        saved_integrity={k:getattr(parser,k) for k in ('gaps','bad_crc','bad_headers','restarts','discarded_bytes')},
        edge_counts=dict(Counter(f.edge_count for f in frames)),edge_overflow_frames=sum(f.edge_overflow for f in frames),
        endpoint_group_period_us_p05_p50_p95=np.percentile(edge_period,[5,50,95]).tolist(),
        device_errors=sorted({f.errors for f in frames}),device_drops=sorted({f.dropped for f in frames}),
        recorded_detector=json.loads((source/'metadata.json').read_text())['detector'],
        motions=motions,holds=holds,controls=controls,
        labels='Absolute approximate video times, no fitted offset. 1:07:45 interpreted as 67.45 s. Placement 13.99–18.99, removal 95.39–100.39 excluded. Motion interiors trim 0.2 s/side; holds 2 s/side. Operator motion starts at unknown time after 106.62 s; quiet post-removal analysis ends 0.5 s before that bound.',
        interpretation='Candidate outputs only, not object association or detection/false-alarm accuracy. ROI bins 1–4 follow the supplied 30–120 cm path; all usable bins remain tested. Empty means no added target, not absence of walls or other legitimate reflectors. Physical speed/distance remain uncalibrated.')
    (output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(5,1,figsize=(14,15),sharex=True,layout='constrained')
    im=axes[0].pcolormesh(times,np.arange(1,9),db(native_power[:,1:9]).T,shading='nearest')
    axes[0].set(ylabel='Native range bin',title='Raw range power, bins 1–8; no empty-scene subtraction')
    fig.colorbar(im,ax=axes[0],label='dB ADC units²')
    xyz=np.array([(times[i],p['range_bin'],p['cycles_per_saved_block'])for i,row in enumerate(maxima)for p in row])
    for ax,zoom in ((axes[1],True),(axes[4],False)):
        zero=xyz[:,2]==0
        ax.scatter(xyz[zero,0],xyz[zero,1],s=3,c='grey',alpha=.4)
        im=ax.scatter(xyz[~zero,0],xyz[~zero,1],s=8,c=xyz[~zero,2],cmap='coolwarm',vmin=-.25,vmax=.25)
        ax.set(ylabel='Native range bin',ylim=(.5,8.5)if zoom else(.5,31.5),
               title='2D CFAR local maxima, zero grey and signed Doppler colored'+(' (zoom)'if zoom else' (all usable ranges)'))
        fig.colorbar(im,ax=ax,label='Cycles/saved block')
    for k in (1,2,3,4):axes[2].plot(times,phase[:,k],'.',ms=2,label=f'bin {k}')
    axes[2].set(ylabel='Cycles/saved block',ylim=(-.2,.2),title='Fixed-bin adjacent-phase progression; no physical velocity calibration')
    axes[2].legend(ncol=4,loc='upper right')
    axes[3].plot(times,distance_cm,'.',ms=2,label='Recorded 1D experimental output')
    for _,left,right,distance in HOLDS:axes[3].plot([left,right],[distance,distance],color='black',lw=2)
    axes[3].set(ylabel='Experimental cm',ylim=(0,180),title='Recorded 1D CFAR distance; black segments are approximate target holds')
    axes[3].legend(loc='upper right')
    for ax in axes:
        for _,left,right,sign in MOTIONS:ax.axvspan(left,right,color='orange'if sign<0 else'lime',alpha=.18)
        for _,left,right in TRANSITIONS:ax.axvspan(left,right,color='grey',alpha=.2)
        ax.axvline(106.62,color='red',ls='--',alpha=.7)
        ax.set_xlim(0,times[-1])
    axes[-1].set_xlabel('Host seconds from first saved frame; red line = operator motion possible after this point')
    fig.suptitle('Frozen AVG16 2D CFAR follow-up: 120↔30 cm; orange approach, green retreat, grey handling transitions')
    fig.savefig(output/'timeline.png',dpi=150);plt.close(fig)

    fig,axes=plt.subplots(1,4,figsize=(15,4),sharex=True,sharey=True,layout='constrained')
    for ax,(label,left,right,_)in zip(axes,MOTIONS):
        index=int(np.argmin(abs(times-(left+right)/2)))
        im=ax.imshow(db(full[index,:,1:9]/threshold[index,:,1:9]),origin='lower',aspect='auto',
                     extent=(.5,8.5,-.53125,.46875),vmin=-12,vmax=12)
        cells=np.array([(r,frequencies[d])for d,r in np.argwhere(accepted[index])if 1<=r<=8]).reshape(-1,2)
        ax.scatter(cells[:,0],cells[:,1],marker='s',facecolors='none',edgecolors='white',s=25,linewidths=.7)
        p=[p for p in maxima[index]if 1<=p['range_bin']<=8]
        ax.scatter([x['range_bin']for x in p],[x['cycles_per_saved_block']for x in p],marker='x',c='red',s=35)
        ax.set(title=f'{label}\nmidpoint {times[index]:.2f} s',xlabel='Native range bin')
    axes[0].set_ylabel('Cycles/saved block')
    fig.colorbar(im,ax=axes,label='dB above/below frozen CFAR threshold')
    fig.suptitle('Video-window midpoint frames; accepted cells outlined, local maxima ×')
    fig.savefig(output/'motion-midpoints.png',dpi=150);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,8),sharex=True,layout='constrained')
    for s in holds+controls[:2]:
        axes[0].plot(np.arange(1,9),s['native_range_power_median_db_bins1_8'],'o-',label=s['label'])
        axes[1].plot(np.arange(1,9),s['zero_doppler_threshold_margin_median_db_bins1_8'],'o-',label=s['label'])
    axes[0].set(ylabel='Median dB ADC units²',title='Raw range spectra of buffered stationary phases; no subtraction')
    axes[0].legend(fontsize=8,ncol=2)
    axes[1].axhline(0,color='black',lw=.8)
    axes[1].set(xlabel='Native range bin',ylabel='Median dB above/below threshold',title='Zero-Doppler cell margin under frozen 2D CFAR')
    fig.savefig(output/'stationary-spectra.png',dpi=150);plt.close(fig)
    for s in motions+holds+controls:
        print(s['label'],s['frames'],'1D',s['recorded_1d_output_frames'],
              '2D zero',s['roi_zero_local_maximum_frames'],'2D moving',s['roi_nonzero_local_maximum_frames'])


if __name__=='__main__':main()
