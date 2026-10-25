import contextlib
import io
import unittest
from unittest.mock import patch
from radar.cli import main


class SourceSelectionTests(unittest.TestCase):
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
