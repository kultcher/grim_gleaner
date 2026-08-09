"""Basic fixed-property scoring for unique equipment recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from gd_affix_relevance.catalog import (
    ItemCatalog,
    ItemDefinition,
    ItemVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring.catalog_scorer import (
    RelevanceScore,
    canonical_skill_reference,
    minimum_score_for_grade,
    profile_weight_for_semantic_id,
    score_semantic_stat_ids,
    semantic_stat_id,
    property_enabled_for_profile,
)
from gd_affix_relevance.slots import (
    WEAPON_SLOTS,
    equipment_class_slot_id,
    slot_ids_from_item_applicability,
)

TYPE_MONSTER_INFREQUENT = "monster_infrequent"
TYPE_EPIC = "epic"
TYPE_LEGENDARY = "legendary"
UNIQUE_ITEM_TYPES = (
    TYPE_MONSTER_INFREQUENT,
    TYPE_EPIC,
    TYPE_LEGENDARY,
)
UNIQUE_TYPE_LABELS = {
    TYPE_MONSTER_INFREQUENT: "Monster Infrequent",
    TYPE_EPIC: "Epic",
    TYPE_LEGENDARY: "Legendary",
}
ADDON_COMPONENT = "component"
ADDON_AUGMENT = "augment"
ADDON_TYPES = (ADDON_COMPONENT, ADDON_AUGMENT)
ADDON_TYPE_LABELS = {
    ADDON_COMPONENT: "Component",
    ADDON_AUGMENT: "Augment",
}


@dataclass(frozen=True, slots=True)
class RankedItemVariant:
    item: ItemDefinition
    variant: ItemVariantDefinition
    item_type: str
    semantic_stat_ids: tuple[str, ...]
    score: RelevanceScore
    has_selected_skill_modifier: bool

    @property
    def marker(self) -> str:
        if self.has_selected_skill_modifier:
            return f"[{self.score.grade}†{self.score.matched_count}]"
        return self.score.marker


@dataclass(frozen=True, slots=True)
class RankedAddonVariant:
    item: ItemDefinition
    variant: ItemVariantDefinition
    addon_type: str
    semantic_stat_ids: tuple[str, ...]
    score: RelevanceScore
    has_selected_skill_modifier: bool

    @property
    def marker(self) -> str:
        if self.has_selected_skill_modifier:
            return f"[{self.score.grade}†{self.score.matched_count}]"
        return self.score.marker


def item_semantic_stat_ids(
    variant: ItemVariantDefinition,
    profile: BuildProfile | None = None,
) -> tuple[str, ...]:
    stat_ids = {
        semantic_stat_id(property_)
        for property_ in variant.properties
        if property_.property_id != "base_attack_speed"
        and property_enabled_for_profile(property_, profile)
    }
    if (
        equipment_class_slot_id(variant.item_class) in WEAPON_SLOTS
        and not any(
            stat_id.startswith("base_weapon_damage_as_") for stat_id in stat_ids
        )
    ):
        stat_ids.add("base_weapon_damage_as_physical")
    return tuple(sorted(stat_ids))


def unique_item_type(variant: ItemVariantDefinition) -> str:
    if variant.category == "monster_infrequent":
        return TYPE_MONSTER_INFREQUENT
    rarity = variant.rarity.casefold()
    if rarity == "epic":
        return TYPE_EPIC
    if rarity == "legendary":
        return TYPE_LEGENDARY
    return ""


def rank_unique_items_for_slot(
    catalog: ItemCatalog,
    profile: BuildProfile,
    *,
    slot_id: str,
    enabled_types: frozenset[str] = frozenset(UNIQUE_ITEM_TYPES),
    minimum_grade: str = "B",
) -> tuple[RankedItemVariant, ...]:
    """Return unique items meeting the requested grade for one atomic slot."""

    minimum_score = minimum_score_for_grade(minimum_grade)
    ranked: list[RankedItemVariant] = []
    for item in catalog.equipment:
        candidates = tuple(
            (variant, unique_item_type(variant))
            for variant in item.variants
            if equipment_class_slot_id(variant.item_class) == slot_id
            and unique_item_type(variant) in enabled_types
        )
        if not candidates:
            continue
        variant, item_type = max(
            candidates,
            key=lambda candidate: (
                candidate[0].level_requirement,
                candidate[0].item_level,
                score_semantic_stat_ids(
                    item_semantic_stat_ids(candidate[0], profile), profile
                ).rank_key,
                candidate[0].record_path,
            ),
        )
        semantic_ids = item_semantic_stat_ids(variant, profile)
        score = score_semantic_stat_ids(semantic_ids, profile)
        if score.effective_score < minimum_score:
            continue
        selected_skills = {
            canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
        }
        has_selected_modifier = any(
            canonical_skill_reference(modifier.modified_skill_reference)
            in selected_skills
            for modifier in variant.skill_modifiers
        )
        ranked.append(
            RankedItemVariant(
                item=item,
                variant=variant,
                item_type=item_type,
                semantic_stat_ids=semantic_ids,
                score=score,
                has_selected_skill_modifier=has_selected_modifier,
            )
        )
    ranked.sort(
        key=lambda match: (
            -match.score.effective_score,
            -match.score.relevance_points,
            -match.score.weighted_match,
            -match.score.matched_count,
            -match.score.coverage_ratio,
            -match.variant.level_requirement,
            match.item.display_name.casefold(),
            match.variant.record_path,
        )
    )
    return tuple(ranked)


def rank_addons_for_slot(
    catalog: ItemCatalog,
    profile: BuildProfile,
    *,
    slot_id: str,
    addon_type: str,
    limit: int = 5,
    resistance_cap_weights: dict[str, int] | None = None,
) -> tuple[RankedAddonVariant, ...]:
    """Return the highest-scoring components or augments for one slot."""

    if addon_type not in ADDON_TYPES:
        raise ValueError(f"unknown add-on type: {addon_type!r}")
    family = (
        catalog.components
        if addon_type == ADDON_COMPONENT
        else catalog.augments
    )
    selected_skills = {
        canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
    }

    def addon_weight(stat_id: str) -> int:
        if resistance_cap_weights is not None and stat_id in resistance_cap_weights:
            return resistance_cap_weights[stat_id] * 2
        return profile_weight_for_semantic_id(profile, stat_id)

    ranked: list[RankedAddonVariant] = []
    for item in family:
        candidates = tuple(
            variant
            for variant in item.variants
            if slot_id
            in slot_ids_from_item_applicability(variant.applicable_slots)
        )
        if not candidates:
            continue
        variant = max(
            candidates,
            key=lambda candidate: (
                candidate.level_requirement,
                candidate.item_level,
                score_semantic_stat_ids(
                    item_semantic_stat_ids(candidate, profile),
                    profile,
                    weight_for=addon_weight,
                ).rank_key,
                candidate.record_path,
            ),
        )
        semantic_ids = item_semantic_stat_ids(variant, profile)
        score = score_semantic_stat_ids(
            semantic_ids, profile, weight_for=addon_weight
        )
        if score.weighted_match == 0:
            continue
        has_selected_modifier = any(
            canonical_skill_reference(modifier.modified_skill_reference)
            in selected_skills
            for modifier in variant.skill_modifiers
        )
        ranked.append(
            RankedAddonVariant(
                item=item,
                variant=variant,
                addon_type=addon_type,
                semantic_stat_ids=semantic_ids,
                score=score,
                has_selected_skill_modifier=has_selected_modifier,
            )
        )
    ranked.sort(
        key=lambda match: (
            -match.score.effective_score,
            -match.score.relevance_points,
            -match.score.weighted_match,
            -match.score.matched_count,
            -match.score.coverage_ratio,
            -match.variant.level_requirement,
            match.item.display_name.casefold(),
            match.variant.record_path,
        )
    )
    return tuple(ranked[:limit])
