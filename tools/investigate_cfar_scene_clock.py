"""Offline sensor-position and host/device clock investigation; no live changes."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import range_spectrum


def load(path):
    config,frames,_=read_recording(path)
    rows=[json.loads(line) for line in (path/'readings.jsonl').read_text().splitlines()]
    arrivals=[json.loads(line) for line in (path/'arrivals.jsonl').read_text().splitlines()]
    if len(rows)!=len(frames) or len(arrivals)!=len(frames):raise ValueError('Frame/reading/arrival alignment mismatch')
    if not all(r['frame_sequence']==f.sequence==a['sequence'] for r,f,a in zip(rows,frames,arrivals)):raise ValueError('Frame sequence alignment mismatch')
    host=np.array([(a['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9 for a in arrivals])
    sensor=np.array([((f.timestamp_us-frames[0].timestamp_us)&0xffffffff)/1e6 for f in frames])
    return dict(path=path,config=config,frames=frames,rows=rows,host=host,sensor=sensor,
                metadata=json.loads((path/'metadata.json').read_text()))


def spectrum_summary(session,mask):
    profiles=[];rx_profiles=[];nfft=4096
    for i in np.flatnonzero(mask):
        z=range_spectrum(session['frames'][i],session['config'],nfft=nfft)
        p=np.mean(abs(z)**2,axis=0)
        profiles.append(p.mean(axis=1));rx_profiles.append(p)
    profiles=np.array(profiles);rx_profiles=np.array(rx_profiles)
    median=np.median(profiles,axis=0)
    coords=np.arange(len(median))*session['config'].spacing_m*session['config'].samples/nfft
    bin2=int(2*nfft/session['config'].samples)
    search=(coords>=.15)&(coords<=3)
    dominant=float(coords[search][np.argmax(median[search])])
    rows=[session['rows'][i] for i in np.flatnonzero(mask)]
    return dict(dominant_raw_peak_0p15_to_3m_m=dominant,frames=len(rows),saved_presence_frames=sum(r['target_detected'] for r in rows),
        saved_numeric_frames=sum(r['target_detected'] and r.get('experimental_range_m') is not None for r in rows),
        native_bin2_power_db=float(10*np.log10(max(median[bin2],1e-12))),
        per_rx_native_bin2_power_db=(10*np.log10(np.maximum(np.median(rx_profiles[:,bin2,:],axis=0),1e-12))).tolist(),
        spectrum_median_power=median.tolist(),spectrum_coordinates_m=coords.tolist())


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('recordings/gui-20261109-224819-094246'))
    p.add_argument('--prior-labels',type=Path,default=Path('evidence/cfar-long-hold-224819-live003/report.json'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    a=load(args.root/'live-003');b=load(args.root/'live-004')
    if a['config'].fingerprint!=b['config'].fingerprint or a['metadata']['detector']!=b['metadata']['detector']:
        raise ValueError('Configuration or detector changed between positions')
    labels=json.loads(args.prior_labels.read_text())
    empty=[r for r in labels['lap_intervals'] if r['target_m'] is None]
    oldmask=np.zeros(len(a['frames']),dtype=bool)
    windows=[]
    for r in empty:
        oldmask|=(a['host']>=r['start_s'])&(a['host']<r['end_s'])
        windows.append([r['start_s'],r['end_s']])
    newmask=(b['host']>=1)&(b['host']<10)
    original=spectrum_summary(a,oldmask);shifted=spectrum_summary(b,newmask)
    timing=[]
    for name in ['live-001','live-002','live-003','live-004']:
        s=a if name=='live-003' else b if name=='live-004' else load(args.root/name)
        timing.append(dict(recording=name,frames=len(s['frames']),host_span_s=float(s['host'][-1]),sensor_span_s=float(s['sensor'][-1]),
            rate_difference_percent=float((s['sensor'][-1]/s['host'][-1]-1)*100),
            max_recorded_relative_timing_error_s=max(r['relative_timing_error_s'] for r in s['rows'])))
    training=(a['host']>=2)&(a['host']<=20);evaluation=a['host']>20
    slope,offset=np.polyfit(a['host'][training],a['sensor'][training],1)
    residual=a['host']-(a['sensor']-offset)/slope
    clock=dict(fit_host_window_s=[2,20],sensor_seconds_per_host_second=float(slope),offset_sensor_s=float(offset),
        evaluation_host_window_s=[20,float(a['host'][-1])],evaluation_frames=int(evaluation.sum()),
        residual_host_seconds_min_p05_median_p95_max=np.percentile(residual[evaluation],[0,5,50,95,100]).tolist(),
        old_max_recorded_error_s=max(r['relative_timing_error_s'] for r in a['rows']),
        note='Diagnostic affine mapping only; no live gating changes. Initial capture latency, absolute age, gradual backlog and actual hardware clock source remain unverified.')
    report=dict(schema=1,config_fingerprint=a['config'].fingerprint,detector=a['metadata']['detector'],
        raw_sha256={str(s['path']):hashlib.sha256((s['path']/'frames.grd').read_bytes()).hexdigest() for s in [a,b]},
        scene_labels=dict(original_empty_host_windows_s=windows,shifted_empty_host_window_s=[1,10],sensor_shift_m_approx=.2,
                          limitation='One position change; no return-to-original control. Orientation, support/cable pose, temperature and exact scene geometry were not instrumented.'),
        original_empty=original,shifted_empty=shifted,whole_shifted_capture=dict(frames=len(b['rows']),duration_sensor_s=float(b['sensor'][-1]),
            duration_host_s=float(b['host'][-1]),presence_frames=sum(r['target_detected'] for r in b['rows']),
            transport=json.loads((b['path']/'capture-summary.json').read_text())),
        bin2_drop_db=original['native_bin2_power_db']-shifted['native_bin2_power_db'],
        timing_captures=timing,clock_diagnostic=clock,
        source_sha256={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in map(Path,[
            'radar_min/__main__.py','radar_min/core.py','tools/investigate_cfar_scene_clock.py',
            'bsps/TARGET_APP_CYSBSYSKIT-DEV-01/config/GeneratedSource/cycfg_system.c',
            'experiments/qualification/main.c',
            '../mtb_shared/mtb-hal-cat1/release-v2.7.4/source/cyhal_timer.c'])},
        reference_urls=[
            'https://www.infineon.com/assets/row/public/documents/30/49/infineon-bgt60cutr13aip-datasheet-en.pdf',
            'https://infineon.github.io/psoc6pdl/pdl_api_reference_manual/html/group__group__sysclk__fll.html'])
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(10,9),layout='constrained')
    for s,label in [(original,'Original position: four empty interiors'),(shifted,'Shifted ~20 cm: empty 1–10 s')]:
        axes[0].plot(s['spectrum_coordinates_m'],10*np.log10(np.maximum(s['spectrum_median_power'],1e-12)),label=label)
    axes[0].axvline(2*a['config'].spacing_m,color='gray',ls=':',lw=1)
    axes[0].set(xlim=(0,2.5),ylabel='Median raw power (dB)',xlabel='Nominal beat coordinate (m)',title='Position-dependent empty-scene spectrum · no subtraction');axes[0].legend(fontsize=8)
    axes[1].plot(a['host'],a['sensor']-a['host'],label='Unmapped clock difference')
    axes[1].axhline(.5,color='red',ls='--',label='Current live rejection threshold')
    axes[1].set(ylabel='Elapsed difference (s)',xlabel='Host time (s)');axes[1].legend(fontsize=8)
    axes[2].plot(a['host'],residual*1000)
    axes[2].axvspan(2,20,color='gray',alpha=.2,label='Clock fit window')
    axes[2].set(ylabel='Mapped residual (ms)',xlabel='Host time (s)',title='Clock mapping fitted before 20 s; later data only evaluated');axes[2].legend(fontsize=8)
    fig.savefig(args.output/'scene-and-clock.png',dpi=150);plt.close(fig)
    lines=['# Sensor-position and clock investigation','',
        'Compared live-003 original-position empty interiors with the all-empty live-004 after the user moved the sensor approximately 20 cm sideways, farther from side clutter. Configuration and detector metadata match exactly. No live code, firmware, thresholds or recordings changed.','',
        '## Scene-dependent unwanted peak','',
        f"- live-004: **0/{len(b['rows'])} detections** over {b['sensor'][-1]:.1f} sensor seconds ({b['host'][-1]:.2f} host seconds), with clean transport.",
        f"- Around native bin 2 (~70 cm), median raw power falls from **{original['native_bin2_power_db']:.2f} dB** to **{shifted['native_bin2_power_db']:.2f} dB**: a **{report['bin2_drop_db']:.2f} dB** decrease. Units are ADC power references, not dBm.",
        f"- The dominant raw spectral maximum over 0.15–3 m changes from {original['dominant_raw_peak_0p15_to_3m_m']:.2f} to {shifted['dominant_raw_peak_0p15_to_3m_m']:.2f} m. The latter is beyond the current detection mask (native bins 1–4, centers approximately 0.35–1.39 m). Zero detections means no accepted return inside that mask, not absence of room reflections. These maxima are not established physical object distances.",
        '- This is strong evidence of position/scene dependence. It does not isolate the side clutter: translating the sensor also changes multipath phases, support/cable geometry and possibly orientation. A purely invariant electronics artifact is less consistent with the change, but electronics/near-field coupling is not excluded.',
        '- The sensor datasheet specifies a broad 120° × 90° field of view. Off-axis objects can contribute even when outside the forward centerline; the FoV is not a hard cutoff or proof of a particular path.', '',
        '## Timing findings','',
        '| Capture | Host span (s) | Sensor span (s) | Endpoint rate difference |', '|---|---:|---:|---:|']
    for r in timing:lines.append(f"| {r['recording']} | {r['host_span_s']:.3f} | {r['sensor_span_s']:.3f} | {r['rate_difference_percent']:.3f}% |")
    lines+=['',
        f"A diagnostic clock mapping fitted using only 2–20 host seconds of live-003 gives sensor seconds = **{slope:.9f} × host seconds {offset:+.6f}**. On later data, maximum absolute mapped residual is **{max(abs(residual[evaluation]))*1000:.1f} ms**. This is much smaller than the current unmapped elapsed discrepancy, which grows to about one second.", '',
        'The checked-in acquisition gate compares elapsed host and device times one-to-one, taking absolute difference and rejecting above 0.5 s. It does not estimate rate difference. Sensor time runs ahead of host time here, which is not the signature expected from growing delivery delay alone.', '',
        'Source audit: qualification firmware requests a 1 MHz HAL timer, writes the raw timer count as the frame timestamp, and schedules captures 100,000 counts apart. The BSP configures an IMO-derived FLL (nominal 100 MHz); HAL frequency setup accepts a 2% frequency tolerance and stores its computed clock rate internally. Success requesting 1 MHz does not prove an independently calibrated physical microsecond. Infineon documents that FLL output inherits reference-clock accuracy.', '',
        '**Clock-scale mismatch is the leading explanation, not proven hardware calibration.** The running clock registers and timer frequency were not read back or measured. Divider/reference error, clock interpretation and timing instrumentation still need distinction. Host wall-clock arrivals support the same discrepancy seen by the live monotonic-time check.', '',
        'A software remedy should represent a bounded host/device clock mapping and separately reject excess latency, stalled streams, queued frames, corruption and restarts. It must not simply increase the threshold or disable freshness checks. A fitted model cannot prove absolute age or distinguish every gradual backlog from clock drift. MCU timer scale also does not establish radar ADC/ramp calibration or explain the distance errors by itself.', '',
        '## Additional captures that would help','',
        '1. Return the sensor to its original marked position, height and orientation; leave the target absent and record 15–20 seconds while stepped away. Recovery of the ~70 cm component would complete an A → B → A position control.',
        '2. At the shifted position, keep the supported box at a measured 80 cm for 20–30 seconds with the operator out of the beam. A quiet empty scene alone does not establish that useful target detection/range accuracy is retained.',
        '3. To isolate the side clutter specifically, if practical keep the sensor fixed and change only the suspected clutter, then restore it. A sensor translation alone cannot identify which object/path causes the component.', '',
        'No further generic long captures are needed to demonstrate the timing failure. Actual timer/clock readback or an independent timing measurement would identify its physical source more directly than more scene sweeps. No hardware programming or configuration changes were performed.', '',
        '[Plots](scene-and-clock.png) · [Full profiles, timing metrics and hashes](report.json)', '',
        'Sources: [sensor datasheet](https://www.infineon.com/assets/row/public/documents/30/49/infineon-bgt60cutr13aip-datasheet-en.pdf), [Infineon FLL documentation](https://infineon.github.io/psoc6pdl/pdl_api_reference_manual/html/group__group__sysclk__fll.html).', '',
        'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.investigate_cfar_scene_clock --root {args.root} --prior-labels {args.prior_labels} --output evidence/new-scene-clock-investigation', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(dict(bin2_drop_db=report['bin2_drop_db'],shifted_detections=report['whole_shifted_capture']['presence_frames'],clock=clock),indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
