from pathlib import Path

import pytest

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixTierDefinition,
    AffixVariantDefinition,
    ItemCatalog,
    ItemDefinition,
    ItemProperty,
    ItemSkillModifier,
    ItemVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile, RUSSIAN_LOCALE
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
    assert "tagPlain=(C1)Plain Name\r\n" in text
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


def test_writer_leaves_clean_vanilla_names_free_of_color_codes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clean"
    source.mkdir()
    (source / "tags_items.txt").write_text(
        "tagPrefix=Charged\n"
        "tagSuffix=of Ferocity\n"
        "tagUnique=Stormrend\n",
        encoding="utf-8",
    )
    catalog = AffixCatalog(
        (
            _affix("tagPrefix", "Charged", _variant("health")),
            _affix(
                "tagSuffix",
                "of Ferocity",
                _variant("health"),
                kind="suffix",
            ),
        )
    )
    items = ItemCatalog(
        (
            _unique_item(
                "tagUnique",
                "Stormrend",
                (ItemProperty("health", "health", {}),),
            ),
        ),
        (),
        (),
        (),
        (),
        (),
    )
    output = tmp_path / "output"

    generate_rainbow_output(
        source,
        output,
        catalog,
        BuildProfile("Health", {"health": 4}),
        items=items,
    )

    text = (output / "tags_items.txt").read_text(encoding="utf-8")
    assert "tagPrefix=(C1)Charged" in text
    assert "tagSuffix=of Ferocity(C1)" in text
    assert "tagUnique=(C1)Stormrend" in text
    assert "{^" not in text


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


def test_russian_writer_places_markers_inside_gender_variants(
    tmp_path: Path,
) -> None:
    source = tmp_path / "text_ru"
    source.mkdir()
    (source / "tags_items.txt").write_text(
        "tagPrefix=[ms]{^G}разлагающий[fs]{^G}разлагающая"
        "[ns]{^G}разлагающее[np]{^G}разлагающие\n"
        "tagSuffix={^G}звериной ярости\n"
        "tagUnique=[ms]{^L}наградной клинок Салазара\n",
        encoding="utf-8-sig",
    )
    catalog = AffixCatalog(
        (
            _affix("tagPrefix", "Разлагающий", _variant()),
            _affix("tagSuffix", "Звериной ярости", _variant(), kind="suffix"),
        )
    )
    items = ItemCatalog(
        (_unique_item("tagUnique", "Наградной клинок", ()),),
        (),
        (),
        (),
        (),
        (),
    )
    output = tmp_path / "generated"

    first = generate_rainbow_output(
        source,
        output,
        catalog,
        BuildProfile(),
        items=items,
        locale=RUSSIAN_LOCALE,
    )
    second_output = tmp_path / "second"
    second = generate_rainbow_output(
        output,
        second_output,
        catalog,
        BuildProfile(),
        items=items,
        locale=RUSSIAN_LOCALE,
    )

    text = (output / "tags_items.txt").read_text(encoding="utf-8-sig")
    assert "tagPrefix=[ms]{^C}(F0){^G}разлагающий" in text
    assert "[fs]{^C}(F0){^G}разлагающая" in text
    assert "[ns]{^C}(F0){^G}разлагающее" in text
    assert "[np]{^C}(F0){^G}разлагающие" in text
    assert "tagSuffix={^G}звериной ярости{^C}(F0)" in text
    assert "tagUnique=[ms]{^C}(F0){^L}наградной клинок Салазара" in text
    assert first.annotated_lines == 3
    assert second.annotated_lines == 0
    assert (output / "tags_items.txt").read_bytes() == (
        second_output / "tags_items.txt"
    ).read_bytes()


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


