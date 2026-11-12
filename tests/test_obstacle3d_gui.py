import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest

from PyQt6 import QtWidgets
import numpy as np

from radar.config import Config
from radar.obstacle3d import Obstacle3DDetector, Settings
from radar.obstacle3d_gui import ObstacleWindow
from radar.synthetic import generate


class Obstacle3DGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_xyz_warning_and_terminal_rendering_match_export(self):
        config = Config()
        settings = Settings(window_seconds=.1, persistence_windows=1)
        window = ObstacleWindow(config, recording='not-opened', start_delay=999, settings=settings)
        try:
            detector = Obstacle3DDetector(config, settings)
            result = detector.push(generate(config, 1, seed=1))
            window.latest = result
            window.redraw()
            window.canvas.draw()
            points = [r['xyz'] for r in result['returns'] if r['persistent'] and r['xyz'] is not None]
            self.assertTrue(points)
            actual = np.array(window.cloud.collections[0]._offsets3d).T
            np.testing.assert_allclose(actual, points)
            self.assertIn('provisional 3D', window.status.text())
            frame = generate(config, 2, seed=2, channel_response=[0, 1, 0], noise=0)
            result = detector.push(frame)
            self.assertTrue(any(r['xyz'] is None for r in result['returns']))
            window.latest = result
            window.redraw()
            self.assertTrue(window.unresolved.collections)
            window.last_result_time = -999
            window.refresh()
            self.assertEqual(len(window.cloud.collections), 0)
            self.assertIn('UNCERTAIN', window.status.text())
            self.assertEqual(window.latest['reason'], 'stale_result')
            window.latest = detector.invalidate('serial_timeout')
            window.redraw()
            self.assertEqual(len(window.cloud.collections), 0)
            self.assertEqual(len(window.unresolved.collections), 0)
            self.assertIn('UNCERTAIN', window.status.text())
        finally:
            window.close()
