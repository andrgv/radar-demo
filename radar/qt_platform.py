"""Work around macOS Qt platform-plugin discovery in this local virtualenv."""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import sys
import tempfile


@contextmanager
def staged_platform_plugins():
    """Stage the installed PyQt6 platform plugins outside the repo on macOS.

    On this Mac, Qt reports that cocoa is missing when it scans the virtualenv
    directory, although the dylib is present. The same installed dylib loads
    from a temporary directory. Respect an explicitly configured plugin path.
    """
    if sys.platform != "darwin" or os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
        yield
        return

    from PyQt6.QtCore import QLibraryInfo

    source = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)) / "platforms"
    plugins = tuple(source.glob("libq*.dylib"))
    if not any(plugin.name == "libqcocoa.dylib" for plugin in plugins):
        raise RuntimeError(f"PyQt6 cocoa platform plugin is missing from {source}")

    # The per-user macOS TMPDIR has the same plugin-loading problem here;
    # /private/tmp is the tested executable plugin location on this host.
    with tempfile.TemporaryDirectory(prefix="glass-radar-qt-", dir="/private/tmp") as temporary:
        Path(temporary).chmod(0o755)
        for plugin in plugins:
            # copy2 would preserve the source's macOS "hidden" file flag,
            # which makes Qt skip the copied dylib during directory scanning.
            shutil.copy(plugin, Path(temporary) / plugin.name)
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = temporary
        try:
            yield
        finally:
            os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
