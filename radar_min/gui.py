"""Thin Qt viewer. Acquisition and raw recording run independently of redraws."""
import hashlib
import json
import queue
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import numpy as np
from PyQt6 import QtCore,QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from .core import Config,Baseline,Detector
from .__main__ import stream,read_recording
from tools.fit_range_signal import ToneFit,traces


VALID_REASONS={'spectral_change_uncalibrated','checking_persistence','ambiguous_separate_peak','no_candidate_above_noise'}


class Estimate:
    def __init__(self,baseline,mode='fixed'):
        self.mode=mode
        self.c=baseline.config
        path=Path(baseline.provenance['recording'])
        if hashlib.sha256((path/'frames.grd').read_bytes()).hexdigest()!=baseline.provenance['raw_sha256']:
            raise ValueError('Empty recording hash changed')
        _,frames,_=read_recording(path,self.c)
        self.reference=np.mean([traces(f,self.c) for f in frames[:baseline.training_frames]],axis=0)
        self.fitter=ToneFit(self.c)
        if mode=='associated':
            from .associated_fit import AssociatedFit
            self.associated=AssociatedFit(self.c)

    def enrich(self,frame,reading):
        reading['experimental_range_m']=None
        reading['experimental_estimator']='fixed-empty-waveform-single-tone; uncalibrated'
        if frame is not None and reading.get('reason') in VALID_REASONS:
            result=self.fitter.fit(traces(frame,self.c)-self.reference)
            reading['experimental_range_m']=result['range_m']
            reading['fit_residual_fraction']=result['residual_fraction']
            reading['fit_boundary']=result['boundary']
            reading['fit_near_optimal_width_m']=result['near_optimal_width_m']
            if self.mode=='associated':
                reading['unrestricted_fit_range_m']=result['range_m']
                associated=self.associated.fit_associated(traces(frame,self.c)-self.reference,reading['candidate_bin'],reading.get('qualified_bins'))
                reading['experimental_range_m']=associated['range_m']
                reading['experimental_estimator']='associated-local-tone-v3; uncalibrated'
                reading['associated_fit']=associated


def format_distance(meters):
    return f'{meters*100:.1f} cm / {meters/0.0254:.1f} in'


def display_values(reading,fresh):
    if not fresh:return '—','No fresh reading','—','—'
    candidate=reading.get('experimental_range_m')
    accepted=range_displayable(reading)
    distance=format_distance(candidate) if accepted else '—'
    detail=(f'{format_distance(candidate)} · candidate only' if candidate is not None and not accepted else 'Experimental estimate · uncalibrated')
    if reading.get('fit_boundary'):
        detail += ' · fit at search limit; distance unresolved'
    elif candidate is None and reading.get('associated_fit'):
        detail='Distance unresolved · '+reading['associated_fit']['reason']
    strength=reading.get('excess_db')
    strength=f'{strength:+.1f} dB' if strength is not None else '—'
    return distance,detail,strength,reading.get('reason','No reading')


def range_displayable(reading):
    # A constrained optimum at the search endpoint does not resolve distance.
    # Presence remains a separate recorded fact; keep the raw fitted candidate.
    return (reading.get('target_detected',False)
            and reading.get('experimental_range_m') is not None
            and not reading.get('fit_boundary',False))


