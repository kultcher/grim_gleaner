"""Match Grim Dawn tooltip lines to Grim Gleaner stats.

The game renders item stats from format templates in ``tags_ui.txt``, e.g.::

    DefenseBleeding={%.0f0}% {^E}Bleeding Resistance

and the detailed (Ctrl) view appends the roll range with
``DamageRangeFormatAppend= {^H}[{%t0}-{%t1}]``. A tooltip line and its
template reduce to the same *key* once colour codes, numbers and signs are
normalised (``"#% bleeding resistance"``), so a line is identified by key and
the key's template tag is mapped to a stat ID by :data:`TAG_STATS`.

The same normalisation is implemented in native/gg_hook (stat_core.cpp);
``tests/test_live_scoring.py`` checks the two agree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.stats import stat_is_registered

# All patterns are ASCII-only so stat_core.cpp can mirror them exactly.
_A = re.ASCII
_COLOR_CODE = re.compile(r"\{\^.\}|\^[A-Za-z]", _A)
_PLACEHOLDER = re.compile(r"\{%[^}]*\}", _A)
_RANGE_SUFFIX = re.compile(
    r"\[ *([0-9]+(?:\.[0-9]+)?) *(?:- *([0-9]+(?:\.[0-9]+)?) *)?\] *$", _A
)
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?", _A)
_SIGNED_HASH = re.compile(r"[+-] *#", _A)
_HASH_RANGE = re.compile(r"# *- *#", _A)
_DURATION_SUFFIX = re.compile(r" (?:over|for) # seconds?$", _A)
_SPACES = re.compile(r"\s+", _A)
_ASCII_LOWER = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
)


def strip_color_codes(text: str) -> str:
    return _COLOR_CODE.sub("", text)


def _finish_key(text: str) -> str:
    """Shared tail of the normalisation. Mirrored step by step in
    stat_core.cpp (FinishKey)."""

    text = text.replace("(", "").replace(")", "")
    text = _SPACES.sub(" ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _HASH_RANGE.sub("#", text)
    text = _SIGNED_HASH.sub("#", text)
    text = text.translate(_ASCII_LOWER)
    return _DURATION_SUFFIX.sub("", text)


def line_key(text: str) -> str:
    """Normalise rendered tooltip text: numbers become ``#``, signs drop."""

    plain = strip_color_codes(text)
    plain = _RANGE_SUFFIX.sub("", plain)
    return _finish_key(_NUMBER.sub("#", plain))


def template_key(template: str) -> str:
    """Normalise a ``tags_ui`` template the same way as rendered text."""

    plain = strip_color_codes(template)
    plain = _PLACEHOLDER.sub("#", plain)
    return _finish_key(_NUMBER.sub("#", plain))


@dataclass(frozen=True, slots=True)
class ParsedLine:
    text: str
    key: str
    values: tuple[float, ...]
    roll_range: tuple[float, float] | None

    @property
    def single_value(self) -> float | None:
        return self.values[0] if len(self.values) == 1 else None


def parse_line(text: str) -> ParsedLine:
    plain = strip_color_codes(text).strip()
    roll_range = None
    match = _RANGE_SUFFIX.search(plain)
    if match:
        low = float(match.group(1))
        high = float(match.group(2)) if match.group(2) is not None else low
        roll_range = (min(low, high), max(low, high))
        plain = plain[: match.start()].rstrip()
    values = tuple(float(number) for number in _NUMBER.findall(plain))
    return ParsedLine(text, line_key(text), values, roll_range)


# --- template tag -> stat ID -------------------------------------------------

