from __future__ import annotations

from pathlib import Path

from gd_affix_relevance.catalog import (
    AffixDefinition,
    CatalogLocaleOverlay,
    ItemDefinition,
    SkillDefinition,
    load_catalog_locale_overlay,
)
from gd_affix_relevance.domain import ENGLISH_LOCALE, RUSSIAN_LOCALE


def _item(tag: str, name: str) -> ItemDefinition:
    return ItemDefinition(
        item_id=f"item:{tag}",
        family="equipment",
        localization_tag=tag,
        display_name=name,
        name_resolution="localized",
        description_tag="",
        description="",
        variants=(),
    )


def _affix(tag: str, name: str) -> AffixDefinition:
    return AffixDefinition(
        affix_id=f"prefix:{tag}",
        localization_tag=tag,
        display_name=name,
        kind="prefix",
        variants=(),
    )


def _skill(tag: str, name: str) -> SkillDefinition:
    return SkillDefinition(
        skill_id=f"records/skills/{tag}.dbr",
        source="base",
        category="player",
        name_tag=tag,
        display_name=name,
        name_resolution="localized",
        description_tag="",
        mastery_id="",
        mastery_name="",
        mastery_level_required=0,
        max_level=0,
        is_mastery=False,
    )


def test_overlay_prefers_russian_value_and_falls_back_to_english() -> None:
    overlay = CatalogLocaleOverlay(
        locale=RUSSIAN_LOCALE,
        strings={"tagItemExample": "Пример"},
    )

    assert overlay.resolve_item(_item("tagItemExample", "Example")) == "Пример"
    assert overlay.resolve_item(_item("tagMissing", "Fallback")) == "Fallback"
    assert overlay.resolve_affix(_affix("tagMissing", "Fallback Affix")) == (
        "Fallback Affix"
    )
    assert overlay.resolve_skill(_skill("tagMissing", "Fallback Skill")) == (
        "Fallback Skill"
    )


def test_overlay_resolve_falls_back_for_empty_tag() -> None:
    overlay = CatalogLocaleOverlay(locale=RUSSIAN_LOCALE, strings={"": "should not use"})

    assert overlay.resolve("", "Fallback") == "Fallback"


def test_load_catalog_locale_overlay_reads_extracted_item_tag_directory(
    tmp_path: Path,
) -> None:
    tags_root = tmp_path / "text_ru"
    tags_root.mkdir()
    (tags_root / "tags_items.txt").write_text(
        "tagItemExample={^G}Пример\ntagItemBlank=\n",
        encoding="utf-8-sig",
    )
    (tags_root / "tagsgdx1_items.txt").write_text(
        "tagItemAom=Пример АоМ\n",
        encoding="utf-8-sig",
    )

    overlay = load_catalog_locale_overlay(tags_root, locale=RUSSIAN_LOCALE)

    assert overlay.locale is RUSSIAN_LOCALE
    assert overlay.strings["tagItemExample"] == "Пример"
    assert overlay.strings["tagItemAom"] == "Пример АоМ"
    assert "tagItemBlank" not in overlay.strings


def test_load_catalog_locale_overlay_is_empty_for_english_locale(
    tmp_path: Path,
) -> None:
    tags_root = tmp_path / "text_en"
    tags_root.mkdir()
    (tags_root / "tags_items.txt").write_text(
        "tagItemExample=Example\n", encoding="utf-8-sig"
    )

    overlay = load_catalog_locale_overlay(tags_root, locale=ENGLISH_LOCALE)

    assert overlay.strings == {}


def test_load_catalog_locale_overlay_is_empty_when_directory_missing(
    tmp_path: Path,
) -> None:
    overlay = load_catalog_locale_overlay(
        tmp_path / "not-prepared-yet", locale=RUSSIAN_LOCALE
    )

    assert overlay.strings == {}
    assert overlay.locale is RUSSIAN_LOCALE


def test_load_catalog_locale_overlay_resolves_packed_gender_variant(
    tmp_path: Path,
) -> None:
    tags_root = tmp_path / "text_ru"
    tags_root.mkdir()
    (tags_root / "tags_items.txt").write_text(
        "tagQualityDullA01=[ms]тупой[fs]тупая[ns]тупое[np]тупые\n"
        "tagItemExampleBase=[fs]заточка\n",
        encoding="utf-8-sig",
    )

    overlay = load_catalog_locale_overlay(tags_root, locale=RUSSIAN_LOCALE)

    assert overlay.strings["tagQualityDullA01"] == "тупой"
    assert overlay.strings["tagItemExampleBase"] == "заточка"


def test_load_catalog_locale_overlay_keeps_first_duplicate_tag(
    tmp_path: Path,
) -> None:
    tags_root = tmp_path / "text_ru"
    tags_root.mkdir()
    (tags_root / "tags_items.txt").write_text(
        "tagDup=First\n", encoding="utf-8-sig"
    )
    (tags_root / "tagsgdx1_items.txt").write_text(
        "tagDup=Second\n", encoding="utf-8-sig"
    )

    overlay = load_catalog_locale_overlay(tags_root, locale=RUSSIAN_LOCALE)

    assert overlay.strings["tagDup"] == "First"
