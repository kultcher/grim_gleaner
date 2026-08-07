"""Explainable affix-relevance scoring."""

from gd_affix_relevance.scoring.catalog_scorer import (
    RankedAffixVariant,
    RelevanceScore,
    affix_common_stat_ids,
    format_ranked_catalog_report,
    profile_weight_for_semantic_id,
    rank_affix_catalog,
    rank_affixes_for_slot,
    score_affix_common_properties,
    score_affix_variant,
    score_semantic_stat_ids,
    semantic_stat_id,
    variant_semantic_stat_ids,
)

__all__ = [
    "RankedAffixVariant",
    "RelevanceScore",
    "affix_common_stat_ids",
    "format_ranked_catalog_report",
    "profile_weight_for_semantic_id",
    "rank_affix_catalog",
    "rank_affixes_for_slot",
    "score_affix_common_properties",
    "score_affix_variant",
    "score_semantic_stat_ids",
    "semantic_stat_id",
    "variant_semantic_stat_ids",
]
