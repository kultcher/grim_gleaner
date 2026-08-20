from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

from gd_affix_relevance.domain import ENGLISH_LOCALE, RUSSIAN_LOCALE
from gd_affix_relevance.ui.app import _entrypoint_runtime_paths, _resolve_ui_locale
from gd_affix_relevance.ui.settings import UI_LOCALE_SETTING


def test_compiled_entrypoint_explicitly_selects_packaged_resources(
    tmp_path,
) -> None:
    root = tmp_path / "Grim Gleaner"

    paths = _entrypoint_runtime_paths(
        SimpleNamespace(containing_dir=str(root.parent)),
        executable=root / "grim_gleaner.exe",
    )

    assert paths.mode == "release"
    assert paths.application_root == root.resolve()
    assert paths.catalog_root == root.resolve() / "catalog"
    assert paths.tags_root == root.resolve() / "tags"


def test_resolve_ui_locale_defaults_to_english_when_unset(tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    assert _resolve_ui_locale(settings) is ENGLISH_LOCALE


def test_resolve_ui_locale_reads_saved_russian_choice(tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(UI_LOCALE_SETTING, "ru")
    settings.sync()

    assert _resolve_ui_locale(settings) is RUSSIAN_LOCALE


def test_resolve_ui_locale_falls_back_to_english_for_corrupted_value(
    tmp_path,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue(UI_LOCALE_SETTING, "not-a-locale")
    settings.sync()

    assert _resolve_ui_locale(settings) is ENGLISH_LOCALE
