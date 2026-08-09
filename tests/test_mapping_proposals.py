from gd_affix_relevance.normalization.mapping_proposals import (
    chance_damage_bundle_keys,
    contextualize_damage_chance,
    propose_field_mapping,
)


def test_confirmed_composite_and_skill_reference_proposals() -> None:
    conversion = propose_field_mapping("conversionPercentage")
    skill_bonus = propose_field_mapping("augmentSkillName1")
    granted_skill = propose_field_mapping("itemSkillName")

    assert conversion is not None
    assert conversion.property_id == "damage_conversion"
    assert conversion.value_role == "percent"
    assert conversion.confidence == "confirmed"

    assert skill_bonus is not None
    assert skill_bonus.property_id == "skill_bonus"
    assert skill_bonus.status == "structured_reference"
    assert skill_bonus.value_role == "skill_reference"

    assert granted_skill is not None
    assert granted_skill.property_id == "granted_item_skill"
    assert granted_skill.status == "structured_reference"


def test_damage_family_proposals_preserve_flat_percent_and_duration_roles() -> None:
    flat = propose_field_mapping("offensiveLightningMin")
    percent = propose_field_mapping("offensiveLightningModifier")
    dot = propose_field_mapping("offensiveSlowLightningMin")
    duration = propose_field_mapping("offensiveSlowLightningDurationModifier")

    assert flat is not None
    assert (flat.property_id, flat.value_role) == (
        "flat_lightning_damage",
        "damage_min",
    )
    assert percent is not None
    assert (percent.property_id, percent.value_role) == (
        "lightning_damage_percent",
        "damage_percent",
    )
    assert dot is not None
    assert (dot.property_id, dot.value_role) == (
        "flat_electrocute_damage",
        "damage_min",
    )
    assert duration is not None
    assert (duration.property_id, duration.value_role) == (
        "electrocute_damage_percent",
        "duration_percent",
    )
    assert duration.component_requirement == "optional"


def test_optional_chance_components_join_their_damage_properties() -> None:
    physical_min = propose_field_mapping("offensiveBonusPhysicalMin")
    physical_chance = propose_field_mapping("offensiveBonusPhysicalChance")
    pierce_min = propose_field_mapping("offensivePierceMin")
    pierce_chance = propose_field_mapping("offensivePierceChance")
    pierce_percent = propose_field_mapping("offensivePierceModifier")
    pierce_percent_chance = propose_field_mapping("offensivePierceModifierChance")

    assert physical_min is not None and physical_chance is not None
    assert physical_min.bundle_key == physical_chance.bundle_key
    assert physical_chance.value_role == "chance_percent"
    assert physical_chance.component_requirement == "optional"

    assert pierce_min is not None and pierce_chance is not None
    assert pierce_min.bundle_key == pierce_chance.bundle_key
    assert pierce_chance.component_requirement == "optional"

    assert pierce_percent is not None and pierce_percent_chance is not None
    assert pierce_percent.bundle_key == pierce_percent_chance.bundle_key
    assert pierce_percent_chance.value_role == "chance_percent"
    assert pierce_percent_chance.component_requirement == "optional"

    chance_bundles = chance_damage_bundle_keys((pierce_min, pierce_chance))
    contextual_min = contextualize_damage_chance(
        pierce_min, chance_bundles
    )
    contextual_chance = contextualize_damage_chance(
        pierce_chance, chance_bundles
    )
    assert contextual_min.property_id == "chance_flat_pierce_damage"
    assert contextual_min.bundle_key == contextual_chance.bundle_key


def test_dot_duration_modifier_is_optional_with_same_percent_damage_bundle() -> None:
    damage = propose_field_mapping("offensiveSlowPoisonModifier")
    duration = propose_field_mapping("offensiveSlowPoisonDurationModifier")

    assert damage is not None and duration is not None
    assert damage.bundle_key == duration.bundle_key
    assert damage.property_id == "poison_damage_percent"
    assert duration.property_id == "poison_damage_percent"
    assert damage.component_requirement == "core"
    assert duration.component_requirement == "optional"


