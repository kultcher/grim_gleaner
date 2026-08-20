"""End-to-end proof that switching ui_locale actually re-renders the UI.

Individual widget tests exercise English text extensively (the default
active locale in ``tests/conftest.py``). These tests configure the Russian
translator once and spot-check representative screens, so a future change
that quietly stops calling ``ui.i18n.t()`` somewhere central would be caught
here even if no other test happens to assert on that string.
"""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import AffixCatalog
from gd_affix_relevance.domain import BuildProfile, ENGLISH_LOCALE, RUSSIAN_LOCALE
from gd_affix_relevance.stats import stat_definition
from gd_affix_relevance.ui import i18n
from gd_affix_relevance.ui.main_window import MainWindow
from gd_affix_relevance.ui.settings import SettingsPage
from gd_affix_relevance.ui.top_matches import TopMatchesPage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_RESOURCES_ROOT = PROJECT_ROOT / "resources" / "i18n"


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _use_russian_locale() -> None:
    i18n.configure(I18N_RESOURCES_ROOT, RUSSIAN_LOCALE)


def test_main_window_navigation_renders_in_russian() -> None:
    _application()
    _use_russian_locale()

    window = MainWindow(BuildProfile(), catalog=AffixCatalog(()))

    nav_labels = {
        window.navigation.item(row).text().strip()
        for row in range(window.navigation.count())
    }
    assert "Профиль билда" in nav_labels
    assert "Оценки снаряжения" in nav_labels
    assert "Экспорт оценок" in nav_labels
    assert "Настройки" in nav_labels
    assert "Руководство" in nav_labels


def test_settings_page_renders_in_russian(tmp_path: Path) -> None:
    _application()
    _use_russian_locale()
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)

    page = SettingsPage(settings)

    assert page.prepare_localization_button.text() == "Обновить файлы языка игры"


def test_prepare_localization_success_requires_catalog_restart() -> None:
    messages = (
        (ENGLISH_LOCALE, "Restart Grim Gleaner"),
        (RUSSIAN_LOCALE, "Перезапустите Grim Gleaner"),
    )

    for locale, expected in messages:
        translator = i18n.Translator(I18N_RESOURCES_ROOT, locale)
        message = translator.t(
            "settings.prepare_localization_success",
            count=4,
            output_root="text_ru",
        )
        assert expected in message


def test_gear_grades_columns_render_in_russian() -> None:
    _application()
    _use_russian_locale()

    page = TopMatchesPage(AffixCatalog(()), BuildProfile())

    any_affix_table = next(iter(page.tables.values()))
    headers = [
        any_affix_table.horizontalHeaderItem(column).text()
        for column in range(any_affix_table.columnCount())
    ]
    assert headers == ["Оценка", "Аффикс", "Балл", "Покрытие"]


def test_stat_label_resolves_russian_translation_for_registry_stat() -> None:
    _application()
    _use_russian_locale()
    definition = stat_definition("flat_fire_damage")
    assert definition is not None

    assert i18n.stat_label(definition.stat_id, definition.label) == (
        "Урон от огня (пост.)"
    )


def test_damage_labels_match_official_grim_dawn_russian_terms() -> None:
    _application()
    _use_russian_locale()

    expected = {
        "flat_acid_damage": "Урон от кислоты (пост.)",
        "flat_aether_damage": "Урон от эфира (пост.)",
        "flat_chaos_damage": "Урон от хаоса (пост.)",
        "flat_cold_damage": "Урон от холода (пост.)",
        "flat_fire_damage": "Урон от огня (пост.)",
        "flat_lightning_damage": "Урон от молнии (пост.)",
        "flat_physical_damage": "Физический урон (пост.)",
        "flat_pierce_damage": "Проникающий урон (пост.)",
        "flat_vitality_damage": "Урон здоровью (пост.)",
        "flat_burn_damage": "Урон от горения (пост., DoT)",
        "flat_electrocute_damage": "Урон от электрошока (пост., DoT)",
        "flat_frostburn_damage": "Урон от обморожения (пост., DoT)",
        "flat_internal_trauma_damage": (
            "Урон от внутренних травм (пост., DoT)"
        ),
        "flat_poison_damage": "Урон от яда (пост., DoT)",
        "flat_vitality_decay_damage": "Урон от разложения (пост., DoT)",
    }

    for stat_id, label in expected.items():
        definition = stat_definition(stat_id)
        assert definition is not None
        assert i18n.stat_label(stat_id, definition.label) == label


def test_resistance_labels_match_official_grim_dawn_russian_terms() -> None:
    _application()
    _use_russian_locale()

    expected = {
        "aether_resistance": "Сопротивление эфиру",
        "cold_resistance": "Сопротивление холоду",
        "elemental_resistance": "Сопротивление стихийному урону",
        "fire_resistance": "Сопротивление огню",
        "physical_resistance": "Сопротивление физическому урону",
        "pierce_resistance": "Сопротивление проникающему урону",
        "poison_acid_resistance": "Сопротивление яду и кислоте",
        "vitality_resistance": "Сопротивление урону здоровью",
        "maximum_aether_resistance": "Максимум сопротивления эфиру",
        "maximum_pierce_resistance": (
            "Максимум сопротивления проникающему урону"
        ),
        "maximum_poison_acid_resistance": (
            "Максимум сопротивления яду и кислоте"
        ),
        "maximum_vitality_resistance": (
            "Максимум сопротивления урону здоровью"
        ),
        "pet_aether_resistance": "Сопротивление питомца эфиру",
        "pet_elemental_resistance": (
            "Сопротивление питомца стихийному урону"
        ),
        "pet_physical_resistance": (
            "Сопротивление питомца физическому урону"
        ),
        "pet_pierce_resistance": (
            "Сопротивление питомца проникающему урону"
        ),
        "pet_poison_acid_resistance": (
            "Сопротивление питомца яду и кислоте"
        ),
        "pet_vitality_resistance": (
            "Сопротивление питомца урону здоровью"
        ),
    }

    for stat_id, label in expected.items():
        definition = stat_definition(stat_id)
        assert definition is not None
        assert i18n.stat_label(stat_id, definition.label) == label
