"""python -m radar_min: serial capture, empty fit, deterministic replay, live text."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import time
from .core import Config, Baseline, Detector, Continuity, power
from .clock_sync import ClockSync
from radar.protocol import Parser
from radar.storage import Recorder, replay


def emit(value, stream=None):
    print(json.dumps(value,allow_nan=False),file=stream or sys.stdout,flush=True)


def stats(parser):
    return {k:getattr(parser,k) for k in ('gaps','bad_crc','bad_headers','restarts','discarded_bytes')}


def read_recording(path, config=None):
    path=Path(path); c=Config.load(path/'config.json')
    if config is not None and c.fingerprint!=config.fingerprint:
        raise ValueError('Recording/baseline configuration mismatch')
    parser=Parser(); frames=list(replay(path,parser))
    if not frames: raise ValueError('No complete frames')
    if parser.bad_crc or parser.bad_headers or parser.buffer or parser.discarded_bytes:
        raise ValueError('Damaged recording: '+json.dumps(stats(parser)))
    return c,frames,parser


def stream(port,config,output,seconds,detector=None,serial_factory=None,observer=None,stop_event=None,quiet=False):
    """Original bytes are saved before DSP; processing never gates raw recording.

    Relative device/host timing catches backlog growth, not absolute sensor age.
    Startup flush cannot prove absolute freshness without a firmware handshake.
    """
    if serial_factory is None:
        import serial
        serial_factory=serial.Serial
    parser=Parser();guard=Continuity(config);count=0;rejected=0;received_bytes=0
    started=time.monotonic();last=started;clock=ClockSync()
    with ExitStack() as stack:
        recorder=stack.enter_context(Recorder(output,config,dict(label='live' if detector else 'capture',
            config_fingerprint=config.fingerprint,firmware_identity='unknown; profile ID is not a firmware hash',
            freshness='relative timing only; no firmware handshake',clock_sync=clock.metadata(),baseline_provenance=detector.baseline.provenance if detector and detector.baseline else None,
            detector=getattr(detector, "metadata", None))))
        readings=stack.enter_context((Path(output)/'readings.jsonl').open('w'))
        ser=serial_factory(port,2000000,timeout=0.1,write_timeout=1)
        try:
            ser.reset_input_buffer();ser.write(b'B')
            while time.monotonic()-started<seconds and not (stop_event and stop_event.is_set()):
                chunk=ser.read(max(1,min(ser.in_waiting,65536)))
                received_bytes+=len(chunk)
                now=time.monotonic()
                frames=parser.feed(chunk)
                if chunk: recorder.write_transport(chunk,parser)
                for frame in frames:
                    recorder.write(frame);count+=1;last=now
                    continuity_reason=guard.check(frame)
                    reason=continuity_reason
                    try: power(frame,config)
                    except ValueError as error: reason=str(error)
                    # Do not learn clock rate from queued, invalid or discontinuous frames.
                    backlog=len(frames)>2 or ser.in_waiting>2*6580
                    sync=clock.update(frame.timestamp_us,now,
                        eligible=reason is None and len(frames)==1 and not backlog,
                        restart=continuity_reason=='restart_or_duplicate')
                    if sync['reason']: reason=sync['reason']
                    if backlog: reason='serial_backlog'
                    if detector:
                        reading=detector.update(frame)
                        if reason:
                            detector.clear()
                            reading.update(target_detected=False,range_bin=None,range_m=None,provisional_range_m=None,experimental_range_m=None,reason=reason)
                    else:
                        reading=dict(frame_sequence=frame.sequence,reason=reason or 'raw_recorded',target_detected=False,range_m=None)
                    if reason: rejected+=1
                    reading.update(serial=stats(parser),relative_timing_error_s=abs(sync['residual_s']),
                        raw_relative_timing_error_s=abs(sync['raw_residual_s']),clock_sync=sync)
                    if observer: observer(frame,reading)
                    emit(reading,readings)
                    if quiet: pass
                    elif detector and sys.stdout.isatty():
                        value=reading.get('experimental_range_m') if reading.get('algorithm')=='range-ca-cfar-v2' else reading.get('provisional_range_m')
                        label=(f"BIN {reading['range_bin']} | experimental {value:.3f} m" if value is not None else 'PRESENCE; DISTANCE UNRESOLVED') if reading['target_detected'] else 'NO RELIABLE READING'
                        print(f"\r{label} | UNCALIBRATED | {reading['reason']} | gaps {parser.gaps} CRC {parser.bad_crc}    ",end='',flush=True)
                    else:
                        emit({k:v for k,v in reading.items() if k not in ('power','excess_profile_db')})
                if now-last>1:
                    if detector: detector.clear()
                    if not received_bytes:
                        detail='No serial bytes received from the board. Close other serial readers, reconnect board USB, then retry.'
                    elif not count:
                        detail=f'Received {received_bytes} serial bytes but no complete radar frame. Check firmware/protocol and port; raw bytes preserved.'
                    else:
                        detail=f'Stream stalled after {count} frames: no fresh frame for one second. Partial recording preserved.'
                    timeout=dict(target_detected=False,range_m=None,reason='serial_timeout',serial=stats(parser),received_bytes=received_bytes,frames=count,detail=detail)
                    if observer:observer(None,timeout)
                    emit(timeout,readings)
                    print('\nNO RELIABLE READING: serial timeout',flush=True)
                    raise TimeoutError(detail)
        finally:
            try: ser.write(b'c')
            finally: ser.close()
            summary=dict(frames=count,rejected_frames=rejected,serial=stats(parser),incomplete_tail_bytes=len(parser.buffer),received_bytes=received_bytes)
            (Path(output)/'capture-summary.json').write_text(json.dumps(summary,indent=2))
    if not count: raise ValueError('No frames captured')
    return summary


def detector_options(parser):
    parser.add_argument('--detector', choices=['baseline', 'cfar'], default='baseline')
    parser.add_argument('--cfar-guard', type=int, default=2, help='Guard bins per side')
    parser.add_argument('--cfar-training', type=int, default=8, help='Training bins per side')
    parser.add_argument('--cfar-min-training', type=int, default=8, help='Minimum total references at edges')
    parser.add_argument('--cfar-factor', type=float, default=6.0, help='Empirical linear-power multiplier, not a Pfa')


def make_detector(args, config, baseline=None):
    if getattr(args, 'detector', 'baseline') == 'cfar':
        from .cfar import CfarConfig, CfarDetector
        if getattr(args, 'estimator', None) == 'associated':
            raise ValueError('--estimator associated requires the baseline detector; CFAR uses its own raw-spectrum peak estimator')
        if args.baseline:
            raise ValueError('--baseline cannot be combined with --detector cfar')
        return CfarDetector(config, CfarConfig(args.cfar_guard, args.cfar_training,
                                             args.cfar_min_training, args.cfar_factor))
    baseline = baseline if baseline is not None else Baseline.load(args.baseline) if args.baseline else None
    if baseline is None:
        raise ValueError('Baseline detector requires --baseline (or capture empty in the GUI)')
    if baseline.config.fingerprint != config.fingerprint:
        raise ValueError('Baseline/config mismatch')
    return Detector(baseline)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    fit=sub.add_parser('baseline',help='Fit empty reference; never learns from holdout')
    fit.add_argument('recording');fit.add_argument('output');fit.add_argument('--count',type=int,default=30)
    rp=sub.add_parser('replay');rp.add_argument('recording');rp.add_argument('--baseline');detector_options(rp);rp.add_argument('--skip',type=int,default=0)
    gui=sub.add_parser('gui',help='Thin experimental range display with raw recording')
    gui.add_argument('--estimator',choices=['fixed','associated'],default='fixed',help='Baseline mode only; CFAR uses a baseline-free fine peak')
    gui.add_argument('--port',default='/dev/cu.usbmodem103');gui.add_argument('--config',required=True)
    detector_options(gui)
    gui.add_argument('--baseline');gui.add_argument('--replay');gui.add_argument('--snapshot')
    for command in ('capture','live'):
        sp=sub.add_parser(command);sp.add_argument('output');sp.add_argument('--port',required=True)
        sp.add_argument('--seconds',type=float,default=60);sp.add_argument('--config',default='configs/range-source-derived.json')
        if command=='live':
            sp.add_argument('--baseline');detector_options(sp)
    args=p.parse_args(argv)
    try:
        if args.cmd=='gui':
            from .gui import launch
            return launch(args)
        elif args.cmd=='baseline':
            c,frames,_=read_recording(args.recording)
            if not 20<=args.count<=len(frames): raise ValueError('Training count must be 20..recording length')
            raw=Path(args.recording)/'frames.grd'
            Baseline.fit(frames[:args.count],c,dict(recording=str(Path(args.recording).resolve()),
                raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),training_count=args.count)).save(args.output)
            emit(dict(training_frames=args.count,reserved_frames=len(frames)-args.count,calibrated=False))
        elif args.cmd=='replay':
            b=Baseline.load(args.baseline) if args.baseline else None
            c,frames,parser=read_recording(args.recording,b.config if b else None)
            if not 0<=args.skip<len(frames): raise ValueError('Invalid skip')
            digest=hashlib.sha256((Path(args.recording)/'frames.grd').read_bytes()).hexdigest()
            if b and digest==b.provenance.get('raw_sha256') and args.skip<b.training_frames:
                raise ValueError('Evaluation overlaps training: use --skip training_count')
            d=make_detector(args,c,b);hits=0
            for frame in frames[args.skip:]:
                result=d.update(frame);hits+=result['target_detected'];emit(result)
            emit(dict(summary=True,frames=len(frames)-args.skip,detected_frames=hits,serial=stats(parser)),sys.stderr)
        else:
            if not 0<args.seconds<86400: raise ValueError('Seconds must be in (0,86400)')
            c=Config.load(args.config);d=make_detector(args,c) if args.cmd=='live' else None
            if d and d.config.fingerprint!=c.fingerprint: raise ValueError('Baseline/config mismatch')
            stream(args.port,c,args.output,args.seconds,d)
    except (ValueError,OSError,TimeoutError) as error:
        emit(dict(error=str(error),target_detected=False,range_m=None),sys.stderr);return 2
    except KeyboardInterrupt:
        emit(dict(reason='stopped',target_detected=False,range_m=None),sys.stderr);return 130
    return 0


if __name__=='__main__':
    raise SystemExit(main())
