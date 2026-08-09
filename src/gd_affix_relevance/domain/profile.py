"""Build-profile state shared by the scorer and profile editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gd_affix_relevance.conversions import (
    CONVERSION_DAMAGE_TYPES,
    CONVERSION_SOURCE_TYPES,
    canonical_damage_type,
)

MIN_STAT_WEIGHT = 0
MAX_STAT_WEIGHT = 4
WEIGHT_LABELS = (
    "Ignored",
    "Incidental",
    "Useful",
    "Emphasized",
    "Core",
)


@dataclass(slots=True)
class BuildProfile:
    """A named set of semantic-stat weights.

    Package expansion is intentionally absent: it is presentation state and has
    no effect on affix relevance.
    """

    name: str = "New Build Profile"
    weights: dict[str, int] = field(default_factory=dict)
    masteries: tuple[str, str] = ("", "")
    skill_weights: dict[str, int] = field(default_factory=dict)
    excluded_conversion_sources: dict[str, set[str]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        supplied_weights = dict(self.weights)
        self.weights.clear()
        for stat_id, weight in supplied_weights.items():
            self.set_weight(stat_id, weight)
        supplied_masteries = tuple(self.masteries)
        if len(supplied_masteries) != 2:
            raise ValueError("profile must contain exactly two mastery slots")
        self.masteries = ("", "")
        for slot, mastery_id in enumerate(supplied_masteries):
            self.set_mastery(slot, mastery_id)
        supplied_skill_weights = dict(self.skill_weights)
        self.skill_weights.clear()
        for skill_id, weight in supplied_skill_weights.items():
            self.set_skill_weight(skill_id, weight)
        supplied_exclusions = {
            destination: set(sources)
            for destination, sources in self.excluded_conversion_sources.items()
        }
        self.excluded_conversion_sources.clear()
        for destination, sources in supplied_exclusions.items():
            for source in sources:
                self.set_conversion_source_enabled(destination, source, False)

    def weight_for(self, stat_id: str) -> int:
        return self.weights.get(stat_id, MIN_STAT_WEIGHT)

    def set_weight(self, stat_id: str, weight: int) -> None:
        if not stat_id.strip():
            raise ValueError("stat_id must not be blank")
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise TypeError("weight must be an integer")
        if not MIN_STAT_WEIGHT <= weight <= MAX_STAT_WEIGHT:
            raise ValueError(
                f"weight must be between {MIN_STAT_WEIGHT} and {MAX_STAT_WEIGHT}"
            )
        if weight == MIN_STAT_WEIGHT:
            self.weights.pop(stat_id, None)
        else:
            self.weights[stat_id] = weight

    def nonzero_count(self, stat_ids: tuple[str, ...]) -> int:
        return sum(self.weight_for(stat_id) > 0 for stat_id in stat_ids)

    def set_mastery(self, slot: int, mastery_id: str) -> None:
        if slot not in (0, 1):
            raise IndexError("mastery slot must be 0 or 1")
        if not isinstance(mastery_id, str):
            raise TypeError("mastery ID must be a string")
        normalized = mastery_id.strip()
        other = self.masteries[1 - slot]
        if normalized and normalized == other:
            raise ValueError("the same mastery cannot occupy both slots")
        values = list(self.masteries)
        values[slot] = normalized
        self.masteries = (values[0], values[1])

    def skill_weight_for(self, skill_id: str) -> int:
        return self.skill_weights.get(skill_id, MIN_STAT_WEIGHT)

    def set_skill_weight(self, skill_id: str, weight: int) -> None:
        if not isinstance(skill_id, str):
            raise TypeError("skill_id must be a string")
        if not skill_id.strip():
            raise ValueError("skill_id must not be blank")
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise TypeError("weight must be an integer")
        if not MIN_STAT_WEIGHT <= weight <= MAX_STAT_WEIGHT:
            raise ValueError(
                f"weight must be between {MIN_STAT_WEIGHT} and {MAX_STAT_WEIGHT}"
            )
        self.skill_weights[skill_id] = weight

    def remove_skill(self, skill_id: str) -> None:
        self.skill_weights.pop(skill_id, None)

    def clear_skills(self) -> None:
        self.skill_weights.clear()

    def conversion_source_enabled(self, destination: str, source: str) -> bool:
        canonical_destination = self._validate_conversion_destination(
            destination
        )
        canonical_source = self._validate_conversion_source(source)
        return canonical_source not in self.excluded_conversion_sources.get(
            canonical_destination, set()
        )

    def set_conversion_source_enabled(
        self, destination: str, source: str, enabled: bool
    ) -> None:
        canonical_destination = self._validate_conversion_destination(
            destination
        )
        canonical_source = self._validate_conversion_source(source)
        if canonical_destination == canonical_source:
            raise ValueError("conversion source and destination must differ")
        if not isinstance(enabled, bool):
            raise TypeError("conversion source state must be a boolean")
        excluded = self.excluded_conversion_sources.setdefault(
            canonical_destination, set()
        )
        if enabled:
            excluded.discard(canonical_source)
        else:
            excluded.add(canonical_source)
        if not excluded:
            self.excluded_conversion_sources.pop(canonical_destination, None)

    @staticmethod
    def _canonical_conversion_type(damage_type: str) -> str:
        if not isinstance(damage_type, str):
            raise TypeError("conversion damage type must be a string")
        return canonical_damage_type(damage_type).replace(" ", "_")

    @classmethod
    def _validate_conversion_destination(cls, damage_type: str) -> str:
        canonical = cls._canonical_conversion_type(damage_type)
        if canonical not in CONVERSION_DAMAGE_TYPES:
            raise ValueError(
                f"unknown conversion destination: {damage_type!r}"
            )
        return canonical

    @classmethod
    def _validate_conversion_source(cls, damage_type: str) -> str:
        canonical = cls._canonical_conversion_type(damage_type)
        if canonical not in CONVERSION_SOURCE_TYPES:
            raise ValueError(f"unknown conversion source: {damage_type!r}")
        return canonical

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "masteries": list(self.masteries),
            "skill_weights": dict(sorted(self.skill_weights.items())),
            "weights": dict(sorted(self.weights.items())),
            "excluded_conversion_sources": {
                destination: sorted(sources)
                for destination, sources in sorted(
                    self.excluded_conversion_sources.items()
                )
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BuildProfile:
        name = payload.get("name", "New Build Profile")
        raw_weights = payload.get("weights", {})
        raw_masteries = payload.get("masteries", ["", ""])
        raw_skill_weights = payload.get("skill_weights", {})
        raw_conversion_exclusions = payload.get(
            "excluded_conversion_sources", {}
        )
        if not isinstance(name, str):
            raise TypeError("profile name must be a string")
        if not isinstance(raw_weights, dict):
            raise TypeError("profile weights must be an object")
        if not isinstance(raw_masteries, list) or len(raw_masteries) != 2:
            raise TypeError("profile masteries must be a two-item array")
        if not all(isinstance(mastery, str) for mastery in raw_masteries):
            raise TypeError("profile mastery IDs must be strings")
        if not isinstance(raw_skill_weights, dict):
            raise TypeError("profile skill weights must be an object")
        if not isinstance(raw_conversion_exclusions, dict):
            raise TypeError("profile conversion exclusions must be an object")

        profile = cls(name=name, masteries=tuple(raw_masteries))
        for stat_id, weight in raw_weights.items():
            if not isinstance(stat_id, str):
                raise TypeError("profile stat IDs must be strings")
            profile.set_weight(stat_id, weight)
        for skill_id, weight in raw_skill_weights.items():
            if not isinstance(skill_id, str):
                raise TypeError("profile skill IDs must be strings")
            profile.set_skill_weight(skill_id, weight)
        for destination, sources in raw_conversion_exclusions.items():
            if not isinstance(destination, str):
                raise TypeError("conversion destinations must be strings")
            if not isinstance(sources, list) or not all(
                isinstance(source, str) for source in sources
            ):
                raise TypeError("conversion exclusions must be string arrays")
            for source in sources:
                profile.set_conversion_source_enabled(
                    destination, source, False
                )
        return profile
