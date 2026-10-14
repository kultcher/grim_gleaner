import pytest
from dataclasses import replace

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixTierDefinition,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import (
    affix_common_stat_ids,
    minimum_score_for_grade,
    profile_score_adjustment,
    rank_affix_catalog,
    rank_affixes_for_slot,
    score_affix_variant,
    score_semantic_stat_ids,
    semantic_stat_id,
    semantic_stat_ids,
)
from gd_affix_relevance.slots import SLOT_RING


def test_negative_pet_resistance_affix_is_not_a_beneficial_match() -> None:
    profile = BuildProfile(weights={"pet_maximum_all_resistance": 4})
    variant = replace(_variant(), properties=(AffixProperty(
        "pet_maximum_all_resistance", "pet_maximum_all_resistance",
        {"percent": "-15"},
    ),))
    score = score_affix_variant(variant, profile)
    assert score.grade == "F"
    assert score.matched_count == 0
    # Counted as a carried (unweighted) stat, so it lowers coverage.
    assert score.total_category_count == 1


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
    assert score.base_effective_score == pytest.approx(8.325)
    assert score.profile_adjustment == pytest.approx(0.925)
    assert score.effective_score == pytest.approx(7.700625)
    assert score.matched_count == 3
    assert score.total_category_count == 4
    assert score.coverage_ratio == 0.75
    assert score.grade == "B"
    assert score.marker == "[B3]"


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


def test_conversion_source_filter_omits_irrelevant_incoming_type() -> None:
    physical_to_fire = AffixProperty(
        "damage_conversion",
        "damage_conversion:1",
        {
            "source_damage_type": "Physical",
            "destination_damage_type": "Fire",
        },
    )
    variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(20,),
        properties=(physical_to_fire,),
        stat_lines=("[x]% Physical Damage converted to Fire Damage",),
        representative_source="base:test.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    profile = BuildProfile(weights={"damage_conversion_to_fire": 4})

    assert score_affix_variant(variant, profile).matched_count == 1
    profile.set_conversion_source_enabled("fire", "physical", False)
    filtered = score_affix_variant(variant, profile)

    assert filtered.matched_count == 0
    assert filtered.total_category_count == 0


def test_item_base_weapon_damage_maps_separately_from_flat_damage() -> None:
    property_ = AffixProperty(
        "flat_lightning_damage",
        "flat_lightning_damage:base_weapon",
        {"damage_min": "100", "damage_max": "120"},
    )

    assert semantic_stat_id(property_) == "base_weapon_damage_as_lightning"


def test_racial_and_pet_conversion_properties_expand_to_registered_ids() -> None:
    racial = AffixProperty(
        "racial_damage_bonus",
        "racial_damage_bonus",
        {"race_reference": "Race003;Race005"},
    )
    pet_conversion = AffixProperty(
        "pet_damage_conversion",
        "pet_damage_conversion:1",
        {"source_damage_type": "life", "destination_damage_type": "cold"},
    )

    assert semantic_stat_ids(racial) == (
        "racial_damage_bonus_vs_aetherial",
        "racial_damage_bonus_vs_aether_corruption",
    )
    assert semantic_stat_ids(pet_conversion) == (
        "pet_damage_conversion_to_cold",
    )


def test_non_scoreable_and_unknown_stats_do_not_reduce_coverage() -> None:
    variant = _variant("health", "base_shield_block_amount", "future_stat")
    profile = BuildProfile(weights={"health": 2})

    score = score_affix_variant(variant, profile)

    assert score.matched_count == 1
    assert score.total_category_count == 1
    assert score.coverage_ratio == 1.0


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
    assert score.coverage_ratio == pytest.approx(2 / 7)
    assert score.base_effective_score == pytest.approx(
        3.25 * (0.70 + 0.30 * (2 / 7))
    )
    assert score.profile_adjustment == pytest.approx(1.0185430778)
    assert score.effective_score == pytest.approx(
        score.base_effective_score * score.profile_adjustment
    )
    assert score.grade == "D"


def test_profile_adjustment_is_bounded_and_ignores_zero_weights() -> None:
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
    mostly_useful = BuildProfile(
        weights={stat_id: 2 for stat_id in stat_ids},
        skill_weights={"ignored_skill": 0},
    )
    all_core = BuildProfile(weights={stat_id: 4 for stat_id in stat_ids})

    assert profile_score_adjustment(mostly_useful) == pytest.approx(1.25)
    assert profile_score_adjustment(all_core) == pytest.approx(0.80)
    assert profile_score_adjustment(BuildProfile()) == 1.0


def test_stretched_grade_thresholds_include_extended_s_ranks() -> None:
    assert minimum_score_for_grade("S++") == 24
    assert minimum_score_for_grade("S+") == 18
    assert minimum_score_for_grade("S") == 14
    assert minimum_score_for_grade("A") == 10
    assert minimum_score_for_grade("B") == 6
    assert minimum_score_for_grade("C") == 3
    assert minimum_score_for_grade("D") == 1


def test_zero_relevance_uses_f_grade() -> None:
    score = score_semantic_stat_ids(("health",), BuildProfile())

    assert score.grade == "F"
    assert score.marker == "[F0]"


def test_high_s_markers_omit_matched_count() -> None:
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

    score = score_semantic_stat_ids(stat_ids, profile)

    assert score.grade == "S+"
    assert score.marker == "[S+]"


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


