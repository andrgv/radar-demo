import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PyQt6 import QtCore, QtWidgets
from radar.config import Config
from radar.gui import Window

application = QtWidgets.QApplication([])
window = Window(Config())
window.show()


def finish():
    Path("artifacts").mkdir(exist_ok=True)
    window.canvas.draw()
    window.canvas.print_png("artifacts/gui-smoke.png")
    assert not window.error, window.error
    assert window.history, "No processed frames reached the GUI"
    assert "Detected spectral peaks" in window.distance_readout.text(), window.distance_readout.text()
    assert "provisional scale" in window.distance_readout.text()
    window.close()
    application.quit()


QtCore.QTimer.singleShot(2500, finish)
application.exec()
print("Qt acquisition/render/close smoke test passed")
