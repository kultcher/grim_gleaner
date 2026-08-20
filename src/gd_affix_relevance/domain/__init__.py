"""Domain objects shared by import, normalization, and scoring layers."""

from gd_affix_relevance.domain.dbr import (
    DbrParseWarning,
    RawDbrField,
    RawDbrRecord,
)
from gd_affix_relevance.domain.localization import LocalizationEntry
from gd_affix_relevance.domain.locale import (
    ENGLISH_LOCALE,
    RUSSIAN_LOCALE,
    SUPPORTED_LOCALES,
    LocaleSpec,
    locale_for_code,
)
from gd_affix_relevance.domain.profile import (
    MAX_STAT_WEIGHT,
    MIN_STAT_WEIGHT,
    WEIGHT_LABELS,
    BuildProfile,
)

__all__ = [
    "DbrParseWarning",
    "RawDbrField",
    "RawDbrRecord",
    "LocalizationEntry",
    "LocaleSpec",
    "ENGLISH_LOCALE",
    "RUSSIAN_LOCALE",
    "SUPPORTED_LOCALES",
    "locale_for_code",
    "BuildProfile",
    "MAX_STAT_WEIGHT",
    "MIN_STAT_WEIGHT",
    "WEIGHT_LABELS",
]
