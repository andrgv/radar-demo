"""python -m radar_min: serial capture, empty fit, deterministic replay, live text."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import time
from .core import Config, Baseline, Detector, Continuity, power
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
    parser=Parser();guard=Continuity(config);count=0;rejected=0
    started=time.monotonic();last=started;anchor=None;elapsed=0;previous_ts=None
    with ExitStack() as stack:
        recorder=stack.enter_context(Recorder(output,config,dict(label='live' if detector else 'capture',
            config_fingerprint=config.fingerprint,firmware_identity='unknown; profile ID is not a firmware hash',
            freshness='relative timing only; no firmware handshake',baseline_provenance=detector.baseline.provenance if detector else None)))
        readings=stack.enter_context((Path(output)/'readings.jsonl').open('w'))
        ser=serial_factory(port,2000000,timeout=0.1,write_timeout=1)
        try:
            ser.reset_input_buffer();ser.write(b'B')
            while time.monotonic()-started<seconds and not (stop_event and stop_event.is_set()):
                chunk=ser.read(max(1,min(ser.in_waiting,65536)))
                now=time.monotonic()
                frames=parser.feed(chunk)
                if chunk: recorder.write_transport(chunk,parser)
                for frame in frames:
                    recorder.write(frame);count+=1;last=now
                    if previous_ts is not None: elapsed+=((frame.timestamp_us-previous_ts)&0xffffffff)/1e6
                    previous_ts=frame.timestamp_us
                    if anchor is None: anchor=now
                    drift=abs((now-anchor)-elapsed)
                    reason=guard.check(frame)
                    try: power(frame,config)
                    except ValueError as error: reason=str(error)
                    if drift>0.5: reason='host_sensor_timing_mismatch'
                    # Multiple queued frames are preserved but not displayed as fresh readings.
                    if len(frames)>2 or ser.in_waiting>2*6580: reason='serial_backlog'
                    if detector:
                        reading=detector.update(frame)
                        if reason:
                            detector.clear()
                            reading.update(target_detected=False,range_bin=None,range_m=None,provisional_range_m=None,reason=reason)
                    else:
                        reading=dict(frame_sequence=frame.sequence,reason=reason or 'raw_recorded',target_detected=False,range_m=None)
                    if reason: rejected+=1
                    reading.update(serial=stats(parser),relative_timing_error_s=drift)
                    if observer: observer(frame,reading)
                    emit(reading,readings)
                    if quiet: pass
                    elif detector and sys.stdout.isatty():
                        label=(f"BIN {reading['range_bin']} | provisional {reading['provisional_range_m']:.3f} m"
                               if reading['target_detected'] else 'NO RELIABLE READING')
                        print(f"\r{label} | UNCALIBRATED | {reading['reason']} | gaps {parser.gaps} CRC {parser.bad_crc}    ",end='',flush=True)
                    else:
                        emit({k:v for k,v in reading.items() if k not in ('power','excess_profile_db')})
                if now-last>1:
                    if detector: detector.clear()
                    timeout=dict(target_detected=False,range_m=None,reason='serial_timeout',serial=stats(parser))
                    if observer:observer(None,timeout)
                    emit(timeout,readings)
                    print('\nNO RELIABLE READING: serial timeout',flush=True)
                    raise TimeoutError('No fresh frame for one second; partial recording preserved')
        finally:
            try: ser.write(b'c')
            finally: ser.close()
            summary=dict(frames=count,rejected_frames=rejected,serial=stats(parser),incomplete_tail_bytes=len(parser.buffer))
            (Path(output)/'capture-summary.json').write_text(json.dumps(summary,indent=2))
    if not count: raise ValueError('No frames captured')
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='cmd',required=True)
    fit=sub.add_parser('baseline',help='Fit empty reference; never learns from holdout')
    fit.add_argument('recording');fit.add_argument('output');fit.add_argument('--count',type=int,default=30)
    rp=sub.add_parser('replay');rp.add_argument('recording');rp.add_argument('--baseline',required=True);rp.add_argument('--skip',type=int,default=0)
    gui=sub.add_parser('gui',help='Thin experimental range display with raw recording')
    gui.add_argument('--port',default='/dev/cu.usbmodem103');gui.add_argument('--config',required=True)
    gui.add_argument('--baseline');gui.add_argument('--replay');gui.add_argument('--snapshot')
    for command in ('capture','live'):
        sp=sub.add_parser(command);sp.add_argument('output');sp.add_argument('--port',required=True)
        sp.add_argument('--seconds',type=float,default=60);sp.add_argument('--config',default='configs/range-source-derived.json')
        if command=='live': sp.add_argument('--baseline',required=True)
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
            b=Baseline.load(args.baseline);c,frames,parser=read_recording(args.recording,b.config)
            if not 0<=args.skip<len(frames): raise ValueError('Invalid skip')
            digest=hashlib.sha256((Path(args.recording)/'frames.grd').read_bytes()).hexdigest()
            if digest==b.provenance.get('raw_sha256') and args.skip<b.training_frames:
                raise ValueError('Evaluation overlaps training: use --skip training_count')
            d=Detector(b);hits=0
            for frame in frames[args.skip:]:
                result=d.update(frame);hits+=result['target_detected'];emit(result)
            emit(dict(summary=True,frames=len(frames)-args.skip,detected_frames=hits,serial=stats(parser)),sys.stderr)
        else:
            if not 0<args.seconds<86400: raise ValueError('Seconds must be in (0,86400)')
            c=Config.load(args.config);d=Detector(Baseline.load(args.baseline)) if args.cmd=='live' else None
            if d and d.config.fingerprint!=c.fingerprint: raise ValueError('Baseline/config mismatch')
            stream(args.port,c,args.output,args.seconds,d)
    except (ValueError,OSError,TimeoutError) as error:
        emit(dict(error=str(error),target_detected=False,range_m=None),sys.stderr);return 2
    except KeyboardInterrupt:
        emit(dict(reason='stopped',target_detected=False,range_m=None),sys.stderr);return 130
    return 0


if __name__=='__main__':
    raise SystemExit(main())
