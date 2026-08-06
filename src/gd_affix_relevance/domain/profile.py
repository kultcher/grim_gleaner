"""Build-profile state shared by the scorer and profile editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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

    def __post_init__(self) -> None:
        supplied_weights = dict(self.weights)
        self.weights.clear()
        for stat_id, weight in supplied_weights.items():
            self.set_weight(stat_id, weight)

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weights": dict(sorted(self.weights.items())),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> BuildProfile:
        name = payload.get("name", "New Build Profile")
        raw_weights = payload.get("weights", {})
        if not isinstance(name, str):
            raise TypeError("profile name must be a string")
        if not isinstance(raw_weights, dict):
            raise TypeError("profile weights must be an object")

        profile = cls(name=name)
        for stat_id, weight in raw_weights.items():
            if not isinstance(stat_id, str):
                raise TypeError("profile stat IDs must be strings")
            profile.set_weight(stat_id, weight)
        return profile
