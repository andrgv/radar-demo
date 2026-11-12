"""Audit a saved clock rejection and optionally benchmark replay-only GUI drawing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from radar_min.__main__ import read_recording, range_doppler_options
from radar_min.clock_sync import ClockSync


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording',type=Path,default=Path('recordings/rd-gui-20261111-132433-610820/live-001'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--benchmark-gui',action='store_true',help='Offscreen replay only; never opens serial')
    args=parser.parse_args()
    _,frames,_=read_recording(args.recording)
    rows=[json.loads(x) for x in (args.recording/'readings.jsonl').read_text().splitlines()]
    if [r['frame_sequence'] for r in rows]!=[f.sequence for f in frames]:
        raise ValueError('Frame/output alignment mismatch')
    if any(r['serial']['gaps'] or r['serial']['bad_crc'] for r in rows):
        raise ValueError('This audit expects an ungapped capture')
    sync=ClockSync();replayed=[]
    for frame,row in zip(frames,rows):
        # Use the original monotonic timestamp domain, not disk/wall arrival time.
        result=sync.update(frame.timestamp_us,row['clock_sync']['host_elapsed_s'])
        if result['reason']!=row['clock_sync']['reason']:
            raise ValueError('Clock replay differs from saved decision')
        replayed.append(result)
    index=next(i for i,r in enumerate(replayed) if r['state']=='invalid')
    candidate=replayed[index]['fit_diagnostics']
    report=dict(recording=str(args.recording),frames=len(frames),first_rejection_index=index,
        first_rejection_sequence=frames[index].sequence,first_rejection_device_elapsed_s=replayed[index]['device_elapsed_s'],
        reasons=dict(Counter(r['reason'] for r in rows)),fit=candidate,
        clock_decisions_reproduced=True,clock_policy=sync.metadata(),
        capture_summary=json.loads((args.recording/'capture-summary.json').read_text()),
        startup_processing_ms_p50_p95_max=np.percentile([r['processing_ms'] for r in rows[:index]],[50,95,100]).tolist(),
        source_sha256={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in
                       ('radar_min/rd_gui.py','radar_min/clock_sync.py','tools/diagnose_joint_timing.py')},
        raw_sha256=hashlib.sha256((args.recording/'frames.grd').read_bytes()).hexdigest(),
        interpretation='Original startup jitter rejection reproduces with unchanged policy. GUI contention is a plausible contributor, not a proven exclusive cause. Lower display workload cannot retrospectively validate the rejected capture; physical live retry remains necessary.')
    if args.benchmark_gui:
        from PyQt6 import QtWidgets
        from radar.qt_platform import staged_platform_plugins
        from radar_min.rd_gui import Window
        options=argparse.ArgumentParser();range_doppler_options(options,mode=False)
        gui=options.parse_args([])
        gui.config=None;gui.port=None;gui.replay=str(args.recording);gui.snapshot=None;gui.view_range_bins=8
        with staged_platform_plugins():
            app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
            window=Window(gui);window.timer.stop();window.show();app.processEvents()
            for frame in frames[:10]:window.processor.update(frame)
            elapsed=[]
            for frame in frames[10:40]:
                reading=window.processor.update(frame)
                start=time.perf_counter()
                window.render(reading,window.processor.snapshot,True);app.processEvents()
                elapsed.append((time.perf_counter()-start)*1000)
            report['current_gui_render_ms_p50_p95_max']=np.percentile(elapsed,[50,95,100]).tolist()
            window.close()
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x=np.array([r['clock_sync']['device_elapsed_s'] for r in rows])
    y=np.array([r['clock_sync']['host_elapsed_s'] for r in rows])
    residual=y-(candidate['candidate_offset_s']+candidate['candidate_rate']*x)
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained')
    ax.plot(x,residual*1000,'.',ms=3)
    ax.axvline(x[index],color='red',ls='--',label='Original fit rejected; subsequent readouts cleared')
    ax.axhline(50,color='gray',ls=':',label='50 ms startup p95 criterion (not a per-frame threshold)')
    ax.set(xlabel='Device elapsed seconds',ylabel='Residual to rejected candidate fit (ms)',title='Recorded relative timing; fit shown for diagnosis only')
    ax.legend(fontsize=8);fig.savefig(args.output/'timing.png',dpi=150);plt.close(fig)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
