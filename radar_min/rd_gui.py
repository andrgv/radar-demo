"""Live full-map CFAR/feature association with raw recording and fail-closed UI."""
from collections import Counter, deque
from datetime import datetime
import json
from pathlib import Path
import queue
import threading
import time

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from .__main__ import read_recording, stream
from .core import Config, db
from .cfar import CfarConfig
from .rd_live import LiveRangeDoppler, current_measurement, feature_table_rows, settings_from_args
from .rx_diagnostics import current_receiver_diagnostic


class Window(QtWidgets.QMainWindow):
    def __init__(self,args):
        super().__init__()
        self.args = args
        if not args.replay and (not args.config or not args.port):
            raise ValueError('Live rd-gui requires --config and --port')
        self.c = Config.load(args.config or Path(args.replay)/'config.json')
        self.cfar_settings,self.association_settings = settings_from_args(args)
        self.processor = self.new_processor()
        nr = self.c.samples//2+1
        if not 0<=args.view_range_bins<=nr-2:raise ValueError('Plot view exceeds usable range bins')
        self.root = Path('recordings')/('rd-gui-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        self.thread = None
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.latest = None
        self.pending_history = deque(maxlen=300)
        self.events = queue.SimpleQueue()
        self.closing = False
        self.counter = 0
        self.track_labels = []
        self.render_key = None
        self.last_render_time = -np.inf
        self.display_interval_s = .25
        self.setWindowTitle('Wavvy · joint range / Doppler diagnostics')
        self.resize(1320,960)
        widget = QtWidgets.QWidget();layout = QtWidgets.QVBoxLayout(widget);self.setCentralWidget(widget)
        title = QtWidgets.QLabel('Range + Doppler detection diagnostics')
        title.setStyleSheet('font-size: 23px; font-weight: bold');layout.addWidget(title)
        mode = 'REPLAY — original host freshness unverified'if args.replay else f'LIVE · {args.port}'
        layout.addWidget(QtWidgets.QLabel(f'{mode} · profile {self.c.profile_id:#x} · 1D CFAR + 2D CFAR + association · zero Doppler retained'))
        notice = QtWidgets.QLabel('Feature IDs are not verified objects. Fine distances are experimental; range resolution and physical velocity remain uncalibrated.')
        notice.setWordWrap(True);layout.addWidget(notice)
        self.summary = QtWidgets.QLabel('No current measurements')
        self.summary.setStyleSheet('font-size: 17px; font-weight: bold');layout.addWidget(self.summary)
        buttons = QtWidgets.QHBoxLayout();layout.addLayout(buttons)
        self.start_button = QtWidgets.QPushButton('Start replay'if args.replay else 'Start live + record')
        self.start_button.clicked.connect(self.start);buttons.addWidget(self.start_button)
        self.stop_button = QtWidgets.QPushButton('Stop');self.stop_button.clicked.connect(self.stop_run);buttons.addWidget(self.stop_button)
        buttons.addStretch()
        buttons.addWidget(QtWidgets.QLabel('Plot zoom: maximum native range bin'))
        self.view_bins = QtWidgets.QSpinBox();self.view_bins.setRange(1,nr-2)
        self.view_bins.setValue(args.view_range_bins or nr-2);buttons.addWidget(self.view_bins)
        buttons.addWidget(QtWidgets.QLabel('(view only; all bins processed)'))
        self.tabs = QtWidgets.QTabWidget();layout.addWidget(self.tabs, 5)
        results_page = QtWidgets.QWidget();results_layout = QtWidgets.QVBoxLayout(results_page)
        self.tabs.addTab(results_page, 'Results + comparison')
        diagnostics_page = QtWidgets.QWidget();diagnostics_layout = QtWidgets.QVBoxLayout(diagnostics_page)
        self.tabs.addTab(diagnostics_page, 'RD maps + feature states')
        self.primary_label = QtWidgets.QLabel('1D baseline distance: —')
        self.primary_label.setStyleSheet('font-size: 26px; font-weight: bold')
        results_layout.addWidget(self.primary_label)
        self.baseline_label = QtWidgets.QLabel('')
        self.baseline_label.setVisible(getattr(args,'motion_aware',False))
        results_layout.addWidget(self.baseline_label)
        self.decision_label = QtWidgets.QLabel('Waiting for current evidence')
        self.decision_label.setWordWrap(True);results_layout.addWidget(self.decision_label)
        self.os_label = QtWidgets.QLabel('OS comparison disabled')
        self.os_label.setWordWrap(True);results_layout.addWidget(self.os_label)
        self.weak_label=QtWidgets.QLabel('Weak-candidate inspection disabled')
        self.weak_label.setWordWrap(True)
        self.weak_label.setVisible(getattr(args,'experimental_weak',False))
        self.weak_label.setToolTip('One OS group, unique current RD maximum and two interior raw-frequency RX peaks. '
            'This does not accept the raw single-tone range model or establish physical object identity. '
            'Saved 120 cm target holds can still produce a roughly 32 cm scene candidate. Primary and motion-aware policies are unchanged.')
        results_layout.addWidget(self.weak_label)
        self.weak_feature_label=QtWidgets.QLabel('Weak scene feature: no current confirmation')
        self.weak_feature_label.setWordWrap(True)
        self.weak_feature_label.setStyleSheet('font-size: 16px; font-weight: 600')
        self.weak_feature_label.setVisible(getattr(args,'experimental_weak',False))
        self.weak_feature_label.setToolTip('Separate weak: IDs confirm consecutive current supported scene peaks. '
            'They do not identify physical objects, accept the rejected phase model or alter the original RD birth margin. '
            'A confirmed weak feature can still be the wrong reflector; saved 120 cm holds include confirmed ~32 cm returns. '
            'Gaps and ambiguity revoke confirmation; the same return can also appear in the original RD/1D bank.')
        results_layout.addWidget(self.weak_feature_label)
        self.inspection_label = QtWidgets.QLabel('Select a candidate to inspect its current estimates')
        self.inspection_label.setWordWrap(True);results_layout.addWidget(self.inspection_label)
        self.rx_label=QtWidgets.QLabel('1D RX inspection: no confirmed current support')
        self.rx_label.setWordWrap(True)
        self.rx_label.setToolTip('Raw range-only RX peaks within the same confirmed 1D support, across all Doppler components. '
            'Unresolved RX peaks are withheld. Spread notes use a quarter native bin; waveform mismatch notes use 50% unexplained energy. '
            'Residual is at the pooled FFT range, not an optimized phase fit: other returns and FFT peak bias contribute. '
            'Agreement does not certify accuracy or target identity. These diagnostics never change distance or detection.')
        results_layout.addWidget(self.rx_label)
        self.comparison_figure = Figure(figsize=(12, 4))
        self.comparison_figure.subplots_adjust(left=.06,right=.985,bottom=.18,top=.86,wspace=.45)
        self.comparison_canvas = FigureCanvasQTAgg(self.comparison_figure)
        self.range_axis,self.slice_axis,self.history_axis = self.comparison_figure.subplots(1, 3)
        self.range_axis.set(xlabel='Nominal range (m)', ylabel='dB ADC units²', title='1D range profile')
        self.slice_axis.set(xlabel='Cycles/saved block', ylabel='dB ADC units²', title='Selected RD Doppler slice', xlim=(-.5,.5))
        self.history_axis.set(xlabel='Frame sequence', ylabel='Experimental cm', title='Processed distance history')
        self.range_lines = {key:self.range_axis.plot([],[],label=label)[0] for key,label in
                            [('power','Power'),('noise_power','Reference'),('threshold_power','Threshold')]}
        self.os_threshold_line = (self.range_axis.plot([],[],'--',label='Experimental OS threshold')[0]
                                  if getattr(args,'experimental_os',False)or getattr(args,'experimental_weak',False) else None)
        self.range_peaks, = self.range_axis.plot([],[],'rx')
        self.rx_peak_lines=[self.range_axis.plot([],[],marker='o',ls='none',ms=4,label=f'RX {i+1} peak')[0]for i in range(3)]
        self.slice_lines = [self.slice_axis.plot([],[],label=label)[0] for label in ('RD power','2D threshold')]
        self.history_lines = [self.history_axis.plot([],[],'.-',ms=2,lw=.5,label=label)[0]
                              for label in ('1D baseline','Selected RD fine')]
        self.motion_history_line = (self.history_axis.plot([],[],'o-',ms=2,lw=.5,label='Motion-aware measured')[0]
                                    if getattr(args,'motion_aware',False) else None)
        self.weak_feature_history_line=(self.history_axis.plot([],[],'^-',ms=2,lw=.5,label='Confirmed weak scene feature (inspection)')[0]
                                        if getattr(args,'experimental_weak',False)else None)
        self.range_support = Rectangle((0,0),0,1,transform=self.range_axis.get_xaxis_transform(),
                                       facecolor='teal',alpha=.12,visible=False)
        self.range_axis.add_patch(self.range_support)
        for axis in (self.range_axis,self.slice_axis,self.history_axis):axis.legend(fontsize=7,ncol=2 if axis is self.range_axis else 1)
        self.result_history = deque(maxlen=300)
        results_layout.addWidget(self.comparison_canvas, 3)
        self.candidate_table = QtWidgets.QTableWidget(0, 9)
        self.candidate_table.setHorizontalHeaderLabels(['Return','Sources','Confirmation','1D fine (cm)',
            'RD fine (cm)','Phase evidence','Association','Readout','Decision / refinement'])
        self.candidate_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.candidate_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.candidate_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.candidate_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.candidate_table.horizontalHeader().setStretchLastSection(True)
        results_layout.addWidget(self.candidate_table, 2)
        self.selected_candidate = None
        self.current_result = None
        self.candidate_table.itemSelectionChanged.connect(self.select_candidate)
        self.figure = Figure(figsize=(12,4),layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure);diagnostics_layout.addWidget(self.canvas,3)
        self.axes = self.figure.subplots(1,2,sharey=True)
        nd = self.processor.rd.count
        self.frequency = self.processor.rd.doppler
        self.extent = [-.5*self.c.spacing_m,(nr-.5)*self.c.spacing_m,
            self.frequency[0]-.5/nd,self.frequency[-1]+.5/nd]
        blank = np.ma.masked_all((nd,nr))
        self.full_image = self.axes[0].imshow(blank,origin='lower',aspect='auto',extent=self.extent,vmin=0,vmax=60)
        self.margin_image = self.axes[1].imshow(blank,origin='lower',aspect='auto',extent=self.extent,vmin=-12,vmax=12)
        self.axes[0].set_title('Full power: CFAR × · measured IDs ○ · ambiguous support ◇',fontsize=9)
        self.axes[1].set_title('Power relative to empirical CFAR threshold',fontsize=10)
        self.axes[0].set_ylabel('Cycles/saved block (physical velocity unverified)')
        for ax in self.axes:
            ax.set_xlabel('Nominal range (m; uncalibrated)')
            ax.axhline(0,color='white',lw=.6,alpha=.5)
        self.figure.colorbar(self.full_image,ax=self.axes[0],label='dB ADC units²')
        self.figure.colorbar(self.margin_image,ax=self.axes[1],label='dB above/below threshold')
        self.accepted_points = self.axes[0].scatter([],[],marker='s',facecolors='none',edgecolors='white',s=25,linewidths=.6)
        self.peak_points = self.axes[0].scatter([],[],marker='x',c='red',s=28)
        self.track_points = self.axes[0].scatter([],[],marker='o',facecolors='none',edgecolors='cyan',s=85,linewidths=1.5)
        self.support_points = self.axes[0].scatter([],[],marker='D',facecolors='none',edgecolors='orange',s=40,linewidths=.9)
        self.view_bins.valueChanged.connect(self.set_view)
        self.set_view()
        diagnostics_layout.addWidget(QtWidgets.QLabel('All-range feature hypotheses — ambiguous/missing rows have no distance measurement'))
        self.table = QtWidgets.QTableWidget(0,8)
        self.table.setHorizontalHeaderLabels(['ID','State','Nominal range (m)','Range bin','Doppler (cycles/block)',
                                              'Peak margin (dB)','Current support (bins)','Frames since peak'])
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(180);diagnostics_layout.addWidget(self.table,2)
        self.table.horizontalHeaderItem(2).setToolTip('Native range-bin center only; no fine fit or distance calibration. Blank when no current confirmed point exists.')
        self.table.horizontalHeaderItem(4).setToolTip('Phase progression per saved block, not m/s. Zero Doppler does not establish a stationary object in the world.')
        self.table.horizontalHeaderItem(6).setToolTip('Current accepted cells near an unresolved feature; not an independently measured distance.')
        self.quality = QtWidgets.QLabel('Waiting for a fresh frame');self.quality.setWordWrap(True);layout.addWidget(self.quality)
        self.quality.setToolTip('Display age is time since the latest processing update, not an independently measured sensor-to-screen latency.')
        self.status = QtWidgets.QLabel('Ready — no empty capture needed');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.saved = QtWidgets.QLabel('Raw frames and feature diagnostics are recorded during live runs.');self.saved.setWordWrap(True);layout.addWidget(self.saved)
        self.ended = QtWidgets.QLabel('');self.ended.setWordWrap(True);layout.addWidget(self.ended)
        self.timer = QtCore.QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(100)
        self.tabs.currentChanged.connect(self.refresh_tab)
        self.controls(False)

    def refresh_tab(self,*_):
        self.render_key = None
        self.last_render_time = -np.inf
        self.tick()

    def new_processor(self):
        settings = CfarConfig(getattr(self.args,'cfar_guard',1),getattr(self.args,'cfar_training',4),
                              getattr(self.args,'cfar_min_training',4),getattr(self.args,'cfar_factor',2.0))
        processor=LiveRangeDoppler(self.c,self.cfar_settings,self.association_settings,settings,
                                  experimental_os=getattr(self.args,'experimental_os',False),
                                  experimental_weak=getattr(self.args,'experimental_weak',False))
        processor.metadata['gui_distance_policy']='experimental motion-aware' if getattr(self.args,'motion_aware',False) else 'frozen 1D baseline'
        return processor

    def select_candidate(self):
        row = self.candidate_table.currentRow()
        if row >= 0 and self.candidate_table.item(row,0):
            self.selected_candidate = self.candidate_table.item(row,0).text()
        if self.current_result:
            self.render_results(*self.current_result)

    def draw_comparison(self, reading, view, valid):
        # Hidden canvases still schedule Matplotlib work. Never redraw both tabs
        # in one update: the acquisition worker shares this process's GIL.
        if self.tabs.currentIndex()!=0:return
        for line in (*self.range_lines.values(),self.range_peaks,*self.rx_peak_lines,*self.slice_lines,*self.history_lines):line.set_data([],[])
        if self.motion_history_line:self.motion_history_line.set_data([],[])
        if self.weak_feature_history_line:self.weak_feature_history_line.set_data([],[])
        if self.os_threshold_line:self.os_threshold_line.set_data([],[])
        self.range_support.set_visible(False)
        if self.result_history:
            seq = [h[0] for h in self.result_history]
            self.history_lines[0].set_data(seq,[h[1] for h in self.result_history])
            self.history_lines[1].set_data(seq,[h[2].get(self.selected_candidate,np.nan) for h in self.result_history])
            if self.motion_history_line:
                motion_x=[];motion_y=[];previous=None
                for s,_,values in self.result_history:
                    identity=values.get('__motion_identity__')
                    if previous is not None and identity is not None and identity!=previous:
                        motion_x.append(s);motion_y.append(np.nan)
                    motion_x.append(s);motion_y.append(values.get('__motion__',np.nan))
                    previous=identity
                self.motion_history_line.set_data(motion_x,motion_y)
            if self.weak_feature_history_line:
                weak_x=[];weak_y=[];previous=None
                for s,_,values in self.result_history:
                    identity=values.get('__weak_feature_id__')
                    if previous is not None and identity is not None and identity!=previous:
                        weak_x.append(s);weak_y.append(np.nan)
                    weak_x.append(s);weak_y.append(values.get('__weak_feature__',np.nan))
                    previous=identity
                self.weak_feature_history_line.set_data(weak_x,weak_y)
            self.history_axis.relim();self.history_axis.autoscale_view()
        if not valid:
            self.comparison_canvas.draw_idle();return
        baseline = reading['one_d']
        x = np.arange(len(baseline['power']))*self.c.spacing_m
        for key,line in self.range_lines.items():line.set_data(x,db(np.array(baseline[key],dtype=float)))
        if self.os_threshold_line and reading.get('clutter_comparison'):
            self.os_threshold_line.set_data(x,db(np.array(reading['clutter_comparison']['os']['threshold_power'],dtype=float)))
        self.range_axis.set_xlim(.5*self.c.spacing_m,(self.view_bins.value()+.5)*self.c.spacing_m)
        bins = [group['range_bin'] for group in baseline['candidates']]
        self.range_peaks.set_data(x[bins],[baseline['power_db'][k] for k in bins])
        diagnostic=current_receiver_diagnostic(reading,self.selected_candidate)
        if diagnostic:
            for line,rx in zip(self.rx_peak_lines,diagnostic['receivers']):
                if rx['range_m']is not None:line.set_data([rx['range_m']],[rx['peak_power_db']])
        self.range_axis.relim();self.range_axis.autoscale_view(scalex=False)
        row = next((r for r in reading['results']['candidates'] if r['candidate_id']==self.selected_candidate), None)
        if row:
            bins = row['support_bins']
            if bins:
                self.range_support.set_x((min(bins)-.5)*self.c.spacing_m)
                self.range_support.set_width((max(bins)-min(bins)+1)*self.c.spacing_m)
                self.range_support.set_visible(True)
            k = row.get('range_bin')
            if k is not None:
                self.slice_lines[0].set_data(self.frequency,db(view.full_power[:,k]))
                self.slice_lines[1].set_data(self.frequency,db(view.threshold_power[:,k]))
                self.slice_axis.relim();self.slice_axis.autoscale_view(scalex=False)
            def cm(value):return f'{value*100:.1f} cm' if value is not None else 'unresolved'
            self.inspection_label.setText(f"Inspecting {row['candidate_id']} · 1D: {cm(row.get('one_d_range_m'))} · RD: {cm(row.get('rd_range_m'))} · {row['motion']} · {row['reason']}")
        else:self.inspection_label.setText('Select a candidate to inspect its current estimates' if self.selected_candidate is None else 'Selected return has no current observation — no held distance')
        self.comparison_canvas.draw_idle()

    def history_entry(self, reading, valid):
        sequence = reading.get('frame_sequence')
        if valid:
            value = reading['one_d'].get('experimental_range_m')
            rd_values = {r['candidate_id']:r['rd_range_m']*100 for r in reading['results']['candidates'] if r.get('rd_range_m') is not None}
            motion=reading.get('motion_result',{})
            if motion.get('experimental_range_m') is not None:
                rd_values['__motion__']=motion['experimental_range_m']*100
                rd_values['__motion_identity__']=('RD',motion['track_id']) if motion.get('source','').startswith('RD') else ('baseline',None)
            weak=reading.get('weak_feature_result')or{}
            if (weak.get('confirmed')and weak.get('experimental_range_m')is not None and
                weak.get('frame_sequence')==sequence and weak.get('measurement_sequence')==sequence):
                rd_values['__weak_feature__']=weak['experimental_range_m']*100
                rd_values['__weak_feature_id__']=weak['feature_id']
            return (sequence,value*100 if value is not None else np.nan,rd_values)
        return (sequence,np.nan,{})

    def remember_entry(self, entry):
        sequence,value,rd_values=entry
        if sequence is None:
            if self.result_history:self.result_history.append((self.result_history[-1][0],np.nan,{}))
            return
        if self.result_history and sequence==self.result_history[-1][0]:return
        if self.result_history and sequence<self.result_history[-1][0]:self.result_history.clear()
        if self.result_history and sequence!=self.result_history[-1][0]+1:
            self.result_history.append((sequence-1,np.nan,{}))
        self.result_history.append((sequence,value,rd_values))

    def remember_result(self, reading, valid):
        self.remember_entry(self.history_entry(reading,valid))
    def render_results(self, reading, view, valid):
        self.current_result = (reading,view,valid)
        self.remember_result(reading, valid)
        blocker = QtCore.QSignalBlocker(self.candidate_table)
        rows = reading.get('results',{}).get('candidates',[]) if valid else []
        self.candidate_table.setRowCount(len(rows))
        selected_index = None
        for i,row in enumerate(rows):
            if row['candidate_id']==self.selected_candidate:selected_index=i
            def cm(value):return f'{value*100:.1f}' if value is not None else '—'
            confirmation = ('1D confirmed' if row.get('one_d_confirmed') else '1D confirming') if '1D' in row['sources'] else ''
            if 'RD' in row['sources']:confirmation += (' / ' if confirmation else '')+'RD '+row['state']
            reasons = [row['reason']]
            for key in ('one_d_fine_range','rd_fine_range'):
                if row.get(key):reasons.append(row[key]['reason'])
            motion=reading.get('motion_result',{})
            motion_selected=(getattr(self.args,'motion_aware',False) and motion.get('experimental_range_m') is not None
                             and motion.get('source','').startswith('RD') and row.get('rd_track_id')==motion.get('track_id'))
            values=[row['candidate_id'],' + '.join(row['sources']),confirmation,cm(row.get('one_d_range_m')),
                    cm(row.get('rd_range_m')),row['motion'],row['association'],
                    'Motion readout' if motion_selected else '1D baseline' if row['primary_eligible'] else 'Inspection only','; '.join(reasons)]
            for j,value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(value)
                item.setToolTip(value)
                self.candidate_table.setItem(i,j,item)
        if selected_index is not None:self.candidate_table.selectRow(selected_index)
        del blocker
        primary = reading.get('results',{}).get('primary') if valid else None
        baseline_text=f"1D baseline distance: {primary['experimental_range_m']*100:.1f} cm" if primary else '1D baseline distance: —'
        if getattr(self.args,'motion_aware',False):
            motion=reading.get('motion_result',{}) if valid else {}
            value=motion.get('experimental_range_m')
            text=f'{value*100:.1f} cm' if value is not None else '—'
            self.primary_label.setText(f'Experimental motion-aware distance: {text}')
            self.baseline_label.setText(baseline_text+f" · source: {motion.get('source') or 'none'} · feature: {motion.get('track_id') or '—'} · {motion.get('reason','No fresh frame')}")
        else:self.primary_label.setText(baseline_text)
        baseline = reading.get('one_d',{}) if valid else {}
        diagnostic=current_receiver_diagnostic(reading,self.selected_candidate)if valid else None
        if diagnostic:
            peak_reasons={'fine_peak_at_group_boundary':'peak at support edge',
                          'multiple_fine_peaks':'competing peaks','nonconcave_fine_peak':'no isolated peak'}
            parts=[f"RX {r['rx']}: {r['range_m']*100:.1f} cm"if r['range_m']is not None else
                   f"RX {r['rx']}: unresolved ({peak_reasons.get(r['reason'],'peak unresolved')})"for r in diagnostic['receivers']]
            spread=diagnostic['spread_m'];residual=diagnostic['single_tone_residual_fraction']
            notes={'rx_peak_unresolved':'RX peak unresolved','rx_peak_disagreement':'RX peaks disagree',
                   'single_tone_mismatch_at_fft_range':'Mixed waveform / FFT-model mismatch'}
            flags='; '.join(notes[f]for f in diagnostic['flags'])or'No diagnostic flag; accuracy unverified'
            scope='Selected confirmed 1D group'if self.selected_candidate else'Nearest confirmed 1D group'
            self.rx_label.setText(f"1D RX inspection · {scope} · "+' / '.join(parts)+
                (f" · spread {spread*100:.1f} cm"if spread is not None else' · spread unavailable')+
                (f" · single-tone unexplained {residual*100:.0f}%"if residual is not None else' · single-tone residual unavailable')+
                ' · '+flags+' · Inspection only')
            self.rx_label.setStyleSheet('color: #a35b00'if diagnostic['flags']else'')
        else:
            self.rx_label.setText('1D RX inspection: '+('no fresh current measurement'if not valid else
                'no confirmed 1D support for selected return'if self.selected_candidate else'no confirmed current 1D support'))
            self.rx_label.setStyleSheet('')
        if self.processor.os_comparison:
            comparison=reading.get('clutter_comparison') if valid else None
            selection=comparison['selection'] if comparison else {}
            value=selection.get('experimental_range_m')
            text=f'{value*100:.1f} cm' if value is not None else '—'
            self.os_label.setText(f"Experimental OS inspection: {text} · {selection.get('reason','No current comparison')} · May detect stationary clutter; not an automatic primary distance.")
        else:self.os_label.setText('OS comparison disabled')
        if getattr(self.args,'experimental_weak',False):
            weak=reading.get('clutter_comparison',{}).get('weak_selection')if valid else None
            value=weak.get('experimental_range_m')if weak else None
            text=f'{value*100:.1f} cm'if value is not None else'—'
            reason=weak['reason'].replace('_',' ')if weak else'No fresh current comparison'
            detail=''
            if weak and weak.get('phase_model_reason'):
                detail=f" · raw model: {'passed original fit checks'if weak['phase_model_accepted']else'withheld'} ({weak['phase_model_reason'].replace('_',' ')})"
            link=reading.get('weak_motion_result')if valid else None
            if link:
                stages={'below_rd_birth_margin':'RD peak below birth margin',
                    'refined_static_feature_without_motion_history':'RD feature has no motion history',
                    'no_confirmed_current_track':'RD feature unconfirmed',
                    'refined_feature_with_nonzero_peak_history':'RD feature has motion history'}
                detail+=' · motion link: '+link['state'].replace('_',' ')
                if link.get('weak_rd_stage'):detail+=' / '+stages.get(link['weak_rd_stage'],'RD refinement or support unresolved')
            self.weak_label.setText(f'Weak scene candidate (inspection only): {text} · {reason}'+detail+' · Not a verified object distance')
            self.weak_label.setToolTip('Inspection only; no physical identity or accepted range model is inferred. '+
                ('Motion link: '+link['reason'].replace('_',' ')+'. A seed is revoked on missing, ambiguous or unsupported measurements; stationary returns cannot reseed.'if link else'No current motion link.'))
        else:self.weak_label.setText('Weak-candidate inspection disabled')
        feature=reading.get('weak_feature_result')if valid else None
        if feature and feature['frame_sequence']==reading.get('frame_sequence'):
            value=feature.get('experimental_range_m')
            if feature['confirmed']and value is not None and feature.get('measurement_sequence')==reading['frame_sequence']:
                self.weak_feature_label.setText(f"Confirmed weak scene feature (inspection): {feature['feature_id']} · {value*100:.1f} cm · current hits {feature['confirmation_hits']} · Target identity unverified")
            elif feature['state']=='confirming':
                required=self.processor.weak_features.settings.confirmation_frames
                self.weak_feature_label.setText(f"Weak scene feature: {feature['feature_id']} · confirming {feature['confirmation_hits']}/{required} consecutive current hits · No confirmed distance")
            else:self.weak_feature_label.setText('Weak scene feature: — · '+feature['reason'].replace('_',' '))
        else:self.weak_feature_label.setText('Weak scene feature: no fresh current confirmation')
        policy_note=(' · Motion-aware readout uses current measured RD evidence; no prediction or verified object identity.'
                     if getattr(self.args,'motion_aware',False) else
                     ' · RD-only features are inspection results; source agreement does not verify an object.')
        self.decision_label.setText(('Experimental, uncalibrated · 1D: '+baseline.get('reason','No fresh frame'))+policy_note)
        if not valid:self.inspection_label.setText('No fresh current measurement')
        self.draw_comparison(reading,view,valid)

    def controls(self,busy):
        self.start_button.setEnabled(not busy)
        self.stop_button.setEnabled(busy)

    def set_view(self,*_):
        for ax in self.axes:ax.set_xlim(.5*self.c.spacing_m,(self.view_bins.value()+.5)*self.c.spacing_m)
        self.canvas.draw_idle()
        if getattr(self,'current_result',None):self.draw_comparison(*self.current_result)

    def stop_run(self):
        self.stop.set()
        with self.lock:self.latest=None
        self.render({},None,False)
        self.status.setText('Stopping — closing recording…')

    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop.clear()
        with self.lock:self.latest=None
        self.processor = self.new_processor()
        self.result_history.clear();self.selected_candidate=None
        with self.lock:self.pending_history.clear()
        self.controls(True);self.counter+=1
        self.render({},None,False)
        output = self.root/f'live-{self.counter:03d}'
        self.status.setText('Starting replay…'if self.args.replay else 'Opening board stream…')
        self.saved.setText('Replay: '+self.args.replay if self.args.replay else 'Recording: '+str(output.resolve()))

        def observe(frame,reading):
            if self.stop.is_set():return
            entry=self.history_entry(reading,reading.get('valid',False))
            with self.lock:
                self.latest=(time.monotonic(),reading,self.processor.snapshot)
                self.pending_history.append(entry)

        def work():
            try:
                if self.args.replay:
                    _,frames,_=read_recording(self.args.replay,self.c)
                    for frame in frames:
                        if self.stop.is_set():break
                        observe(frame,self.processor.update(frame))
                        if self.stop.wait(self.c.frame_interval_s):break
                    self.events.put(('finished','Replay finished'))
                else:
                    self.root.mkdir(parents=True,exist_ok=True)
                    stream(self.args.port,self.c,output,3600,detector=self.processor,
                           observer=observe,stop_event=self.stop,quiet=True)
                    self.events.put(('saved',str(output.resolve())))
            except Exception as error:
                if output.exists():(output/'gui-error.json').write_text(json.dumps(dict(type=type(error).__name__,message=str(error)),indent=2))
                self.events.put(('error',str(error)))
            finally:
                self.processor.clear()
                with self.lock:self.latest=None
                self.events.put(('done',None))
        self.thread=threading.Thread(target=work,daemon=False);self.thread.start()

    def replay_snapshot(self,index):
        if not self.args.replay:raise ValueError('Snapshot requires replay')
        _,frames,_=read_recording(self.args.replay,self.c)
        if not 0<=index<len(frames):raise ValueError('Snapshot frame outside recording')
        self.processor = self.new_processor()
        self.result_history.clear()
        for frame in frames[:index+1]:
            reading=self.processor.update(frame)
            self.remember_result(reading, reading['valid'])
        with self.lock:self.latest=(time.monotonic(),reading,self.processor.snapshot)
        self.status.setText(f'Replay snapshot at frame {index} — device/map checks only')
        self.saved.setText('Replay: '+self.args.replay)
        self.tick()

    def render(self,reading,view,fresh):
        valid = (fresh and reading.get('valid',False) and reading.get('association',{}).get('valid',False)
                 and view is not None and view.sequence==reading.get('frame_sequence'))
        self.render_results(reading,view,valid)
        for label in self.track_labels:label.remove()
        self.track_labels.clear()
        empty = np.empty((0,2))
        for scatter in (self.accepted_points,self.peak_points,self.track_points,self.support_points):scatter.set_offsets(empty)
        rows = feature_table_rows(reading,self.c,valid)
        self.table.setRowCount(len(rows))
        colors = dict(measured='#e5ffff',tentative='#f4f4f4',ambiguous='#fff0d6',missed='#eeeeee')
        for i,(state,values)in enumerate(rows):
            for j,value in enumerate(values):
                cell=QtWidgets.QTableWidgetItem(value)
                cell.setBackground(QtGui.QColor(colors.get(state,'white')))
                self.table.setItem(i,j,cell)
        if not valid:
            blank=np.ma.masked_all((self.processor.rd.count,self.c.samples//2+1))
            self.full_image.set_data(blank);self.margin_image.set_data(blank)
            self.summary.setText('No current measurements')
            self.ended.setText('')
            if self.tabs.currentIndex()==1:self.canvas.draw_idle()
            return
        self.full_image.set_data(db(view.full_power))
        ceiling=float(db(np.max(view.full_power)));self.full_image.set_clim(ceiling-60,ceiling)
        ratio=np.divide(view.full_power,view.threshold_power,out=np.full_like(view.full_power,np.nan),where=np.isfinite(view.threshold_power))
        self.margin_image.set_data(np.ma.masked_invalid(db(ratio)))
        cells=np.argwhere(view.accepted)
        self.accepted_points.set_offsets(np.array([(r*self.c.spacing_m,self.frequency[d])for d,r in cells]).reshape(-1,2))
        maxima=[p for group in reading['cfar_clusters']for p in group['local_maxima']]
        self.peak_points.set_offsets(np.array([(p['range_bin']*self.c.spacing_m,self.frequency[p['doppler_bin']])for p in maxima]).reshape(-1,2))
        tracks=reading['association']['tracks']
        measured=[t for t in tracks if current_measurement(t,reading['frame_sequence'])]
        points=[(t['measurement']['range_bin']*self.c.spacing_m,t['measurement']['cycles_per_saved_block'])for t in measured]
        self.track_points.set_offsets(np.array(points).reshape(-1,2))
        for t,(x,y)in zip(measured,points):
            self.track_labels.append(self.axes[0].annotate(str(t['track_id']),(x,y),xytext=(4,5),textcoords='offset points',color='cyan',fontsize=8))
        support=sorted({tuple(cell)for t in tracks if t['state']=='ambiguous'for cell in t['current_support_cells']})
        self.support_points.set_offsets(np.array([(r*self.c.spacing_m,self.frequency[d])for d,r in support]).reshape(-1,2))
        states=Counter(t['state']for t in tracks)
        self.summary.setText(f'Measured features: {len(measured)} · Confirming: {states["tentative"]} · Ambiguous: {states["ambiguous"]} · Missing: {states["missed"]}')
        ended=reading['association']['ended_tracks']
        reasons=dict(confirmation_interrupted='unconfirmed peak disappeared',
                     confirmation_quality_interrupted='quality fell during confirmation',
                     no_support_expired='no current support',ambiguous_support_expired='ambiguity expired')
        self.ended.setText('Ended this frame: '+', '.join(f'{t["track_id"]}: {reasons.get(t["reason"],t["reason"].replace("_"," "))}'for t in ended) if ended else '')
        if self.tabs.currentIndex()==1:self.canvas.draw_idle()

    def tick(self):
        while not self.events.empty():
            kind,value=self.events.get()
            if kind=='saved':self.saved.setText('Recording saved: '+value);self.status.setText('Stopped — recording preserved')
            elif kind=='error':self.status.setText('Stopped: '+value)
            elif kind=='finished':self.status.setText(value)
            elif kind=='done':self.controls(False)
        with self.lock:
            snapshot=self.latest
            history=list(self.pending_history);self.pending_history.clear()
        for entry in history:self.remember_entry(entry)
        now=time.monotonic()
        age=now-snapshot[0] if snapshot else np.inf
        fresh=age<1
        reading=snapshot[1]if snapshot else{}
        view=snapshot[2]if snapshot else None
        invalid=(not fresh or not reading.get('valid',False) or view is None or
                 view.sequence!=reading.get('frame_sequence'))
        key=('invalid',reading.get('reason'),fresh) if invalid else (snapshot[0],fresh)
        # Continue checking freshness at 10 Hz; expensive display work is capped
        # at 4 Hz. A rejection or stall bypasses that cap and clears immediately.
        if key!=self.render_key and (invalid or now-self.last_render_time>=self.display_interval_s):
            self.render(reading,view,fresh);self.render_key=key;self.last_render_time=now
        if fresh:
            serial=reading.get('serial',{})
            clock=reading.get('clock_sync',{}).get('state','replay/unavailable')
            reason=reading.get('reason','No reading')
            if reading.get('valid',False):label='Current frame'
            elif reason=='serial_backlog':label='Serial backlog — measurements cleared'
            elif reason.startswith(('clock_','host_')):label='Host timing rejected — measurements cleared'
            else:label='Frame rejected — measurements cleared'
            self.quality.setText(f'{label} · sequence {reading.get("frame_sequence","—")} · display age {age*1000:.0f} ms · DSP {reading.get("processing_ms",0):.2f} ms · gaps {serial.get("gaps",0)} · CRC {serial.get("bad_crc",0)} · host clock {clock}')
            fit=reading.get('clock_sync',{}).get('fit_diagnostics')
            if reason=='clock_fit_unstable':
                detail=(f" · fit p95 {fit['p95_residual_s']*1000:.1f} ms (limit {fit['p95_limit_s']*1000:.1f}); max {fit['max_residual_s']*1000:.1f} ms" if fit else '')
                self.quality.setText(self.quality.text()+detail+' · Stop and start a new capture to retry; raw recording continues.')
        else:self.quality.setText('No fresh frame — maps and point measurements cleared')
        if self.closing and (self.thread is None or not self.thread.is_alive()):self.close()

    def closeEvent(self,event):
        if self.thread and self.thread.is_alive():
            self.closing=True;self.stop_run();event.ignore()
        else:
            self.timer.stop()
            # Matplotlib queues a zero-delay Qt redraw. Cancel pending work
            # before Qt destroys the canvases, including during replay teardown.
            self.comparison_canvas._draw_pending=False
            self.canvas._draw_pending=False
            event.accept()


def launch(args):
    from radar.qt_platform import staged_platform_plugins
    with staged_platform_plugins():
        app=QtWidgets.QApplication.instance()or QtWidgets.QApplication([])
        window=Window(args)
        try:
            window.show()
            if args.snapshot:
                window.replay_snapshot(args.snapshot_frame)
                path=Path(args.snapshot).resolve();path.parent.mkdir(parents=True,exist_ok=True)
                def save():
                    if not window.grab().save(str(path)):app.exit(2)
                    window.close()
                QtCore.QTimer.singleShot(200,save)
            return app.exec()
        finally:
            if window.thread is None or not window.thread.is_alive():window.close()
