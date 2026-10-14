"""Basic fixed-property scoring for unique equipment recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from gd_affix_relevance.catalog import (
    ItemCatalog,
    ItemDefinition,
    ItemVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.level_bands import level_is_eligible
from gd_affix_relevance.scoring.catalog_scorer import (
    RelevanceScore,
    canonical_skill_reference,
    minimum_score_for_grade,
    profile_weight_for_semantic_id,
    score_semantic_stat_ids,
    semantic_stat_ids,
    property_enabled_for_profile,
)
from gd_affix_relevance.stats import stat_is_scoreable
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
    def is_awakened(self) -> bool:
        return is_awakened_variant(self.variant)

    @property
    def marker(self) -> str:
        flags = ""
        if self.variant.granted_skill_reference or self.variant.granted_skill_name:
            flags += "*"
        if self.has_selected_skill_modifier:
            flags += "!"
        return f"[{self.score.marker_body}{flags}]"


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
        flags = ""
        if self.variant.granted_skill_reference or self.variant.granted_skill_name:
            flags += "*"
        if self.has_selected_skill_modifier:
            flags += "!"
        return f"[{self.score.marker_body}{flags}]"


def item_semantic_stat_ids(
    variant: ItemVariantDefinition,
    profile: BuildProfile | None = None,
) -> tuple[str, ...]:
    stat_ids = {
        stat_id
        for property_ in variant.properties
        if property_.property_id not in {"base_attack_speed", "granted_item_skill"}
        and property_enabled_for_profile(property_, profile)
        for stat_id in semantic_stat_ids(property_)
        if stat_is_scoreable(stat_id)
    }
    if profile is not None:
        selected_skills = {
            canonical_skill_reference(skill_id)
            for skill_id in profile.skill_weights
        }
        stat_ids.update(
            f"skill_modifier:{modified_skill}"
            for modifier in variant.skill_modifiers
            if (
                modified_skill := canonical_skill_reference(
                    modifier.modified_skill_reference
                )
            )
            in selected_skills
        )
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


def item_variant_is_eligible(
    variant: ItemVariantDefinition, profile: BuildProfile
) -> bool:
    """Whether an item variant is usable within the profile's level band."""

    return level_is_eligible(variant.level_requirement, profile.level_band)


def is_awakened_variant(variant: ItemVariantDefinition) -> bool:
    """Whether a record is an Awakened Legendary crafted from an Epic.

    Awakened records share their Epic's name tag and level requirement, so the
    catalog groups them as variants of the same item. They are identified by
    their ``records/items/awakened/`` record path.
    """

    return "/awakened/" in variant.record_path.replace("\\", "/").casefold()


def _best_variant(
    candidates: tuple[ItemVariantDefinition, ...],
    profile: BuildProfile,
) -> ItemVariantDefinition:
    """Pick the highest-level eligible record, then the best-scoring one."""

    return max(
        candidates,
        key=lambda candidate: (
            candidate.level_requirement,
            candidate.item_level,
            score_semantic_stat_ids(
                item_semantic_stat_ids(candidate, profile), profile
            ).rank_key,
            candidate.record_path,
        ),
    )


def select_tag_variant(
    item: ItemDefinition,
    profile: BuildProfile,
) -> ItemVariantDefinition | None:
    """Choose the one record whose grade an item's shared name tag receives.

    Standard records are preferred so the in-game grade describes the item as
    it drops. With ``profile.prefer_awakened_grades`` the Awakened version is
    used whenever one is eligible at the selected level. An item that only
    exists in Awakened form is always graded by it.
    """

    all_candidates = tuple(
        variant for variant in item.variants if unique_item_type(variant)
    )
    if not all_candidates:
        return None
    eligible = tuple(
        variant
        for variant in all_candidates
        if item_variant_is_eligible(variant, profile)
    )
    if not eligible:
        lowest = min(variant.level_requirement for variant in all_candidates)
        eligible = tuple(
            variant
            for variant in all_candidates
            if variant.level_requirement == lowest
        )
    awakened = tuple(variant for variant in eligible if is_awakened_variant(variant))
    standard = tuple(
        variant for variant in eligible if not is_awakened_variant(variant)
    )
    if profile.prefer_awakened_grades and awakened:
        best_standard_level = max(
            (variant.level_requirement for variant in standard), default=-1
        )
        best_awakened = _best_variant(awakened, profile)
        if best_awakened.level_requirement >= best_standard_level:
            return best_awakened
    return _best_variant(standard or awakened, profile)


def rank_unique_items_for_slot(
    catalog: ItemCatalog,
    profile: BuildProfile,
    *,
    slot_id: str,
    enabled_types: frozenset[str] = frozenset(UNIQUE_ITEM_TYPES),
    minimum_grade: str = "B",
) -> tuple[RankedItemVariant, ...]:
    """Return unique items meeting the requested grade for one atomic slot.

    An Epic and the Awakened Legendary made from it are listed as separate
    entries because their stats, and therefore grades, usually differ.
    """

    minimum_score = minimum_score_for_grade(minimum_grade)
    selected_skills = {
        canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
    }
    ranked: list[RankedItemVariant] = []
    for item in catalog.equipment:
        candidates = tuple(
            variant
            for variant in item.variants
            if equipment_class_slot_id(variant.item_class) == slot_id
            and unique_item_type(variant) in enabled_types
            and item_variant_is_eligible(variant, profile)
        )
        if not candidates:
            continue
        families = (
            tuple(v for v in candidates if not is_awakened_variant(v)),
            tuple(v for v in candidates if is_awakened_variant(v)),
        )
        for family in families:
            if not family:
                continue
            variant = _best_variant(family, profile)
            semantic_ids = item_semantic_stat_ids(variant, profile)
            score = score_semantic_stat_ids(semantic_ids, profile)
            if score.effective_score < minimum_score:
                continue
            has_selected_modifier = any(
                canonical_skill_reference(modifier.modified_skill_reference)
                in selected_skills
                for modifier in variant.skill_modifiers
            )
            ranked.append(
                RankedItemVariant(
                    item=item,
                    variant=variant,
                    item_type=unique_item_type(variant),
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
            match.is_awakened,
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
            and item_variant_is_eligible(variant, profile)
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
