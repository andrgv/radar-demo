"""Audit current-measurement semantics and fixed-settings association replays."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATASETS = [
    ('first','recordings/avg16-motion-01','evidence/rd-cfar2d-20261110',
     'evidence/rd-cfar2d-20261110/summary.json',(2,3,4)),
    ('followup','recordings/gui-20261110-221227-169414/live-001','evidence/rd-cfar2d-followup-20261110',
     'evidence/rd-cfar2d-followup-20261110/report.json',(1,2,3,4))]


def lines(path):
    return [json.loads(x)for x in path.read_text().splitlines()]


def review(name,source_path,baseline_path,label_path,roi):
    output = ROOT/'evidence/rd-association-20261110'
    exported = output/name
    source = ROOT/source_path
    baseline = ROOT/baseline_path/'replay'
    meta = json.loads((exported/'metadata.json').read_text())
    old = json.loads((baseline/'metadata.json').read_text())
    if meta['cfar']!=old['cfar'] or meta['cfar_source_sha256']!=old['cfar_source_sha256'] or meta['raw_sha256']!=old['raw_sha256']:
        raise ValueError('Association must retain the frozen CFAR/input')
    rows = lines(exported/'tracks.jsonl')
    candidates = lines(exported/'candidates.jsonl')
    arrivals = lines(source/'arrivals.jsonl')
    diagnostics = lines(exported/'diagnostics.jsonl')
    if not([r['sequence']for r in rows]==[r['sequence']for r in candidates]==[r['sequence']for r in arrivals]):
        raise ValueError('Track/candidate/arrival alignment mismatch')
    with np.load(exported/'cfar.npz')as a,np.load(baseline/'cfar.npz')as b:
        np.testing.assert_array_equal(a['accepted'],b['accepted'])
        np.testing.assert_allclose(a['threshold_power'],b['threshold_power'],rtol=0,atol=0,equal_nan=True)
        accepted = a['accepted']
    times = (np.array([r['host_unix_ns']for r in arrivals])-arrivals[0]['host_unix_ns'])/1e9
    maxima = [[p for g in r['clusters']for p in g['local_maxima']]for r in candidates]
    histories = defaultdict(list)
    for i,(row,peaks)in enumerate(zip(rows,maxima)):
        cells = {(p['doppler_bin'],p['range_bin'])for p in peaks}
        ids = [t['track_id']for t in row['tracks']]
        assert len(ids)==len(set(ids))
        for track in row['tracks']:
            histories[track['track_id']].append((i,track))
            if track['measurement_valid']:
                p = track['measurement']
                assert track['state']=='measured'and track['confirmed']
                assert track['last_peak_sequence']==row['sequence']
                assert(p['doppler_bin'],p['range_bin'])in cells
            else:
                assert track['measurement']is None
            for d,r in track['current_support_cells']:assert accepted[i,d,r]
        assert all(t['measurement']is None for t in row['ended_tracks'])
    labels = json.loads((ROOT/label_path).read_text())

    def summarize(phase):
        left,right = phase['window_host_s']
        ids = np.flatnonzero((times>=left)&(times<=right))
        raw = [[p for p in maxima[i]if p['range_bin']in roi]for i in ids]
        measured = [[t for t in rows[i]['tracks']if t['measurement_valid']and t['measurement']['range_bin']in roi]for i in ids]
        moving_ids = {t['track_id']for tracks in measured for t in tracks if t['measurement']['doppler_bin']!=8}
        return dict(label=phase['label'],window_host_s=[left,right],frames=len(ids),
            raw_roi_zero_frames=sum(any(p['doppler_bin']==8 for p in peaks)for peaks in raw),
            raw_roi_nonzero_frames=sum(any(p['doppler_bin']!=8 for p in peaks)for peaks in raw),
            measured_roi_zero_frames=sum(any(t['measurement']['doppler_bin']==8 for t in tracks)for tracks in measured),
            measured_roi_nonzero_frames=sum(any(t['measurement']['doppler_bin']!=8 for t in tracks)for tracks in measured),
            ambiguous_roi_support_frames=sum(any(t['state']=='ambiguous'and any(r in roi for d,r in t['current_support_cells'])for t in rows[i]['tracks'])for i in ids),
            raw_all_range_nonzero_frames=sum(any(p['doppler_bin']!=8 for p in maxima[i])for i in ids),
            measured_all_range_nonzero_frames=sum(any(t['measurement_valid']and t['measurement']['doppler_bin']!=8 for t in rows[i]['tracks'])for i in ids),
            measured_roi_feature_ids=sorted({t['track_id']for tracks in measured for t in tracks}),
            measured_nonzero_roi_feature_ids=sorted(moving_ids))

    # Describe all same-ID nonzero→zero transitions, not a hand-picked object.
    transitions = []
    for track_id,history in histories.items():
        previous = None
        for i,track in history:
            if not track['measurement_valid']:continue
            current = track['measurement']
            if previous is not None:
                old_i,old_peak = previous
                if old_peak['doppler_bin']!=8 and current['doppler_bin']==8:
                    transitions.append(dict(track_id=track_id,from_host_s=float(times[old_i]),to_host_s=float(times[i]),
                        from_range_bin=old_peak['range_bin'],to_range_bin=current['range_bin'],
                        intervening_frames=i-old_i-1))
            previous = (i,current)
    result = dict(recording=source_path,frames=len(rows),valid_frames=sum(r['valid']for r in rows),roi_bins=list(roi),
        raw_sha256=meta['raw_sha256'],cfar=meta['cfar'],association=meta['association'],
        cfar_source_sha256=meta['cfar_source_sha256'],association_source_sha256=meta['association_source_sha256'],
        frozen_cfar_arrays_identical=True,current_measurement_invariant_violations=0,
        states=dict(Counter(t['state']for r in rows for t in r['tracks'])),
        ended_reasons=dict(Counter(t['reason']for r in rows for t in r['ended_tracks'])),
        observation_dispositions=dict(Counter(o['disposition']for r in rows for o in r['observations'])),
        feature_hypotheses=len(histories),confirmed_feature_ids=len({t['track_id']for r in rows for t in r['tracks']if t['confirmed']}),
        association_ms_p05_p50_p95_max=np.percentile([d['association_processing_ms']for d in diagnostics],[5,50,95,100]).tolist(),
        motions=[summarize(p)for p in labels['motions']],holds=[summarize(p)for p in labels['holds']],
        controls=[summarize(p)for p in labels.get('controls',[])],same_id_nonzero_to_zero_transitions=transitions,
        note='Feature IDs, not object identity. Label windows/ROI inherited unchanged from prior reviews. Ambiguous support has no point measurement. Candidate filtering trades short/weak motion coverage for persistence; no ground-truth accuracy claim.')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes = plt.subplots(4,1,sharex=True,figsize=(14,13),layout='constrained')
    raw = np.array([(times[i],p['range_bin'],p['cycles_per_saved_block'])for i,peaks in enumerate(maxima)for p in peaks])
    measured = np.array([(times[i],t['measurement']['range_bin'],t['measurement']['cycles_per_saved_block'])
        for i,row in enumerate(rows)for t in row['tracks']if t['measurement_valid']])
    axes[0].scatter(raw[:,0],raw[:,1],s=3,c='grey',alpha=.25,label='raw CFAR maxima')
    im = axes[0].scatter(measured[:,0],measured[:,1],s=6,c=measured[:,2],cmap='coolwarm',vmin=-.25,vmax=.25)
    axes[0].set(ylabel='Native range bin',ylim=(.5,31.5),title='Confirmed current measurements over raw CFAR candidates; all ranges')
    fig.colorbar(im,ax=axes[0],label='Cycles/saved block')
    for track_id,history in histories.items():
        points = [(i,t['measurement'])for i,t in history if t['measurement_valid']and t['measurement']['range_bin']<=8]
        if not points:continue
        color = plt.get_cmap('tab20')(track_id%20)
        x = np.array([times[i]for i,_ in points]);y = np.array([p['range_bin']for _,p in points])
        axes[1].scatter(x,y,s=6,color=color)
        axes[1].annotate(str(track_id),(x[0],y[0]),xytext=(2,5),textcoords='offset points',fontsize=7,color=color)
    for i,row in enumerate(rows):
        for track in row['tracks']:
            support = [r for d,r in track['current_support_cells']if r<=8]
            if track['state']=='ambiguous'and support:
                axes[1].vlines(times[i],min(support)-.12,max(support)+.12,color='orange',alpha=.35,lw=1)
    axes[1].set(ylabel='Native range bin',ylim=(.5,8.5),title='Feature IDs at fresh points; orange = current ambiguous cell support, no range measurement')
    raw_roi = np.isin(raw[:,1],roi);measured_roi = np.isin(measured[:,1],roi)
    axes[2].scatter(raw[raw_roi,0],raw[raw_roi,2],s=8,c='grey',alpha=.3,label='raw maxima')
    axes[2].scatter(measured[measured_roi,0],measured[measured_roi,2],s=8,c='blue',label='confirmed current measurements')
    axes[2].set(ylabel='Cycles/saved block',ylim=(-.3,.3),title=f'Frequency evidence in the unchanged analysis ROI {list(roi)}')
    axes[2].legend(loc='upper right')
    raw_counts = [sum(p['doppler_bin']!=8 for p in peaks)for peaks in maxima]
    measured_counts = [sum(t['measurement_valid']and t['measurement']['doppler_bin']!=8 for t in row['tracks'])for row in rows]
    axes[3].step(times,raw_counts,where='mid',color='grey',alpha=.6,label='raw nonzero maxima')
    axes[3].step(times,measured_counts,where='mid',color='blue',label='confirmed nonzero measurements')
    axes[3].set(xlabel='Host seconds from first saved frame',ylabel='Count, all ranges',title='Nonzero candidates and measurements; stationary clutter tracks are still retained')
    axes[3].legend(loc='upper right')
    for phase in labels['motions']:
        left,right=phase['window_host_s']
        for ax in axes:ax.axvspan(left,right,color='orange'if 'approach'in phase['label']else'lime',alpha=.15)
    for ax in axes:ax.set_xlim(0,times[-1])
    fig.suptitle(f'{name}: fixed-settings radar feature association; native coordinates, object identity unverified')
    fig.savefig(output/f'{name}-tracks.png',dpi=150);plt.close(fig)
    return result


def main():
    reports = {name:review(name,source,baseline,labels,roi)for name,source,baseline,labels,roi in DATASETS}
    assert reports['first']['association']==reports['followup']['association']
    assert reports['first']['association_source_sha256']==reports['followup']['association_source_sha256']
    output = ROOT/'evidence/rd-association-20261110'
    summary = dict(review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),datasets=reports)
    (output/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    for name,r in reports.items():
        print(name,'states',r['states'],'confirmed IDs',r['confirmed_feature_ids'])
        for phase in r['motions']+r['holds']+r['controls']:
            print(phase['label'],phase['frames'],'raw moving',phase['raw_roi_nonzero_frames'],
                  'measured moving',phase['measured_roi_nonzero_frames'],'ambiguous',phase['ambiguous_roi_support_frames'])


if __name__=='__main__':main()
