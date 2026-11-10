"""Summarize position/clutter follow-up captures without changing the detector."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from radar_min.cfar import CfarConfig,CfarDetector
from tools.investigate_cfar_scene_clock import load,spectrum_summary
from tools.validate_cfar_captures import summarize


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('recordings/gui-20261109-224819-094246'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    sessions={name:load(args.root/name) for name in ['live-005','live-006','live-007']}
    labels={'live-005':'Near original position; intended empty scene.',
        'live-006':'Original position followed by attempted clutter removal; clutter not restored. User says earlier portions likely include movement; about ten seconds before the final few seconds are decluttered/clean. Sensor stability was not explicitly confirmed.',
        'live-007':'Shifted position with box at reported 80 cm. Clutter had been changed previously; effects are not independently isolated.'}
    windows=[('live-005','near-original empty',1,22,None),('live-006','early recording',.5,2.5,None),
             ('live-006','approximate clean decluttered interior',35,43,None),('live-007','80 cm target interior',2,17,.8)]
    report=dict(schema=1,labels=labels,windows=[],sessions={})
    for name,s in sessions.items():
        detector=CfarDetector(s['config'],CfarConfig(**s['metadata']['detector']['cfar']))
        matches=True
        for f,original in zip(s['frames'],s['rows']):
            r=detector.update(f)
            # Saved transport faults must not be mistaken for algorithm differences.
            if original['reason'] in ('sequence_gap','host_sensor_timing_mismatch','serial_backlog'):continue
            a,b=r.get('experimental_range_m'),original.get('experimental_range_m')
            matches &= r['target_detected']==original['target_detected'] and (a is None)==(b is None) and (a is None or abs(a-b)<1e-9)
        if not matches:raise ValueError('Saved/current detector mismatch: '+name)
        report['sessions'][name]=dict(recording=str(s['path']),frames=len(s['frames']),duration_host_s=float(s['host'][-1]),
            duration_sensor_s=float(s['sensor'][-1]),rate_difference_percent=float((s['sensor'][-1]/s['host'][-1]-1)*100),
            whole_recording=summarize(s['rows'],s['frames'],s['config'],.8 if name=='live-007' else None),
            transport=json.loads((s['path']/'capture-summary.json').read_text()),
            raw_sha256=hashlib.sha256((s['path']/'frames.grd').read_bytes()).hexdigest(),
            config_fingerprint=s['config'].fingerprint,detector=s['metadata']['detector'],replay_matches_outside_transport_faults=True)
    for name,label,start,end,target in windows:
        s=sessions[name];mask=(s['host']>=start)&(s['host']<end);ids=np.flatnonzero(mask)
        metrics=summarize([s['rows'][i] for i in ids],[s['frames'][i] for i in ids],s['config'],target)
        report['windows'].append(dict(recording=name,label=label,start_host_s=start,end_host_s=end,target_m=target,
            metrics=metrics,raw_spectrum=spectrum_summary(s,mask)))
    report['early_to_late_bin2_drop_db']=report['windows'][1]['raw_spectrum']['native_bin2_power_db']-report['windows'][2]['raw_spectrum']['native_bin2_power_db']
    report['label_limits']='User labels are approximate. For live-006 only 35–43 host seconds are treated as a conservative interior of the roughly ten-second clean period preceding the final few seconds; earlier movement and tail are excluded from clean-scene metrics. Sensor stability is not confirmed; no restoration control. No tuning, smoothing or empty subtraction.'
    sources=['radar_min/cfar.py','radar_min/cfar_range.py','radar_min/core.py',
             'tools/evaluate_cfar_clutter_followup.py','tools/investigate_cfar_scene_clock.py','tools/validate_cfar_captures.py']
    report['source_sha256']={s:hashlib.sha256(Path(s).read_bytes()).hexdigest() for s in sources}
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(4,1,figsize=(11,11),layout='constrained')
    for ax,(name,s) in zip(axes[:3],sessions.items()):
        values=[r['experimental_range_m']*100 if r['target_detected'] and r.get('experimental_range_m') is not None else np.nan for r in s['rows']]
        ax.plot(s['host'],values,'.',ms=3,label='Saved live estimate')
        if name=='live-007':ax.axhline(80,color='black',ls='--',lw=1,label='Reported 80 cm placement')
        for w in report['windows']:
            if w['recording']==name:ax.axvspan(w['start_host_s'],w['end_host_s'],alpha=.12,color='teal' if w['target_m'] else 'gray')
        ax.set(title=name+' · '+labels[name].split('.')[0],xlabel='Host seconds since first frame',ylabel='Coordinate (cm)',ylim=(0,150));ax.legend(fontsize=8)
    for w in report['windows']:
        r=w['raw_spectrum']
        axes[3].plot(r['spectrum_coordinates_m'],10*np.log10(np.maximum(r['spectrum_median_power'],1e-12)),label=f"{w['recording']} {w['label']}")
    axes[3].set(xlim=(0,2.5),xlabel='Nominal beat coordinate (m)',ylabel='Median raw power (dB)',title='Current-frame spectra without reference subtraction');axes[3].legend(fontsize=8)
    fig.savefig(args.output/'clutter-followup.png',dpi=150);plt.close(fig)
    lines=['# Position and clutter follow-up: live-005/006/007','',
        'No thresholds, processing or firmware changed. Saved/current detector outputs agree outside explicitly recorded transport faults. These are fresh observations, not parameter-tuning data.','',
        '## Whole captures','',
        '| Capture | Description | Numeric outputs / frames | Median (cm) |',
        '|---|---|---:|---:|']
    for name,r in report['sessions'].items():
        m=r['whole_recording'];q=m['range_cm_p05_median_p95']
        lines.append(f"| {name} | {labels[name]} | {m['range_frames']}/{m['frames']} | {q[1]:.1f} |")
    lines+=['','## Inspection windows','',
        '| Capture / window | Host seconds | Numeric outputs / frames | Median (cm) | 5th–95th (cm) | Conditional MAE (cm) |',
        '|---|---:|---:|---:|---:|---:|']
    for w in report['windows']:
        m=w['metrics'];q=m['range_cm_p05_median_p95'];mae=m['conditional_mae_cm']
        lines.append(f"| {w['recording']} {w['label']} | {w['start_host_s']:g}–{w['end_host_s']:g} | {m['range_frames']}/{m['frames']} | {f'{q[1]:.1f}' if q else '—'} | {f'{q[0]:.1f}–{q[2]:.1f}' if q else '—'} | {f'{mae:.1f}' if mae is not None else '—'} |")
    lines+=['','## Findings','',
        f"- The early/approximately clean live-006 median power at native bin 2 drops by **{report['early_to_late_bin2_drop_db']:.2f} dB**. All three RX channels show a large decrease. The approximately clean 35–43 s window has no accepted outputs. Earlier movement-contaminated data and the final few seconds are excluded from clean-scene metrics. Timing is approximate and sensor stability is not established.",
        '- Near-original live-005 again produces persistent unwanted empty-scene readings, now near **84 cm**, rather than the earlier ~70 cm. The return is not pinned to one hardcoded displayed distance. Position/scene variation changes its apparent peak.',
        '- Shifted live-007 gives **151/151** numeric outputs in 2–17 s, a **78.31 cm** median for the reported 80 cm target, **76.33–79.05 cm** empirical 5th–95th interval, and **1.82 cm conditional MAE**. All 151 outputs in that window are within 5 cm of the reported placement. This is one geometry/placement, not a general error bound.',
        '- Whole live-007 includes one CRC error/sequence gap near startup. Live-006 also has one; live-005 has none. Neither run reaches the long-recording timing cutoff. The observed device/host rate mismatch remains.',
        '- These results strengthen the environmental/geometry dependence diagnosis. They do not identify a specific reflection path or exclude effects from operator movement, small sensor-pose changes, support or cable coupling. Clutter was not restored, so there is no reverse intervention control.',
        '- The shifted target capture occurs after clutter changes. It cannot isolate the effects of sensor relocation versus clutter removal. Nor does it by itself establish the empty-scene behavior at that exact final pose.',
        '- The unwanted ~84 cm empty readout overlaps the intended 80 cm target region. Blacklisting a fixed range or adding a global offset would not provide target identity.', '',
        '## Next work / captures','',
        'No more broad distance sweeps are needed to establish the present failure modes. The exact manipulation times and sensor stability remain unverified; do not score earlier movement as empty false alarms. The acquisition clock mapping/freshness logic remains the next software issue to address; no extra long capture is needed to reproduce it.', '',
        'After that change is frozen, a short empty capture and repeated supported 50/80/100 cm placements at one marked pose in the cleaner setup would test transfer. The same sensor height, orientation and operator position should be maintained. A clutter-restoration reversal would strengthen causal attribution, but is not required to see that this operating scene changed substantially.', '',
        '[Plots](clutter-followup.png) · [Full metrics, spectra, transport and hashes](report.json)', '',
        'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.evaluate_cfar_clutter_followup --root {args.root} --output evidence/new-clutter-followup', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(dict(bin2_drop_db=report['early_to_late_bin2_drop_db'],target=report['windows'][-1]['metrics']),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
