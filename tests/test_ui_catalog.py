from gd_affix_relevance.ui.catalog import (
    DAMAGE_TAB,
    PETS_TAB,
    PROFILE_TABS,
    all_stat_definitions,
)


def test_catalog_ids_are_unique_and_default_packages_exist() -> None:
    package_ids = [
        package.package_id for tab in PROFILE_TABS for package in tab.packages
    ]
    stat_ids = [definition.stat_id for definition in all_stat_definitions()]

    assert len(package_ids) == len(set(package_ids))
    assert len(stat_ids) == len(set(stat_ids))
    assert all(any(package.default_expanded for package in tab.packages) for tab in PROFILE_TABS)


def test_damage_base_owns_resistance_reduction_and_conversions_are_directional() -> None:
    base = DAMAGE_TAB.packages[0]
    base_ids = {definition.stat_id for definition in base.stats}
    conversion_ids = {
        definition.stat_id
        for package in DAMAGE_TAB.packages[1:]
        for definition in package.stats
        if definition.stat_id.startswith("damage_conversion_to_")
    }

    assert "target_resistance_reduction_flat" in base_ids
    assert "target_resistance_reduction_percent" in base_ids
    assert "damage_conversion" not in base_ids
    assert conversion_ids == {
        "damage_conversion_to_acid",
        "damage_conversion_to_aether",
        "damage_conversion_to_chaos",
        "damage_conversion_to_cold",
        "damage_conversion_to_elemental",
        "damage_conversion_to_fire",
        "damage_conversion_to_lightning",
        "damage_conversion_to_physical",
        "damage_conversion_to_pierce",
        "damage_conversion_to_vitality",
    }


def test_reachable_chance_damage_families_have_distinct_profile_rows() -> None:
    stats_by_package = {
        package.package_id: {definition.stat_id for definition in package.stats}
        for package in DAMAGE_TAB.packages
    }

    expected_by_package = {
        "damage_elemental": {"chance_flat_elemental_damage"},
        "damage_acid": {"chance_flat_poison_damage"},
        "damage_bleeding": {"chance_flat_bleeding_damage"},
        "damage_fire": {
            "chance_flat_fire_damage",
            "chance_flat_burn_damage",
        },
        "damage_chaos": {"chance_flat_chaos_damage"},
        "damage_cold": {"chance_flat_frostburn_damage"},
        "damage_lightning": {"chance_flat_electrocute_damage"},
        "damage_physical": {
            "chance_flat_physical_damage",
            "chance_flat_internal_trauma_damage",
        },
        "damage_pierce": {"chance_flat_pierce_damage"},
        "damage_vitality": {"chance_flat_vitality_decay_damage"},
    }
    for package_id, expected_ids in expected_by_package.items():
        assert expected_ids <= stats_by_package[package_id]

    electrocute = next(
        definition
        for definition in all_stat_definitions()
        if definition.stat_id == "chance_flat_electrocute_damage"
    )
    assert electrocute.label == "Chance to Deal Flat Electrocute Damage"
    assert "armor_piercing_percent" in stats_by_package["damage_pierce"]
    armor_piercing = next(
        definition
        for package in DAMAGE_TAB.packages
        for definition in package.stats
        if definition.stat_id == "armor_piercing_percent"
    )
    assert armor_piercing.label == "100% Armor Piercing"


def test_pet_tab_surfaces_every_current_affix_pet_stat_by_default() -> None:
    assert [package.label for package in PETS_TAB.packages] == [
        "Damage",
        "Defenses",
        "Damage Conversions",
        "Retaliation",
        "Utility / Other",
    ]
    assert all(package.default_expanded for package in PETS_TAB.packages)
    surfaced = {
        definition.stat_id
        for package in PETS_TAB.packages
        for definition in package.stats
    }
    assert {
        "pet_total_damage_percent",
        "pet_offensive_ability_percent",
        "pet_critical_damage",
        "pet_attack_speed",
        "pet_health_percent",
        "pet_defensive_ability_percent",
        "pet_elemental_resistance",
        "pet_aether_resistance",
        "pet_bleeding_resistance",
        "pet_chaos_resistance",
        "pet_physical_resistance",
        "pet_pierce_resistance",
        "pet_vitality_resistance",
        "pet_stun_resistance",
        "pet_freeze_resistance",
        "pet_slow_resistance",
        "pet_total_speed",
    } <= surfaced
    assert {
        f"pet_damage_conversion_to_{damage_type}"
        for damage_type in (
            "acid",
            "aether",
            "chaos",
            "cold",
            "elemental",
            "fire",
            "lightning",
            "physical",
            "pierce",
            "vitality",
        )
    } <= surfaced
