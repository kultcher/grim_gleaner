"""Rules that convert raw DBR fields into semantic properties."""

from gd_affix_relevance.normalization.field_policy import (
    SEMANTIC_FINGERPRINT_IGNORED_FIELDS,
    fields_for_semantic_analysis,
)

__all__ = [
    "SEMANTIC_FINGERPRINT_IGNORED_FIELDS",
    "fields_for_semantic_analysis",
]

