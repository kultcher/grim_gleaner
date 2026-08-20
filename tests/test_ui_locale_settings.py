import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.domain import ENGLISH_LOCALE, RUSSIAN_LOCALE
from gd_affix_relevance.ui.settings import (
    GAME_LOCALE_SETTING,
    UI_LOCALE_SETTING,
    SettingsPage,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_ui_locale_and_game_locale_are_stored_under_separate_keys(
    tmp_path: Path,
) -> None:
    _application()
    settings = _settings(tmp_path)
    page = SettingsPage(settings)

    page.ui_locale_combo.setCurrentIndex(
        page.ui_locale_combo.findData(RUSSIAN_LOCALE.code)
    )

    assert settings.value(UI_LOCALE_SETTING) == "ru"
    assert settings.value(GAME_LOCALE_SETTING) == "ru"
    # Changing the game-language combo afterward must not move ui_locale:
    # the two settings are independently editable, only linked by the
    # convenience default applied when ui_locale changes.
    page.game_locale_combo.setCurrentIndex(
        page.game_locale_combo.findData(ENGLISH_LOCALE.code)
    )
    assert settings.value(GAME_LOCALE_SETTING) == "en"
    assert settings.value(UI_LOCALE_SETTING) == "ru"


def test_selecting_russian_ui_locale_cascades_game_locale_by_default(
    tmp_path: Path,
) -> None:
    _application()
    settings = _settings(tmp_path)
    page = SettingsPage(settings)
    assert page.selected_game_locale() is ENGLISH_LOCALE

    page.ui_locale_combo.setCurrentIndex(
        page.ui_locale_combo.findData(RUSSIAN_LOCALE.code)
    )

    assert page.selected_ui_locale() is RUSSIAN_LOCALE
    assert page.selected_game_locale() is RUSSIAN_LOCALE
    assert "restart" in page.ui_locale_status.text().casefold()


def test_settings_without_locale_fields_default_to_english(tmp_path: Path) -> None:
    _application()
    settings = _settings(tmp_path)
    # Simulate a profile saved by a version that predates ui_locale/game_locale.
    assert settings.value(UI_LOCALE_SETTING) is None
    assert settings.value(GAME_LOCALE_SETTING) is None

    page = SettingsPage(settings)

    assert page.selected_ui_locale() is ENGLISH_LOCALE
    assert page.selected_game_locale() is ENGLISH_LOCALE


def test_corrupted_locale_values_safely_fall_back_to_english(
    tmp_path: Path,
) -> None:
    _application()
    settings = _settings(tmp_path)
    settings.setValue(UI_LOCALE_SETTING, "not-a-real-locale")
    settings.setValue(GAME_LOCALE_SETTING, "xx")
    settings.sync()

    page = SettingsPage(settings)

    assert page._saved_ui_locale() is ENGLISH_LOCALE
    assert page._saved_game_locale() is ENGLISH_LOCALE
    assert page.ui_locale_combo.currentData() == ENGLISH_LOCALE.code
    assert page.game_locale_combo.currentData() == ENGLISH_LOCALE.code
