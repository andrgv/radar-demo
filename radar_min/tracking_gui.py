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


DASHBOARD_STYLE="""
QMainWindow { background: #050506; }
QWidget { color: #ffffff; font-family: "Helvetica Neue", Helvetica, Arial; font-size: 13px; font-weight: 400; }
QFrame#headerCard, QFrame#metricCard, QFrame#controlCard {
    background: #171719; border: 1px solid #26262a; border-radius: 16px;
}
QLabel#title { color: #fafafa; font-size: 22px; font-weight: 500; }
QLabel#subtitle, QLabel#muted { color: #8f8f98; }
QLabel#chip {
    color: #cfc1ef; background: #1c1a20; border: 1px solid #3b3348;
    border-radius: 10px; padding: 5px 9px; font-size: 12px;
}
QLabel#metricLabel { color: #ffffff; font-size: 13px; font-weight: 400; }
QLabel#distanceValue { color: #ffffff; font-size: 52px; font-weight: 500; }
QLabel#signalValue { color: #ffffff; font-size: 20px; font-weight: 500; }
QLabel#statusValue { color: #ceced4; font-size: 13px; }
QLabel#trackingBanner {
    color: #f0eaff; background: #211a2b; border: 1px solid #4b3769;
    border-radius: 10px; padding: 10px 12px; font-size: 16px; font-weight: 500;
}
QPushButton {
    min-height: 35px; border-radius: 10px; padding: 0 16px;
    font-size: 13px; font-weight: 400;
}
QPushButton#secondaryButton { color: #111114; background: #f4f4f5; border: none; }
QPushButton#secondaryButton:hover { background: #ffffff; }
QPushButton#secondaryButton:focus { background: #ece2ff; }
QPushButton#primaryButton { color: #ffffff; background: #7c3aed; border: 1px solid #9764f4; }
QPushButton#primaryButton:hover { background: #8b4df0; }
QPushButton#primaryButton:focus { background: #9d6af5; }
QPushButton#dangerButton { color: #ffdce1; background: #482027; border: 1px solid #74333f; }
QPushButton#dangerButton:hover { background: #5a2731; }
QPushButton#dangerButton:focus { background: #63313c; }
QPushButton:disabled { color: #55555e; background: #121214; border: 1px solid #232327; }
QTabWidget::pane {
    background: #171719; border: 1px solid #26262a; border-radius: 13px; top: -1px;
}
QTabBar::tab {
    color: #ffffff; background: #151517; border: 1px solid #39353f;
    padding: 11px 28px; margin-right: 6px; border-top-left-radius: 10px; border-top-right-radius: 10px;
    font-weight: 400;
}
QTabBar::tab:selected { color: #190d30; background: #d2baff; border: 2px solid #e9dbff; }
QTabBar::tab:hover:!selected { color: #d0d0d5; background: #1c1c1f; }
"""


def style_axis(axis):
    axis.set_facecolor('#111113')
    axis.tick_params(colors='#ffffff',labelsize=10)
    axis.xaxis.label.set_color('#ffffff');axis.yaxis.label.set_color('#ffffff')
    axis.xaxis.label.set_size(10);axis.yaxis.label.set_size(10)
    axis.title.set_color('#ffffff');axis.title.set_size(12)
    axis.grid(True,color='#38383e',alpha=.28,linewidth=.7)
    for spine in axis.spines.values():spine.set_color('#303035')


