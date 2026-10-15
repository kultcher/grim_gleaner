"""Optional magnitude influence on relevance scores.

Relevance asks "does this item carry stats the build wants?". Magnitude
refines that with "is this stat strong compared with comparable items or
affixes at this level?" (docs/magnitude-backburner-reminder.md):

- Comparisons stay inside the catalog's magnitude cohorts (same stat, level
  band, exact slot/applicability, prefix vs suffix and Magic vs Rare for
  affixes, MI vs Epic vs Legendary for named items).
- Named items have the confirmed ``attributeScalePercent`` roles applied
  before percentiles are taken, so their values compare as the game shows
  them.
- Percentiles are midrank; cohorts smaller than ``MIN_COHORT`` are neutral.
- Each matched stat's relevance points are multiplied by
  ``1 + m * (2p - 1)`` with influence ``m`` (Off 0, Low 5%, Normal 10%,
  High 20%). Off reproduces the plain relevance score exactly.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from gd_affix_relevance.catalog.named_item_scaling import (
    scale_multiplier,
    scaled_roles,
)

MAGNITUDE_INFLUENCE: dict[str, float] = {
    "off": 0.0,
    "low": 0.05,
    "normal": 0.10,
    "high": 0.20,
}
DEFAULT_MAGNITUDE_INFLUENCE = "off"
MIN_COHORT = 4


def influence_for(level: str) -> float:
    try:
        return MAGNITUDE_INFLUENCE[level]
    except KeyError as error:
        raise ValueError(f"unknown magnitude influence: {level!r}") from error


def _record_key(variant_id: str) -> str:
    """'gdx1:records/items/x.dbr' or 'records/items/x.dbr' -> normalised path."""

    path = variant_id.split(":", 1)[1] if ":" in variant_id.split("/", 1)[0] else variant_id
    return path.strip().replace("\\", "/").casefold()


def _midrank(values: list[float], value: float) -> float:
    if len(values) <= 1:
        return 0.5
    low = bisect_left(values, value)
    high = bisect_right(values, value)
    return ((low + high - 1) / 2.0) / (len(values) - 1)


@dataclass(frozen=True, slots=True)
class StatMagnitude:
    percentile: float
    cohort_size: int


class MagnitudeModel:
    """Scaled midrank percentiles per (record, level band, stat)."""

    def __init__(
        self,
        magnitude_catalog: object,
        scale_percent_by_record: Mapping[str, float | None] | None = None,
    ) -> None:
        self._catalog = magnitude_catalog
        self._scales = {
            _record_key(path): scale
            for path, scale in (scale_percent_by_record or {}).items()
            if scale
        }
        self._index: dict[tuple[str, str], dict[str, StatMagnitude]] | None = None

    @classmethod
    def from_bundle(cls, bundle: object) -> MagnitudeModel:
        scales = {
            variant.record_path: variant.attribute_scale_percent
            for item in bundle.items.all_items()  # type: ignore[attr-defined]
            for variant in item.variants
            if variant.attribute_scale_percent
        }
        return cls(bundle.magnitude, scales)  # type: ignore[attr-defined]

    def _build(self) -> dict[tuple[str, str], dict[str, StatMagnitude]]:
        cohorts: dict[str, list[tuple[tuple[str, str], str, float]]] = defaultdict(list)
        for entry in self._catalog.entries:  # type: ignore[attr-defined]
            record = _record_key(entry.variant_id)
            scale = self._scales.get(record) if entry.entity_type != "affix" else None
            for property_ in entry.properties:
                value = property_.scalar_value
                if value is None:
                    continue
                if scale and set(property_.value_roles) & scaled_roles(
                    property_.property_id, property_.property_key
                ):
                    value = float(int(value * scale_multiplier(scale)))
                cohorts[property_.cohort_id].append(
                    ((record, entry.band_id), property_.property_id, value)
                )
        index: dict[tuple[str, str], dict[str, StatMagnitude]] = defaultdict(dict)
        for members in cohorts.values():
            values = sorted(value for _, _, value in members)
            for key, property_id, value in members:
                current = index[key].get(property_id)
                magnitude = StatMagnitude(_midrank(values, value), len(values))
                # A record with two properties of one stat keeps the stronger.
                if current is None or magnitude.percentile > current.percentile:
                    index[key][property_id] = magnitude
        return dict(index)

    def stats(self, record_path: str, band_id: str) -> dict[str, StatMagnitude]:
        if self._index is None:
            self._index = self._build()
        return self._index.get((_record_key(record_path), band_id), {})

    def multipliers(
        self,
        record_paths: Iterable[str],
        band_id: str,
        influence: float,
    ) -> dict[str, float]:
        """Per-stat score multipliers for the union of several records.

        When records share a stat (an item and its affixes), the strongest
        magnitude applies, mirroring how the union of stats is scored once.
        """

        if influence <= 0:
            return {}
        result: dict[str, float] = {}
        for record in record_paths:
            if not record:
                continue
            for stat_id, magnitude in self.stats(record, band_id).items():
                if magnitude.cohort_size < MIN_COHORT:
                    continue
                multiplier = 1.0 + influence * (2.0 * magnitude.percentile - 1.0)
                result[stat_id] = max(result.get(stat_id, 0.0), multiplier)
        return result


_active_model: MagnitudeModel | None = None


def set_active_magnitude_model(model: MagnitudeModel | None) -> None:
    """Register the model used by scorers when a profile enables magnitude."""

    global _active_model
    _active_model = model


def active_magnitude_model() -> MagnitudeModel | None:
    return _active_model


def profile_multipliers(profile: object, record_paths: Iterable[str]) -> dict[str, float] | None:
    """Multipliers for *profile*, or None when magnitude is off/unavailable."""

    level = getattr(profile, "magnitude_influence", DEFAULT_MAGNITUDE_INFLUENCE)
    influence = MAGNITUDE_INFLUENCE.get(level, 0.0)
    model = _active_model
    if influence <= 0 or model is None:
        return None
    return model.multipliers(record_paths, profile.level_band, influence)  # type: ignore[attr-defined]
