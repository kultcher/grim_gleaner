import pytest

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import (
    affix_common_stat_ids,
    rank_affix_catalog,
    rank_affixes_for_slot,
    score_affix_variant,
    score_semantic_stat_ids,
    semantic_stat_id,
)
from gd_affix_relevance.slots import SLOT_RING


def _variant(*property_ids: str, slot: str = "Ring") -> AffixVariantDefinition:
    return AffixVariantDefinition(
        gear_slot=slot,
        level_requirements=(5,),
        properties=tuple(
            AffixProperty(property_id, property_id, {})
            for property_id in property_ids
        ),
        stat_lines=tuple(property_id for property_id in property_ids),
        representative_source="base:records/items/example.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )


def _affix(
    affix_id: str,
    name: str,
    variant: AffixVariantDefinition,
) -> AffixDefinition:
    return AffixDefinition(
        affix_id=affix_id,
        localization_tag=f"tag{name}",
        display_name=name,
        kind="prefix",
        variants=(variant,),
    )


def test_catalog_scorer_uses_editable_profile_stat_ids_directly() -> None:
    variant = _variant(
        "flat_bleeding_damage",
        "bleeding_damage_percent",
        "health",
        "fire_resistance",
    )
    profile = BuildProfile(
        "Bleed",
        {
            "flat_bleeding_damage": 4,
            "bleeding_damage_percent": 4,
            "health": 2,
        },
    )

    score = score_affix_variant(variant, profile)

    assert score.weighted_match == 10
    assert score.relevance_points == 9
    assert score.effective_score == pytest.approx(8.325)
    assert score.matched_count == 3
    assert score.total_category_count == 4
    assert score.coverage_ratio == 0.75
    assert score.grade == "A"
    assert score.marker == "[A3]"


def test_conversion_property_maps_its_destination_to_profile_id() -> None:
    property_ = AffixProperty(
        "damage_conversion",
        "damage_conversion:1",
        {
            "source_damage_type": "physical",
            "destination_damage_type": "life",
        },
    )

    assert semantic_stat_id(property_) == "damage_conversion_to_vitality"


def test_nonlinear_score_softly_penalizes_low_item_coverage() -> None:
    stat_ids = (
        "defensive_ability",
        "elemental_resistance",
        "chaos_damage_percent",
        "damage_conversion_to_chaos",
        "flat_chaos_damage",
        "base_attack_speed",
        "skill_bonus:one",
        "skill_bonus:two",
    )
    profile = BuildProfile(
        weights={"defensive_ability": 2, "elemental_resistance": 3}
    )

    score = score_semantic_stat_ids(stat_ids, profile)

    assert score.weighted_match == 5
    assert score.relevance_points == 3.25
    assert score.coverage_ratio == 0.25
    assert score.effective_score == pytest.approx(2.51875)
    assert score.grade == "C"


def test_catalog_ranking_orders_variants_and_applies_limit() -> None:
    profile = BuildProfile("Health", {"health": 4, "movement_speed": 1})
    catalog = AffixCatalog(
        (
            _affix("prefix:slow", "Slow", _variant("movement_speed")),
            _affix("prefix:tough", "Tough", _variant("health")),
            _affix(
                "prefix:healthy",
                "Healthy",
                _variant("health", "movement_speed"),
            ),
        )
    )

    matches = rank_affix_catalog(catalog, profile, limit=2)

    assert [match.affix.display_name for match in matches] == ["Healthy", "Tough"]
    assert matches[0].score.weighted_match == 5
    assert matches[1].score.weighted_match == 4


def test_affix_common_stats_exclude_tier_or_slot_specific_additions() -> None:
    affix = AffixDefinition(
        affix_id="prefix:leveled",
        localization_tag="tagLeveled",
        display_name="Leveled",
        kind="prefix",
        variants=(
            _variant("health", "offensive_ability"),
            _variant("health", "attack_speed"),
        ),
    )

    assert affix_common_stat_ids(affix) == ("health",)


def test_catalog_scorer_matches_exact_selected_skill_bonus_reference() -> None:
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    property_ = AffixProperty(
        "skill_bonus",
        "skill_bonus:1",
        {"skill_reference": skill_id},
    )
    variant = AffixVariantDefinition(
        gear_slot="Head",
        level_requirements=(20,),
        properties=(property_,),
        stat_lines=("+[x] to Cadence",),
        representative_source="base:records/items/example.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    profile = BuildProfile(skill_weights={skill_id: 4})

    score = score_affix_variant(variant, profile)

    assert score.weighted_match == 4
    assert score.matched_count == 1
    assert score.matched_stat_ids == (f"skill_bonus:{skill_id}",)


def test_slot_ranking_uses_highest_level_layout_and_marks_variations() -> None:
    low = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
        representative_source="base:records/items/low.dbr",
        source_record_count=1,
        stat_layout_count=2,
        applicable_slots=(SLOT_RING,),
    )
    high = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(82,),
        properties=(
            AffixProperty("health", "health", {}),
            AffixProperty("offensive_ability", "offensive_ability", {}),
        ),
        stat_lines=("+[x] Health", "+[x] Offensive Ability"),
        representative_source="base:records/items/high.dbr",
        source_record_count=1,
        stat_layout_count=2,
        applicable_slots=(SLOT_RING,),
    )
    affix = AffixDefinition(
        affix_id="prefix:leveled-ring",
        localization_tag="tagLeveledRing",
        display_name="Leveled",
        kind="prefix",
        variants=(low, high),
    )
    profile = BuildProfile(weights={"health": 2, "offensive_ability": 3})

    matches = rank_affixes_for_slot(
        AffixCatalog((affix,)),
        profile,
        slot_id=SLOT_RING,
        kind="prefix",
    )

    assert len(matches) == 1
    assert matches[0].variant is high
    assert matches[0].has_level_variations
    assert matches[0].marker == "[C2]"