_DAMAGE_TYPES = {
    "Physical": "physical",
    "Pierce": "pierce",
    "Cold": "cold",
    "Fire": "fire",
    "Poison": "acid",
    "Lightning": "lightning",
    "Life": "vitality",
    "Chaos": "chaos",
    "Aether": "aether",
    "Elemental": "elemental",
}
_DOT_TYPES = {
    "Physical": "internal_trauma",
    "Bleeding": "bleeding",
    "Cold": "frostburn",
    "Fire": "burn",
    "Poison": "poison",
    "Lightning": "electrocute",
    "Life": "vitality_decay",
}
_RESISTANCES = {
    "Physical": "physical_resistance",
    "Pierce": "pierce_resistance",
    "ElementalResistance": "elemental_resistance",
    "Cold": "cold_resistance",
    "Fire": "fire_resistance",
    "Aether": "aether_resistance",
    "Chaos": "chaos_resistance",
    "Poison": "poison_acid_resistance",
    "Lightning": "lightning_resistance",
    "Life": "vitality_resistance",
    "Bleeding": "bleeding_resistance",
    "Stun": "stun_resistance",
    "StunNegative": "stun_resistance",
    "Trap": "entrapment_resistance",
    "TrapNegative": "entrapment_resistance",
    "Freeze": "freeze_resistance",
    "FreezeNegative": "freeze_resistance",
    "Petrify": "petrify_resistance",
    "PetrifyNegative": "petrify_resistance",
    "Convert": "mind_control_resistance",
    "Disruption": "disruption_resistance",
}
_MAX_RESISTANCES = {
    "Physical": "maximum_physical_resistance",
    "Pierce": "maximum_pierce_resistance",
    "Cold": "maximum_cold_resistance",
    "Fire": "maximum_fire_resistance",
    "Aether": "maximum_aether_resistance",
    "Chaos": "maximum_chaos_resistance",
    "Poison": "maximum_poison_acid_resistance",
    "Lightning": "maximum_lightning_resistance",
    "Life": "maximum_vitality_resistance",
    "Bleeding": "maximum_bleeding_resistance",
    "All": "maximum_all_resistance",
}
_RETALIATION = {
    "Physical": "physical_retaliation_damage",
    "Pierce": "pierce_retaliation_damage",
    "Cold": "cold_retaliation_damage",
    "Fire": "fire_retaliation_damage",
    "Poison": "acid_retaliation_damage",
    "Lightning": "lightning_retaliation_damage",
    "Life": "vitality_retaliation_damage",
    "Chaos": "chaos_retaliation_damage",
    "Aether": "aether_retaliation_damage",
    "Elemental": "elemental_retaliation_damage",
}


