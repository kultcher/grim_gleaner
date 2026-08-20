from __future__ import annotations

import json
from pathlib import Path

from gd_affix_relevance.domain import ENGLISH_LOCALE, RUSSIAN_LOCALE
from gd_affix_relevance.ui import i18n


def _write_resources(root: Path, *, en: dict, ru: dict) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "en.json").write_text(json.dumps(en), encoding="utf-8")
    (root / "ru.json").write_text(json.dumps(ru), encoding="utf-8")


def test_translator_prefers_active_locale_and_falls_back_to_english(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "i18n"
    _write_resources(
        resources,
        en={"nav.settings": "Settings", "nav.guide": "Guide"},
        ru={"nav.settings": "Настройки"},
    )

    translator = i18n.Translator(resources, RUSSIAN_LOCALE)

    assert translator.t("nav.settings") == "Настройки"
    assert translator.t("nav.guide") == "Guide"
    assert "nav.guide" not in translator.missing_keys


def test_translator_records_and_returns_key_for_missing_translations(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "i18n"
    _write_resources(resources, en={}, ru={})

    translator = i18n.Translator(resources, RUSSIAN_LOCALE)

    assert translator.t("nav.unknown") == "nav.unknown"
    assert "nav.unknown" in translator.missing_keys


def test_translator_formats_keyword_arguments(tmp_path: Path) -> None:
    resources = tmp_path / "i18n"
    _write_resources(
        resources,
        en={"export.confirm": "Export {count} entries?"},
        ru={"export.confirm": "Экспортировать {count} записей?"},
    )

    translator = i18n.Translator(resources, RUSSIAN_LOCALE)

    assert translator.t("export.confirm", count=3) == "Экспортировать 3 записей?"


def test_translator_english_locale_uses_english_resource_only(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "i18n"
    _write_resources(
        resources,
        en={"nav.settings": "Settings"},
        ru={"nav.settings": "Настройки"},
    )

    translator = i18n.Translator(resources, ENGLISH_LOCALE)

    assert translator.t("nav.settings") == "Settings"


def test_stat_label_falls_back_to_catalog_label_when_untranslated(
    tmp_path: Path,
) -> None:
    resources = tmp_path / "i18n"
    _write_resources(
        resources,
        en={},
        ru={"stat.flat_fire_damage": "Урон огнём (фикс.)"},
    )

    translator = i18n.Translator(resources, RUSSIAN_LOCALE)

    assert (
        translator.stat_label("flat_fire_damage", "Fire Damage (Flat)")
        == "Урон огнём (фикс.)"
    )
    assert (
        translator.stat_label("unmapped_stat", "Unmapped Stat")
        == "Unmapped Stat"
    )


def test_module_level_t_returns_key_before_configure(tmp_path: Path) -> None:
    i18n._translator = None  # ensure isolation from other tests

    assert i18n.t("nav.settings") == "nav.settings"
    assert i18n.stat_label("flat_fire_damage", "Fire Damage (Flat)") == (
        "Fire Damage (Flat)"
    )


def test_module_level_configure_sets_active_translator(tmp_path: Path) -> None:
    resources = tmp_path / "i18n"
    _write_resources(
        resources,
        en={"nav.settings": "Settings"},
        ru={"nav.settings": "Настройки"},
    )
    try:
        i18n.configure(resources, RUSSIAN_LOCALE)

        assert i18n.active_locale() is RUSSIAN_LOCALE
        assert i18n.t("nav.settings") == "Настройки"
    finally:
        i18n._translator = None


def test_load_translations_returns_empty_dict_when_file_missing(
    tmp_path: Path,
) -> None:
    assert i18n.load_translations(tmp_path / "missing", ENGLISH_LOCALE) == {}
