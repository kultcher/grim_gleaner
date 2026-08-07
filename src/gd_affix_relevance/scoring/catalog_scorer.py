"""Explainable category-presence scoring for compiled affix catalogs."""

from __future__ import annotations

from dataclasses import dataclass

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.slots import slot_ids_from_legacy_label


@dataclass(frozen=True, slots=True)
class RelevanceScore:
    grade: str
    weighted_match: int
    matched_count: int
    total_category_count: int
    coverage_ratio: float
    matched_stat_ids: tuple[str, ...]

    @property
    def marker(self) -> str:
        return f"[{self.grade}{self.matched_count}]"

    @property
    def rank_key(self) -> tuple[float, ...]:
        return (
            float(self.weighted_match),
            float(self.matched_count),
            self.coverage_ratio,
        )


@dataclass(frozen=True, slots=True)
class RankedAffixVariant:
    affix: AffixDefinition
    variant: AffixVariantDefinition
    semantic_stat_ids: tuple[str, ...]
    score: RelevanceScore
    has_level_variations: bool = False

    @property
    def marker(self) -> str:
        if self.has_level_variations:
            return f"[{self.score.grade}!{self.score.matched_count}]"
        return self.score.marker


def semantic_stat_id(property_: AffixProperty) -> str:
    """Translate a compiled property into the ID used by build profiles."""

    if property_.property_id == "damage_conversion":
        destination = property_.attributes.get("destination_damage_type", "unknown")
        destination = {"life": "vitality", "poison": "acid"}.get(
            destination.casefold(), destination.casefold()
        )
        return f"damage_conversion_to_{destination}"
    if property_.property_id in {"skill_bonus", "granted_item_skill"}:
        reference = property_.attributes.get("skill_reference", property_.property_key)
        return f"{property_.property_id}:{reference}"
    if property_.property_id in {"pet_bonus", "unmapped"}:
        return f"{property_.property_id}:{property_.property_key}"
    return property_.property_id


def variant_semantic_stat_ids(
    variant: AffixVariantDefinition,
) -> tuple[str, ...]:
    return tuple(sorted({semantic_stat_id(property_) for property_ in variant.properties}))


def score_affix_variant(
    variant: AffixVariantDefinition,
    profile: BuildProfile,
) -> RelevanceScore:
    """Score semantic-category presence without considering numeric roll size."""

    return score_semantic_stat_ids(variant_semantic_stat_ids(variant), profile)


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

    return score_semantic_stat_ids(affix_common_stat_ids(affix), profile)


def score_semantic_stat_ids(
    stat_ids: tuple[str, ...],
    profile: BuildProfile,
) -> RelevanceScore:
    matched = tuple(
        sorted(
            (
                stat_id
                for stat_id in stat_ids
                if profile_weight_for_semantic_id(profile, stat_id) > 0
            ),
            key=lambda stat_id: (
                -profile_weight_for_semantic_id(profile, stat_id),
                stat_id,
            ),
        )
    )
    weighted_match = sum(
        profile_weight_for_semantic_id(profile, stat_id) for stat_id in matched
    )
    matched_count = len(matched)
    total_category_count = len(stat_ids)
    coverage_ratio = (
        matched_count / total_category_count if total_category_count else 0.0
    )
    return RelevanceScore(
        grade=_grade_for_weighted_match(weighted_match),
        weighted_match=weighted_match,
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
            stat_ids = variant_semantic_stat_ids(variant)
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
            -match.score.weighted_match,
            -match.score.matched_count,
            -match.score.coverage_ratio,
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
        layouts = {variant_semantic_stat_ids(variant) for variant in variants}
        selected = max(
            variants,
            key=lambda variant: (
                max(variant.level_requirements, default=0),
                score_affix_variant(variant, profile).rank_key,
                len(variant.properties),
                variant.representative_source,
            ),
        )
        semantic_ids = variant_semantic_stat_ids(selected)
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
            -match.score.weighted_match,
            -match.score.matched_count,
            -match.score.coverage_ratio,
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

    prefix = "skill_bonus:"
    if semantic_stat_id.startswith(prefix):
        return profile.skill_weight_for(semantic_stat_id[len(prefix) :])
    return profile.weight_for(semantic_stat_id)


def _grade_for_weighted_match(weighted_match: int) -> str:
    if weighted_match >= 10:
        return "S"
    if weighted_match >= 7:
        return "A"
    if weighted_match >= 4:
        return "B"
    if weighted_match >= 2:
        return "C"
    if weighted_match >= 1:
        return "D"
    return "-"


def _humanize(stat_id: str) -> str:
    return stat_id.replace("_", " ").title()


def _variant_slot_ids(variant: AffixVariantDefinition) -> tuple[str, ...]:
    return variant.applicable_slots or slot_ids_from_legacy_label(
        variant.gear_slot
    )
