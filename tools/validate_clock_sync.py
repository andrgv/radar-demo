"""Replay saved host/device timelines through the new clock gate; no raw edits."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
from radar_min.__main__ import read_recording
from radar_min.core import Continuity,power
from radar_min.clock_sync import ClockSync


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('recordings/gui-20261109-224819-094246'))
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    sessions=[];timelines=[]
    for name in [f'live-{i:03}' for i in range(1,8)]:
        path=args.root/name;config,frames,_=read_recording(path)
        arrivals=[json.loads(l) for l in (path/'arrivals.jsonl').read_text().splitlines()]
        old=[json.loads(l) for l in (path/'readings.jsonl').read_text().splitlines()]
        if len(frames)!=len(arrivals) or len(frames)!=len(old):raise ValueError('Alignment mismatch')
        guard=Continuity(config);clock=ClockSync();updates=[];gates=[]
        for frame,arrival,reading in zip(frames,arrivals,old):
            if frame.sequence!=arrival['sequence'] or frame.sequence!=reading['frame_sequence']:raise ValueError('Sequence alignment mismatch')
            host=(arrival['host_unix_ns']-arrivals[0]['host_unix_ns'])/1e9
            continuity_reason=guard.check(frame)
            reason=continuity_reason
            try:power(frame,config)
            except ValueError as error:reason=str(error)
            backlog=reading['reason']=='serial_backlog'
            sync=clock.update(frame.timestamp_us,host,eligible=reason is None and not backlog,restart=continuity_reason=='restart_or_duplicate')
            if sync['reason']:reason=sync['reason']
            if backlog:reason='serial_backlog'
            updates.append(sync);gates.append(reason)
            timelines.append(dict(recording=name,sequence=frame.sequence,host_s=host,old_reason=reading['reason'],new_gate_reason=reason,clock=sync))
        frozen=[r for r in updates if r['state']=='frozen']
        sessions.append(dict(recording=str(path),frames=len(frames),raw_sha256=hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest(),
            old_timing_rejections=sum(r['reason']=='host_sensor_timing_mismatch' for r in old),
            new_clock_rejections=sum(r['reason'] is not None for r in updates),
            new_other_gate_reasons=dict(Counter(r for r in gates if r)),
            final_clock=updates[-1],max_corrected_error_after_freeze_s=max((abs(r['residual_s']) for r in frozen),default=None)))
    args.output.mkdir(parents=True,exist_ok=False)
    report=dict(clock_policy=ClockSync().metadata(),sessions=sessions,
        validation_limit='Uses saved wall-clock frame arrival times as a proxy for read-loop monotonic times. Actual transport backlog flags are retained, but exact original chunk sizes are not reconstructed. Synthetic stream tests exercise the real acquisition path separately.',
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['radar_min/clock_sync.py','radar_min/__main__.py','tools/validate_clock_sync.py']})
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (args.output/'timelines.jsonl').open('w') as f:
        for row in timelines:f.write(json.dumps(row,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[r for r in timelines if r['recording']=='live-003']
    fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
    axes[0].plot([r['host_s'] for r in rows],[abs(r['clock']['raw_residual_s']) for r in rows],label='Unmapped elapsed difference')
    axes[0].plot([r['host_s'] for r in rows],[abs(r['clock']['residual_s']) for r in rows],label='Corrected difference')
    axes[0].axhline(.5,color='red',ls='--',label='Unchanged rejection threshold')
    axes[0].set(ylabel='Absolute timing error (s)',title='Saved long capture · raw data unchanged');axes[0].legend(fontsize=8)
    axes[1].plot([r['host_s'] for r in rows],[r['clock']['host_seconds_per_device_second'] for r in rows])
    axes[1].set(xlabel='Host arrival elapsed (s)',ylabel='Host seconds / device second',title='One startup fit; mapping freezes instead of adapting to later delays')
    fig.savefig(args.output/'clock-fix.png',dpi=150);plt.close(fig)
    lines=['# Bounded startup clock mapping: validation','',
        'The live capture path now learns a relative clock rate during startup and freezes it. No scene baseline, threshold tuning, firmware change or edits to original recordings.','',
        '| Capture | Frames | Old timing rejections | New clock rejections | Final state | Maximum error after freeze |',
        '|---|---:|---:|---:|---|---:|']
    for r in sessions:
        error=r['max_corrected_error_after_freeze_s']
        lines.append(f"| {Path(r['recording']).name} | {r['frames']} | {r['old_timing_rejections']} | {r['new_clock_rejections']} | {r['final_clock']['state']} | {f'{error*1000:.1f} ms' if error is not None else 'not yet fitted'} |")
    lines+=['','## Live policy','',
        '- Fit an affine host-time/device-time mapping after at least 20 device seconds and 100 eligible samples. Short captures retain the original nominal-rate check.',
        '- Only valid, continuous, single-frame, non-backlogged arrivals can train it. Require rate within ±2% of nominal, startup maximum residual ≤100 ms and 95th-percentile residual ≤50 ms.',
        '- Freeze once fitted. No ongoing rate adaptation, reanchoring, persisted machine-specific constant or latency forgiveness. The progress-error threshold remains 0.5 s.',
        '- An invalid mapping, a duplicate/restarted device timestamp, impossible rate, unstable fit, unavailable fit after 30 device seconds, backwards host time or excessive corrected progress error invalidates timing until a new capture is explicitly started.',
        '- Existing frame continuity, ADC validation, serial-backlog rejection, one-second timeout and raw recording remain active. A rejected reading clears presence and both coarse/fine coordinates.',
        '- Logs retain the raw elapsed difference plus corrected error, mapping state, rate and fit count. Metadata records policy. No old readings are rewritten.', '',
        '## Tests and limitations','',
        '- Synthetic tests cover one-hour positive/negative 0.7% rate differences, a 0.6 s late delivery step, a growing delay after freeze, out-of-bound rate, unstable startup, timestamp wrap, restart/duplicate, backwards host time and ineligible fit samples.',
        '- Real-stream integration tests exercise 1,500 recorded frames with skew, plus an injected delay that clears the fine readout while retaining raw bytes and closing serial. A queued burst remains rejected and does not train the fit. Existing timeout/corruption/continuity tests also run.',
        '- Saved-capture replay uses frame wall-clock arrivals as a proxy for reader monotonic time; it cannot reconstruct every original read chunk. Actual queue flags are retained. This validates relative timing behavior, not restored historical live correctness or absolute sensor age.',
        '- During startup, a sufficiently smooth latency ramp can be indistinguishable from clock skew within the allowed rate range. A constant initial backlog is also unobservable from relative timing. Absolute freshness still needs firmware identity/start acknowledgment and clock verification.',
        '- A frozen estimate deliberately rejects later rate changes large enough to exceed the progress limit; it does not continually learn away stalls. New live hardware validation remains to be performed after restarting the app.', '',
        '[Timing plot](clock-fix.png) · [Report/policy/source hashes](report.json) · [Per-frame gate decisions](timelines.jsonl)', '',
        'Reproduce into a new directory:', '', '```sh',
        f'MPLCONFIGDIR=/tmp/radar-mpl .venv/bin/python -m tools.validate_clock_sync --root {args.root} --output evidence/new-clock-sync-validation',
        'QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests_min -v', '```','']
    (args.output/'README.md').write_text('\n'.join(lines))
    print(json.dumps(sessions,indent=2))
    return 0


if __name__=='__main__':raise SystemExit(main())
