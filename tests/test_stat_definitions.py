"""Keep the field mappings, stat registry and UI labels in step.

Adding a stat touches the field-mapping table, the registry and the two label
files; these checks fail when one of those steps is missed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gd_affix_relevance.stats import field_mappings
from gd_affix_relevance.stats.registry import (
    NON_SCOREABLE_STAT_IDS,
    POLARITIES,
    registered_stat_definitions,
    stat_is_registered,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_ROOT = PROJECT_ROOT / "resources" / "i18n"


def _stat_labels(locale_code: str) -> dict[str, str]:
    payload = json.loads(
        (I18N_ROOT / f"{locale_code}.json").read_text(encoding="utf-8")
    )
    return {
        key.removeprefix("stat."): value
        for key, value in payload.items()
        if key.startswith("stat.")
    }


def _user_facing_stats() -> list[str]:
    return [
        definition.stat_id
        for definition in registered_stat_definitions()
        if definition.stat_id not in NON_SCOREABLE_STAT_IDS
    ]


@pytest.mark.parametrize("locale_code", ["en", "ru"])
def test_every_registered_stat_has_a_label(locale_code: str) -> None:
    labels = _stat_labels(locale_code)
    missing = [stat_id for stat_id in _user_facing_stats() if stat_id not in labels]
    assert missing == []


@pytest.mark.parametrize("locale_code", ["en", "ru"])
def test_label_files_do_not_reference_unknown_stats(locale_code: str) -> None:
    unknown = [
        stat_id
        for stat_id in _stat_labels(locale_code)
        if not stat_is_registered(stat_id)
    ]
    assert unknown == []


def test_english_labels_match_the_registry() -> None:
    """The registry label is the English fallback; en.json must not drift."""

    labels = _stat_labels("en")
    drift = [
        (definition.stat_id, definition.label, labels[definition.stat_id])
        for definition in registered_stat_definitions()
        if definition.stat_id in labels
        and labels[definition.stat_id] != definition.label
    ]
    assert drift == []


def test_every_statically_mapped_field_produces_a_registered_stat() -> None:
    mapped = {
        *(rule[0] for rule in field_mappings.CHARACTER_RULES.values()),
        *(rule[0] for rule in field_mappings.DEFENSIVE_RULES.values()),
        *(rule[0] for rule in field_mappings.CONFIRMED_COMPOSITE_RULES.values()),
    }
    assert sorted(stat_id for stat_id in mapped if not stat_is_registered(stat_id)) == []


def test_pet_stats_derive_from_registered_player_stats() -> None:
    """Pet stats are compiled as ``pet_`` + the player stat ID."""

    orphaned = [
        definition.stat_id
        for definition in registered_stat_definitions()
        if definition.stat_id.startswith("pet_")
        and definition.stat_id not in NON_SCOREABLE_STAT_IDS
        and not stat_is_registered(definition.stat_id.removeprefix("pet_"))
    ]
    assert orphaned == []


def test_polarities_are_valid() -> None:
    assert {
        definition.polarity for definition in registered_stat_definitions()
    } <= set(POLARITIES)
