"""GUI application entry point."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.domain import (
    ENGLISH_LOCALE,
    LocaleSpec,
    ui_locale_for_code,
)
from gd_affix_relevance.grade_export import detect_grim_dawn_user_settings_root
from gd_affix_relevance.runtime_paths import RuntimePaths, resolve_runtime_paths
from gd_affix_relevance.ui import i18n
from gd_affix_relevance.ui.main_window import MainWindow
from gd_affix_relevance.ui.settings import UI_LOCALE_SETTING
from gd_affix_relevance.ui.style import APP_STYLESHEET

SETTINGS_ROOT_ENVIRONMENT_VARIABLE = "GRIM_GLEANER_SETTINGS_ROOT"
DOCUMENTS_ROOT_ENVIRONMENT_VARIABLE = "GRIM_GLEANER_DOCUMENTS_ROOT"


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
    settings = _application_settings()
    runtime_paths = _entrypoint_runtime_paths()
    i18n.configure(runtime_paths.i18n_root, _resolve_ui_locale(settings))
    window = MainWindow(
        settings=settings,
        runtime_paths=runtime_paths,
        user_settings_root=_user_settings_root(),
    )
    window.show()
    QTimer.singleShot(0, window.show_startup_prompts)
    return application.exec()


def _application_settings(
    environment: Mapping[str, str] | None = None,
) -> QSettings:
    """Return normal settings or an isolated INI file for install tests."""

    environment = os.environ if environment is None else environment
    configured_root = environment.get(
        SETTINGS_ROOT_ENVIRONMENT_VARIABLE, ""
    ).strip()
    if not configured_root:
        return QSettings()

    root = Path(configured_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return QSettings(
        str(root / "grim-gleaner.ini"),
        QSettings.Format.IniFormat,
    )


def _user_settings_root(
    environment: Mapping[str, str] | None = None,
) -> Path | None:
    """Resolve Documents normally, with an isolated test override."""

    environment = os.environ if environment is None else environment
    configured_root = environment.get(
        DOCUMENTS_ROOT_ENVIRONMENT_VARIABLE, ""
    ).strip()
    documents_root = Path(configured_root) if configured_root else None
    return detect_grim_dawn_user_settings_root(documents_root)


def _resolve_ui_locale(settings: QSettings) -> LocaleSpec:
    """Read the persisted interface language, defaulting safely to English.

    The UI locale is chosen once at startup (see ``ui.i18n``): changing it
    later in Settings takes effect on the next launch, not live.
    """

    code = settings.value(UI_LOCALE_SETTING, ENGLISH_LOCALE.code, type=str)
    try:
        return ui_locale_for_code(code)
    except ValueError:
        return ENGLISH_LOCALE


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
