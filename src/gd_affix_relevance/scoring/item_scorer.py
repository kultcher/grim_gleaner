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
    minimum_score_for_grade,
    score_semantic_stat_ids,
    semantic_stat_id,
)
from gd_affix_relevance.slots import equipment_class_slot_id

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


def item_semantic_stat_ids(
    variant: ItemVariantDefinition,
) -> tuple[str, ...]:
    return tuple(
        sorted({semantic_stat_id(property_) for property_ in variant.properties})
    )


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
                    item_semantic_stat_ids(candidate[0]), profile
                ).rank_key,
                candidate[0].record_path,
            ),
        )
        semantic_ids = item_semantic_stat_ids(variant)
        score = score_semantic_stat_ids(semantic_ids, profile)
        if score.effective_score < minimum_score:
            continue
        selected_skills = set(profile.skill_weights)
        has_selected_modifier = any(
            modifier.modified_skill_reference in selected_skills
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
