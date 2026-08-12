"""Explainable category-presence scoring for compiled affix catalogs."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.conversions import canonical_damage_type
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.slots import slot_ids_from_legacy_label
from gd_affix_relevance.stats import (
    RACE_STAT_SUFFIXES,
    stat_is_registered,
    stat_is_scoreable,
)


@dataclass(frozen=True, slots=True)
class RelevanceScore:
    grade: str
    weighted_match: int
    relevance_points: float
    base_effective_score: float
    profile_adjustment: float
    effective_score: float
    matched_count: int
    total_category_count: int
    coverage_ratio: float
    matched_stat_ids: tuple[str, ...]

    @property
    def marker_body(self) -> str:
        count = "" if self.grade in {"S+", "S++"} else str(self.matched_count)
        return f"{self.grade}{count}"

    @property
    def marker(self) -> str:
        return f"[{self.marker_body}]"

    @property
    def rank_key(self) -> tuple[float, ...]:
        return (
            self.effective_score,
            self.relevance_points,
            float(self.weighted_match),
            float(self.matched_count),
            self.coverage_ratio,
        )


GRADE_THRESHOLDS = {
    "S++": 24.0,
    "S+": 18.0,
    "S": 14.0,
    "A": 10.0,
    "B": 6.0,
    "C": 3.0,
    "D": 1.0,
}

# An even mix of the four nonzero ratings under the quadratic point curve.
REFERENCE_PROFILE_INTENSITY = 1.875
MIN_PROFILE_ADJUSTMENT = 0.80
MAX_PROFILE_ADJUSTMENT = 1.25
FULL_ADJUSTMENT_WEIGHT_COUNT = 8


@dataclass(frozen=True, slots=True)
class RankedAffixVariant:
    affix: AffixDefinition
    variant: AffixVariantDefinition
    semantic_stat_ids: tuple[str, ...]
    score: RelevanceScore
    has_level_variations: bool = False

    @property
    def marker(self) -> str:
        granted_flag = "*" if any(
            property_.property_id == "granted_item_skill"
            for property_ in self.variant.properties
        ) else ""
        return f"[{self.score.marker_body}{granted_flag}]"


def semantic_stat_id(property_: AffixProperty) -> str:
    """Translate a compiled property into the ID used by build profiles."""

    if property_.property_key.endswith(":base_weapon") and (
        property_.property_id.startswith("flat_")
        and property_.property_id.endswith("_damage")
    ):
        damage_type = property_.property_id.removeprefix("flat_").removesuffix(
            "_damage"
        )
        return f"base_weapon_damage_as_{damage_type}"
    if property_.property_id == "damage_conversion":
        destination = property_.attributes.get("destination_damage_type", "unknown")
        destination = canonical_damage_type(destination)
        return f"damage_conversion_to_{destination}"
    if property_.property_id in {"skill_bonus", "granted_item_skill"}:
        reference = property_.attributes.get("skill_reference", property_.property_key)
        return f"{property_.property_id}:{reference}"
    if property_.property_id == "mastery_bonus":
        reference = property_.attributes.get("mastery_reference", "")
        mastery_id = next(
            (
                part
                for part in reference.lower().replace("\\", "/").split("/")
                if part.startswith("playerclass")
            ),
            reference,
        )
        return f"mastery_bonus:{mastery_id}"
    if property_.property_id in {"pet_bonus", "unmapped"}:
        return f"{property_.property_id}:{property_.property_key}"
    return property_.property_id


def semantic_stat_ids(property_: AffixProperty) -> tuple[str, ...]:
    """Expand one compiled property into profile-weightable semantic IDs."""

    if property_.property_id in {
        "racial_damage_bonus",
        "racial_defense_bonus",
    }:
        references = property_.attributes.get("race_reference", "")
        return tuple(
            f"{property_.property_id}_vs_{suffix}"
            for reference in references.split(";")
            if (suffix := RACE_STAT_SUFFIXES.get(reference.strip().casefold()))
        )
    if property_.property_id == "pet_damage_conversion":
        destination = property_.attributes.get(
            "destination_damage_type", "unknown"
        )
        destination = canonical_damage_type(destination)
        return (f"pet_damage_conversion_to_{destination}",)
    return (semantic_stat_id(property_),)


def variant_semantic_stat_ids(
    variant: AffixVariantDefinition,
    profile: BuildProfile | None = None,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                stat_id
                for property_ in variant.properties
                if property_.property_id != "granted_item_skill"
                and property_enabled_for_profile(property_, profile)
                for stat_id in semantic_stat_ids(property_)
                if stat_is_scoreable(stat_id)
            }
        )
    )


def unregistered_catalog_stat_ids(bundle: object) -> tuple[str, ...]:
    """Return score-relevant compiled IDs missing from the central registry."""

    unknown: set[str] = set()
    for affix in bundle.affixes.affixes:  # type: ignore[attr-defined]
        for variant in affix.variants:
            for property_ in variant.properties:
                if property_.property_id == "granted_item_skill":
                    continue
                unknown.update(
                    stat_id
                    for stat_id in semantic_stat_ids(property_)
                    if not stat_is_registered(stat_id)
                )
    for item in bundle.items.all_items():  # type: ignore[attr-defined]
        for variant in item.variants:
            for property_ in variant.properties:
                if property_.property_id in {
                    "base_attack_speed",
                    "granted_item_skill",
                }:
                    continue
                unknown.update(
                    stat_id
                    for stat_id in semantic_stat_ids(property_)
                    if not stat_is_registered(stat_id)
                )
    return tuple(sorted(unknown))


def score_affix_variant(
    variant: AffixVariantDefinition,
    profile: BuildProfile,
) -> RelevanceScore:
    """Score semantic-category presence without considering numeric roll size."""

    return score_semantic_stat_ids(
        variant_semantic_stat_ids(variant, profile), profile
    )


def affix_common_stat_ids(affix: AffixDefinition) -> tuple[str, ...]:
    """Return categories present on every compiled variant of an affix tag."""

    variant_sets = [set(variant_semantic_stat_ids(variant)) for variant in affix.variants]
    if not variant_sets:
        return ()
    common = set.intersection(*variant_sets)
    return tuple(sorted(common))


def score_affix_common_properties(
    affix: AffixDefinition,
    profile: BuildProfile,
) -> RelevanceScore:
    """Conservatively score only properties shared by all variants of a tag."""

    variant_sets = [
        set(variant_semantic_stat_ids(variant, profile))
        for variant in affix.variants
    ]
    common = tuple(sorted(set.intersection(*variant_sets))) if variant_sets else ()
    return score_semantic_stat_ids(common, profile)


def score_semantic_stat_ids(
    stat_ids: tuple[str, ...],
    profile: BuildProfile,
    *,
    weight_for: Callable[[str], int] | None = None,
) -> RelevanceScore:
    stat_ids = tuple(
        stat_id for stat_id in stat_ids if stat_is_scoreable(stat_id)
    )
    resolve_weight = weight_for or (
        lambda stat_id: profile_weight_for_semantic_id(profile, stat_id)
    )
    matched = tuple(
        sorted(
            (
                stat_id
                for stat_id in stat_ids
                if resolve_weight(stat_id) > 0
            ),
            key=lambda stat_id: (
                -resolve_weight(stat_id),
                stat_id,
            ),
        )
    )
    weighted_match = sum(
        resolve_weight(stat_id) for stat_id in matched
    )
    matched_count = len(matched)
    total_category_count = len(stat_ids)
    coverage_ratio = (
        matched_count / total_category_count if total_category_count else 0.0
    )
    relevance_points = sum(
        _points_for_weight(resolve_weight(stat_id))
        for stat_id in matched
    )
    coverage_multiplier = 0.70 + 0.30 * coverage_ratio
    base_effective_score = relevance_points * coverage_multiplier
    profile_adjustment = profile_score_adjustment(profile)
    effective_score = base_effective_score * profile_adjustment
    return RelevanceScore(
        grade=_grade_for_effective_score(effective_score),
        weighted_match=weighted_match,
        relevance_points=relevance_points,
        base_effective_score=base_effective_score,
        profile_adjustment=profile_adjustment,
        effective_score=effective_score,
        matched_count=matched_count,
        total_category_count=total_category_count,
        coverage_ratio=coverage_ratio,
        matched_stat_ids=matched,
    )


def rank_affix_catalog(
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    limit: int | None = 20,
) -> tuple[RankedAffixVariant, ...]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    ranked: list[RankedAffixVariant] = []
    for affix in catalog.affixes:
        for variant in affix.variants:
            stat_ids = variant_semantic_stat_ids(variant, profile)
            ranked.append(
                RankedAffixVariant(
                    affix=affix,
                    variant=variant,
                    semantic_stat_ids=stat_ids,
                    score=score_affix_variant(variant, profile),
                )
            )
    ranked.sort(
        key=lambda match: (
            *(-value for value in match.score.rank_key),
            match.affix.display_name.casefold(),
            match.variant.gear_slot.casefold(),
            match.affix.affix_id,
        )
    )
    return tuple(ranked if limit is None else ranked[:limit])


def rank_affixes_for_slot(
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    slot_id: str,
    kind: str,
    limit: int = 5,
) -> tuple[RankedAffixVariant, ...]:
    """Rank one highest-level layout per affix for an atomic slot."""

    if limit < 1:
        raise ValueError("limit must be at least 1")
    ranked: list[RankedAffixVariant] = []
    for affix in catalog.affixes:
        if affix.kind != kind:
            continue
        variants = tuple(
            variant
            for variant in affix.variants
            if slot_id in _variant_slot_ids(variant)
        )
        if not variants:
            continue
        layouts = {
            variant_semantic_stat_ids(variant, profile)
            for variant in variants
        }
        selected = max(
            variants,
            key=lambda variant: (
                max(variant.level_requirements, default=0),
                score_affix_variant(variant, profile).rank_key,
                len(variant.properties),
                variant.representative_source,
            ),
        )
        semantic_ids = variant_semantic_stat_ids(selected, profile)
        score = score_semantic_stat_ids(semantic_ids, profile)
        if score.weighted_match == 0:
            continue
        ranked.append(
            RankedAffixVariant(
                affix=affix,
                variant=selected,
                semantic_stat_ids=semantic_ids,
                score=score,
                has_level_variations=len(layouts) > 1,
            )
        )
    ranked.sort(
        key=lambda match: (
            *(-value for value in match.score.rank_key),
            -max(match.variant.level_requirements, default=0),
            match.affix.display_name.casefold(),
            match.affix.localization_tag.casefold(),
        )
    )
    return tuple(ranked[:limit])


def format_ranked_catalog_report(
    matches: tuple[RankedAffixVariant, ...],
    *,
    profile: BuildProfile,
    candidate_pool_size: int,
    labels: dict[str, str] | None = None,
) -> str:
    label_lookup = labels or {}
    lines = [
        f"Grim Gleaner ranked affixes - {profile.name}",
        f"Candidate variants graded: {candidate_pool_size}",
        f"Top variants shown: {len(matches)}",
    ]
    for index, match in enumerate(matches, start=1):
        score = match.score
        matched = "; ".join(
            f"{label_lookup.get(stat_id, _humanize(stat_id))} "
            f"({profile_weight_for_semantic_id(profile, stat_id)})"
            for stat_id in score.matched_stat_ids
        )
        lines.extend(
            [
                "",
                f"{index}. {match.marker} {match.affix.display_name}",
                f"   Type: {match.affix.kind.title()}",
                f"   Gear slot: {match.variant.gear_slot}",
                f"   Weighted match: {score.weighted_match}",
                f"   Effective score: {score.effective_score:.2f}",
                f"   Base score: {score.base_effective_score:.2f}",
                f"   Profile adjustment: x{score.profile_adjustment:.3f}",
                "   Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})",
                f"   Matched: {matched or 'None'}",
                "   All stats:",
            ]
        )
        lines.extend(f"   - {line}" for line in match.variant.stat_lines)
        lines.extend(
            [
                f"   Localization: {match.affix.localization_tag}",
                f"   Representative: {match.variant.representative_source}",
            ]
        )
    return "\n".join(lines) + "\n"


def profile_weight_for_semantic_id(
    profile: BuildProfile, semantic_stat_id: str
) -> int:
    """Read ordinary stat weights or exact selected-skill weights."""

    for prefix in ("skill_bonus:", "skill_modifier:"):
        if semantic_stat_id.startswith(prefix):
            reference = semantic_stat_id[len(prefix) :]
            canonical = canonical_skill_reference(reference)
            return max(
                (
                    weight
                    for skill_id, weight in profile.skill_weights.items()
                    if canonical_skill_reference(skill_id) == canonical
                ),
                default=0,
            )
    mastery_prefix = "mastery_bonus:"
    if semantic_stat_id.startswith(mastery_prefix):
        mastery_id = semantic_stat_id[len(mastery_prefix) :]
        return 4 if mastery_id in profile.masteries else 0
    return profile.weight_for(semantic_stat_id)


def canonical_skill_reference(reference: str) -> str:
    """Collapse a named skill's runtime ``_buff`` record onto its base DBR."""

    normalized = reference.strip().lower().replace("\\", "/")
    if normalized.endswith("_buff.dbr"):
        return normalized.removesuffix("_buff.dbr") + ".dbr"
    return normalized