def _build_tag_stats() -> dict[str, str]:
    tags: dict[str, str] = {
        "tagCharAttribute01": "cunning",
        "tagCharAttribute02": "physique",
        "tagCharAttribute03": "spirit",
        "tagCharAttribute04": "health",
        "tagCharAttribute05": "energy",
        "tagCharAttribute01Modifier": "cunning_percent",
        "tagCharAttribute02Modifier": "physique_percent",
        "tagCharAttribute03Modifier": "spirit_percent",
        "tagCharAttribute04Modifier": "health_percent",
        "tagCharAttribute05Modifier": "energy_percent",
        "tagCharLifeRegen": "health_regeneration",
        "tagCharLifeRegenModifier": "health_regeneration_percent",
        "tagCharManaRegen": "energy_regeneration",
        "tagCharManaRegenModifier": "energy_regeneration_percent",
        "tagCharRunSpeed": "movement_speed",
        "tagCharRunSpeedModifier": "movement_speed",
        "tagCharSpellCastSpeed": "casting_speed",
        "tagCharSpellCastSpeedModifier": "casting_speed",
        "tagCharAttackSpeed": "attack_speed",
        "tagCharAttackSpeedModifier": "attack_speed",
        "tagCharTotalSpeedModifier": "total_speed",
        "tagCharOffensiveAbility": "offensive_ability",
        "tagCharOffensiveAbilityModifier": "offensive_ability_percent",
        "tagCharDefensiveAbility": "defensive_ability",
        "tagCharDefensiveAbilityModifier": "defensive_ability_percent",
        "tagCharDodgePercent": "dodge_chance",
        "tagCharDeflectProjectiles": "projectile_deflection",
        "tagCharEnergyAbsorptionPercent": "energy_absorbed_from_enemy_spells",
        "tagCharLightRadius": "light_radius_percent",
        "tagCharPercentHealIncreaseModifier": "healing_effects_increase",
        "tagCharItemGlobalReduction": "all_attribute_requirements_reduction",
        "SkillCooldownReduction": "cooldown_reduction",
        "SkillCooldownReductionModifier": "cooldown_reduction",
        "SkillManaCostReduction": "skill_energy_cost_reduction",
        "SkillManaCostReductionModifier": "skill_energy_cost_reduction",
        "SkillEnhancement": "all_skills_bonus",
        "DamageLifeLeech": "attack_damage_converted_to_health",
        "DamageModifierStun": "stun_duration",
        "DamageModifierPierceRatio": "armor_piercing_percent",
        "DamageBasePierceRatio": "armor_piercing_percent",
        "DefenseAbsorptionProtection": "armor",
        "DefenseAbsorptionProtectionPlus": "armor",
        "DefenseAbsorptionProtectionBonus": "armor",
        "DefenseProtectionModifier": "armor_percent",
        "DefenseAbsorptionModifier": "armor_absorption_percent",
        "DefenseBlockAmountModifier": "shield_block_amount_percent",
        "tagDamageModifierTotalDamage": "total_damage_percent",
        "tagDamageModifierCritDamage": "critical_damage",
        "tagTotalSpeedResistance": "slow_resistance",
        "DamagePercentCurrentLife": "enemy_health_reduction_percent",
        "DamageManaDrain": "energy_burn_percent",
        "tagRetaliationModifierTotalDamage": "retaliation_damage_percent",
    }
    for tag, damage in _DAMAGE_TYPES.items():
        tags[f"DamageModifier{tag}"] = f"{damage}_damage_percent"
        tags[f"Damage{tag}"] = f"flat_{damage}_damage"
        tags[f"Retaliation{tag}"] = _RETALIATION[tag]
    tags["DamageBonusPhysical"] = "flat_physical_damage"
    for tag, dot in _DOT_TYPES.items():
        tags[f"DamageDurationModifier{tag}"] = f"{dot}_damage_percent"
    for tag, stat_id in _RESISTANCES.items():
        tags[f"Defense{tag}"] = stat_id
    for tag, stat_id in _MAX_RESISTANCES.items():
        tags[f"Defense{tag}MaxResist"] = stat_id
    return tags


#: Template tag (without a trailing ``R`` range variant) -> stat ID.
TAG_STATS: dict[str, str] = _build_tag_stats()

_DAMAGE_NAMES = {
    "physical": "physical",
    "pierce": "pierce",
    "piercing": "pierce",
    "cold": "cold",
    "fire": "fire",
    "acid": "acid",
    "lightning": "lightning",
    "vitality": "vitality",
    "chaos": "chaos",
    "aether": "aether",
    "elemental": "elemental",
}
_DOT_NAMES = {
    "internal trauma": "internal_trauma",
    "internal trauma damage": "internal_trauma",
    "bleeding damage": "bleeding",
    "frostburn damage": "frostburn",
    "burn damage": "burn",
    "poison damage": "poison",
    "electrocute damage": "electrocute",
    "vitality decay": "vitality_decay",
    "vitality decay damage": "vitality_decay",
}


def composed_keys(race_names: dict[str, str] | None = None) -> dict[str, str]:
    """Keys for lines the game composes from several fragments (no single
    template): flat DoT, chance-of damage, conversions and racial bonuses."""

    keys: dict[str, str] = {}
    for name, dot in _DOT_NAMES.items():
        keys[f"# {name}"] = f"flat_{dot}_damage"
        keys[f"#% chance of # {name}"] = f"chance_flat_{dot}_damage"
    for name, damage in _DAMAGE_NAMES.items():
        keys[f"#% chance of # {name} damage"] = f"chance_flat_{damage}_damage"
        for source in _DAMAGE_NAMES:
            if source != name:
                keys[f"#% {source} damage converted to {name} damage"] = (
                    f"damage_conversion_to_{damage}"
                )
    for display, suffix in (race_names or {}).items():
        lowered = display.casefold()
        keys[f"#% damage to {lowered}"] = f"racial_damage_bonus_vs_{suffix}"
        keys[f"#% less damage from {lowered}"] = f"racial_defense_bonus_vs_{suffix}"
    return keys