def test_confirmed_target_reduction_bundles_include_duration() -> None:
    damage = propose_field_mapping("offensiveTotalDamageReductionPercentMin")
    damage_duration = propose_field_mapping(
        "offensiveTotalDamageReductionPercentDurationMin"
    )
    resistance = propose_field_mapping("offensiveTotalResistanceReductionAbsoluteMin")
    resistance_duration = propose_field_mapping(
        "offensiveTotalResistanceReductionAbsoluteDurationMin"
    )

    assert damage is not None and damage_duration is not None
    assert damage.bundle_key == damage_duration.bundle_key
    assert damage.confidence == damage_duration.confidence == "confirmed"
    assert "Reduced Target's Damage" in damage.display_template

    assert resistance is not None and resistance_duration is not None
    assert resistance.bundle_key == resistance_duration.bundle_key
    assert resistance.confidence == resistance_duration.confidence == "confirmed"
    assert "Reduced Target's Resistances" in resistance.display_template


def test_confirmed_confusion_range_and_chance_form_one_bundle() -> None:
    fields = [
        propose_field_mapping("offensiveConfusionChance"),
        propose_field_mapping("offensiveConfusionMin"),
        propose_field_mapping("offensiveConfusionMax"),
    ]

    assert all(proposal is not None for proposal in fields)
    assert {proposal.bundle_key for proposal in fields if proposal is not None} == {
        "confusion"
    }
    assert {proposal.value_role for proposal in fields if proposal is not None} == {
        "chance_percent",
        "duration_min",
        "duration_max",
    }
    assert all(
        proposal.confidence == "confirmed"
        for proposal in fields
        if proposal is not None
    )


def test_confirmed_single_field_utility_mappings_have_display_templates() -> None:
    expected = {
        "characterDefensiveBlockRecoveryReduction": "Shield Recovery Time",
        "characterEnergyAbsorptionPercent": "Energy Absorbed from Enemy Spells",
        "characterGlobalReqReduction": "All Attribute Requirements",
        "characterHealIncreasePercent": "Healing Effects Increased",
        "characterHuntingDexterityReqReduction": "Ranged Weapons",
        "characterLightRadius": "Increased Light Radius",
    }

    for raw_field, expected_text in expected.items():
        proposal = propose_field_mapping(raw_field)
        assert proposal is not None
        assert proposal.confidence == "confirmed"
        assert expected_text in proposal.display_template


def test_confirmed_defensive_ability_reduction_bundle() -> None:
    fields = [
        propose_field_mapping("offensiveSlowDefensiveAbilityChance"),
        propose_field_mapping("offensiveSlowDefensiveAbilityMin"),
        propose_field_mapping("offensiveSlowDefensiveAbilityDurationMin"),
    ]

    assert all(proposal is not None for proposal in fields)
    assert {proposal.bundle_key for proposal in fields if proposal is not None} == {
        "defensive_ability_reduction"
    }
    assert {proposal.value_role for proposal in fields if proposal is not None} == {
        "chance_percent",
        "reduction_flat",
        "duration_seconds",
    }
    assert all(
        proposal.confidence == "confirmed"
        for proposal in fields
        if proposal is not None
    )


def test_retaliation_effects_and_global_chance_remain_modular() -> None:
    outer_chance = propose_field_mapping("retaliationGlobalChance")
    attack_fields = [
        propose_field_mapping("retaliationSlowAttackSpeedChance"),
        propose_field_mapping("retaliationSlowAttackSpeedMin"),
        propose_field_mapping("retaliationSlowAttackSpeedDurationMin"),
        propose_field_mapping("retaliationSlowAttackSpeedGlobal"),
    ]
    movement_fields = [
        propose_field_mapping("retaliationSlowRunSpeedChance"),
        propose_field_mapping("retaliationSlowRunSpeedMin"),
        propose_field_mapping("retaliationSlowRunSpeedDurationMin"),
        propose_field_mapping("retaliationSlowRunSpeedGlobal"),
    ]

    assert outer_chance is not None
    assert outer_chance.bundle_key == "retaliation_effect_choice"
    assert outer_chance.confidence == "confirmed"
    assert {
        proposal.bundle_key for proposal in attack_fields if proposal is not None
    } == {"attack_speed_slow_retaliation"}
    assert {
        proposal.bundle_key for proposal in movement_fields if proposal is not None
    } == {"movement_speed_slow_retaliation"}
    assert attack_fields[-1] is not None
    assert attack_fields[-1].component_requirement == "metadata"
    assert movement_fields[-1] is not None
    assert movement_fields[-1].component_requirement == "metadata"


