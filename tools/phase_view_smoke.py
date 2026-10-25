import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PyQt6 import QtWidgets
from radar.config import Config
from radar.gui import Window
from radar.processing import Processor
from radar.synthetic import Target, generate

application = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
config = Config()
distance = float(config.ranges[7])
processor = Processor(config, phase_probe_range=distance)
with patch.object(Window, "acquire", return_value=None):
    window = Window(config, phase_probe_range=distance)
window.timer.stop()
window.show()
for sequence, azimuth in enumerate(np.linspace(-20, 20, 30), start=1):
    target = Target(distance, azimuth_deg=float(azimuth), elevation_deg=float(azimuth / 2))
    result = processor.process(generate(config, sequence, targets=[target], seed=sequence))
    window.results.put_nowait(result)
    window.refresh()
assert window.probe_history[0][0] < -19
assert window.probe_history[-1][0] > 19
assert window.direction_axes.get_xlim() == (-30, 30)
assert window.phase_tabs.currentIndex() == 0
application.processEvents()
Path("artifacts").mkdir(exist_ok=True)
window.phase_canvas.draw()
window.phase_canvas.print_png("artifacts/phase-movement-view.png")
invalid = replace(result, phase_probe=replace(result.phase_probe, angle_valid=False))
window.results.put_nowait(invalid)
window.refresh()
assert np.isnan(window.probe_history[-1]).all()
assert not window.direction_axes.collections
window.close()
print("Phase movement view: direction changes, history, zoom and invalid-point removal pass")
