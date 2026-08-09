"""Data-driven tabs, packages, and stat rows for the profile editor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatDefinition:
    stat_id: str
    label: str


@dataclass(frozen=True, slots=True)
class PackageDefinition:
    package_id: str
    label: str
    stats: tuple[StatDefinition, ...]
    default_expanded: bool = False


@dataclass(frozen=True, slots=True)
class TabDefinition:
    tab_id: str
    label: str
    packages: tuple[PackageDefinition, ...]


def stat(stat_id: str, label: str) -> StatDefinition:
    return StatDefinition(stat_id, label)


def conversion_stat(destination: str, label: str) -> StatDefinition:
    return stat(f"damage_conversion_to_{destination}", f"Damage Converted to {label}")


def base_weapon_damage_stat(damage_type: str, label: str) -> StatDefinition:
    return stat(
        f"base_weapon_damage_as_{damage_type}",
        f"Base Weapon Damage as {label}",
    )


def chance_damage_stat(damage_type: str, label: str) -> StatDefinition:
    return stat(
        f"chance_flat_{damage_type}_damage",
        f"Chance of {label} Damage",
    )


DAMAGE_TAB = TabDefinition(
    "damage",
    "Damage",
    (
        PackageDefinition(
            "damage_base",
            "Base",
            (
                stat("total_damage_percent", "All Damage"),
                stat("critical_damage", "Critical Damage"),
                stat("offensive_ability", "Offensive Ability (Flat)"),
                stat("offensive_ability_percent", "Offensive Ability (+%)"),
                stat("defensive_ability_reduction", "Defensive Ability Reduction"),
                stat("target_resistance_reduction_flat", "Resistance Reduction (Flat)"),
                stat(
                    "target_resistance_reduction_percent",
                    "Resistance Reduction (+%)",
                ),
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "damage_elemental",
            "Elemental",
            (
                stat("flat_elemental_damage", "Elemental Damage (Flat)"),
                stat("elemental_damage_percent", "Elemental Damage (+%)"),
                base_weapon_damage_stat("elemental", "Elemental"),
                conversion_stat("elemental", "Elemental"),
            ),
        ),
        PackageDefinition(
            "damage_acid",
            "Acid / Poison",
            (
                stat("flat_acid_damage", "Acid Damage (Flat)"),
                stat("acid_damage_percent", "Acid Damage (+%)"),
                base_weapon_damage_stat("acid", "Acid"),
                stat("flat_poison_damage", "Poison Damage (Flat DoT)"),
                stat("poison_damage_percent", "Poison Damage (+% DoT)"),
                conversion_stat("acid", "Acid"),
            ),
        ),
        PackageDefinition(
            "damage_aether",
            "Aether",
            (
                stat("flat_aether_damage", "Aether Damage (Flat)"),
                stat("aether_damage_percent", "Aether Damage (+%)"),
                base_weapon_damage_stat("aether", "Aether"),
                conversion_stat("aether", "Aether"),
            ),
        ),
        PackageDefinition(
            "damage_bleeding",
            "Bleeding",
            (
                stat("flat_bleeding_damage", "Bleeding Damage (Flat DoT)"),
                stat("bleeding_damage_percent", "Bleeding Damage (+% DoT)"),
            ),
        ),
        PackageDefinition(
            "damage_fire",
            "Fire / Burn",
            (
                stat("flat_fire_damage", "Fire Damage (Flat)"),
                chance_damage_stat("fire", "Fire"),
                stat("fire_damage_percent", "Fire Damage (+%)"),
                base_weapon_damage_stat("fire", "Fire"),
                stat("flat_burn_damage", "Burn Damage (Flat DoT)"),
                chance_damage_stat("burn", "Burn"),
                stat("burn_damage_percent", "Burn Damage (+% DoT)"),
                conversion_stat("fire", "Fire"),
            ),
        ),
        PackageDefinition(
            "damage_chaos",
            "Chaos",
            (
                stat("flat_chaos_damage", "Chaos Damage (Flat)"),
                stat("chaos_damage_percent", "Chaos Damage (+%)"),
                base_weapon_damage_stat("chaos", "Chaos"),
                conversion_stat("chaos", "Chaos"),
            ),
        ),
        PackageDefinition(
            "damage_cold",
            "Cold / Frostburn",
            (
                stat("flat_cold_damage", "Cold Damage (Flat)"),
                stat("cold_damage_percent", "Cold Damage (+%)"),
                base_weapon_damage_stat("cold", "Cold"),
                stat("flat_frostburn_damage", "Frostburn Damage (Flat DoT)"),
                stat("frostburn_damage_percent", "Frostburn Damage (+% DoT)"),
                conversion_stat("cold", "Cold"),
            ),
        ),
        PackageDefinition(
            "damage_lightning",
            "Lightning / Electrocute",
            (
                stat("flat_lightning_damage", "Lightning Damage (Flat)"),
                stat("lightning_damage_percent", "Lightning Damage (+%)"),
                base_weapon_damage_stat("lightning", "Lightning"),
                stat("flat_electrocute_damage", "Electrocute Damage (Flat DoT)"),
                stat("electrocute_damage_percent", "Electrocute Damage (+% DoT)"),
                conversion_stat("lightning", "Lightning"),
            ),
        ),
        PackageDefinition(
            "damage_physical",
            "Physical / Internal Trauma",
            (
                stat("flat_physical_damage", "Physical Damage (Flat)"),
                chance_damage_stat("physical", "Physical"),
                stat("physical_damage_percent", "Physical Damage (+%)"),
                base_weapon_damage_stat("physical", "Physical"),
                stat("flat_internal_trauma_damage", "Internal Trauma (Flat DoT)"),
                stat("internal_trauma_damage_percent", "Internal Trauma (+% DoT)"),
                conversion_stat("physical", "Physical"),
            ),
        ),
        PackageDefinition(
            "damage_pierce",
            "Pierce",
            (
                stat("flat_pierce_damage", "Pierce Damage (Flat)"),
                chance_damage_stat("pierce", "Pierce"),
                stat("pierce_damage_percent", "Pierce Damage (+%)"),
                base_weapon_damage_stat("pierce", "Pierce"),
                stat("armor_piercing_percent", "100% Armor Piercing"),
                conversion_stat("pierce", "Pierce"),
            ),
        ),
        PackageDefinition(
            "damage_vitality",
            "Vitality / Vitality Decay",
            (
                stat("flat_vitality_damage", "Vitality Damage (Flat)"),
                stat("vitality_damage_percent", "Vitality Damage (+%)"),
                base_weapon_damage_stat("vitality", "Vitality"),
                stat("flat_vitality_decay_damage", "Vitality Decay (Flat DoT)"),
                stat("vitality_decay_damage_percent", "Vitality Decay (+% DoT)"),
                conversion_stat("vitality", "Vitality"),
            ),
        ),
    ),
)


RESISTANCE_STATS = tuple(
    stat(stat_id, label)
    for stat_id, label in (
        ("elemental_resistance", "Elemental Resistance"),
        ("aether_resistance", "Aether Resistance"),
        ("bleeding_resistance", "Bleeding Resistance"),
        ("chaos_resistance", "Chaos Resistance"),
        ("cold_resistance", "Cold Resistance"),
        ("fire_resistance", "Fire Resistance"),
        ("lightning_resistance", "Lightning Resistance"),
        ("physical_resistance", "Physical Resistance"),
        ("pierce_resistance", "Pierce Resistance"),
        ("poison_acid_resistance", "Poison & Acid Resistance"),
        ("vitality_resistance", "Vitality Resistance"),
    )
)


DEFENSES_TAB = TabDefinition(
    "defenses",
    "Defenses",
    (
        PackageDefinition(
            "defense_resistances",
            "Resistances",
            RESISTANCE_STATS,
            default_expanded=True,
        ),
        PackageDefinition(
            "defense_ability",
            "Defensive Ability",
            (
                stat("defensive_ability", "Defensive Ability (Flat)"),
                stat("defensive_ability_percent", "Defensive Ability (+%)"),
                stat("target_damage_reduction_percent", "Reduced Target Damage"),
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "defense_supplemental",
            "Supplemental Defenses",
            (
                stat("armor_percent", "Armor (+%)"),
                stat("armor_absorption_percent", "Armor Absorption (+%)"),
                stat("dodge_chance", "Dodge Chance"),
            ),
        ),
        PackageDefinition(
            "defense_shield",
            "Shield",
            (
                stat("shield_block_amount_percent", "Shield Block Amount"),
                stat("shield_block_chance_percent", "Shield Block Chance"),
                stat(
                    "shield_recovery_time_reduction",
                    "Shield Recovery Time Reduction",
                ),
            ),
        ),
        PackageDefinition(
            "defense_control",
            "Control Resistances",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("stun_resistance", "Stun Resistance"),
                    ("freeze_resistance", "Freeze Resistance"),
                    ("entrapment_resistance", "Entrapment Resistance"),
                    ("petrify_resistance", "Petrify Resistance"),
                    ("slow_resistance", "Slow Resistance"),
                    ("disruption_resistance", "Disruption Resistance"),
                )
            ),
        ),
        PackageDefinition(
            "defense_retaliation",
            "Retaliation",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("retaliation_damage_percent", "Retaliation Damage (+%)"),
                    ("acid_retaliation_damage", "Acid Retaliation"),
                    ("fire_retaliation_damage", "Fire Retaliation"),
                    ("physical_retaliation_damage", "Physical Retaliation"),
                    (
                        "attack_speed_slow_retaliation",
                        "Reduced Attack Speed Retaliation",
                    ),
                    (
                        "movement_speed_slow_retaliation",
                        "Reduced Movement Speed Retaliation",
                    ),
                    ("retaliation_effect_choice", "Retaliation Effect Chance"),
                )
            ),
        ),
    ),
)


CORE_TAB = TabDefinition(
    "core",
    "Core",
    (
        PackageDefinition(
            "core_speed",
            "Speed",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("cooldown_reduction", "Cooldown Reduction"),
                    ("movement_speed", "Movement Speed"),
                    ("attack_speed", "Attack Speed"),
                    ("casting_speed", "Casting Speed"),
                    ("total_speed", "Total Speed"),
                )
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "core_health",
            "Health",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("health", "Health (Flat)"),
                    ("health_percent", "Health (+%)"),
                    ("health_regeneration", "Health Regeneration (Flat)"),
                    (
                        "health_regeneration_percent",
                        "Health Regeneration (+%)",
                    ),
                    (
                        "attack_damage_converted_to_health",
                        "Attack Damage Converted to Health",
                    ),
                    ("healing_effects_increase", "Healing Effects Increase"),
                )
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "core_attributes",
            "Attributes",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("physique", "Physique (Flat)"),
                    ("physique_percent", "Physique (+%)"),
                    ("cunning", "Cunning (Flat)"),
                    ("cunning_percent", "Cunning (+%)"),
                    ("spirit", "Spirit (Flat)"),
                    ("spirit_percent", "Spirit (+%)"),
                )
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "core_energy",
            "Energy",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("energy", "Energy (Flat)"),
                    ("energy_percent", "Energy (+%)"),
                    ("energy_regeneration", "Energy Regeneration (Flat)"),
                    (
                        "energy_regeneration_percent",
                        "Energy Regeneration (+%)",
                    ),
                    (
                        "energy_absorbed_from_enemy_spells",
                        "Energy Absorbed from Enemy Spells",
                    ),
                    ("skill_energy_cost_reduction", "Skill Energy Cost Reduction"),
                )
            ),
        ),
        PackageDefinition(
            "core_requirements",
            "Attribute Requirements",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    (
                        "all_attribute_requirements_reduction",
                        "All Attribute Requirements Reduction",
                    ),
                    (
                        "melee_weapon_cunning_requirement_reduction",
                        "Melee Weapon Cunning Requirement Reduction",
                    ),
                    (
                        "ranged_weapon_cunning_requirement_reduction",
                        "Ranged Weapon Cunning Requirement Reduction",
                    ),
                )
            ),
        ),
    ),
)


ADVANCED_TAB = TabDefinition(
    "advanced",
    "Advanced",
    (
        PackageDefinition(
            "advanced_niche",
            "Rare / Niche",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("confusion", "Chance to Confuse Target"),
                    ("racial_damage_bonus", "Damage to Creature Type"),
                    ("enemy_health_reduction_percent", "Enemy Health Reduction"),
                    ("energy_burn_percent", "Energy Burn (+%)"),
                    ("light_radius_percent", "Increased Light Radius"),
                    ("stun_duration", "Stun Duration"),
                )
            ),
            default_expanded=True,
        ),
    ),
)


PETS_TAB = TabDefinition(
    "pets",
    "Pets",
    (
        PackageDefinition(
            "pets_damage",
            "Damage",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("pet_total_damage_percent", "Pet Total Damage (+%)"),
                    (
                        "pet_offensive_ability_percent",
                        "Pet Offensive Ability (+%)",
                    ),
                    ("pet_critical_damage", "Pet Critical Damage"),
                    ("pet_attack_speed", "Pet Attack Speed"),
                )
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "pets_defenses",
            "Defenses",
            tuple(
                stat(stat_id, label)
                for stat_id, label in (
                    ("pet_health_percent", "Pet Health (+%)"),
                    (
                        "pet_defensive_ability_percent",
                        "Pet Defensive Ability (+%)",
                    ),
                    ("pet_elemental_resistance", "Pet Elemental Resistance"),
                    ("pet_aether_resistance", "Pet Aether Resistance"),
                    ("pet_bleeding_resistance", "Pet Bleeding Resistance"),
                    ("pet_chaos_resistance", "Pet Chaos Resistance"),
                    ("pet_physical_resistance", "Pet Physical Resistance"),
                    ("pet_pierce_resistance", "Pet Pierce Resistance"),
                    ("pet_vitality_resistance", "Pet Vitality Resistance"),
                    ("pet_stun_resistance", "Pet Stun Resistance"),
                    ("pet_freeze_resistance", "Pet Freeze Resistance"),
                    ("pet_slow_resistance", "Pet Slow Resistance"),
                )
            ),
            default_expanded=True,
        ),
        PackageDefinition(
            "pets_utility",
            "Utility / Other",
            (stat("pet_total_speed", "Pet Total Speed"),),
            default_expanded=True,
        ),
    ),
)


PROFILE_TABS = (DAMAGE_TAB, DEFENSES_TAB, CORE_TAB, ADVANCED_TAB, PETS_TAB)


def all_stat_definitions() -> tuple[StatDefinition, ...]:
    return tuple(
        stat_definition
        for tab in PROFILE_TABS
        for package in tab.packages
        for stat_definition in package.stats
    )


def validate_catalog() -> None:
    tab_ids = [tab.tab_id for tab in PROFILE_TABS]
    package_ids = [package.package_id for tab in PROFILE_TABS for package in tab.packages]
    stat_ids = [definition.stat_id for definition in all_stat_definitions()]
    if len(tab_ids) != len(set(tab_ids)):
        raise ValueError("profile tab IDs must be unique")
    if len(package_ids) != len(set(package_ids)):
        raise ValueError("profile package IDs must be unique")
    if len(stat_ids) != len(set(stat_ids)):
        raise ValueError("profile stat IDs must be unique")


validate_catalog()
