"""Build the derived, level-banded scalar magnitude index."""

from __future__ import annotations

import json
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from gd_affix_relevance.level_bands import LEVEL_BANDS as SHARED_LEVEL_BANDS

LEVEL_BANDS: tuple[dict[str, Any], ...] = tuple(
    {
        "band_id": band.band_id,
        "minimum_level": band.minimum_level,
        "maximum_level": band.maximum_level,
    }
    for band in SHARED_LEVEL_BANDS
)

_COMPOUND_ROLE_MARKERS = (
    "chance",
    "duration",
    "seconds",
    "global_flag",
    "level_equation",
    "trigger_controller",
)
_PAIR_ROLES = (
    ("damage_min", "damage_max"),
    ("percent_min", "percent_max"),
)
_SINGLE_ROLES = (
    "damage_percent",
    "percent",
    "flat",
    "reduction_percent",
    "reduction_flat",
    "skill_level",
    "value",
    "damage_min",
    "percent_min",
)
_QUALIFIER_ROLES = frozenset(
    {
        "source_damage_type",
        "destination_damage_type",
        "skill_reference",
        "mastery_reference",
        "race_reference",
    }
)
_EXCLUDED_PROPERTY_IDS = frozenset(
    {
        "base_attack_speed",
        "granted_item_skill",
        "unmapped",
        "unresolved_composite",
    }
)


@dataclass(slots=True)
class _SelectedVariant:
    entity_type: str
    entity_id: str
    variant_id: str
    band_id: str
    gear_slot: str
    category: str
    rarity: str
    level_requirement: int
    band_variant_ids: tuple[str, ...]
    scalar_properties: list[dict[str, Any]]