def stability_windows(history,window_s=2.0):
    """Display-only spread of accepted raw ranges in fixed time windows.

    Missing measurements are excluded; at least three accepted measurements are
    required per window. This describes repeatability, not distance accuracy.
    """
    buckets={}
    for elapsed,raw,_ in history:
        if np.isfinite(raw):
            buckets.setdefault(int(elapsed//window_s),[]).append(raw)
    return [(index*window_s,np.std(values,ddof=1))
            for index,values in sorted(buckets.items()) if len(values)>=3]


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


class DashboardButton(QtWidgets.QPushButton):
    """Keep keyboard interaction without Qt's native dotted focus rectangle."""
    def paintEvent(self,event):
        option=QtWidgets.QStyleOptionButton()
        self.initStyleOption(option)
        option.state &= ~QtWidgets.QStyle.StateFlag.State_HasFocus
        painter=QtWidgets.QStylePainter(self)
        painter.drawControl(QtWidgets.QStyle.ControlElement.CE_PushButton,option)


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
        self.setWindowTitle('Wavvy');self.resize(1120,900);self.setStyleSheet(DASHBOARD_STYLE)
        widget=QtWidgets.QWidget();layout=QtWidgets.QVBoxLayout(widget);layout.setContentsMargins(18,18,18,18);layout.setSpacing(12);self.setCentralWidget(widget)
        source='REPLAY' if args.replay else args.port

        header=QtWidgets.QFrame();header_layout=QtWidgets.QHBoxLayout(header);header_layout.setContentsMargins(4,2,4,2)
        title=QtWidgets.QLabel('Wavvy');title.setObjectName('title');header_layout.addWidget(title);header_layout.addStretch()
        chip=QtWidgets.QLabel(f'{self.c.profile_id:#x}  ·  {source}');chip.setObjectName('chip');header_layout.addWidget(chip)
        layout.addWidget(header)

        overview=QtWidgets.QHBoxLayout();overview.setSpacing(24);layout.addLayout(overview)
        distance_card=QtWidgets.QFrame();distance_layout=QtWidgets.QVBoxLayout(distance_card);distance_layout.setContentsMargins(4,12,4,12)
        distance_label=QtWidgets.QLabel('Distance');distance_label.setObjectName('metricLabel');distance_layout.addWidget(distance_label)
        self.distance=QtWidgets.QLabel('—');self.distance.setObjectName('distanceValue');distance_layout.addWidget(self.distance)
        self.detail=QtWidgets.QLabel('Capture an empty background, then start tracking.');self.detail.setObjectName('muted');self.detail.setWordWrap(True);distance_layout.addWidget(self.detail)
        secondary=QtWidgets.QHBoxLayout();secondary.setSpacing(24);distance_layout.addLayout(secondary)
        signal_card=QtWidgets.QFrame();signal_layout=QtWidgets.QVBoxLayout(signal_card);signal_layout.setContentsMargins(0,10,0,0)
        signal_label=QtWidgets.QLabel('Signal change');signal_label.setObjectName('metricLabel');signal_layout.addWidget(signal_label)
        self.strength=QtWidgets.QLabel('—');self.strength.setObjectName('signalValue');self.strength.setWordWrap(True);signal_layout.addWidget(self.strength);signal_layout.addStretch()
        secondary.addWidget(signal_card,1)

        status_card=QtWidgets.QFrame();status_layout=QtWidgets.QVBoxLayout(status_card);status_layout.setContentsMargins(0,10,0,0)
        status_label=QtWidgets.QLabel('Status');status_label.setObjectName('metricLabel');status_layout.addWidget(status_label)
        self.status=QtWidgets.QLabel('Idle');self.status.setObjectName('statusValue');self.status.setWordWrap(True);status_layout.addWidget(self.status);status_layout.addStretch()
        secondary.addWidget(status_card,1)
        overview.addWidget(distance_card,2)

        stability_card=QtWidgets.QFrame();stability_layout=QtWidgets.QVBoxLayout(stability_card);stability_layout.setContentsMargins(0,0,0,0)
        self.stability_figure=Figure(figsize=(6,2.1),layout='constrained');self.stability_figure.set_facecolor('#050506')
        self.stability_canvas=FigureCanvasQTAgg(self.stability_figure);self.stability_canvas.setMinimumHeight(235);stability_layout.addWidget(self.stability_canvas)
        self.stability_axis=self.stability_figure.subplots()
        self.stability_axis.set(title='Distance stability · 2-second windows',xlabel='Time since Start (s)',
            ylabel='Distance variation (cm)',xlim=(0,30),ylim=(0,1))
        style_axis(self.stability_axis)
        self.stability_bars=[]
        self.stability_note=QtWidgets.QLabel('Bars show standard deviation. Lower = steadier; target movement also raises bars.\nAt least 3 accepted readings per bar. This does not measure accuracy.')
        self.stability_note.setWordWrap(True);stability_layout.addWidget(self.stability_note)
        self.stability_canvas.setToolTip('Each bar shows the sample standard deviation of accepted, unsmoothed distance readings within a 2-second window. Target movement also increases the spread. This does not measure error from the true target distance.')
        overview.addWidget(stability_card,3)

        controls=QtWidgets.QFrame();controls_layout=QtWidgets.QHBoxLayout(controls);controls_layout.setContentsMargins(0,0,0,8);controls_layout.setSpacing(9)
        self.empty=DashboardButton('Empty scene');self.empty.setObjectName('secondaryButton');self.empty.clicked.connect(lambda:self.start(True));controls_layout.addWidget(self.empty)
        self.live=DashboardButton('Replay' if args.replay else 'Start');self.live.setObjectName('primaryButton');self.live.clicked.connect(lambda:self.start(False));controls_layout.addWidget(self.live)
        self.stop_button=DashboardButton('Stop');self.stop_button.setObjectName('dangerButton');self.stop_button.clicked.connect(self.stop.set);controls_layout.addWidget(self.stop_button)
        for button in (self.empty,self.live,self.stop_button):
            button.setAttribute(QtCore.Qt.WidgetAttribute.WA_MacShowFocusRect,False)
        controls_layout.addStretch()
        layout.addWidget(controls)

        self.tabs=QtWidgets.QTabWidget();layout.addWidget(self.tabs,1)
        range_tab=QtWidgets.QWidget();range_layout=QtWidgets.QVBoxLayout(range_tab)
        self.range_figure=Figure(figsize=(9,3.5),layout='constrained');self.range_canvas=FigureCanvasQTAgg(self.range_figure);range_layout.addWidget(self.range_canvas)
        self.range_figure.set_facecolor('#171719')
        self.profile,self.range_trace=self.range_figure.subplots(1,2)
        self.line,=self.profile.plot([],[],color='#8b5cf6',lw=1.8);self.profile.axhline(0,color='#62626a',lw=.7)
        self.profile.set(title='Radar return vs. empty scene',xlabel='Nominal distance from sensor (m)',ylabel='Power change vs. empty scene (dB)',xlim=(0,1.5),ylim=(-20,30))
        self.range_history,=self.range_trace.plot([],[],color='#8b5cf6',marker='.',ms=3)
        self.range_trace.set(title='Measured target distance over time',xlabel='Time since Start (s)',ylabel='Accepted distance estimate (cm)',ylim=(0,160))
        style_axis(self.profile);style_axis(self.range_trace)
        self.tabs.addTab(range_tab,'Range')

        tracking_tab=QtWidgets.QWidget();tracking_layout=QtWidgets.QVBoxLayout(tracking_tab)
        self.tracking=QtWidgets.QLabel('Tracking: waiting for target');self.tracking.setObjectName('trackingBanner');self.tracking.setWordWrap(True);tracking_layout.addWidget(self.tracking)
        self.tracking_figure=Figure(figsize=(9,3.5),layout='constrained');self.tracking_canvas=FigureCanvasQTAgg(self.tracking_figure);tracking_layout.addWidget(self.tracking_canvas)
        self.tracking_figure.set_facecolor('#171719')
        self.tracking_trace=self.tracking_figure.subplots()
        self.raw_track,=self.tracking_trace.plot([],[],color='#98989f',marker='.',ls='none',ms=4,label='Measured')
        self.smooth_track,=self.tracking_trace.plot([],[],color='#8b5cf6',lw=2.2,label='Tracked')
        self.tracking_trace.set(title='Single-target tracking · measured and smoothed distance',xlabel='Time since Start (s)',ylabel='Experimental target distance (cm)',ylim=(0,160));style_axis(self.tracking_trace)
        legend=self.tracking_trace.legend(loc='upper right',facecolor='#1b1b1e',edgecolor='#37373d',labelcolor='#ffffff');legend.get_frame().set_alpha(.95)
        self.tabs.addTab(tracking_tab,'Tracking')

        self.saved=QtWidgets.QLabel('Recording: —');self.saved.setObjectName('muted');self.saved.setWordWrap(True);layout.addWidget(self.saved)
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
        self.strength.setText(strength)
        if fresh:
            transport=reading.get('serial',{})
            diagnostics=f'{reason} · bin {reading.get("candidate_bin","—")} · gaps {transport.get("gaps",0)} · CRC {transport.get("bad_crc",0)}'
            track=reading.get('track') or {}
            if track.get('state')=='tracking':
                self.status.setText('Tracking · '+track.get('motion','unknown').replace('_',' '))
            else:self.status.setText(reason.replace('_',' '))
            self.status.setToolTip(diagnostics)
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
        for bar in self.stability_bars:bar.remove()
        self.stability_bars=[]
        windows=stability_windows(history)
        if windows:
            starts,spreads=zip(*windows)
            self.stability_bars=list(self.stability_axis.bar(starts,spreads,width=1.4,align='edge',color='#a879ff'))
            self.stability_axis.set_ylim(0,max(1,max(spreads)*1.2))
        else:self.stability_axis.set_ylim(0,1)
        end=history[-1][0] if history else 0
        self.stability_axis.set_xlim(max(0,end-30),max(30,end+2))
        self.stability_canvas.draw_idle()
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
