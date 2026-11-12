"""Frozen 1D/RD comparison for live-006; supplied motion labels, no tuning."""
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np


def main():
    output = Path('evidence/avg16-motion-20261111')
    rd = Path('evidence/avg16-motion-rd-20261111')
    report = json.loads((output/'report.json').read_text())
    session = report['sessions'][0]
    source = Path(session['recording'])
    readings = [json.loads(x) for x in (output/'readings.jsonl').read_text().splitlines()]
    saved = [json.loads(x) for x in (source/'readings.jsonl').read_text().splitlines()]
    candidates = [json.loads(x) for x in (rd/'candidates.jsonl').read_text().splitlines()]
    tracks = [json.loads(x) for x in (rd/'tracks.jsonl').read_text().splitlines()]
    keys = ('frame_sequence', 'target_detected', 'range_bin', 'experimental_range_m', 'reason')
    if len(readings) != len(saved) or not all(all(a[k] == b[k] for k in keys) for a, b in zip(readings, saved)):
        raise ValueError('1D replay/live mismatch')
    sequences = [r['frame_sequence'] for r in readings]
    if sequences != [r['sequence'] for r in candidates] or sequences != [r['sequence'] for r in tracks]:
        raise ValueError('1D/RD sequence mismatch')
    metadata = json.loads((rd/'metadata.json').read_text())
    if metadata['raw_sha256'] != session['raw_sha256']:
        raise ValueError('RD input mismatch')
    times = np.array([r['host_time_s'] for r in readings])
    peaks = [[p for g in r['clusters'] for p in g['local_maxima']] for r in candidates]
    measured = [[t['measurement'] for t in r['tracks'] if t['measurement_valid']] for r in tracks]
    with np.load(rd/'cfar.npz') as a:
        accepted = a['accepted']
    windows = []
    for w in session['windows']:
        if w['trim_s'] == 1:
            continue
        left, right = w['window_host_s']
        ids = np.flatnonzero((times >= left) & (times < right))

        def count(pool, sign=None, bins=range(1, 5)):
            return sum(any(p['range_bin'] in bins and (sign is None or
                (p['cycles_per_saved_block']*sign > 0 if sign else p['cycles_per_saved_block']==0))
                for p in pool[i]) for i in ids)

        item = dict(label=w['label'], state=w['state'], frames=len(ids),
            window_host_s=[left, right], one_d_numeric_frames=w['numeric_frames'],
            raw_zero_peak_frames_bins1_4=count(peaks, 0),
            raw_negative_peak_frames_bins1_4=count(peaks, -1),
            raw_positive_peak_frames_bins1_4=count(peaks, 1),
            confirmed_zero_peak_frames_bins1_4=count(measured, 0),
            confirmed_negative_peak_frames_bins1_4=count(measured, -1),
            confirmed_positive_peak_frames_bins1_4=count(measured, 1),
            confirmed_peak_bin_counts=dict(Counter(str(p['range_bin']) for i in ids for p in measured[i] if 1<=p['range_bin']<=4)),
            ambiguous_frames_bins1_4=sum(any(t['state']=='ambiguous' and any(1<=r<=4 for _,r in t['current_support_cells']) for t in tracks[i]['tracks']) for i in ids))
        if w['state']=='hold':
            coordinate=w['nominal_target_m']
            spacing=299792458*session['config']['sample_rate_hz']/(2*session['config']['slope_hz_s']*session['config']['samples'])
            bins=sorted({int(np.floor(coordinate/spacing)),int(np.ceil(coordinate/spacing))}-{0})
            item.update(nominal_endpoint_bins=bins,
                        nominal_endpoint_zero_accepted_frames=int(np.any(accepted[ids,8][:,bins],axis=1).sum()),
                        nominal_endpoint_raw_zero_peak_frames=count(peaks,0,bins),
                        nominal_endpoint_confirmed_zero_peak_frames=count(measured,0,bins))
        else:
            sign=w['expected_phase_sign']
            item.update(expected_phase_sign=sign,
                        raw_expected_sign_frames=count(peaks,sign),
                        confirmed_expected_sign_frames=count(measured,sign),
                        raw_opposite_sign_frames=count(peaks,-sign),
                        confirmed_opposite_sign_frames=count(measured,-sign))
        windows.append(item)
    control_dir=Path('evidence/avg16-operator-empty-rd-20261111')
    control_meta=json.loads((control_dir/'metadata.json').read_text())
    for key in ('cfar','association','cfar_source_sha256','association_source_sha256'):
        if control_meta[key]!=metadata[key]:
            raise ValueError('RD target-absent settings/source mismatch: '+key)
    control_report=json.loads(Path('evidence/avg16-operator-empty-abab-20261111/report.json').read_text())
    if control_meta['raw_sha256']!=control_report['sessions'][0]['raw_sha256']:
        raise ValueError('RD target-absent raw input mismatch')
    control_tracks=[json.loads(x) for x in (control_dir/'tracks.jsonl').read_text().splitlines()]
    control_rows=[json.loads(x) for x in Path('evidence/avg16-operator-empty-abab-20261111/readings.jsonl').read_text().splitlines()]
    if [r['sequence'] for r in control_tracks]!=[r['frame_sequence'] for r in control_rows]:
        raise ValueError('RD target-absent sequence mismatch')
    control_windows=[]
    for w in control_report['sessions'][0]['windows']:
        if w['trim_s']!=2:continue
        ids=[i for i,r in enumerate(control_rows) if w['window_host_s'][0]<=r['host_time_s']<w['window_host_s'][1]]
        points=[[t['measurement'] for t in control_tracks[i]['tracks'] if t['measurement_valid'] and 1<=t['measurement']['range_bin']<=4] for i in ids]
        control_windows.append(dict(label=w['label'],frames=len(ids),
            confirmed_roi_feature_frames=sum(bool(row) for row in points),
            confirmed_peak_bin_counts=dict(Counter(str(p['range_bin']) for row in points for p in row)),
            confirmed_nonzero_frames=sum(any(p['cycles_per_saved_block']!=0 for p in row) for row in points)))
    detail=dict(source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        one_d_report_sha256=hashlib.sha256((output/'report.json').read_bytes()).hexdigest(),
        rd_metadata=metadata, saved_live_replay_matches=True, compared_frames=len(readings),windows=windows,
        target_absent_control=dict(metadata=control_meta,windows=control_windows,
            interpretation='All four quiet interiors retain a bin-1 zero-Doppler feature despite no added target. This is scene-feature evidence, not verified target detection; naive union/nearest-feature fusion would promote this nuisance.'),
        interpretation='Same frames, unchanged settings. ROI bins1–4 is a declared 50–120cm diagnostic path, not a detector filter or physical identity match. Counts are feature/cell evidence, not object-detection accuracy; nonzero signed peaks may come from manual operator/hand motion. Native RD points are not fine ranges or m/s. No timing-offset fitting.')
    (output/'rd-comparison.json').write_text(json.dumps(detail,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(13,10),sharex=True,layout='constrained')
    values=[r['experimental_range_m']*100 if r['target_detected'] and r['experimental_range_m'] is not None else np.nan for r in readings]
    axes[0].plot(times,values,'.',ms=2)
    axes[0].set(ylabel='Experimental cm',ylim=(0,160),title='1D current fine distance; gaps preserved')
    for ax,pool,title in [(axes[1],peaks,'Raw 2D CFAR local maxima, diagnostic bins 1–4'),(axes[2],measured,'Confirmed current RD features, diagnostic bins 1–4')]:
        xyz=np.array([(times[i],p['range_bin'],p['cycles_per_saved_block']) for i,row in enumerate(pool) for p in row if 1<=p['range_bin']<=4]).reshape(-1,3)
        if len(xyz):
            zero=xyz[:,2]==0
            ax.scatter(xyz[zero,0],xyz[zero,1],s=4,color='gray',label='Zero Doppler')
            im=ax.scatter(xyz[~zero,0],xyz[~zero,1],s=12,c=xyz[~zero,2],cmap='coolwarm',vmin=-.25,vmax=.25)
            fig.colorbar(im,ax=ax,label='Cycles/saved block')
        ax.set(ylabel='Native range bin',ylim=(.5,4.5),title=title)
    for w in session['windows']:
        if w['trim_s']==1:continue
        if w['state']=='hold':
            left,right=w['original_window_host_s']
            axes[0].plot([left,right],[w['nominal_target_m']*100]*2,'k--',lw=1)
        else:
            left,right=w['original_window_host_s']
            for ax in axes:ax.axvspan(left,right,color='orange' if w['expected_phase_sign']<0 else 'teal',alpha=.18)
    axes[-1].set_xlabel('Host seconds from first saved frame; orange approach, teal retreat')
    fig.suptitle('Manual 120↔50 cm motion; operator at A; physical reflector identity unverified')
    fig.savefig(output/'rd-comparison.png',dpi=150);plt.close(fig)
    for w in windows:
        print(json.dumps(w))


if __name__=='__main__':main()
