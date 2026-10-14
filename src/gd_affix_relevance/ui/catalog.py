"""Compatibility exports for profile stat presentation definitions."""

from dataclasses import replace

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.scoring.catalog_scorer import semantic_stat_ids
from gd_affix_relevance.scoring.item_scorer import item_semantic_stat_ids
from gd_affix_relevance.stats.registry import (
    ADVANCED_TAB,
    CORE_TAB,
    DAMAGE_TAB,
    DEFENSES_TAB,
    PETS_TAB,
    PROFILE_TABS,
    RESISTANCE_STATS,
    PackageDefinition,
    StatDefinition,
    TabDefinition,
    all_stat_definitions,
    base_weapon_damage_stat,
    chance_damage_stat,
    conversion_stat,
    stat,
    validate_catalog,
)


def gear_catalog_stat_ids(
    affixes: AffixCatalog, items: ItemCatalog
) -> frozenset[str]:
    """Find available stat categories across all gear levels and sources.

    Inspect intrinsic gear/affix properties, matching the relevance scorer's
    scope. Granted skills, set bonuses and consumables are not gear matches.
    Keep the registry intact so old profiles remain readable after a rebuild.
    """

    available: set[str] = set()
    for affix in affixes.affixes:
        for variant in (*affix.variants, *affix.tiers):
            for property_ in variant.properties:
                available.update(semantic_stat_ids(property_))
    for family in (items.equipment, items.components, items.augments, items.relics):
        for item in family:
            for variant in item.variants:
                available.update(item_semantic_stat_ids(variant))
                for property_ in variant.properties:
                    available.update(semantic_stat_ids(property_))
    return frozenset(available)


def profile_tabs_for_stat_ids(
    available_stat_ids: frozenset[str] | None,
) -> tuple[TabDefinition, ...]:
    """Hide unavailable rows and empty packages/tabs in the profile editor."""

    if available_stat_ids is None:
        return PROFILE_TABS
    tabs: list[TabDefinition] = []
    for tab in PROFILE_TABS:
        packages = tuple(
            replace(package, stats=stats)
            for package in tab.packages
            if (stats := tuple(
                definition
                for definition in package.stats
                if definition.stat_id in available_stat_ids
            ))
        )
        if packages:
            tabs.append(replace(tab, packages=packages))
    return tuple(tabs)


__all__ = [
    "ADVANCED_TAB",
    "CORE_TAB",
    "DAMAGE_TAB",
    "DEFENSES_TAB",
    "PETS_TAB",
    "PROFILE_TABS",
    "RESISTANCE_STATS",
    "PackageDefinition",
    "StatDefinition",
    "TabDefinition",
    "all_stat_definitions",
    "base_weapon_damage_stat",
    "chance_damage_stat",
    "conversion_stat",
    "stat",
    "validate_catalog",
    "gear_catalog_stat_ids",
    "profile_tabs_for_stat_ids",
]
