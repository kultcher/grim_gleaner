"""GUI application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.runtime_paths import RuntimePaths, resolve_runtime_paths
from gd_affix_relevance.ui.main_window import MainWindow
from gd_affix_relevance.ui.style import APP_STYLESHEET


def create_application(argv: Sequence[str] | None = None) -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    application = QApplication(list(argv) if argv is not None else sys.argv)
    application.setApplicationName("Grim Gleaner")
    application.setOrganizationName("Grim Gleaner")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
    return application


def main(argv: Sequence[str] | None = None) -> int:
    application = create_application(argv)
    window = MainWindow(
        settings=QSettings(),
        runtime_paths=_entrypoint_runtime_paths(),
    )
    window.show()
    QTimer.singleShot(0, window.show_startup_prompts)
    return application.exec()


def _entrypoint_runtime_paths(
    compiled_marker: object | None = None,
    executable: Path | None = None,
) -> RuntimePaths:
    """Resolve packaged resources beside Nuitka's compiled executable.

    Nuitka injects ``__compiled__`` into the entry-point module. Once that
    marker confirms this is a compiled build, ``sys.argv[0]`` is the actual
    launched executable path and therefore the unambiguous root for portable
    catalogs, tags, profiles, staging files, and backups.
    """

    marker = (
        globals().get("__compiled__")
        if compiled_marker is None
        else compiled_marker
    )
    if marker is not None:
        executable_path = (
            Path(sys.argv[0]) if executable is None else Path(executable)
        )
        return resolve_runtime_paths(
            application_root=executable_path.expanduser().resolve().parent
        )
    return resolve_runtime_paths()


if __name__ == "__main__":
    raise SystemExit(main())
