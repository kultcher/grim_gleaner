"""Discovery boundary for supported magic and rare building-block affixes."""

from __future__ import annotations

from typing import Literal

from gd_affix_relevance.domain import RawDbrRecord

AffixKind = Literal["prefix", "suffix"]

SUPPORTED_AFFIX_CLASSIFICATIONS = frozenset({"Magical", "Rare"})
EXCLUDED_AFFIX_DIRECTORIES = frozenset(
    {"prefixunique", "suffixunique", "prefixtables", "suffixtables"}
)


def supported_affix_kind(record: RawDbrRecord) -> AffixKind | None:
    """Return the affix kind when *record* is in the supported MVP scope."""

    if record.source_path.suffix.lower() != ".dbr":
        return None
    if record.first_value("Class") != "LootRandomizer":
        return None
    if record.first_value("itemClassification") not in SUPPORTED_AFFIX_CLASSIFICATIONS:
        return None
    if not record.first_value("lootRandomizerName"):
        return None

    path_parts = tuple(part.lower() for part in record.source_path.parts)
    if any(part in EXCLUDED_AFFIX_DIRECTORIES for part in path_parts):
        return None

    try:
        lootaffixes_index = path_parts.index("lootaffixes")
        kind = path_parts[lootaffixes_index + 1]
    except (ValueError, IndexError):
        return None

    if kind == "prefix":
        return "prefix"
    if kind == "suffix":
        return "suffix"
    return None

