"""Canonical damage types used by conversion profile filters."""

from __future__ import annotations


CONVERSION_DAMAGE_TYPES = (
    "physical",
    "pierce",
    "fire",
    "cold",
    "lightning",
    "acid",
    "vitality",
    "aether",
    "chaos",
    "elemental",
)

SPECIFIC_SKILL_CONVERSION_SOURCE = "specific_skill"
CONVERSION_SOURCE_TYPES = (
    *CONVERSION_DAMAGE_TYPES,
    SPECIFIC_SKILL_CONVERSION_SOURCE,
)

CONVERSION_DAMAGE_LABELS = {
    "physical": "Physical",
    "pierce": "Pierce",
    "fire": "Fire",
    "cold": "Cold",
    "lightning": "Lightning",
    "acid": "Acid",
    "vitality": "Vitality",
    "aether": "Aether",
    "chaos": "Chaos",
    "elemental": "Elemental",
    SPECIFIC_SKILL_CONVERSION_SOURCE: "Specific Skill",
}

_DAMAGE_TYPE_ALIASES = {
    "life": "vitality",
    "poison": "acid",
}


def canonical_damage_type(value: str) -> str:
    normalized = value.strip().casefold()
    return _DAMAGE_TYPE_ALIASES.get(normalized, normalized)


def conversion_sources_for(destination: str) -> tuple[str, ...]:
    canonical_destination = canonical_damage_type(destination)
    damage_sources = tuple(
        damage_type
        for damage_type in CONVERSION_DAMAGE_TYPES
        if damage_type != canonical_destination
    )
    return (*damage_sources, SPECIFIC_SKILL_CONVERSION_SOURCE)