def test_cooldown_chance_is_optional_component_of_cooldown_reduction() -> None:
    reduction = propose_field_mapping("skillCooldownReduction")
    chance = propose_field_mapping("skillCooldownReductionChance")

    assert reduction is not None and chance is not None
    assert reduction.bundle_key == chance.bundle_key == "cooldown_reduction"
    assert reduction.value_role == "reduction_percent"
    assert chance.value_role == "chance_percent"
    assert chance.component_requirement == "optional"
    assert chance.confidence == "confirmed"


def test_final_reachable_review_fields_are_confirmed() -> None:
    expected = {
        "offensiveManaBurnDrainMin": ("energy_burn_percent", "Energy Burn"),
        "characterMeleeDexterityReqReduction": (
            "melee_weapon_cunning_requirement_reduction",
            "Melee Weapons",
        ),
        "defensiveAbsorptionModifier": (
            "armor_absorption_percent",
            "Armor Absorption",
        ),
    }

    for raw_field, (property_id, template_text) in expected.items():
        proposal = propose_field_mapping(raw_field)
        assert proposal is not None
        assert proposal.property_id == property_id
        assert proposal.confidence == "confirmed"
        assert template_text in proposal.display_template

    resistance = propose_field_mapping(
        "offensiveTotalResistanceReductionPercentMin"
    )
    duration = propose_field_mapping(
        "offensiveTotalResistanceReductionPercentDurationMin"
    )
    assert resistance is not None and duration is not None
    assert resistance.bundle_key == duration.bundle_key
    assert resistance.property_id == "target_resistance_reduction_percent"
    assert resistance.confidence == duration.confidence == "confirmed"


def test_orphan_only_fields_remain_auditable_but_are_ignored() -> None:
    for raw_field in (
        "characterIncreasedExperience",
        "offensiveFreezeChance",
        "offensiveSlowDefensiveReductionMin",
        "offensiveSlowManaLeachMin",
    ):
        proposal = propose_field_mapping(raw_field)
        assert proposal is not None
        assert proposal.status == "ignored"
        assert proposal.confidence == "confirmed"
        assert "no incoming item references" in proposal.notes


def test_metadata_is_ignored_and_unknown_field_remains_unmapped() -> None:
    metadata = propose_field_mapping("lootRandomizerCost")

    assert metadata is not None
    assert metadata.status == "ignored"
    assert propose_field_mapping("futureUnknownStat") is None


def test_item_only_base_damage_numbered_conversions_and_max_resists_map() -> None:
    base_min = propose_field_mapping("offensiveBaseFireMin")
    base_max = propose_field_mapping("offensiveBaseFireMax")
    conversion_source = propose_field_mapping("conversionInType2")
    conversion_percent = propose_field_mapping("conversionPercentage2")
    maximum_resistance = propose_field_mapping("defensiveFireMaxResist")

    assert base_min is not None and base_max is not None
    assert base_min.property_id == base_max.property_id == "flat_fire_damage"
    assert base_min.bundle_key == base_max.bundle_key == (
        "flat_fire_damage:base_weapon"
    )
    assert conversion_source is not None and conversion_percent is not None
    assert conversion_source.bundle_key == conversion_percent.bundle_key == (
        "damage_conversion:2"
    )
    assert maximum_resistance is not None
    assert maximum_resistance.property_id == "maximum_fire_resistance"
