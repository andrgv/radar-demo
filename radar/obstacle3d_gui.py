"""USB/replay 3D obstacle view; no empty-scene calibration required."""
import queue
import threading
import time

import numpy as np
from PyQt6 import QtCore, QtWidgets
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from .obstacle3d import Settings, iter_results


class ObstacleWindow(QtWidgets.QMainWindow):
    def __init__(self, config, *, port=None, recording=None, record=None, seconds=None,
                 start_delay=0, settings=None):
        super().__init__()
        self.config = config
        self.settings = (settings or Settings()).validate()
        self.stop = threading.Event()
        self.queue = queue.Queue(maxsize=1)
        self.error = None
        self.finished = False
        self.auto_close = seconds is not None
        self.latest = None
        self.last_result_time = None
        self.setWindowTitle('Wavvy | experimental 3D obstacle candidates')
        self.resize(1150, 800)
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        self.status = QtWidgets.QLabel('UNCERTAIN — waiting for radar data')
        self.status.setStyleSheet('font-size: 20px; font-weight: bold; padding: 8px;')
        layout.addWidget(self.status)
        self.detail = QtWidgets.QLabel(
            'Provisional sensor-relative XYZ; angles unvalidated. Unresolved returns remain warnings. '
            'No return does not establish a clear path. Material unknown.')
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel('View range (m; detection still scans all acquired bins):'))
        self.view_range = QtWidgets.QDoubleSpinBox()
        self.view_range.setRange(.1, max(.1, float(config.ranges[-2])))
        self.view_range.setValue(min(4., self.view_range.maximum()))
        self.view_range.valueChanged.connect(self.redraw)
        controls.addWidget(self.view_range)
        layout.addLayout(controls)
        self.figure = Figure(layout='constrained')
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.cloud = self.figure.add_subplot(121, projection='3d')
        self.unresolved = self.figure.add_subplot(122)
        layout.addWidget(self.canvas)
        self.setCentralWidget(widget)
        self.worker = threading.Thread(target=self.acquire, kwargs=dict(
            port=port, recording=recording, output=record, seconds=seconds), daemon=True)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(100)
        self.start_timer = QtCore.QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.worker.start)
        if start_delay:
            self.status.setText(f'UNCERTAIN — acquisition starts after {start_delay:g} seconds')
        self.start_timer.start(int(start_delay * 1000))
        self.redraw()

    def acquire(self, **kwargs):
        try:
            for result in iter_results(self.config, settings=self.settings, stop=self.stop,
                                       paced=True, **kwargs):
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    pass
                self.queue.put_nowait(result)
        except Exception as error:
            self.error = str(error)
        finally:
            self.finished = True

    def refresh(self):
        try:
            self.latest = self.queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self.last_result_time = time.monotonic()
            self.redraw()
        if (self.latest is not None and self.latest['complete_window'] and self.last_result_time is not None
                and time.monotonic() - self.last_result_time > max(2., 2 * self.settings.window_seconds)):
            self.latest = {**self.latest, 'state': 'uncertain', 'reason': 'stale_result',
                           'complete_window': False, 'returns': []}
            self.redraw()
        if self.error:
            self.latest = None
            self.status.setText('UNCERTAIN — acquisition error: ' + self.error)
            self.redraw()
        if self.finished and self.auto_close:
            self.close()

    def redraw(self, *_):
        self.cloud.clear()
        self.unresolved.clear()
        maximum = self.view_range.value()
        result = self.latest
        returns = result['returns'] if result is not None else []
        persistent = [r for r in returns if r['persistent']]
        positioned = [r for r in persistent if r['xyz'] is not None]
        unresolved = [r for r in persistent if r['xyz'] is None]
        points = np.array([r['xyz'] for r in positioned if 0 < r['provisional_range_m'] <= maximum]).reshape(-1, 3)
        if len(points):
            self.cloud.scatter(*points.T, color='tab:blue', s=35)
        warnings = [r for r in unresolved if 0 < r['provisional_range_m'] <= maximum]
        if warnings:
            self.unresolved.scatter([r['provisional_range_m'] for r in warnings],
                                    [r['contrast_db'] for r in warnings], marker='^', color='darkorange')
        self.cloud.set(xlim=(-maximum, maximum), ylim=(0, maximum), zlim=(-maximum, maximum),
                       xlabel='Right (m)', ylabel='Forward (m)', zlabel='Up (m)',
                       title='Provisional 3D reflector candidates\nAngular calibration unverified')
        self.unresolved.set(xlim=(0, maximum), xlabel='Provisional range (m)',
                            ylabel='Local contrast (dB)', title='Unresolved-direction warnings\nNo XYZ is assigned')
        self.unresolved.grid(alpha=.2)
        if result is not None:
            if persistent:
                self.status.setText(f'OBSTACLE CANDIDATES — {len(positioned)} provisional 3D, '
                                    f'{len(unresolved)} unresolved direction')
            else:
                self.status.setText('UNCERTAIN — ' + result['reason'].replace('_', ' '))
            tentative = len(returns) - len(persistent)
            self.detail.setText(
                f'{tentative} tentative returns; {self.settings.persistence_windows} consecutive '
                f'{self.settings.window_seconds:g} s windows required. '
                'Sensor-relative positions, not verified surfaces or a world map. '
                'Material unknown; no return does not establish a clear path.')
        self.canvas.draw_idle()

    def closeEvent(self, event):
        self.start_timer.stop()
        self.timer.stop()
        self.stop.set()
        if self.worker.ident is not None:
            self.worker.join(timeout=3)
        event.accept()


def run(config, **kwargs):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = ObstacleWindow(config, **kwargs)
    window.show()
    return app.exec()