def compile_magnitude_payload(
    affixes: list[dict[str, Any]],
    item_payloads: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Compile percentile metadata from concrete catalog tiers.

    The primary catalogs remain the source of truth. This payload is a
    rebuildable cache containing only simple one-dimensional measurements.
    """

    selected = [
        *_selected_affix_variants(affixes),
        *_selected_item_variants(item_payloads),
    ]
    cohorts: dict[str, list[float]] = defaultdict(list)
    for variant in selected:
        for scalar in variant.scalar_properties:
            cohort_id = _cohort_id(variant, scalar["identity"])
            scalar["cohort_id"] = cohort_id
            cohorts[cohort_id].append(scalar["scalar_value"])
    sorted_cohorts = {
        cohort_id: sorted(values) for cohort_id, values in cohorts.items()
    }

    entries: list[dict[str, Any]] = []
    for variant in selected:
        properties: list[dict[str, Any]] = []
        for scalar in variant.scalar_properties:
            cohort_id = scalar["cohort_id"]
            values = sorted_cohorts[cohort_id]
            properties.append(
                {
                    "property_id": scalar["property_id"],
                    "property_key": scalar["property_key"],
                    "scalar_value": scalar["scalar_value"],
                    "value_roles": list(scalar["value_roles"]),
                    "percentile": _midrank_percentile(
                        values, scalar["scalar_value"]
                    ),
                    "cohort_size": len(values),
                    "cohort_id": cohort_id,
                }
            )
        entries.append(
            {
                "entity_type": variant.entity_type,
                "entity_id": variant.entity_id,
                "variant_id": variant.variant_id,
                "band_id": variant.band_id,
                "gear_slot": variant.gear_slot,
                "category": variant.category,
                "rarity": variant.rarity,
                "level_requirement": variant.level_requirement,
                "band_variant_ids": list(variant.band_variant_ids),
                "properties": sorted(
                    properties,
                    key=lambda property_: (
                        property_["property_id"],
                        property_["property_key"],
                        property_["cohort_id"],
                    ),
                ),
            }
        )
    entries.sort(
        key=lambda entry: (
            entry["entity_type"],
            entry["entity_id"],
            entry["gear_slot"],
            entry["category"],
            entry["rarity"],
            entry["band_id"],
            entry["level_requirement"],
            entry["variant_id"],
        )
    )
    return {"bands": list(LEVEL_BANDS), "entries": entries}


def _selected_affix_variants(
    affixes: list[dict[str, Any]],
) -> list[_SelectedVariant]:
    selected: list[_SelectedVariant] = []
    for affix in affixes:
        by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for tier in affix.get("tiers", ()):
            by_slot[str(tier["gear_slot"])].append(tier)
        for gear_slot, tiers in sorted(by_slot.items()):
            for band in LEVEL_BANDS:
                chosen = _select_band_variants(tiers, band)
                if not chosen:
                    continue
                band_ids = _band_layout_variant_ids(tiers, band)
                for tier in chosen:
                    properties = list(tier.get("properties", ()))
                    selected.append(
                        _SelectedVariant(
                            entity_type="affix",
                            entity_id=str(affix["affix_id"]),
                            variant_id=str(tier["tier_id"]),
                            band_id=str(band["band_id"]),
                            gear_slot=gear_slot,
                            category=str(affix["kind"]),
                            rarity=str(affix.get("rarity", "")),
                            level_requirement=int(
                                tier.get("level_requirement", 0)
                            ),
                            band_variant_ids=band_ids,
                            scalar_properties=_scalar_properties(properties),
                        )
                    )
    return selected


def _selected_item_variants(
    item_payloads: dict[str, list[dict[str, Any]]],
) -> list[_SelectedVariant]:
    selected: list[_SelectedVariant] = []
    for family, items in sorted(item_payloads.items()):
        for item in items:
            groups: dict[tuple[str, str, str], list[dict[str, Any]]] = (
                defaultdict(list)
            )
            for variant in item.get("variants", ()):
                category = _item_magnitude_category(family, variant)
                key = (
                    category,
                    str(variant.get("rarity", "")),
                    str(variant.get("gear_slot", "")),
                )
                groups[key].append(variant)
            for (category, rarity, gear_slot), variants in sorted(
                groups.items()
            ):
                for band in LEVEL_BANDS:
                    chosen = _select_band_variants(variants, band)
                    if not chosen:
                        continue
                    band_ids = _band_layout_variant_ids(
                        variants, band, item=True
                    )
                    for variant in chosen:
                        variant_id = _item_variant_id(variant)
                        properties = list(variant.get("properties", ()))
                        selected.append(
                            _SelectedVariant(
                                entity_type="item",
                                entity_id=str(item["item_id"]),
                                variant_id=variant_id,
                                band_id=str(band["band_id"]),
                                gear_slot=gear_slot,
                                category=category,
                                rarity=rarity,
                                level_requirement=int(
                                    variant.get("level_requirement", 0)
                                ),
                                band_variant_ids=band_ids,
                                scalar_properties=_scalar_properties(
                                    properties
                                ),
                            )
                        )
    return selected


def _select_band_variants(
    variants: Iterable[dict[str, Any]], band: dict[str, Any]
) -> list[dict[str, Any]]:
    maximum = band["maximum_level"]
    eligible = [
        variant
        for variant in variants
        if maximum is None
        or _effective_level(variant.get("level_requirement", 0)) <= maximum
    ]
    if not eligible:
        return []
    selected_level = max(
        _effective_level(variant.get("level_requirement", 0))
        for variant in eligible
    )
    at_level = [
        variant
        for variant in eligible
        if _effective_level(variant.get("level_requirement", 0))
        == selected_level
    ]
    return _deduplicate_variants(at_level)


def _band_layout_variant_ids(
    variants: Iterable[dict[str, Any]],
    band: dict[str, Any],
    *,
    item: bool = False,
) -> tuple[str, ...]:
    ordered = sorted(
        variants,
        key=lambda variant: (
            _effective_level(variant.get("level_requirement", 0)),
            _variant_id(variant, item=item),
        ),
    )
    minimum = int(band["minimum_level"])
    maximum = band["maximum_level"]
    before = [
        variant
        for variant in ordered
        if _effective_level(variant.get("level_requirement", 0)) < minimum
    ]
    in_band = [
        variant
        for variant in ordered
        if minimum
        <= _effective_level(variant.get("level_requirement", 0))
        <= (maximum if maximum is not None else math.inf)
    ]
    prior: list[dict[str, Any]] = []
    if before:
        prior_level = _effective_level(before[-1].get("level_requirement", 0))
        prior = [
            variant
            for variant in before
            if _effective_level(variant.get("level_requirement", 0))
            == prior_level
        ]
    candidates = prior + in_band
    layouts: dict[str, str] = {}
    for variant in candidates:
        signature = _layout_signature(variant.get("properties", ()))
        layouts.setdefault(signature, _variant_id(variant, item=item))
    return tuple(layouts.values())


def _deduplicate_variants(
    variants: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for variant in sorted(
        variants, key=lambda value: _variant_id(value, item="tier_id" not in value)
    ):
        signature = json.dumps(
            variant.get("properties", ()), sort_keys=True, separators=(",", ":")
        )
        unique.setdefault(signature, variant)
    return list(unique.values())


def _scalar_properties(
    properties: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    scalar: list[dict[str, Any]] = []
    for property_ in properties:
        property_id = str(property_.get("property_id", ""))
        if property_id in _EXCLUDED_PROPERTY_IDS:
            continue
        attributes = {
            str(key): str(value)
            for key, value in (property_.get("attributes") or {}).items()
        }
        if any(
            marker in role
            for role in attributes
            for marker in _COMPOUND_ROLE_MARKERS
        ):
            continue
        measured = _scalar_value(attributes)
        if measured is None:
            continue
        value, roles = measured
        qualifiers = tuple(
            sorted(
                (role, attributes[role].casefold())
                for role in _QUALIFIER_ROLES
                if attributes.get(role)
            )
        )
        identity = json.dumps(
            (property_id, qualifiers), separators=(",", ":")
        )
        scalar.append(
            {
                "property_id": property_id,
                "property_key": str(property_.get("property_key", property_id)),
                "scalar_value": abs(value),
                "value_roles": roles,
                "identity": identity,
            }
        )
    return scalar


def _scalar_value(
    attributes: dict[str, str],
) -> tuple[float, tuple[str, ...]] | None:
    for low_role, high_role in _PAIR_ROLES:
        low = _number(attributes.get(low_role))
        high = _number(attributes.get(high_role))
        if low is None and high is None:
            continue
        if low is None:
            low = high
        if high is None:
            high = low
        assert low is not None and high is not None
        return (low + high) / 2.0, (low_role, high_role)
    for role in _SINGLE_ROLES:
        value = _number(attributes.get(role))
        if value is not None:
            return value, (role,)
    return None


def _number(value: str | None) -> float | None:
    try:
        parsed = float(value or "")
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _cohort_id(variant: _SelectedVariant, identity: str) -> str:
    return f"{variant.entity_type}|{variant.band_id}|{variant.gear_slot.casefold()}|{variant.category.casefold()}|{variant.rarity.casefold()}|{identity}"


def _midrank_percentile(values: list[float], value: float) -> float:
    if len(values) <= 1:
        return 0.5
    low = bisect_left(values, value)
    high = bisect_right(values, value)
    rank = (low + high - 1) / 2.0
    return round(rank / (len(values) - 1), 6)


def _layout_signature(properties: Iterable[dict[str, Any]]) -> str:
    layout: list[tuple[str, tuple[tuple[str, str], ...]]] = []
    for property_ in properties:
        attributes = property_.get("attributes") or {}
        qualifiers = tuple(
            sorted(
                (str(role), str(value).casefold())
                for role, value in attributes.items()
                if role in _QUALIFIER_ROLES
            )
        )
        layout.append((str(property_.get("property_id", "")), qualifiers))
    return json.dumps(sorted(layout), separators=(",", ":"))


def _item_magnitude_category(
    family: str, variant: dict[str, Any]
) -> str:
    category = str(variant.get("category", family.removesuffix("s")))
    rarity = str(variant.get("rarity", "")).casefold()
    if category == "monster_infrequent":
        return category
    if rarity in {"epic", "legendary"}:
        return rarity
    return category


def _item_variant_id(variant: dict[str, Any]) -> str:
    return f"{variant.get('source', '')}:{variant.get('record_path', '')}"


def _variant_id(variant: dict[str, Any], *, item: bool) -> str:
    return _item_variant_id(variant) if item else str(variant["tier_id"])


def _effective_level(value: Any) -> int:
    try:
        return max(1, int(float(value or 0)))
    except (TypeError, ValueError):
        return 1
