from __future__ import annotations

import pytest

from gd_affix_relevance.domain import (
    ENGLISH_LOCALE,
    RUSSIAN_LOCALE,
    SUPPORTED_GAME_LOCALES,
    SUPPORTED_UI_LOCALES,
    game_locale_for_code,
    locale_for_code,
    ui_locale_for_code,
)


def test_supported_locales_define_all_locale_dependent_names() -> None:
    assert ENGLISH_LOCALE.code == "en"
    assert ENGLISH_LOCALE.game_text_directory == "text_en"
    assert ENGLISH_LOCALE.catalog_filename == "strings.en.json"

    assert RUSSIAN_LOCALE.code == "ru"
    assert RUSSIAN_LOCALE.game_text_directory == "text_ru"
    assert RUSSIAN_LOCALE.catalog_filename == "strings.ru.json"
    assert SUPPORTED_UI_LOCALES == (ENGLISH_LOCALE, RUSSIAN_LOCALE)
    assert SUPPORTED_GAME_LOCALES == (ENGLISH_LOCALE, RUSSIAN_LOCALE)


def test_locale_lookup_is_normalized_and_rejects_unknown_codes() -> None:
    assert locale_for_code(" RU ") is RUSSIAN_LOCALE
    assert ui_locale_for_code("ru") is RUSSIAN_LOCALE
    assert game_locale_for_code("ru") is RUSSIAN_LOCALE

    with pytest.raises(ValueError, match="Unsupported locale"):
        locale_for_code("de")