def test_affix_ranking_regrades_from_highest_tier_inside_profile_band() -> None:
    low = AffixTierDefinition(
        tier_id="base:records/items/prefix/low.dbr",
        source="base",
        record_path="records/items/prefix/low.dbr",
        gear_slot="Ring",
        applicable_slots=(SLOT_RING,),
        level_requirement=20,
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
    )
    high = AffixTierDefinition(
        tier_id="base:records/items/prefix/high.dbr",
        source="base",
        record_path="records/items/prefix/high.dbr",
        gear_slot="Ring",
        applicable_slots=(SLOT_RING,),
        level_requirement=70,
        properties=(
            AffixProperty("health", "health", {}),
            AffixProperty("offensive_ability", "offensive_ability", {}),
        ),
        stat_lines=("+[x] Health", "+[x] Offensive Ability"),
    )
    affix = AffixDefinition(
        affix_id="prefix:banded",
        localization_tag="tagBanded",
        display_name="Banded",
        kind="prefix",
        variants=(_variant("health"),),
        tiers=(low, high),
    )
    catalog = AffixCatalog((affix,))
    profile = BuildProfile(
        weights={"health": 4, "offensive_ability": 4},
        level_band="50-64",
    )

    low_match = rank_affixes_for_slot(
        catalog, profile, slot_id=SLOT_RING, kind="prefix"
    )[0]
    assert low_match.variant.level_requirements == (20,)
    assert low_match.score.matched_stat_ids == ("health",)

    profile.set_level_band("65-79")
    high_match = rank_affixes_for_slot(
        catalog, profile, slot_id=SLOT_RING, kind="prefix"
    )[0]
    assert high_match.variant.level_requirements == (70,)
    assert high_match.score.matched_stat_ids == (
        "health",
        "offensive_ability",
    )
    assert high_match.score.effective_score > low_match.score.effective_score


def test_affix_above_profile_band_is_excluded() -> None:
    tier = AffixTierDefinition(
        tier_id="base:records/items/prefix/late.dbr",
        source="base",
        record_path="records/items/prefix/late.dbr",
        gear_slot="Ring",
        applicable_slots=(SLOT_RING,),
        level_requirement=65,
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
    )
    affix = AffixDefinition(
        affix_id="prefix:late",
        localization_tag="tagLate",
        display_name="Late",
        kind="prefix",
        variants=(_variant("health"),),
        tiers=(tier,),
    )

    assert not rank_affixes_for_slot(
        AffixCatalog((affix,)),
        BuildProfile(weights={"health": 4}, level_band="1-49"),
        slot_id=SLOT_RING,
        kind="prefix",
    )


def _signed_property(property_id: str, **attributes: str) -> AffixProperty:
    return AffixProperty(property_id, property_id, dict(attributes))


def test_detrimental_sign_maps_to_penalty_and_never_matches() -> None:
    bonus = _signed_property("pet_maximum_all_resistance", percent="15.000000")
    penalty = _signed_property("pet_maximum_all_resistance", percent="-15.000000")
    profile = BuildProfile(weights={"pet_maximum_all_resistance": 4})

    assert semantic_stat_ids(bonus) == ("pet_maximum_all_resistance",)
    assert semantic_stat_ids(penalty) == ("penalty:pet_maximum_all_resistance",)

    bonus_score = score_semantic_stat_ids(semantic_stat_ids(bonus), profile)
    penalty_score = score_semantic_stat_ids(semantic_stat_ids(penalty), profile)
    assert bonus_score.matched_count == 1
    assert penalty_score.matched_count == 0
    assert penalty_score.weighted_match == 0
    # The penalty is still a stat the item carries, so it dilutes coverage.
    assert penalty_score.total_category_count == 1


def test_penalty_lowers_coverage_of_an_otherwise_matching_item() -> None:
    profile = BuildProfile(weights={"pet_total_damage_percent": 4})
    clean = (_signed_property("pet_total_damage_percent", percent="20"),)
    with_penalty = (
        *clean,
        _signed_property("pet_maximum_all_resistance", percent="-15"),
    )

    def score(properties: tuple[AffixProperty, ...]):
        return score_semantic_stat_ids(
            tuple(
                stat_id
                for property_ in properties
                for stat_id in semantic_stat_ids(property_)
            ),
            profile,
        )

    assert score(with_penalty).effective_score < score(clean).effective_score


def test_lower_polarity_stats_treat_negative_values_as_beneficial(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gd_affix_relevance.scoring import catalog_scorer

    monkeypatch.setattr(
        catalog_scorer,
        "stat_polarity",
        lambda stat_id: "lower" if stat_id == "skill_cooldown_reduction" else "higher",
    )
    good = _signed_property("skill_cooldown_reduction", percent="-10")
    bad = _signed_property("skill_cooldown_reduction", percent="10")

    assert semantic_stat_ids(good) == ("skill_cooldown_reduction",)
    assert semantic_stat_ids(bad) == ("penalty:skill_cooldown_reduction",)


def test_conversions_and_unsigned_properties_are_never_penalties() -> None:
    conversion = AffixProperty(
        "damage_conversion",
        "damage_conversion:1",
        {
            "source_damage_type": "Fire",
            "destination_damage_type": "Chaos",
            "percent": "-30",
        },
    )
    no_value = _signed_property("health")

    assert semantic_stat_ids(conversion) == ("damage_conversion_to_chaos",)
    assert semantic_stat_ids(no_value) == ("health",)
