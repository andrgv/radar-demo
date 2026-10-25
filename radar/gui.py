import queue
import threading
import time
import numpy as np
from PyQt6 import QtCore, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from .acquisition import Source, paced_frames
from .processing import Processor
from .storage import Recorder


def range_readout(result):
    qualification = "" if result.calibrated else " (provisional scale; NOT validated object distances)"
    distances = sorted({round(item.range_m, 3) for item in result.detections})
    if not distances:
        return "No detections above threshold" + qualification
    values = ", ".join(
        f"{distance:.3f} m" if result.calibrated else
        f"bin {int(np.argmin(abs(result.ranges - distance)))} (~{distance:.3f} m from config)"
        for distance in distances[:8])
    if len(distances) > 8:
        values += f" (+{len(distances) - 8} more)"
    return ("Detected ranges" if result.calibrated else "Detected spectral peaks") + qualification + ": " + values


class Window(QtWidgets.QMainWindow):
    acquisition_finished = QtCore.pyqtSignal()

    def __init__(self, config, port=None, recording=None, record=None, metadata=None, phase_probe_range=None,
                 background_path=None, spatial_map=False, seconds=None, start_delay=0, point_cloud=False):
        super().__init__()
        if seconds is not None and (not np.isfinite(seconds) or seconds <= 0):
            raise ValueError('seconds must be finite and greater than zero')
        self.seconds = seconds
        if not np.isfinite(start_delay) or start_delay < 0:
            raise ValueError('start_delay must be finite and nonnegative')
        self.pending_start = start_delay > 0
        self.start_deadline = time.monotonic() + start_delay
        if seconds is not None:
            self.acquisition_finished.connect(self.close)
        self.completion_label = 'Replay complete' if recording else 'Acquisition complete; recording closed'
        mode = f"LIVE {port}" if port else ("REPLAY" if recording else "SYNTHETIC")
        self.setWindowTitle(f"3 RX radar | {mode} | material feature research")
        self.resize(1350, 900)
        self.config = config
        self.spatial_map = spatial_map or point_cloud
        spatial_map=self.spatial_map
        self.point_cloud=point_cloud
        self.phase_probe_range = phase_probe_range
        self.background_path = background_path
        self.stop = threading.Event()
        self.results = queue.Queue(maxsize=2)
        self.display_drops = 0
        self.error = None
        self.finished = False
        self.stats = {}
        self.figure = Figure(layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.profile = self.figure.add_subplot(231)
        self.angle = self.figure.add_subplot(232)
        self.cloud = self.figure.add_subplot(233, projection="3d")
        self.doppler = self.figure.add_subplot(234)
        self.temporal = self.figure.add_subplot(235)
        self.feature_axes = self.figure.add_subplot(236)
        self.history = []
        self.probe_history = []
        self.relative_phase_history = []
        self.phase_tabs = None
        self.phase_canvas = None
        self.status = QtWidgets.QLabel()
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        if not port and not recording:
            banner = QtWidgets.QLabel("SIMULATION - generated targets only. No radar hardware is being read.")
            banner.setStyleSheet("background: #ffc857; color: #111; padding: 12px; font-weight: bold;")
        else:
            banner = QtWidgets.QLabel(f"LIVE RADAR: {port}" if port else f"RECORDED DATA: {recording}")
        banner.setText(banner.text() + f" | {config.geometry_label} | roll {config.mount_roll_deg:g} deg")
        if background_path:
            banner.setText(banner.text() + " | EXPERIMENTAL static background subtraction")
        layout.addWidget(banner)
        self.distance_readout = QtWidgets.QLabel("Waiting for range detections...")
        self.distance_readout.setWordWrap(True)
        self.distance_readout.setStyleSheet("font-size: 16px; padding: 8px;")
        layout.addWidget(self.distance_readout)
        self.probe_readout = QtWidgets.QLabel()
        self.probe_readout.setWordWrap(True)
        self.probe_readout.setVisible(phase_probe_range is not None)
        if phase_probe_range is not None:
            self.probe_readout.setText("Phase probe: waiting for data. This is not object tracking.")
        layout.addWidget(self.probe_readout)
        if phase_probe_range is not None:
            self.phase_tabs = QtWidgets.QTabWidget()
            phase_widget = QtWidgets.QWidget()
            phase_layout = QtWidgets.QVBoxLayout(phase_widget)
            controls = QtWidgets.QHBoxLayout()
            controls.addWidget(QtWidgets.QLabel("Angle view: +/-"))
            self.angle_span = QtWidgets.QSpinBox()
            self.angle_span.setRange(10, 90)
            self.angle_span.setValue(30)
            self.angle_span.setSuffix(" deg")
            controls.addWidget(self.angle_span)
            controls.addWidget(QtWidgets.QLabel("Right = positive azimuth; up = positive elevation. Raw estimates, no smoothing."))
            controls.addStretch()
            phase_layout.addLayout(controls)
            self.phase_figure = Figure(layout="constrained")
            phase_grid = self.phase_figure.add_gridspec(2, 2, height_ratios=[1.5, 1])
            self.direction_axes = self.phase_figure.add_subplot(phase_grid[0, 0])
            self.close_cloud = self.phase_figure.add_subplot(phase_grid[0, 1], projection="3d")
            self.direction_history_axes = self.phase_figure.add_subplot(phase_grid[1, :])
            self.phase_canvas = FigureCanvasQTAgg(self.phase_figure)
            phase_layout.addWidget(self.phase_canvas)
            self.phase_tabs.addTab(phase_widget, "Phase movement check")
            self.phase_tabs.addTab(self.canvas, "Radar overview")
            layout.addWidget(self.phase_tabs)
        else:
            layout.addWidget(self.canvas)
        if spatial_map:
            self.spatial_figure = Figure(layout='constrained')
            self.spatial_canvas = FigureCanvasQTAgg(self.spatial_figure)
            from .spatial import SpatialRenderer
            self.spatial_renderer = SpatialRenderer(self.spatial_canvas)
            self.spatial_tabs = QtWidgets.QTabWidget()
            self.spatial_tabs.addTab(self.spatial_canvas, '3D reflectivity (unvalidated angles)')
            previous = self.phase_tabs if self.phase_tabs is not None else self.canvas
            layout.removeWidget(previous)
            self.spatial_tabs.addTab(previous, 'Diagnostics')
            layout.addWidget(self.spatial_tabs)
            controls = QtWidgets.QHBoxLayout()
            controls.addWidget(QtWidgets.QLabel('Display range below strongest cell (dB):'))
            self.spatial_dynamic_range = QtWidgets.QSpinBox()
            self.spatial_dynamic_range.setRange(3, 60)
            self.spatial_dynamic_range.setValue(30)
            controls.addWidget(self.spatial_dynamic_range)
            controls.addWidget(QtWidgets.QLabel('View range (m):'))
            self.spatial_range = QtWidgets.QDoubleSpinBox()
            self.spatial_range.setRange(float(config.ranges[2]), float(config.ranges[-2]))
            self.spatial_range.setValue(min(4.0, float(config.ranges[-2])))
            controls.addWidget(self.spatial_range)
            layout.addLayout(controls)
        layout.addWidget(self.status)
        self.setCentralWidget(widget)
        self.worker = threading.Thread(target=self.acquire,
            args=(port, recording, record, metadata), daemon=True)
        if not self.pending_start:
            self.worker.start()
        else:
            self.distance_readout.setStyleSheet('font-size: 64px; font-weight: bold; color: #ff0000; padding: 16px;')
            self.distance_readout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.distance_readout.setText(f'Set up now — acquisition starts in {int(np.ceil(start_delay))} seconds')
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)

    def acquire(self, port, recording, record, metadata):
        source = None
        recorder = None
        duration_timer = None
        try:
            from .background import SpectralBackground
            background = SpectralBackground.from_path(self.background_path, self.config) if self.background_path else None
            processor = Processor(self.config, phase_probe_range=self.phase_probe_range, background=background,
                                  spatial_map=self.spatial_map,point_cloud=self.point_cloud)
            source = Source(self.config, port, recording)
            metadata = {**(metadata or {}), "background_method": "fixed_complex_spectrum" if background else "none",
                        "background_source": self.background_path}
            recorder = Recorder(record, self.config, metadata) if record else None
            source.transport_recorder = recorder
            if recorder is not None and background is not None:
                background.save(recorder.path / "spectral-background.npz")
            if self.seconds is not None:
                duration_timer = threading.Timer(self.seconds, self.stop.set)
                duration_timer.daemon = True
                duration_timer.start()
            for frame in paced_frames(source, self.stop):
                start = time.perf_counter()
                result = processor.process(frame)
                if recorder:
                    recorder.write(frame, result)
                self.stats = {"sequence_gaps": source.parser.gaps, "crc_errors": source.parser.bad_crc,
                    "bad_headers": source.parser.bad_headers, "restarts": source.parser.restarts,
                    "discarded_serial_bytes": source.parser.discarded_bytes,
                    "device_drops": frame.dropped, "device_errors": frame.errors,
                    "capture_elapsed_us":frame.capture_elapsed_us,
                    "detections": len(result.detections),
                    "valid_3d": sum(item.angle_valid for item in result.detections),
                    "scene_points": len(result.spatial_volume.point_cloud.xyz) if result.spatial_volume is not None and result.spatial_volume.point_cloud is not None else 0,
                    "background_subtracted": result.background_subtracted,
                    "processing_ms": round((time.perf_counter() - start) * 1000, 1)}
                try:
                    self.results.put_nowait(result)
                except queue.Full:
                    try:
                        self.results.get_nowait()
                    except queue.Empty:
                        pass
                    self.display_drops += 1
                    self.results.put_nowait(result)
        except Exception as error:
            self.error = str(error)
        finally:
            if duration_timer is not None:
                duration_timer.cancel()
            if recorder:
                recorder.close()
            if source:
                source.close()
            self.finished = True
            self.acquisition_finished.emit()

    def refresh(self):
        if self.pending_start:
            remaining = self.start_deadline - time.monotonic()
            if remaining > 0:
                self.distance_readout.setText(f'Set up now — acquisition starts in {int(np.ceil(remaining))} seconds')
                self.status.setText('Setup countdown — not acquiring or recording yet')
                return
            self.pending_start = False
            self.distance_readout.setStyleSheet('font-size: 16px; padding: 8px;')
            self.distance_readout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
            self.distance_readout.setText('Acquiring — waiting for radar data...')
            self.worker.start()
            return
        result = None
        while True:
            try:
                result = self.results.get_nowait()
            except queue.Empty:
                break
        if result is None:
            if self.error:
                self.status.setText("Acquisition error: " + self.error)
            elif self.finished:
                self.status.setText(self.completion_label + " | " + str(self.stats))
            return
        if self.spatial_map and result.spatial_volume is not None:
            if self.spatial_tabs.currentIndex() == 0:
                self.spatial_renderer.update(result.spatial_volume, self.spatial_dynamic_range.value(),
                                             self.spatial_range.value())
                self.distance_readout.setText(range_readout(result))
                self.status.setText(f"Frame {result.sequence} | {self.stats} | display skips {self.display_drops}")
                return  # Hidden diagnostics must not rebuild or draw every frame.
        for axes in (self.profile, self.angle, self.cloud, self.doppler, self.temporal, self.feature_axes):
            axes.clear()
        self.profile.plot(result.ranges, result.profile_db)
        self.distance_readout.setText(range_readout(result))
        detected_ranges = sorted({item.range_m for item in result.detections})
        for distance in detected_ranges[:8]:
            range_bin = int(np.argmin(abs(result.ranges - distance)))
            power = result.profile_db[range_bin]
            self.profile.plot(distance, power, "o", color="tab:red")
            peak_label = f"{distance:.3f} m" if result.calibrated else f"bin {range_bin}"
            self.profile.annotate(peak_label, (distance, power),
                xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8)
        self.profile.set(title="Range profile", xlabel="Range (m)", ylabel="Power (dB ADC²)")
        self.angle.imshow(result.heatmap_db, origin="lower", aspect="auto",
            extent=[result.azimuths[0], result.azimuths[-1], result.ranges[0], result.ranges[-1]], cmap="magma")
        self.angle.set(title="Range–azimuth (elevation slice 0°)", xlabel="Azimuth (deg)", ylabel="Range (m)")
        for moving, color in ((False, "tab:blue"), (True, "tab:orange")):
            points = [item.xyz for item in result.detections if item.angle_valid and item.moving == moving]
            if points:
                points = np.asarray(points)
                self.cloud.scatter(*points.T, c=color, label="moving" if moving else "stationary")
        maximum = max(1, result.ranges[-1])
        probe = result.phase_probe
        if probe is not None:
            maximum = max(1, probe.selected_range_m * 2)
            usable = probe.usable
            self.probe_history.append((probe.azimuth_deg, probe.elevation_deg) if usable else (np.nan, np.nan))
            self.probe_history = self.probe_history[-100:]
            self.relative_phase_history.append(probe.relative_phase_deg)
            self.relative_phase_history = self.relative_phase_history[-100:]
            if self.phase_tabs is not None and self.phase_tabs.currentIndex() == 0:
                self.render_phase_view(probe, usable)
            direction_text = (f"azimuth {probe.azimuth_deg:+.1f} deg, elevation {probe.elevation_deg:+.1f} deg"
                              if usable else "DIRECTION REJECTED: " + probe.rejection_reason)
            self.probe_readout.setText(
                f"PHASE PROBE (not a track): bin {probe.range_bin}, range {probe.selected_range_m:.2f} m, {direction_text} | "
                f"coherence {probe.min_coherence:.3f} | local SNR {probe.snr_db:.1f} dB / "
                f"detection threshold {probe.threshold_db:.1f} dB | "
                f"{'local peak' if probe.local_peak else 'not a local peak; may contain background'} | "
                f"RAW RX2-RX1 {probe.relative_phase_deg[0]:+.1f} deg, RX3-RX1 {probe.relative_phase_deg[1]:+.1f} deg")
            if usable:
                self.cloud.scatter(*probe.xyz, s=100, facecolors="none", edgecolors="magenta",
                    label="Phase probe (not a detection)")
                self.cloud.legend(fontsize=7)
        self.cloud.set(xlim=(-maximum, maximum), ylim=(0, maximum), zlim=(-maximum / 2, maximum / 2),
            xlabel="Right (m)", ylabel="Forward (m)", zlabel="Up (m)", title="3D frame detections (untracked)")
        self.doppler.imshow(result.doppler_db, origin="lower", aspect="auto",
            extent=[result.ranges[0], result.ranges[-1], result.velocities[0], result.velocities[-1]], cmap="viridis")
        self.doppler.set(title="Range–Doppler (static retained)", xlabel="Range (m)", ylabel=result.doppler_unit)
        self.history.append(result.features["reflection_db"])
        self.history = self.history[-100:]
        self.temporal.plot(self.history)
        self.temporal.set(title="Strongest return over displayed frames", xlabel="Displayed frame", ylabel="dB ADC²")
        self.feature_axes.axis("off")
        feature_text = "Material: UNKNOWN (no trained classifier)\n\n" + "\n".join(
            f"{key}: {value:.4g}" for key, value in result.features.items())
        self.feature_axes.text(0, 1, feature_text, va="top", fontsize=9)
        state = "CALIBRATED CONFIG" if result.calibrated else "PROVISIONAL AXES — verify timing, geometry and phase"
        self.status.setText(f"{state} | frame {result.sequence} | {self.stats} | display skips {self.display_drops}")
        if self.phase_tabs is None or self.phase_tabs.currentIndex() == 1:
            self.canvas.draw_idle()

    def render_phase_view(self, probe, usable):
        span = self.angle_span.value()
        for axes in (self.direction_axes, self.close_cloud, self.direction_history_axes):
            axes.clear()
        self.direction_axes.axhline(0, color="gray", linewidth=0.8)
        self.direction_axes.axvline(0, color="gray", linewidth=0.8)
        self.direction_axes.grid(alpha=0.25)
        self.direction_axes.set(xlim=(-span, span), ylim=(-span, span),
            xlabel="Azimuth (degrees)", ylabel="Elevation (degrees)",
            title="Current phase direction (untracked)")
        self.direction_axes.set_aspect("equal", adjustable="box")
        distance = probe.selected_range_m
        horizontal_extent = max(0.1, distance * np.sin(np.radians(span)))
        depth_extent = max(0.2, distance * 0.2)
        self.close_cloud.set(xlim=(-horizontal_extent, horizontal_extent),
            ylim=(max(0, distance - depth_extent), distance + depth_extent),
            zlim=(-horizontal_extent, horizontal_extent), xlabel="Right (m)",
            ylabel="Forward (m)", zlabel="Up (m)", title="Close-up: selected range")
        self.close_cloud.set_box_aspect((1, 0.6, 1))
        self.close_cloud.view_init(elev=15, azim=-70)
        self.close_cloud.scatter(0, distance, 0, marker="+", color="gray", s=120)
        if usable:
            self.direction_axes.scatter(probe.azimuth_deg, probe.elevation_deg,
                s=220, color="magenta", edgecolors="black", zorder=3)
            self.direction_axes.text(0.03, 0.97, f"AZ {probe.azimuth_deg:+.1f} deg\nEL {probe.elevation_deg:+.1f} deg",
                transform=self.direction_axes.transAxes, va="top", fontsize=12, fontweight="bold",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
            self.close_cloud.scatter(*probe.xyz, s=220, color="magenta", edgecolors="black", depthshade=False)
            if max(abs(probe.azimuth_deg), abs(probe.elevation_deg)) > span:
                self.direction_axes.text(0.5, 0.95, "Outside angle view - increase +/- degrees",
                    transform=self.direction_axes.transAxes, ha="center", va="top", color="red")
        else:
            self.direction_axes.text(0.5, 0.5, "No trustworthy direction\n" + probe.rejection_reason + "\nNo previous point is held",
                transform=self.direction_axes.transAxes, ha="center", va="center", color="red", fontsize=9, wrap=True)
        values = np.asarray(self.probe_history if usable else self.relative_phase_history)
        labels = ("Azimuth (left/right)", "Elevation (down/up)") if usable else ("RAW RX2-RX1 phase", "RAW RX3-RX1 phase")
        self.direction_history_axes.plot(values[:, 0], color="tab:blue", marker=".", label=labels[0])
        self.direction_history_axes.plot(values[:, 1], color="tab:orange", marker=".", label=labels[1])
        self.direction_history_axes.axhline(0, color="gray", linewidth=0.8)
        self.direction_history_axes.set(ylim=(-span, span) if usable else (-180, 180), xlabel="Displayed update (last 100)",
            ylabel="Degrees", title=("Raw angle history (no smoothing; invalid estimates leave gaps)" if usable
                else "RAW inter-channel phase only - not azimuth/elevation; direction rejected"))
        self.direction_history_axes.grid(alpha=0.25)
        self.direction_history_axes.legend(loc="upper left")
        self.phase_canvas.draw_idle()

    def closeEvent(self, event):
        self.timer.stop()
        self.stop.set()
        if self.worker.ident is not None:
            self.worker.join(timeout=3)
        event.accept()


def run(config, **kwargs):
    application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = Window(config, **kwargs)
    window.show()
    return application.exec()
