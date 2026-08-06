"""Auditable first-pass proposals for raw DBR field normalization."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from gd_affix_relevance.normalization.field_policy import (
    SEMANTIC_FINGERPRINT_IGNORED_FIELDS,
)

MappingStatus = Literal["mapped", "structured_reference", "ignored"]
MappingConfidence = Literal["confirmed", "strongly_inferred", "needs_review"]
ComponentRequirement = Literal["core", "optional", "metadata"]


@dataclass(frozen=True, slots=True)
class FieldMappingProposal:
    raw_field: str
    property_id: str
    bundle_key: str
    display_label: str
    value_role: str
    component_requirement: ComponentRequirement
    status: MappingStatus
    confidence: MappingConfidence
    display_template: str = ""
    notes: str = ""


def _proposal(
    raw_field: str,
    property_id: str,
    display_label: str,
    value_role: str,
    *,
    bundle_key: str | None = None,
    component_requirement: ComponentRequirement = "core",
    confidence: MappingConfidence = "strongly_inferred",
    status: MappingStatus = "mapped",
    display_template: str = "",
    notes: str = "",
) -> FieldMappingProposal:
    return FieldMappingProposal(
        raw_field=raw_field,
        property_id=property_id,
        bundle_key=bundle_key if bundle_key is not None else property_id,
        display_label=display_label,
        value_role=value_role,
        component_requirement=component_requirement,
        status=status,
        confidence=confidence,
        display_template=display_template,
        notes=notes,
    )


CHARACTER_RULES: dict[str, tuple[str, str, str]] = {
    "characterAttackSpeedModifier": ("attack_speed", "Attack Speed", "percent"),
    "characterDefensiveAbility": ("defensive_ability", "Defensive Ability", "flat"),
    "characterDefensiveAbilityModifier": (
        "defensive_ability_percent",
        "Defensive Ability",
        "percent",
    ),
    "characterDexterity": ("cunning", "Cunning", "flat"),
    "characterDexterityModifier": ("cunning_percent", "Cunning", "percent"),
    "characterDodgePercent": ("dodge_chance", "Chance to Dodge", "percent"),
    "characterIntelligence": ("spirit", "Spirit", "flat"),
    "characterIntelligenceModifier": ("spirit_percent", "Spirit", "percent"),
    "characterLife": ("health", "Health", "flat"),
    "characterLifeModifier": ("health_percent", "Health", "percent"),
    "characterLifeRegen": ("health_regeneration", "Health Regeneration", "flat"),
    "characterLifeRegenModifier": (
        "health_regeneration_percent",
        "Health Regeneration",
        "percent",
    ),
    "characterMana": ("energy", "Energy", "flat"),
    "characterManaModifier": ("energy_percent", "Energy", "percent"),
    "characterManaRegen": ("energy_regeneration", "Energy Regeneration", "flat"),
    "characterManaRegenModifier": (
        "energy_regeneration_percent",
        "Energy Regeneration",
        "percent",
    ),
    "characterOffensiveAbility": ("offensive_ability", "Offensive Ability", "flat"),
    "characterOffensiveAbilityModifier": (
        "offensive_ability_percent",
        "Offensive Ability",
        "percent",
    ),
    "characterRunSpeedModifier": ("movement_speed", "Movement Speed", "percent"),
    "characterSpellCastSpeedModifier": ("casting_speed", "Casting Speed", "percent"),
    "characterStrength": ("physique", "Physique", "flat"),
    "characterStrengthModifier": ("physique_percent", "Physique", "percent"),
    "characterTotalSpeedModifier": ("total_speed", "Total Speed", "percent"),
}

DEFENSIVE_RULES: dict[str, tuple[str, str]] = {
    "defensiveAether": ("aether_resistance", "Aether Resistance"),
    "defensiveBleeding": ("bleeding_resistance", "Bleeding Resistance"),
    "defensiveChaos": ("chaos_resistance", "Chaos Resistance"),
    "defensiveCold": ("cold_resistance", "Cold Resistance"),
    "defensiveDisruption": ("disruption_resistance", "Disruption Resistance"),
    "defensiveElementalResistance": ("elemental_resistance", "Elemental Resistance"),
    "defensiveFire": ("fire_resistance", "Fire Resistance"),
    "defensiveFreeze": ("freeze_resistance", "Freeze Resistance"),
    "defensiveLife": ("vitality_resistance", "Vitality Resistance"),
    "defensiveLightning": ("lightning_resistance", "Lightning Resistance"),
    "defensivePetrify": ("petrify_resistance", "Petrify Resistance"),
    "defensivePhysical": ("physical_resistance", "Physical Resistance"),
    "defensivePierce": ("pierce_resistance", "Pierce Resistance"),
    "defensivePoison": ("poison_acid_resistance", "Poison & Acid Resistance"),
    "defensiveStun": ("stun_resistance", "Stun Resistance"),
    "defensiveTotalSpeedResistance": ("slow_resistance", "Slow Resistance"),
    "defensiveTrap": ("entrapment_resistance", "Entrapment Resistance"),
}

REVIEW_RULES: dict[str, tuple[str, str, str]] = {
}

# These fields currently occur only on localized affix definitions with no
# incoming item-record references. Keep the list explicit so they can be
# re-evaluated if a future game database reconnects one of those affixes.
LEGACY_ORPHANED_FIELDS = frozenset(
    {
        "characterConstitutionModifier",
        "characterIncreasedExperience",
        "defensiveBleedingDuration",
        "defensivePoisonDuration",
        "defensiveProtection",
        "offensiveFreezeChance",
        "offensiveFreezeMin",
        "offensiveSlowDefensiveReductionChance",
        "offensiveSlowDefensiveReductionDurationMin",
        "offensiveSlowDefensiveReductionMin",
        "offensiveSlowManaLeachChance",
        "offensiveSlowManaLeachDurationMin",
        "offensiveSlowManaLeachMin",
        "offensiveTotalResistanceReductionAbsoluteChance",
    }
)

CONFIRMED_COMPOSITE_RULES: dict[str, tuple[str, str, str, str, str]] = {
    "characterDefensiveBlockRecoveryReduction": (
        "shield_recovery_time_reduction",
        "shield_recovery_time_reduction",
        "Shield Recovery Time",
        "reduction_percent",
        "-{reduction_percent}% Shield Recovery Time",
    ),
    "characterEnergyAbsorptionPercent": (
        "energy_absorbed_from_enemy_spells",
        "energy_absorbed_from_enemy_spells",
        "Energy Absorbed from Enemy Spells",
        "percent",
        "{percent}% Energy Absorbed from Enemy Spells",
    ),
    "characterGlobalReqReduction": (
        "all_attribute_requirements_reduction",
        "all_attribute_requirements_reduction",
        "Reduction to All Attribute Requirements",
        "percent",
        "{percent}% Reduction to All Attribute Requirements",
    ),
    "characterHealIncreasePercent": (
        "healing_effects_increase",
        "healing_effects_increase",
        "Healing Effects Increased",
        "percent",
        "Healing Effects Increased by {percent}%",
    ),
    "characterHuntingDexterityReqReduction": (
        "ranged_weapon_cunning_requirement_reduction",
        "ranged_weapon_cunning_requirement_reduction",
        "Reduced Cunning Requirement for Ranged Weapons",
        "percent",
        "-{percent}% Reduced Cunning Requirement for Ranged Weapons",
    ),
    "characterMeleeDexterityReqReduction": (
        "melee_weapon_cunning_requirement_reduction",
        "melee_weapon_cunning_requirement_reduction",
        "Reduced Cunning Requirement for Melee Weapons",
        "percent",
        "-{percent}% Reduced Cunning Requirement for Melee Weapons",
    ),
    "characterLightRadius": (
        "light_radius_percent",
        "light_radius_percent",
        "Increased Light Radius",
        "percent",
        "{percent}% Increased Light Radius",
    ),
    "offensiveConfusionChance": (
        "confusion",
        "confusion",
        "Chance to Confuse Target",
        "chance_percent",
        "{chance_percent}% Chance to Confuse Target for {duration_min}-{duration_max} Seconds",
    ),
    "offensiveConfusionMax": (
        "confusion",
        "confusion",
        "Chance to Confuse Target",
        "duration_max",
        "{chance_percent}% Chance to Confuse Target for {duration_min}-{duration_max} Seconds",
    ),
    "offensiveConfusionMin": (
        "confusion",
        "confusion",
        "Chance to Confuse Target",
        "duration_min",
        "{chance_percent}% Chance to Confuse Target for {duration_min}-{duration_max} Seconds",
    ),
    "offensivePercentCurrentLifeMax": (
        "enemy_health_reduction_percent",
        "enemy_health_reduction_percent",
        "Reduction in Enemy Health",
        "percent_max",
        "{percent_min}-{percent_max}% Reduction in Enemy's Health",
    ),
    "offensivePercentCurrentLifeMin": (
        "enemy_health_reduction_percent",
        "enemy_health_reduction_percent",
        "Reduction in Enemy Health",
        "percent_min",
        "{percent_min}-{percent_max}% Reduction in Enemy's Health",
    ),
    "defensiveAbsorptionModifier": (
        "armor_absorption_percent",
        "armor_absorption_percent",
        "Increased Armor Absorption",
        "percent",
        "Increases Armor Absorption by {percent}%",
    ),
    "offensiveManaBurnDrainMin": (
        "energy_burn_percent",
        "energy_burn_percent",
        "Energy Burn",
        "percent",
        "{percent}% Energy Burn",
    ),
    "offensiveSlowDefensiveAbilityChance": (
        "defensive_ability_reduction",
        "defensive_ability_reduction",
        "Chance to Reduce Target Defensive Ability",
        "chance_percent",
        "{chance_percent}% Chance to Reduce Target's Defensive Ability by {reduction_flat} for {duration_seconds} Seconds",
    ),
    "offensiveSlowDefensiveAbilityDurationMin": (
        "defensive_ability_reduction",
        "defensive_ability_reduction",
        "Chance to Reduce Target Defensive Ability",
        "duration_seconds",
        "{chance_percent}% Chance to Reduce Target's Defensive Ability by {reduction_flat} for {duration_seconds} Seconds",
    ),
    "offensiveSlowDefensiveAbilityMin": (
        "defensive_ability_reduction",
        "defensive_ability_reduction",
        "Chance to Reduce Target Defensive Ability",
        "reduction_flat",
        "{chance_percent}% Chance to Reduce Target's Defensive Ability by {reduction_flat} for {duration_seconds} Seconds",
    ),
    "offensiveTotalDamageReductionPercentDurationMin": (
        "target_damage_reduction_percent",
        "target_damage_reduction_percent",
        "Reduced Target Damage",
        "duration_seconds",
        "{reduction_percent}% Reduced Target's Damage for {duration_seconds} Seconds",
    ),
    "offensiveTotalDamageReductionPercentMin": (
        "target_damage_reduction_percent",
        "target_damage_reduction_percent",
        "Reduced Target Damage",
        "reduction_percent",
        "{reduction_percent}% Reduced Target's Damage for {duration_seconds} Seconds",
    ),
    "offensiveTotalResistanceReductionAbsoluteDurationMin": (
        "target_resistance_reduction_flat",
        "target_resistance_reduction_flat",
        "Reduced Target Resistances",
        "duration_seconds",
        "{reduction_flat} Reduced Target's Resistances for {duration_seconds} Seconds",
    ),
    "offensiveTotalResistanceReductionAbsoluteMin": (
        "target_resistance_reduction_flat",
        "target_resistance_reduction_flat",
        "Reduced Target Resistances",
        "reduction_flat",
        "{reduction_flat} Reduced Target's Resistances for {duration_seconds} Seconds",
    ),
    "offensiveTotalResistanceReductionPercentDurationMin": (
        "target_resistance_reduction_percent",
        "target_resistance_reduction_percent",
        "Percent Reduced Target Resistances",
        "duration_seconds",
        "{reduction_percent}% Reduced Target's Resistances for {duration_seconds} Seconds",
    ),
    "offensiveTotalResistanceReductionPercentMin": (
        "target_resistance_reduction_percent",
        "target_resistance_reduction_percent",
        "Percent Reduced Target Resistances",
        "reduction_percent",
        "{reduction_percent}% Reduced Target's Resistances for {duration_seconds} Seconds",
    ),
    "retaliationGlobalChance": (
        "retaliation_effect_choice",
        "retaliation_effect_choice",
        "Chance of One Retaliation Effect",
        "global_chance_percent",
        "{global_chance_percent}% Chance of One of the Following Retaliation Effects",
    ),
    "retaliationSlowAttackSpeedChance": (
        "attack_speed_slow_retaliation",
        "attack_speed_slow_retaliation",
        "Reduced Attack Speed Retaliation",
        "effect_chance_percent",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Attack Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowAttackSpeedDurationMin": (
        "attack_speed_slow_retaliation",
        "attack_speed_slow_retaliation",
        "Reduced Attack Speed Retaliation",
        "duration_seconds",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Attack Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowAttackSpeedGlobal": (
        "attack_speed_slow_retaliation",
        "attack_speed_slow_retaliation",
        "Reduced Attack Speed Retaliation",
        "global_flag",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Attack Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowAttackSpeedMin": (
        "attack_speed_slow_retaliation",
        "attack_speed_slow_retaliation",
        "Reduced Attack Speed Retaliation",
        "reduction_percent",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Attack Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowRunSpeedChance": (
        "movement_speed_slow_retaliation",
        "movement_speed_slow_retaliation",
        "Reduced Movement Speed Retaliation",
        "effect_chance_percent",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Movement Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowRunSpeedDurationMin": (
        "movement_speed_slow_retaliation",
        "movement_speed_slow_retaliation",
        "Reduced Movement Speed Retaliation",
        "duration_seconds",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Movement Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowRunSpeedGlobal": (
        "movement_speed_slow_retaliation",
        "movement_speed_slow_retaliation",
        "Reduced Movement Speed Retaliation",
        "global_flag",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Movement Speed Retaliation for {duration_seconds} Seconds",
    ),
    "retaliationSlowRunSpeedMin": (
        "movement_speed_slow_retaliation",
        "movement_speed_slow_retaliation",
        "Reduced Movement Speed Retaliation",
        "reduction_percent",
        "{effect_chance_percent}% Chance of {reduction_percent}% Reduced Movement Speed Retaliation for {duration_seconds} Seconds",
    ),
    "skillCooldownReductionChance": (
        "cooldown_reduction",
        "cooldown_reduction",
        "Skill Cooldown Reduction",
        "chance_percent",
        "{chance_percent}% Chance of +{reduction_percent}% Skill Cooldown Reduction",
    ),
}


CONFIRMED_COMPONENT_REQUIREMENTS: dict[str, ComponentRequirement] = {
    "retaliationSlowAttackSpeedGlobal": "metadata",
    "retaliationSlowRunSpeedGlobal": "metadata",
    "skillCooldownReductionChance": "optional",
}


CONFIRMED_COMPONENT_NOTES: dict[str, str] = {
    "retaliationGlobalChance": (
        "Outer wrapper for the active retaliation effect bundles in the same record; "
        "do not merge it into one specific retaliation effect."
    ),
    "retaliationSlowAttackSpeedChance": (
        "Effect-local chance. The effect can occur without retaliationGlobalChance; "
        "a renderer must account for the outer wrapper when both are present."
    ),
    "retaliationSlowRunSpeedChance": (
        "Effect-local chance. The effect can occur without retaliationGlobalChance; "
        "a renderer must account for the outer wrapper when both are present."
    ),
    "retaliationSlowAttackSpeedGlobal": "Internal structural flag; not a separate player-facing stat.",
    "retaliationSlowRunSpeedGlobal": "Internal structural flag; not a separate player-facing stat.",
    "skillCooldownReductionChance": (
        "Optional chance wrapper around skillCooldownReduction; standalone cooldown "
        "reduction records omit this field."
    ),
}

DAMAGE_TOKENS: dict[str, tuple[str, str]] = {
    "Aether": ("aether", "Aether"),
    "BonusPhysical": ("physical", "Physical"),
    "Chaos": ("chaos", "Chaos"),
    "Cold": ("cold", "Cold"),
    "Elemental": ("elemental", "Elemental"),
    "Fire": ("fire", "Fire"),
    "Life": ("vitality", "Vitality"),
    "Lightning": ("lightning", "Lightning"),
    "Physical": ("physical", "Physical"),
    "Pierce": ("pierce", "Pierce"),
    "Poison": ("acid", "Acid"),
}

DOT_TOKENS: dict[str, tuple[str, str]] = {
    "Bleeding": ("bleeding", "Bleeding"),
    "Cold": ("frostburn", "Frostburn"),
    "Fire": ("burn", "Burn"),
    "Life": ("vitality_decay", "Vitality Decay"),
    "Lightning": ("electrocute", "Electrocute"),
    "Physical": ("internal_trauma", "Internal Trauma"),
    "Poison": ("poison", "Poison"),
}


def propose_field_mapping(raw_field: str) -> FieldMappingProposal | None:
    """Return an auditable mapping proposal, or ``None`` when still unknown."""

    if raw_field in SEMANTIC_FINGERPRINT_IGNORED_FIELDS:
        return _proposal(
            raw_field,
            "",
            "",
            "ignored_metadata",
            component_requirement="metadata",
            confidence="confirmed",
            status="ignored",
        )

    if raw_field in LEGACY_ORPHANED_FIELDS:
        return _proposal(
            raw_field,
            "",
            "",
            "ignored_legacy_orphan",
            component_requirement="metadata",
            confidence="confirmed",
            status="ignored",
            notes=(
                "Currently found only on affix definitions with no incoming item "
                "references; retained for future database re-evaluation."
            ),
        )

    if rule := CONFIRMED_COMPOSITE_RULES.get(raw_field):
        property_id, bundle_key, label, role, display_template = rule
        return _proposal(
            raw_field,
            property_id,
            label,
            role,
            bundle_key=bundle_key,
            component_requirement=CONFIRMED_COMPONENT_REQUIREMENTS.get(
                raw_field, "core"
            ),
            confidence="confirmed",
            display_template=display_template,
            notes=CONFIRMED_COMPONENT_NOTES.get(raw_field, ""),
        )

    if rule := CHARACTER_RULES.get(raw_field):
        property_id, label, role = rule
        confidence: MappingConfidence = (
            "confirmed"
            if raw_field
            in {
                "characterOffensiveAbility",
                "characterOffensiveAbilityModifier",
                "characterAttackSpeedModifier",
                "characterDefensiveAbility",
                "characterManaRegen",
                "characterSpellCastSpeedModifier",
            }
            else "strongly_inferred"
        )
        return _proposal(raw_field, property_id, label, role, confidence=confidence)

    if rule := DEFENSIVE_RULES.get(raw_field):
        property_id, label = rule
        return _proposal(raw_field, property_id, label, "percent")

    if rule := REVIEW_RULES.get(raw_field):
        return _proposal(
            raw_field,
            *rule,
            confidence="needs_review",
            notes="Plausible player-facing mapping; confirm against an in-game or Grim Tools example.",
        )

    if match := re.fullmatch(r"augmentSkill(Name|Level)(\d+)", raw_field):
        role = "skill_reference" if match.group(1) == "Name" else "skill_level"
        return _proposal(
            raw_field,
            "skill_bonus",
            "Skill Bonus",
            role,
            bundle_key=f"skill_bonus:{match.group(2)}",
            confidence="confirmed",
            status="structured_reference",
            notes="Resolve referenced skill DBR to skillDisplayName; do not display filename.",
        )

    item_skill_roles = {
        "itemSkillAutoController": "trigger_controller",
        "itemSkillLevelEq": "level_equation",
        "itemSkillName": "skill_reference",
    }
    if role := item_skill_roles.get(raw_field):
        return _proposal(
            raw_field,
            "granted_item_skill",
            "Granted Skill",
            role,
            confidence="confirmed",
            status="structured_reference",
            notes="Preserve for inspection; excluded from initial relevance scoring.",
        )

    if raw_field == "petBonusName":
        return _proposal(
            raw_field,
            "pet_bonus",
            "Pet Bonus",
            "record_reference",
            status="structured_reference",
            notes="Referenced pet-bonus record requires a separate normalization pass.",
        )

    if match := re.fullmatch(
        r"conversion(InType|OutType|Percentage)(\d*)", raw_field
    ):
        role = {
            "InType": "source_damage_type",
            "OutType": "destination_damage_type",
            "Percentage": "percent",
        }[match.group(1)]
        index = match.group(2) or "1"
        return _proposal(
            raw_field,
            "damage_conversion",
            "Damage Conversion",
            role,
            bundle_key=f"damage_conversion:{index}",
            confidence="confirmed",
        )

    if raw_field in {"racialBonusRace", "racialBonusPercentDamage"}:
        role = "race_reference" if raw_field.endswith("Race") else "percent"
        return _proposal(raw_field, "racial_damage_bonus", "Damage to Creature Type", role)

    if raw_field == "skillCooldownReduction":
        return _proposal(
            raw_field,
            "cooldown_reduction",
            "Skill Cooldown Reduction",
            "reduction_percent",
            display_template="{reduction_percent}% Skill Cooldown Reduction",
        )

    if raw_field == "skillManaCostReduction":
        return _proposal(
            raw_field,
            "skill_energy_cost_reduction",
            "Skill Energy Cost Reduction",
            "percent",
        )

    exact_rules = {
        "augmentAllLevel": ("all_skills_bonus", "All Skills", "skill_level"),
        "blockRecoveryTime": (
            "base_shield_recovery_time",
            "Base Shield Recovery Time",
            "seconds",
        ),
        "characterBaseAttackSpeed": (
            "base_attack_speed",
            "Base Weapon Attack Speed",
            "value",
        ),
        "defensiveAllMaxResist": (
            "maximum_all_resistance",
            "Maximum All Resistances",
            "percent",
        ),
        "defensiveBlock": ("base_shield_block_amount", "Base Shield Block", "flat"),
        "defensiveBlockChance": (
            "base_shield_block_chance",
            "Base Shield Block Chance",
            "percent",
        ),
        "defensiveBlockAmountModifier": (
            "shield_block_amount_percent",
            "Shield Block Amount",
            "percent",
        ),
        "defensiveBlockModifier": (
            "shield_block_chance_percent",
            "Shield Block Chance",
            "percent",
        ),
        "defensiveBonusProtection": ("armor", "Armor", "flat"),
        "defensiveProtectionModifier": ("armor_percent", "Armor", "percent"),
        "offensiveCritDamageModifier": ("critical_damage", "Critical Damage", "percent"),
        "offensiveLifeLeechMin": (
            "attack_damage_converted_to_health",
            "Attack Damage Converted to Health",
            "percent",
        ),
        "offensivePierceRatioMin": (
            "armor_piercing_percent",
            "Armor Piercing",
            "percent",
        ),
        "defensivePercentReflectionResistance": (
            "reflected_damage_reduction",
            "Reflected Damage Reduction",
            "percent",
        ),
        "offensiveStunModifier": ("stun_duration", "Stun Duration", "percent"),
        "offensiveTotalDamageModifier": ("total_damage_percent", "Total Damage", "percent"),
        "retaliationTotalDamageModifier": (
            "retaliation_damage_percent",
            "Retaliation Damage",
            "percent",
        ),
    }
    if rule := exact_rules.get(raw_field):
        return _proposal(raw_field, *rule)

    max_resistance_tokens = {
        "Aether": ("aether", "Aether"),
        "Bleeding": ("bleeding", "Bleeding"),
        "Chaos": ("chaos", "Chaos"),
        "Cold": ("cold", "Cold"),
        "Elemental": ("elemental", "Elemental"),
        "Fire": ("fire", "Fire"),
        "Life": ("vitality", "Vitality"),
        "Lightning": ("lightning", "Lightning"),
        "Physical": ("physical", "Physical"),
        "Pierce": ("pierce", "Pierce"),
        "Poison": ("poison_acid", "Poison & Acid"),
    }
    if match := re.fullmatch(
        r"defensive(" + "|".join(max_resistance_tokens) + r")MaxResist",
        raw_field,
    ):
        resistance_id, resistance_label = max_resistance_tokens[match.group(1)]
        return _proposal(
            raw_field,
            f"maximum_{resistance_id}_resistance",
            f"Maximum {resistance_label} Resistance",
            "percent",
        )

    if match := re.fullmatch(
        r"offensiveBase(" + "|".join(DAMAGE_TOKENS) + r")(Min|Max)",
        raw_field,
    ):
        damage_id, damage_label = DAMAGE_TOKENS[match.group(1)]
        return _proposal(
            raw_field,
            f"flat_{damage_id}_damage",
            f"{damage_label} Damage",
            "damage_min" if match.group(2) == "Min" else "damage_max",
            bundle_key=f"flat_{damage_id}_damage:base_weapon",
            component_requirement="core" if match.group(2) == "Min" else "optional",
        )

    if match := re.fullmatch(
        r"offensive("
        + "|".join(DAMAGE_TOKENS)
        + r")(Min|Max|Modifier|Chance|ModifierChance)",
        raw_field,
    ):
        damage_id, damage_label = DAMAGE_TOKENS[match.group(1)]
        suffix = match.group(2)
        if suffix in {"Modifier", "ModifierChance"}:
            property_id = f"{damage_id}_damage_percent"
            return _proposal(
                raw_field,
                property_id,
                f"{damage_label} Damage",
                "damage_percent" if suffix == "Modifier" else "chance_percent",
                component_requirement=(
                    "core" if suffix == "Modifier" else "optional"
                ),
            )
        property_id = f"flat_{damage_id}_damage"
        bundle_key = (
            f"{property_id}:bonus_physical"
            if match.group(1) == "BonusPhysical"
            else property_id
        )
        roles = {
            "Min": "damage_min",
            "Max": "damage_max",
            "Chance": "chance_percent",
        }
        return _proposal(
            raw_field,
            property_id,
            f"{damage_label} Damage",
            roles[suffix],
            bundle_key=bundle_key,
            component_requirement="core" if suffix == "Min" else "optional",
        )

    if match := re.fullmatch(
        r"offensiveSlow("
        + "|".join(DOT_TOKENS)
        + r")(Min|Max|Modifier|Chance|ModifierChance|DurationMin|DurationMax|DurationModifier)",
        raw_field,
    ):
        dot_id, dot_label = DOT_TOKENS[match.group(1)]
        suffix = match.group(2)
        if suffix == "Modifier":
            property_id = f"{dot_id}_damage_percent"
            role = "damage_percent"
            requirement: ComponentRequirement = "core"
        elif suffix == "DurationModifier":
            property_id = f"{dot_id}_damage_percent"
            role = "duration_percent"
            requirement = "optional"
        elif suffix == "ModifierChance":
            property_id = f"{dot_id}_damage_percent"
            role = "chance_percent"
            requirement = "optional"
        elif suffix.startswith("Duration"):
            property_id = f"flat_{dot_id}_damage"
            role = "duration_min" if suffix == "DurationMin" else "duration_max"
            requirement = "core" if suffix == "DurationMin" else "optional"
        elif suffix == "Chance":
            property_id = f"flat_{dot_id}_damage"
            role = "chance_percent"
            requirement = "optional"
        else:
            property_id = f"flat_{dot_id}_damage"
            role = "damage_min" if suffix == "Min" else "damage_max"
            requirement = "core" if suffix == "Min" else "optional"
        notes = (
            "Optional increased-duration component of the percent damage-over-time property."
            if suffix == "DurationModifier"
            else ""
        )
        return _proposal(
            raw_field,
            property_id,
            f"{dot_label} Damage",
            role,
            component_requirement=requirement,
            notes=notes,
        )

    if match := re.fullmatch(
        r"retaliation(" + "|".join(DAMAGE_TOKENS) + r")(Min|Max|Modifier)",
        raw_field,
    ):
        damage_id, damage_label = DAMAGE_TOKENS[match.group(1)]
        suffix = match.group(2)
        role = "damage_percent" if suffix == "Modifier" else f"damage_{suffix.lower()}"
        return _proposal(
            raw_field,
            f"{damage_id}_retaliation_damage",
            f"{damage_label} Retaliation",
            role,
        )

    if "Reduction" in raw_field or raw_field.endswith("Chance"):
        return _proposal(
            raw_field,
            "unresolved_composite",
            "Composite effect requiring review",
            "component",
            confidence="needs_review",
            bundle_key=f"unresolved:{raw_field}",
            notes="Retained, but requires grouping with related chance/duration/effect fields.",
        )

    return None