def _base_tag(tag: str) -> str:
    return tag[:-1] if tag.endswith("R") and tag[:-1] in TAG_STATS else tag


@dataclass
class StatLineIndex:
    """Tooltip-line key -> stat ID, built from the game's own templates."""

    stats_by_key: dict[str, str]
    tags_by_key: dict[str, str]
    ambiguous_keys: frozenset[str] = frozenset()

    @classmethod
    def from_templates(cls, templates: dict[str, str]) -> StatLineIndex:
        stats_by_key: dict[str, str] = {}
        tags_by_key: dict[str, str] = {}
        ambiguous: set[str] = set()
        for tag, template in templates.items():
            stat_id = TAG_STATS.get(_base_tag(tag))
            if stat_id is None or not stat_is_registered(stat_id):
                continue
            key = template_key(template)
            if "#" not in key:
                continue
            existing = stats_by_key.get(key)
            if existing is not None and existing != stat_id:
                ambiguous.add(key)
                continue
            stats_by_key[key] = stat_id
            tags_by_key.setdefault(key, tag)
        from gd_affix_relevance.stats.registry import RACES

        race_names = {display: suffix for _, suffix, display in RACES}
        for key, stat_id in composed_keys(race_names).items():
            if stat_is_registered(stat_id):
                stats_by_key.setdefault(key, stat_id)
        return cls(stats_by_key, tags_by_key, frozenset(ambiguous))

    @classmethod
    def from_tags_file(cls, path: Path) -> StatLineIndex:
        return cls.from_templates(read_templates(path))

    def stat_for(self, text: str) -> str | None:
        return self.stats_by_key.get(line_key(text))


def read_templates(path: Path) -> dict[str, str]:
    """Read ``Tag=Template`` lines that contain format placeholders."""

    templates: dict[str, str] = {}
    for raw in Path(path).read_text(encoding="utf-8-sig", errors="replace").splitlines():
        tag, separator, template = raw.partition("=")
        if separator and "{%" in template and tag and not tag.startswith("#"):
            templates[tag.strip()] = template
    return templates


PET_HEADING_WORDS = frozenset({"pet", "pets"})
_WORD = re.compile(r"[a-z]+", re.ASCII)


def is_pet_heading(key: str) -> bool:
    """A number-free line naming pets ("Bonus to All Pets:") starts the pet
    section. Mirrored in stat_core.cpp."""

    return "#" not in key and any(word in PET_HEADING_WORDS for word in _WORD.findall(key))


def match_tooltip_stats(
    index: StatLineIndex,
    lines: list[tuple[int, str]],
) -> list[tuple[ParsedLine, str | None]]:
    """Pair each tooltip line with its stat, switching to pet stats after a
    "Bonus to All Pets" style heading (until the text class changes)."""

    results: list[tuple[ParsedLine, str | None]] = []
    pet_class: int | None = None
    for text_class, text in lines:
        parsed = parse_line(text)
        stat_id = index.stats_by_key.get(parsed.key)
        if stat_id is None and is_pet_heading(parsed.key):
            pet_class = -1  # the next class seen is the pet section
            results.append((parsed, None))
            continue
        if pet_class == -1:
            pet_class = text_class
        elif pet_class is not None and text_class != pet_class:
            pet_class = None
        if stat_id is not None and pet_class is not None:
            pet_stat = f"pet_{stat_id}"
            stat_id = pet_stat if stat_is_registered(pet_stat) else None
        results.append((parsed, stat_id))
    return results
