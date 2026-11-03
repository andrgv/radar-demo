"""Separate Qt GUI for conservative single-object range tracking.

This module intentionally leaves radar_min.gui unchanged. Only one live GUI may
own the serial port at a time.
"""

import argparse
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

from .__main__ import read_recording,stream
from .core import Baseline,Config,Detector
from .gui import Estimate,display_values,range_displayable
from .tracking import SingleRangeTracker,enrich_tracking


def tracking_display(reading,fresh):
    if not fresh:
        return 'Tracking: no fresh frame'
    track=reading.get('track') or {}
    state=track.get('state','idle')
    track_id=track.get('track_id')
    value=track.get('range_m')
    distance=f'{value*100:.1f} cm' if value is not None else '—'
    if state=='tracking':
        motion=track.get('motion','unknown').replace('_',' ')
        return f'Track {track_id}: {distance} · {motion}'
    if state=='tentative':
        return f'Finding target: {distance} · {track.get("hits",0)}/3 hits'
    if state=='coasting':
        age=track.get('measurement_age_s')
        age=f'{age:.1f} s' if age is not None else 'unknown age'
        return f'No current measurement · last track {track_id}: {distance} · {age}'
    if state=='lost':
        return 'Track lost'
    return 'Tracking: waiting for target'


class TrackingWindow(QtWidgets.QMainWindow):
    def __init__(self,args):
        super().__init__();self.args=args;self.c=Config.load(args.config)
        self.baseline=Baseline.load(args.baseline) if args.baseline else None
        if self.baseline and self.baseline.config.fingerprint!=self.c.fingerprint:
            raise ValueError('Baseline/config mismatch')
        if args.replay and not self.baseline:
            raise ValueError('Replay requires --baseline')
        self.thread=None;self.stop=threading.Event();self.events=queue.SimpleQueue();self.latest=None
        self.closing=False;self.history=deque(maxlen=300);self.lock=threading.Lock();self.t0=time.monotonic();self.counter=0
        self.root=Path('recordings')/('tracking-gui-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        self.setWindowTitle('Wavvy · range + tracking experiment');self.resize(1000,780)
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget);self.setCentralWidget(widget)
        title=QtWidgets.QLabel('Wavvy — range and tracking experiment');title.setStyleSheet('font-size: 23px; font-weight: bold');layout.addWidget(title)
        source='REPLAY' if args.replay else args.port
        layout.addWidget(QtWidgets.QLabel(f'Profile {self.c.profile_id:#x} · {source} · {args.estimator} estimator · Experimental, not calibrated'))
        self.distance=QtWidgets.QLabel('—');self.distance.setStyleSheet('font-size: 48px; font-weight: bold');layout.addWidget(self.distance)
        self.detail=QtWidgets.QLabel('Capture an empty background, then start tracking.');layout.addWidget(self.detail)
        self.strength=QtWidgets.QLabel('Signal change vs empty: —');layout.addWidget(self.strength)
        self.status=QtWidgets.QLabel('Idle');self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=QtWidgets.QHBoxLayout();layout.addLayout(buttons)
        self.empty=QtWidgets.QPushButton('Target removed: capture empty (10 s)');self.empty.clicked.connect(lambda:self.start(True));buttons.addWidget(self.empty)
        self.live=QtWidgets.QPushButton('Start replay' if args.replay else 'Start tracking + record');self.live.clicked.connect(lambda:self.start(False));buttons.addWidget(self.live)
        self.stop_button=QtWidgets.QPushButton('Stop');self.stop_button.clicked.connect(self.stop.set);buttons.addWidget(self.stop_button)

        self.tabs=QtWidgets.QTabWidget();layout.addWidget(self.tabs)
        range_tab=QtWidgets.QWidget();range_layout=QtWidgets.QVBoxLayout(range_tab)
        range_layout.addWidget(QtWidgets.QLabel('Original range view: current spectral change and accepted measured-distance history.'))
        self.range_figure=Figure(figsize=(9,3.5),layout='constrained');self.range_canvas=FigureCanvasQTAgg(self.range_figure);range_layout.addWidget(self.range_canvas)
        self.profile,self.range_trace=self.range_figure.subplots(1,2)
        self.line,=self.profile.plot([],[],color='#167d8d');self.profile.axhline(0,color='gray',lw=.5)
        self.profile.set(xlabel='Nominal distance coordinate (m)',ylabel='Power change vs empty (dB)',xlim=(0,1.5),ylim=(-20,30))
        self.range_history,=self.range_trace.plot([],[],color='#167d8d',marker='.',ms=3)
        self.range_trace.set(xlabel='Elapsed seconds',ylabel='Accepted experimental estimate (cm)',ylim=(0,160))
        self.tabs.addTab(range_tab,'Range')

        tracking_tab=QtWidgets.QWidget();tracking_layout=QtWidgets.QVBoxLayout(tracking_tab)
        self.tracking=QtWidgets.QLabel('Tracking: waiting for target');self.tracking.setStyleSheet('font-size: 18px; font-weight: bold');self.tracking.setWordWrap(True);tracking_layout.addWidget(self.tracking)
        tracking_layout.addWidget(QtWidgets.QLabel('Gray dots are current accepted measurements; the teal line is the smoothed single-object track.'))
        self.tracking_figure=Figure(figsize=(9,3.5),layout='constrained');self.tracking_canvas=FigureCanvasQTAgg(self.tracking_figure);tracking_layout.addWidget(self.tracking_canvas)
        self.tracking_trace=self.tracking_figure.subplots()
        self.raw_track,=self.tracking_trace.plot([],[],color='#8a8a8a',marker='.',ls='none',ms=4,label='Measured')
        self.smooth_track,=self.tracking_trace.plot([],[],color='#167d8d',lw=2,label='Tracked')
        self.tracking_trace.set(xlabel='Elapsed seconds',ylabel='Experimental range estimate (cm)',ylim=(0,160));self.tracking_trace.legend(loc='upper right')
        self.tabs.addTab(tracking_tab,'Tracking')

        self.saved=QtWidgets.QLabel('Raw frames and per-frame tracking state are saved. A retained track is never labeled as a current measurement.');self.saved.setWordWrap(True);layout.addWidget(self.saved)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(100);self.controls(False)

    def controls(self,busy):
        self.empty.setEnabled(not busy and not self.args.replay)
        self.live.setEnabled(not busy and self.baseline is not None)
        self.stop_button.setEnabled(busy)

    def start(self,empty):
        if self.thread and self.thread.is_alive():return
        self.stop.clear();self.latest=None;self.history.clear();self.t0=time.monotonic();self.controls(True)
        self.counter+=1;output=self.root/f'{"empty" if empty else "live"}-{self.counter:03d}'
        self.status.setText('Step away: waiting 5 seconds, then capturing empty for 10 seconds.' if empty else 'Starting tracking…')
        self.saved.setText('Replay: '+self.args.replay if self.args.replay else 'Recording: '+str(output.resolve()))

        def work():
            try:
                estimator=Estimate(self.baseline,self.args.estimator) if not empty else None
                tracker=SingleRangeTracker()

                def observe(frame,reading):
                    if estimator:estimator.enrich(frame,reading)
                    enrich_tracking(reading,tracker)
                    stamp=time.monotonic();value=reading.get('experimental_range_m');track=reading.get('track') or {}
                    tracked=track.get('range_m') if track.get('measured') else None
                    with self.lock:
                        self.latest=(stamp,dict(reading))
                        self.history.append((stamp-self.t0,
                            value*100 if range_displayable(reading) else np.nan,
                            tracked*100 if tracked is not None else np.nan))

                if self.args.replay:
                    _,frames,_=read_recording(Path(self.args.replay),self.c);detector=Detector(self.baseline)
                    for frame in frames:
                        if self.stop.is_set():break
                        observe(frame,detector.update(frame))
                        if self.stop.wait(self.c.frame_interval_s):break
                else:
                    self.root.mkdir(parents=True,exist_ok=True)
                    if empty and self.stop.wait(5):return
                    self.events.put(('acquiring',empty))
                    stream(self.args.port,self.c,output,10 if empty else 3600,
                        detector=None if empty else Detector(self.baseline),observer=observe,
                        stop_event=self.stop,quiet=True)
                    self.events.put(('saved',str(output.resolve())))
                    if empty:
                        _,frames,_=read_recording(output,self.c)
                        if self.stop.is_set() or len(frames)<40:
                            raise ValueError('Empty capture incomplete; previous baseline retained')
                        baseline=Baseline.fit(frames[:30],self.c,dict(
                            recording=str(output.resolve()),
                            raw_sha256=hashlib.sha256((output/'frames.grd').read_bytes()).hexdigest(),
                            training_count=30))
                        baseline.save(output/'baseline.json');detector=Detector(baseline)
                        hits=sum(detector.update(frame)['target_detected'] for frame in frames[30:])
                        (output/'empty-holdout.json').write_text(json.dumps(dict(
                            training_frames=30,unused_frames=len(frames)-30,
                            false_detections=hits,independent_recording=False),indent=2))
                        self.events.put(('baseline',(baseline,hits,len(frames)-30)))
            except Exception as error:
                if output.exists():
                    (output/'tracking-gui-error.json').write_text(json.dumps(dict(
                        type=type(error).__name__,message=str(error)),indent=2))
                self.events.put(('error',str(error)))
            finally:
                self.latest=None;self.events.put(('done',None))

        self.thread=threading.Thread(target=work,daemon=False);self.thread.start()

    def tick(self):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='baseline':
                self.baseline,hits,n=value
                self.status.setText(f'Background ready. Unused empty frames: {hits}/{n} detections. Place target, then Start tracking.')
            elif kind=='acquiring':self.status.setText('Opening board stream; waiting for first frame…')
            elif kind=='saved':self.saved.setText('Recording saved: '+value)
            elif kind=='error':self.status.setText('Stopped: '+value)
            elif kind=='done':
                self.controls(False)
                if not self.status.text().startswith(('Background ready','Stopped:')):
                    self.status.setText('Stopped — recording preserved')
        with self.lock:snapshot=self.latest;history=list(self.history)
        fresh=snapshot is not None and time.monotonic()-snapshot[0]<1
        reading=snapshot[1] if snapshot else {}
        distance,detail,strength,reason=display_values(reading,fresh)
        self.distance.setText(distance);self.detail.setText(detail)
        self.tracking.setText(tracking_display(reading,fresh))
        self.strength.setText('Signal change vs empty at candidate bin: '+strength)
        if fresh:
            transport=reading.get('serial',{})
            self.status.setText(f'{reason} · bin {reading.get("candidate_bin","—")} · gaps {transport.get("gaps",0)} · CRC {transport.get("bad_crc",0)}')
            values=reading.get('excess_profile_db',[]);self.line.set_data(np.arange(len(values))*self.c.spacing_m,values)
            visible=values[:int(1.5/self.c.spacing_m)+1]
            if visible:self.profile.set_ylim(min(-10,min(visible)-3),max(10,max(visible)+3))
        else:self.line.set_data([],[])
        if history:
            times,raw,tracked=zip(*history)
            self.range_history.set_data(times,raw)
            self.raw_track.set_data(times,raw);self.smooth_track.set_data(times,tracked)
            left=max(0,times[-1]-30);right=max(1,times[-1])
            self.range_trace.set_xlim(left,right);self.tracking_trace.set_xlim(left,right)
        else:
            self.range_history.set_data([],[])
            self.raw_track.set_data([],[]);self.smooth_track.set_data([],[])
        if self.tabs.currentIndex()==0:self.range_canvas.draw_idle()
        else:self.tracking_canvas.draw_idle()
        if self.closing and (self.thread is None or not self.thread.is_alive()):self.close()

    def closeEvent(self,event):
        if self.thread and self.thread.is_alive():
            self.closing=True;self.stop.set();event.ignore()
        else:event.accept()


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description='Separate experimental single-object tracking GUI')
    parser.add_argument('--port',default='/dev/cu.usbmodem103')
    parser.add_argument('--config',required=True)
    parser.add_argument('--baseline')
    parser.add_argument('--replay')
    parser.add_argument('--estimator',choices=['fixed','associated'],default='associated')
    return parser.parse_args(argv)


def main(argv=None):
    args=parse_args(argv)
    from radar.qt_platform import staged_platform_plugins
    with staged_platform_plugins():
        app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        window=TrackingWindow(args);window.show()
        return app.exec()


if __name__=='__main__':
    raise SystemExit(main())
