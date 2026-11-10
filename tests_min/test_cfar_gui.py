"""Exercise the actual Qt replay path without a baseline, serial access or fitting."""
import argparse
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6 import QtWidgets
from radar.storage import Recorder
from radar_min.gui import Window, display_values
from radar_min.cfar import CfarDetector
from tests_min.test_cfar import C, frame


class CfarGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_replay_no_empty_reference_or_estimator_and_plot_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp)/'config.json';C.save(config)
            recording = Path(tmp)/'replay'
            with Recorder(recording, C) as recorder:
                for i in range(1, 5):recorder.write(frame(i))
            args = argparse.Namespace(config=str(config), baseline=None, detector='cfar',
                cfar_guard=2, cfar_training=8, cfar_min_training=8, cfar_factor=6,
                replay=str(recording), estimator='fixed', port='must-not-open')
            with patch('radar_min.gui.Estimate', side_effect=AssertionError('No empty fitting')), \
                 patch('radar_min.gui.stream', side_effect=AssertionError('No serial in replay')):
                window = Window(args)
                try:
                    self.assertFalse(window.empty.isEnabled())
                    self.assertTrue(window.live.isEnabled())
                    window.start(False);window.thread.join(timeout=5)
                    self.assertFalse(window.thread.is_alive())
                    window.tick()
                    self.assertNotIn('Stopped:', window.status.text())
                    self.assertEqual(len(window.history), 4)
                    d = CfarDetector(C)
                    for i in range(1, 4):reading = d.update(frame(i))
                    window.latest = (time.monotonic(), reading)
                    window.tick()
                    self.assertEqual(len(window.threshold_line.get_xdata()), 33)
                    self.assertEqual(len(window.peaks.get_xdata()), 1)
                    self.assertAlmostEqual(float(window.distance.text().split()[0]), 2*C.spacing_m*100, delta=1)
                    self.assertIn('Raw-spectrum', window.detail.text())
                    self.assertEqual(display_values(reading, False)[0], '—')
                    reading['target_detected'] = False
                    self.assertEqual(display_values(reading, True)[0], '—')
                    window.latest = (time.monotonic()-2, reading);window.tick()
                    self.assertEqual(len(window.threshold_line.get_xdata()), 0)
                    self.assertFalse(window.root.exists())
                finally:window.close()


if __name__ == '__main__':unittest.main()
