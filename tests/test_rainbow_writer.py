from pathlib import Path

import pytest

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
    ItemCatalog,
    ItemDefinition,
    ItemProperty,
    ItemSkillModifier,
    ItemVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.output import (
    build_affix_markers,
    build_unique_item_markers,
    generate_rainbow_output,
)


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
    kind: str = "prefix",
) -> AffixDefinition:
    return AffixDefinition(
        affix_id=f"{kind}:{tag}",
        localization_tag=tag,
        display_name=name,
        kind=kind,
        variants=variants,
    )


def _unique_item(
    tag: str,
    name: str,
    properties: tuple[ItemProperty, ...],
    *,
    granted_skill_reference: str = "",
    skill_modifiers: tuple[ItemSkillModifier, ...] = (),
) -> ItemDefinition:
    variant = ItemVariantDefinition(
        source="base",
        record_path=f"records/items/gearweapons/{tag}.dbr",
        category="legendary",
        rarity="Legendary",
        item_class="WeaponHunting_Ranged2h",
        gear_slot="Two-handed weapon",
        item_level=94,
        level_requirement=84,
        applicable_slots=(),
        set_reference="",
        set_name="",
        granted_skill_reference=granted_skill_reference,
        granted_skill_name="Granted Skill" if granted_skill_reference else "",
        effect_skill_reference="",
        effect_skill_name="",
        effect_properties=(),
        effect_stat_lines=(),
        completion_bonus_reference="",
        properties=properties,
        stat_lines=tuple(property_.property_id for property_ in properties),
        skill_modifiers=skill_modifiers,
        acquisition_source="Random Drop",
    )
    return ItemDefinition(
        item_id=f"equipment:{tag}",
        family="equipment",
        localization_tag=tag,
        display_name=name,
        name_resolution="localized",
        description_tag="",
        description="",
        variants=(variant,),
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
        b"tagPlain=Plain Name\r\n"
        b"tagSuffix={^G}of Ending\r\n"
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
            _affix("tagPlain", "Plain Name", _variant("health")),
            _affix(
                "tagSuffix",
                "of Ending",
                _variant("health"),
                kind="suffix",
            ),
            _affix("tagMissing", "Missing Name", _variant("health")),
        )
    )
    profile = BuildProfile("Health", {"health": 4, "attack_speed": 4})
    output = tmp_path / "generated" / "text_en"

    result = generate_rainbow_output(source, output, catalog, profile)

    generated = (output / "tags_items.txt").read_bytes()
    assert generated.startswith(b"\xef\xbb\xbf")
    text = generated.decode("utf-8-sig")
    assert "tagAffix={^C}(C1){^G}Affix Name\r\n" in text
    assert "tagSpecial={^C}(C1)X{^O}Special Name\r\n" in text
    assert "tagPlain={^C}(C1){^E}Plain Name\r\n" in text
    assert "tagSuffix={^G}of Ending{^C}(C1)\r\n" in text
    assert "tagBaseItem={^B}Base Item\r\n" in text
    assert (output / "readme.bin").read_bytes() == b"untouched"
    assert (source / "tags_items.txt").read_bytes() == original
    assert result.files_written == 2
    assert result.affix_tags_scored == 5
    assert result.affix_tags_found == 4
    assert result.unique_tags_scored == 0
    assert result.unique_tags_found == 0
    assert result.annotated_lines == 4
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
    text = (second_output / "tags_items.txt").read_text(encoding="utf-8")
    assert "(C1)(S++1)" not in text
    assert "tagAffix={^C}(C1){^G}Affix Name" in text


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


def test_markers_omit_high_s_counts_and_flag_granted_affix_skills() -> None:
    profile = BuildProfile(
        weights={f"stat_{index}": 4 for index in range(8)}
    )
    high_variant = _variant(*(f"stat_{index}" for index in range(6)))
    granted_variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(
            AffixProperty("stat_0", "stat_0", {}),
            AffixProperty(
                "granted_item_skill",
                "granted_item_skill",
                {"skill_reference": "records/skills/itemskills/example.dbr"},
            ),
        ),
        stat_lines=(),
        representative_source="base:granted.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    markers = build_affix_markers(
        AffixCatalog(
            (
                _affix("tagHigh", "High", high_variant),
                _affix("tagGranted", "Granted", granted_variant),
            )
        ),
        profile,
    )

    assert markers["tagHigh"] == "(S+)"
    assert markers["tagGranted"] == "(C1*)"


def test_writer_grades_unique_items_and_flags_only_relevant_modifiers(
    tmp_path: Path,
) -> None:
    selected_skill = "records/skills/playerclass01/cadence1.dbr"
    properties = tuple(
        ItemProperty(f"stat_{index}", f"stat_{index}", {})
        for index in range(8)
    )
    relevant_modifier = ItemSkillModifier(
        selected_skill, "Cadence", "modifier.dbr", (), ()
    )
    unused_modifier = ItemSkillModifier(
        "records/skills/playerclass02/firestrike1.dbr",
        "Fire Strike",
        "unused_modifier.dbr",
        (),
        (),
    )
    relevant = _unique_item(
        "tagRelevantUnique",
        "Relevant Unique",
        properties,
        granted_skill_reference="records/skills/itemskills/granted.dbr",
        skill_modifiers=(relevant_modifier,),
    )
    unused = _unique_item(
        "tagUnusedUnique",
        "Unused Unique",
        properties,
        skill_modifiers=(unused_modifier,),
    )
    items = ItemCatalog((relevant, unused), (), (), (), (), ())
    profile = BuildProfile(
        weights={f"stat_{index}": 4 for index in range(8)},
        skill_weights={selected_skill: 0},
    )

    markers = build_unique_item_markers(items, profile)
    assert markers["tagRelevantUnique"] == "(S++*!)"
    assert markers["tagUnusedUnique"] == "(S++)"

    source = tmp_path / "source"
    source.mkdir()
    (source / "tags_items.txt").write_text(
        "tagRelevantUnique=(S) {^I}Relevant Unique\n"
        "tagUnusedUnique={^P}Unused Unique\n",
        encoding="utf-8",
    )
    output = tmp_path / "output"
    result = generate_rainbow_output(
        source,
        output,
        AffixCatalog(()),
        profile,
        items=items,
    )
    text = (output / "tags_items.txt").read_text(encoding="utf-8")

    assert (
        "tagRelevantUnique={^C}(S++*!){^E}($) {^I}Relevant Unique"
        in text
    )
    assert "tagUnusedUnique={^C}(S++){^P}Unused Unique" in text
    assert result.unique_tags_found == result.unique_tags_scored == 2

    second_output = tmp_path / "second-output"
    second = generate_rainbow_output(
        output,
        second_output,
        AffixCatalog(()),
        profile,
        items=items,
    )
    assert second.annotated_lines == 0
    assert (output / "tags_items.txt").read_bytes() == (
        second_output / "tags_items.txt"
    ).read_bytes()