def property_enabled_for_profile(
    property_: AffixProperty, profile: BuildProfile | None
) -> bool:
    if profile is None or property_.property_id != "damage_conversion":
        return True
    source = canonical_damage_type(
        property_.attributes.get("source_damage_type", "")
    )
    destination = canonical_damage_type(
        property_.attributes.get("destination_damage_type", "")
    )
    if not source or not destination:
        return True
    return profile.conversion_source_enabled(destination, source)


def minimum_score_for_grade(grade: str) -> float:
    """Return the effective-score floor for a display-grade cutoff."""

    normalized = grade.upper()
    if normalized not in GRADE_THRESHOLDS:
        raise ValueError("minimum grade must be S++, S+, S, A, B, C, or D")
    return GRADE_THRESHOLDS[normalized]


def _points_for_weight(weight: int) -> float:
    return (weight * weight) / 4


def profile_score_adjustment(profile: BuildProfile) -> float:
    """Return a bounded correction for different nonzero rating styles.

    Zeroes are omitted so a deliberately sparse profile is not inflated merely
    for rating fewer things. Small nonzero samples blend back toward 1.0 because
    their average intensity is a weak signal of the user's general style.
    """

    weights = [
        *(
            weight
            for stat_id, weight in profile.weights.items()
            if weight > 0 and stat_is_scoreable(stat_id)
        ),
        *(weight for weight in profile.skill_weights.values() if weight > 0),
    ]
    if not weights:
        return 1.0
    intensity = sum(_points_for_weight(weight) for weight in weights) / len(weights)
    raw_adjustment = math.sqrt(REFERENCE_PROFILE_INTENSITY / intensity)
    bounded_adjustment = min(
        MAX_PROFILE_ADJUSTMENT,
        max(MIN_PROFILE_ADJUSTMENT, raw_adjustment),
    )
    confidence = min(len(weights) / FULL_ADJUSTMENT_WEIGHT_COUNT, 1.0)
    return 1.0 + (bounded_adjustment - 1.0) * confidence


def _grade_for_effective_score(effective_score: float) -> str:
    for grade, threshold in GRADE_THRESHOLDS.items():
        if effective_score >= threshold:
            return grade
    return "F"


def _humanize(stat_id: str) -> str:
    return stat_id.replace("_", " ").title()


def _variant_slot_ids(variant: AffixVariantDefinition) -> tuple[str, ...]:
    return variant.applicable_slots or slot_ids_from_legacy_label(
        variant.gear_slot
    )
