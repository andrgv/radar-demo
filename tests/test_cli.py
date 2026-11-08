import contextlib
import io
import unittest
from unittest.mock import patch
from radar.cli import main


class SourceSelectionTests(unittest.TestCase):
    def test_door_distance_units(self):
        report = dict(selected_bin=None, heldout=None, limitations='test')
        for option, value, expected in (('--distance-inches', '48.5', 1.2319),
                                        ('--distance', '1.2', 1.2)):
            with self.subTest(option=option), \
                 patch('radar.cli.Config.load'), \
                 patch('radar.door_check.record_door_check', return_value=report) as capture, \
                 contextlib.redirect_stdout(io.StringIO()):
                main(['door-check', 'unused', '--port', 'FAKE', '--config', 'unused', option, value])
                self.assertAlmostEqual(capture.call_args.args[3], expected)

    def test_door_distance_requires_exactly_one_unit(self):
        for distances in ([], ['--distance', '1', '--distance-inches', '40']):
            with self.subTest(distances=distances), contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as error:
                main(['door-check', 'unused', '--port', 'FAKE', '--config', 'unused', *distances])
            self.assertEqual(error.exception.code, 2)

    def test_gui_requires_explicit_source(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["gui"])
        self.assertEqual(error.exception.code, 2)

    @patch("radar.gui.run", return_value=0)
    def test_explicit_simulation(self, run):
        self.assertEqual(main(["gui", "--synthetic"]), 0)
        run.assert_called_once()
        self.assertIsNone(run.call_args.kwargs["port"])

    def test_live_and_simulation_are_mutually_exclusive(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["gui", "--synthetic", "--port", "COM7"])