def test_writer_prefers_primary_files_and_fills_missing_files_from_fallback(
    tmp_path: Path,
) -> None:
    installed = tmp_path / "game" / "settings" / "text_en"
    bundled = tmp_path / "app" / "tags"
    installed.mkdir(parents=True)
    bundled.mkdir(parents=True)
    (installed / "tags_items.txt").write_text(
        "tagAffix={^G}Rainbow Name\n",
        encoding="utf-8",
    )
    (installed / "rainbow-extra.txt").write_text(
        "tagExtra=Keep Me\n",
        encoding="utf-8",
    )
    (bundled / "tags_items.txt").write_text(
        "tagAffix=Bundled Name\n",
        encoding="utf-8",
    )
    (bundled / "tagsgdx3_items.txt").write_text(
        "tagExpansion=Expansion Name\n",
        encoding="utf-8",
    )
    catalog = AffixCatalog(
        (_affix("tagAffix", "Affix Name", _variant("health")),)
    )
    output = tmp_path / "output"

    result = generate_rainbow_output(
        installed,
        output,
        catalog,
        BuildProfile("Health", {"health": 4}),
        fallback_source_root=bundled,
    )

    assert "{^G}Rainbow Name" in (output / "tags_items.txt").read_text(
        encoding="utf-8"
    )
    assert "Bundled Name" not in (output / "tags_items.txt").read_text(
        encoding="utf-8"
    )
    assert (output / "tagsgdx3_items.txt").is_file()
    assert (output / "rainbow-extra.txt").is_file()
    assert result.files_written == 3
    assert result.source_root == installed.resolve()
    assert result.fallback_source_root == bundled.resolve()


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
    assert build_affix_markers(catalog, profile)["tagConversion"] == "(F0)"


def test_markers_omit_high_s_counts_and_flag_granted_affix_skills() -> None:
    stat_ids = (
        "health",
        "defensive_ability",
        "offensive_ability",
        "attack_speed",
        "casting_speed",
        "movement_speed",
    )
    profile = BuildProfile(
        weights={stat_id: 4 for stat_id in stat_ids}
    )
    high_variant = _variant(*stat_ids)
    granted_variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(
            AffixProperty("health", "health", {}),
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


def test_export_markers_follow_profile_level_eligibility_and_tier_stats() -> None:
    low = AffixTierDefinition(
        tier_id="base:low.dbr",
        source="base",
        record_path="low.dbr",
        gear_slot="Ring",
        applicable_slots=(),
        level_requirement=20,
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
    )
    high = AffixTierDefinition(
        tier_id="base:high.dbr",
        source="base",
        record_path="high.dbr",
        gear_slot="Ring",
        applicable_slots=(),
        level_requirement=70,
        properties=(
            AffixProperty("health", "health", {}),
            AffixProperty("offensive_ability", "offensive_ability", {}),
        ),
        stat_lines=("+[x] Health", "+[x] Offensive Ability"),
    )
    late = AffixTierDefinition(
        tier_id="base:late.dbr",
        source="base",
        record_path="late.dbr",
        gear_slot="Ring",
        applicable_slots=(),
        level_requirement=65,
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
    )
    banded = AffixDefinition(
        affix_id="prefix:banded",
        localization_tag="tagBanded",
        display_name="Banded",
        kind="prefix",
        variants=(_variant("health"),),
        tiers=(low, high),
    )
    unavailable = AffixDefinition(
        affix_id="prefix:unavailable",
        localization_tag="tagUnavailable",
        display_name="Unavailable",
        kind="prefix",
        variants=(_variant("health"),),
        tiers=(late,),
    )
    catalog = AffixCatalog((banded, unavailable))
    profile = BuildProfile(
        weights={"health": 4, "offensive_ability": 4},
        level_band="50-64",
    )

    low_markers = build_affix_markers(catalog, profile)
    assert low_markers["tagBanded"] == "(C1)"
    assert low_markers["tagUnavailable"] == "(C1)"

    profile.set_level_band("65-79")
    high_markers = build_affix_markers(catalog, profile)
    assert high_markers["tagBanded"] == "(B2)"
    assert high_markers["tagUnavailable"] == "(C1)"


def test_unique_export_uses_nearest_future_variant_above_profile_band() -> None:
    item = _unique_item(
        "tagLateUnique",
        "Late Unique",
        (ItemProperty("health", "health", {}),),
    )

    assert build_unique_item_markers(
        ItemCatalog((item,), (), (), (), (), ()),
        BuildProfile(weights={"health": 4}, level_band="1-49"),
    ) == {"tagLateUnique": "(C1)"}


def test_writer_grades_unique_items_and_flags_only_relevant_modifiers(
    tmp_path: Path,
) -> None:
    selected_skill = "records/skills/playerclass01/cadence1.dbr"
    stat_ids = (
        "health",
        "defensive_ability",
        "offensive_ability",
        "attack_speed",
        "casting_speed",
        "movement_speed",
        "elemental_resistance",
        "total_damage_percent",
    )
    properties = tuple(
        ItemProperty(stat_id, stat_id, {}) for stat_id in stat_ids
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
        weights={stat_id: 4 for stat_id in stat_ids},
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