class Window(QtWidgets.QMainWindow):
    def __init__(self,args):
        super().__init__();self.args=args;self.c=Config.load(args.config)
        self.baseline=Baseline.load(args.baseline) if args.baseline else None
        if self.baseline and self.baseline.config.fingerprint!=self.c.fingerprint:raise ValueError('Baseline/config mismatch')
        if args.replay and not self.baseline:raise ValueError('Replay requires --baseline')
        self.thread=None;self.stop=threading.Event();self.events=queue.SimpleQueue();self.latest=None;self.last_seen=None
        self.closing=False;self.history=deque(maxlen=300);self.lock=threading.Lock();self.t0=time.monotonic();self.counter=0
        self.root=Path('recordings')/('gui-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        self.setWindowTitle('Wavvy · experimental range');self.resize(960,720)
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget);self.setCentralWidget(widget)
        title=QtWidgets.QLabel('Wavvy — range experiment');title.setStyleSheet('font-size: 23px; font-weight: bold');layout.addWidget(title)
        layout.addWidget(QtWidgets.QLabel(f'Profile {self.c.profile_id:#x} · {"REPLAY" if args.replay else args.port} · {args.estimator} estimator · Not calibrated'))
        self.distance=QtWidgets.QLabel('—');self.distance.setStyleSheet('font-size: 48px; font-weight: bold');layout.addWidget(self.distance)
        self.detail=QtWidgets.QLabel('Capture an empty background, then start live.');layout.addWidget(self.detail)
        self.strength=QtWidgets.QLabel('Signal change vs empty: —');layout.addWidget(self.strength)
        self.status=QtWidgets.QLabel('Idle');self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=QtWidgets.QHBoxLayout();layout.addLayout(buttons)
        self.empty=QtWidgets.QPushButton('Box removed: capture empty (10 s)');self.empty.clicked.connect(lambda:self.start(True));buttons.addWidget(self.empty)
        self.live=QtWidgets.QPushButton('Start replay' if args.replay else 'Start live + record');self.live.clicked.connect(lambda:self.start(False));buttons.addWidget(self.live)
        self.stop_button=QtWidgets.QPushButton('Stop');self.stop_button.clicked.connect(self.stop.set);buttons.addWidget(self.stop_button)
        self.figure=Figure(figsize=(9,3),layout='constrained');self.canvas=FigureCanvasQTAgg(self.figure);layout.addWidget(self.canvas)
        self.profile,self.trace=self.figure.subplots(1,2)
        self.line,=self.profile.plot([],[],color='#167d8d');self.profile.axhline(0,color='gray',lw=.5)
        self.profile.set(xlabel='Nominal distance coordinate (m)',ylabel='Power change vs empty (dB)',xlim=(0,1.5),ylim=(-20,30))
        self.track,=self.trace.plot([],[],color='#167d8d',marker='.',ms=3);self.trace.set(xlabel='Elapsed seconds',ylabel='Accepted experimental estimate (cm)',ylim=(0,160))
        self.saved=QtWidgets.QLabel('All raw frames saved during live runs. dB is a power ratio to the empty reference, not dBm or calibrated SNR.');self.saved.setWordWrap(True);layout.addWidget(self.saved)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(100);self.controls(False)

    def controls(self,busy):
        self.empty.setEnabled(not busy and not self.args.replay);self.live.setEnabled(not busy and self.baseline is not None);self.stop_button.setEnabled(busy)

    def start(self,empty):
        if self.thread and self.thread.is_alive():return
        self.stop.clear();self.latest=None;self.last_seen=None;self.history.clear();self.t0=time.monotonic();self.controls(True)
        self.counter+=1;output=self.root/f'{"empty" if empty else "live"}-{self.counter:03d}'
        self.status.setText('Step away: waiting 5 seconds, then capturing empty for 10 seconds.' if empty else 'Starting…')
        self.saved.setText('Replay: '+self.args.replay if self.args.replay else 'Recording: '+str(output.resolve()))
        def work():
            try:
                estimator=Estimate(self.baseline,self.args.estimator) if not empty else None
                def observe(frame,reading):
                    if estimator:estimator.enrich(frame,reading)
                    stamp=time.monotonic()
                    value=reading.get('experimental_range_m')
                    with self.lock:
                        self.latest=(stamp,dict(reading))
                        self.history.append((stamp-self.t0,value*100 if range_displayable(reading) else np.nan))
                if self.args.replay:
                    _,frames,_=read_recording(Path(self.args.replay),self.c);d=Detector(self.baseline)
                    for f in frames:
                        if self.stop.is_set():break
                        observe(f,d.update(f))
                        if self.stop.wait(self.c.frame_interval_s):break
                else:
                    self.root.mkdir(parents=True,exist_ok=True)
                    # Five seconds to step away before empty acquisition begins.
                    if empty and self.stop.wait(5):return
                    self.events.put(('acquiring',empty))
                    stream(self.args.port,self.c,output,10 if empty else 3600,
                        detector=None if empty else Detector(self.baseline),observer=observe,
                        stop_event=self.stop,quiet=True)
                    self.events.put(('saved',str(output.resolve())))
                    if empty:
                        _,frames,_=read_recording(output,self.c)
                        if self.stop.is_set() or len(frames)<40:raise ValueError('Empty capture incomplete; previous baseline retained')
                        b=Baseline.fit(frames[:30],self.c,dict(recording=str(output.resolve()),raw_sha256=hashlib.sha256((output/'frames.grd').read_bytes()).hexdigest(),training_count=30))
                        b.save(output/'baseline.json');d=Detector(b);hits=sum(d.update(f)['target_detected'] for f in frames[30:])
                        (output/'empty-holdout.json').write_text(json.dumps(dict(training_frames=30,unused_frames=len(frames)-30,false_detections=hits,independent_recording=False),indent=2))
                        self.events.put(('baseline',(b,hits,len(frames)-30)))
            except Exception as error:
                if output.exists():
                    (output/'gui-error.json').write_text(json.dumps(dict(type=type(error).__name__,message=str(error)),indent=2))
                self.events.put(('error',str(error)))
            finally:self.latest=None;self.events.put(('done',None))
        self.thread=threading.Thread(target=work,daemon=False);self.thread.start()

    def tick(self):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='baseline':
                self.baseline,hits,n=value;self.status.setText(f'Background ready. Unused empty frames: {hits}/{n} detections. Place target, then Start live.')
            elif kind=='acquiring':self.status.setText('Opening board stream; waiting for first frame…')
            elif kind=='saved':self.saved.setText('Recording saved: '+value)
            elif kind=='error':self.status.setText('Stopped: '+value)
            elif kind=='done':
                self.controls(False)
                if not self.status.text().startswith(('Background ready','Stopped:')):self.status.setText('Stopped — recording preserved')
        with self.lock:snapshot=self.latest;history=list(self.history)
        fresh=snapshot is not None and time.monotonic()-snapshot[0]<1
        reading=snapshot[1] if snapshot else {}
        distance,detail,strength,reason=display_values(reading,fresh)
        self.distance.setText(distance);self.detail.setText(detail);self.strength.setText('Signal change vs empty at candidate bin: '+strength)
        if fresh:
            transport=reading.get('serial',{})
            self.status.setText(f'{reason} · bin {reading.get("candidate_bin","—")} · gaps {transport.get("gaps",0)} · CRC {transport.get("bad_crc",0)}')
            values=reading.get('excess_profile_db',[]);self.line.set_data(np.arange(len(values))*self.c.spacing_m,values)
            visible=values[:int(1.5/self.c.spacing_m)+1]
            if visible:self.profile.set_ylim(min(-10,min(visible)-3),max(10,max(visible)+3))
        else:self.line.set_data([],[])
        if history:
            t,y=zip(*history);self.track.set_data(t,y);self.trace.set_xlim(max(0,t[-1]-30),max(1,t[-1]))
        else:self.track.set_data([],[])
        self.canvas.draw_idle()
        if self.closing and (self.thread is None or not self.thread.is_alive()):self.close()

    def closeEvent(self,event):
        if self.thread and self.thread.is_alive():self.closing=True;self.stop.set();event.ignore()
        else:event.accept()


def launch(args):
    from radar.qt_platform import staged_platform_plugins
    with staged_platform_plugins():
        app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window=Window(args);window.show()
        if args.snapshot:
            if not args.replay:raise ValueError('Snapshot mode requires replay; no implicit device access')
            window.start(False)
            def snapshot():
                window.grab().save(str(Path(args.snapshot).resolve()));window.close()
            QtCore.QTimer.singleShot(1800,snapshot)
        return app.exec()
