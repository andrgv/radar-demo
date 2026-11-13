import os
from pathlib import Path
import stat
import sys
import unittest
from unittest.mock import patch

from radar.qt_platform import staged_platform_plugins


@unittest.skipUnless(sys.platform == "darwin", "macOS platform plugins only")
class QtPlatformTests(unittest.TestCase):
    def test_staged_cocoa_plugin_is_not_hidden(self):
        with patch.dict(os.environ, {"QT_QPA_PLATFORM_PLUGIN_PATH": ""}):
            with staged_platform_plugins():
                directory = Path(os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"])
                cocoa = directory / "libqcocoa.dylib"
                self.assertTrue(cocoa.is_file())
                self.assertFalse(cocoa.stat().st_flags & stat.UF_HIDDEN)
            self.assertFalse(directory.exists())


if __name__ == "__main__":
    unittest.main()
