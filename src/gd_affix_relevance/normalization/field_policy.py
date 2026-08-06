"""Coarse field policy applied before stat-specific normalization rules."""

from __future__ import annotations

from gd_affix_relevance.domain import RawDbrField, RawDbrRecord

# These fields remain available on RawDbrRecord, but they cannot contribute a
# semantic stat category or a category fingerprint. Level is retained for the
# separate tier-consistency audit.
SEMANTIC_FINGERPRINT_IGNORED_FIELDS = frozenset(
    {
        "templateName",
        "Class",
        "FileDescription",
        "characterBaseAttackSpeedTag",
        "itemClassification",
        "levelRequirement",
        "lootRandomizerCost",
        "lootRandomizerJitter",
        "lootRandomizerName",
        "marketAdjustmentPercent",
    }
)


def fields_for_semantic_analysis(record: RawDbrRecord) -> tuple[RawDbrField, ...]:
    """Return non-metadata fields without deciding whether values are active.

    Zero/default detection and composite grouping belong to stat-specific
    normalization rules. In particular, record references and expressions must
    survive this coarse pass.
    """

    return tuple(
        field
        for field in record.fields
        if field.key not in SEMANTIC_FINGERPRINT_IGNORED_FIELDS
    )
