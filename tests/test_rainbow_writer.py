from pathlib import Path

import pytest

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.output import build_affix_markers, generate_rainbow_output


def _variant(*stat_ids: str) -> AffixVariantDefinition:
    return AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=tuple(AffixProperty(stat_id, stat_id, {}) for stat_id in stat_ids),
        stat_lines=stat_ids,
        representative_source="base:example.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )


def _affix(
    tag: str,
    name: str,
    *variants: AffixVariantDefinition,
) -> AffixDefinition:
    return AffixDefinition(
        affix_id=f"prefix:{tag}",
        localization_tag=tag,
        display_name=name,
        kind="prefix",
        variants=variants,
    )


def test_writer_clones_complete_folder_and_changes_exact_affix_tags_only(
    tmp_path: Path,
) -> None:
    source = tmp_path / "rainbow"
    source.mkdir()
    original = (
        b"\xef\xbb\xbf"
        b"# keep this comment\r\n"
        b"tagAffix={^G}Affix Name\r\n"
        b"tagSpecial=X{^O}Special Name\r\n"
        b"tagBaseItem={^B}Base Item\r\n"
    )
    (source / "tags_items.txt").write_bytes(original)
    (source / "readme.bin").write_bytes(b"untouched")
    catalog = AffixCatalog(
        (
            _affix(
                "tagAffix",
                "Affix Name",
                _variant("health", "attack_speed"),
                _variant("health", "movement_speed"),
            ),
            _affix("tagSpecial", "Special Name", _variant("health")),
            _affix("tagMissing", "Missing Name", _variant("health")),
        )
    )
    profile = BuildProfile("Health", {"health": 4, "attack_speed": 4})
    output = tmp_path / "generated" / "text_en"

    result = generate_rainbow_output(source, output, catalog, profile)

    generated = (output / "tags_items.txt").read_bytes()
    assert generated.startswith(b"\xef\xbb\xbf")
    text = generated.decode("utf-8-sig")
    assert "tagAffix=(C*1){^G}Affix Name\r\n" in text
    assert "tagSpecial=X(C1){^O}Special Name\r\n" in text
    assert "tagBaseItem={^B}Base Item\r\n" in text
    assert (output / "readme.bin").read_bytes() == b"untouched"
    assert (source / "tags_items.txt").read_bytes() == original
    assert result.files_written == 2
    assert result.affix_tags_scored == 3
    assert result.affix_tags_found == 2
    assert result.annotated_lines == 2
    assert result.missing_affix_tags == ("tagMissing",)


def test_writer_replaces_its_marker_and_is_idempotent(tmp_path: Path) -> None:
    first_source = tmp_path / "first"
    first_source.mkdir()
    (first_source / "tags_items.txt").write_text(
        "tagAffix=(S++1){^G}Affix Name\n",
        encoding="utf-8",
    )
    catalog = AffixCatalog(
        (_affix("tagAffix", "Affix Name", _variant("health")),)
    )
    profile = BuildProfile("Health", {"health": 4})
    first_output = tmp_path / "first-output"
    second_output = tmp_path / "second-output"

    first = generate_rainbow_output(first_source, first_output, catalog, profile)
    second = generate_rainbow_output(first_output, second_output, catalog, profile)

    assert first.annotated_lines == 1
    assert second.annotated_lines == 0
    assert (first_output / "tags_items.txt").read_bytes() == (
        second_output / "tags_items.txt"
    ).read_bytes()
    assert "(C1)(S++1)" not in (second_output / "tags_items.txt").read_text(
        encoding="utf-8"
    )


def test_writer_rejects_overlapping_source_and_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "tags_items.txt").write_text("tag=value\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must not overlap"):
        generate_rainbow_output(
            source,
            source / "generated",
            AffixCatalog(()),
            BuildProfile(),
        )


def test_marker_scoring_respects_conversion_source_filters() -> None:
    conversion = AffixProperty(
        "damage_conversion",
        "damage_conversion:1",
        {
            "source_damage_type": "Physical",
            "destination_damage_type": "Fire",
        },
    )
    variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(conversion,),
        stat_lines=("[x]% Physical Damage converted to Fire Damage",),
        representative_source="base:example.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    catalog = AffixCatalog((_affix("tagConversion", "Converted", variant),))
    profile = BuildProfile(weights={"damage_conversion_to_fire": 4})

    assert build_affix_markers(catalog, profile)["tagConversion"] == "(C1)"
    profile.set_conversion_source_enabled("fire", "physical", False)
    assert build_affix_markers(catalog, profile)["tagConversion"] == "(-0)"
