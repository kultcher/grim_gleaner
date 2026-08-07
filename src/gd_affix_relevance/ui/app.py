"""GUI application entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

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
    window = MainWindow(settings=QSettings())
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
