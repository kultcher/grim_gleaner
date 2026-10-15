"""Reference implementation of live item evaluation.

Everything the in-game hook computes is defined here first; the DLL reads a
grade table generated from these rules (live/grade_table.py) and its results
are compared against this module during testing.

- Whole-item relevance: the union of the stats of the base item, prefix and
  suffix records, scored with the app's normal formula
  (``score_semantic_stat_ids``), including optional magnitude multipliers.
- Rarity class: Monster Infrequent / Epic / Legendary come from the base
  item; otherwise the affixes decide (any Rare affix -> rare, any affix ->
  magic), else the base (common).
- Roll quality: each rolled stat line with a detail range contributes its
  position in that range (0 = minimum roll, 1 = maximum), weighted by the
  same relevance points as scoring (weight^2 / 4). Unweighted stats and fixed
  values are ignored. None when nothing qualifies.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring.catalog_scorer import (
    GRADE_THRESHOLDS,
    RelevanceScore,
    profile_weight_for_semantic_id,
    property_enabled_for_profile,
    score_semantic_stat_ids,
    semantic_stat_ids,
)
from gd_affix_relevance.scoring.item_scorer import item_semantic_stat_ids
from gd_affix_relevance.scoring.magnitude import profile_multipliers
from gd_affix_relevance.stats import stat_is_scoreable
from gd_affix_relevance.live.stat_lines import (
    ParsedLine,
    StatLineIndex,
    match_tooltip_stats,
)

GRADE_ORDER = ("F", "D", "C", "B", "A", "S", "S+", "S++")
RARITY_CLASSES = (
    "common",
    "magic",
    "rare",
    "monster_infrequent",
    "epic",
    "legendary",
    "other",
)
UNIQUE_RARITY_CLASSES = frozenset({"monster_infrequent", "epic", "legendary"})
MAX_LABEL_LENGTH = 7  # fits MSVC std::wstring's inline buffer: no allocation


def normalize_record(path: str) -> str:
    return path.strip().replace("\\", "/").casefold()


def _points(weight: int) -> float:
    return (weight * weight) / 4


@dataclass(frozen=True, slots=True)
class RecordInfo:
    kind: str  # "item", "prefix" or "suffix"
    rarity_class: str
    display_name: str
    stat_ids: tuple[str, ...]


def _base_rarity_class(category: str, rarity: str) -> str:
    if category == "monster_infrequent":
        return "monster_infrequent"
    lowered = rarity.casefold()
    return {
        "common": "common",
        "magical": "magic",
        "magic": "magic",
        "rare": "rare",
        "epic": "epic",
        "legendary": "legendary",
    }.get(lowered, "other")


def item_rarity_class(base: RecordInfo | None, affixes: Iterable[RecordInfo]) -> str:
    affix_classes = [affix.rarity_class for affix in affixes]
    base_class = base.rarity_class if base is not None else "other"
    if base_class in UNIQUE_RARITY_CLASSES:
        return base_class
    if "rare" in affix_classes:
        return "rare"
    if affix_classes:
        return "magic"
    return base_class


@dataclass
class LiveCatalog:
    """Record path -> stats for one profile (conversion exclusions and
    selected skill modifiers are profile-dependent)."""

    records: dict[str, RecordInfo]

    @classmethod
    def build(cls, bundle: object, profile: BuildProfile) -> LiveCatalog:
        records: dict[str, RecordInfo] = {}
        for item in bundle.items.equipment:  # type: ignore[attr-defined]
            for variant in item.variants:
                records[normalize_record(variant.record_path)] = RecordInfo(
                    "item",
                    _base_rarity_class(variant.category, variant.rarity),
                    item.display_name,
                    item_semantic_stat_ids(variant, profile),
                )
        for affix in bundle.affixes.affixes:  # type: ignore[attr-defined]
            rarity_class = _base_rarity_class("", affix.rarity)
            for tier in affix.tiers:
                stat_ids = tuple(
                    sorted(
                        {
                            stat_id
                            for property_ in tier.properties
                            if property_.property_id != "granted_item_skill"
                            and property_enabled_for_profile(property_, profile)
                            for stat_id in semantic_stat_ids(property_)
                            if stat_is_scoreable(stat_id)
                        }
                    )
                )
                records[normalize_record(tier.record_path)] = RecordInfo(
                    affix.kind, rarity_class, affix.display_name, stat_ids
                )
        return cls(records)

    def get(self, record: str) -> RecordInfo | None:
        return self.records.get(normalize_record(record)) if record else None


@dataclass(frozen=True, slots=True)
class LiveRelevance:
    score: RelevanceScore
    rarity_class: str
    stat_ids: tuple[str, ...]
    unknown_records: tuple[str, ...]


def score_live_item(
    catalog: LiveCatalog,
    profile: BuildProfile,
    base_record: str,
    prefix_record: str = "",
    suffix_record: str = "",
) -> LiveRelevance:
    records = [record for record in (base_record, prefix_record, suffix_record) if record]
    infos = {record: catalog.get(record) for record in records}
    unknown = tuple(record for record, info in infos.items() if info is None)
    base = infos.get(base_record)
    affixes = [infos[record] for record in (prefix_record, suffix_record) if record and infos[record]]
    stat_ids = tuple(
        sorted({stat_id for info in infos.values() if info for stat_id in info.stat_ids})
    )
    score = score_semantic_stat_ids(
        stat_ids,
        profile,
        multipliers=profile_multipliers(profile, records),
    )
    return LiveRelevance(score, item_rarity_class(base, affixes), stat_ids, unknown)


@dataclass(frozen=True, slots=True)
class RolledStat:
    text: str
    stat_id: str
    percentile: float
    points: float


@dataclass(frozen=True, slots=True)
class RollQuality:
    value: float | None
    rolled: tuple[RolledStat, ...] = ()
    unmatched_lines: tuple[str, ...] = ()


def roll_percentile(parsed: ParsedLine) -> float | None:
    value = parsed.single_value
    if value is None or parsed.roll_range is None:
        return None
    low, high = parsed.roll_range
    if high <= low:
        return None
    return min(1.0, max(0.0, (value - low) / (high - low)))


def roll_quality(
    index: StatLineIndex,
    profile: BuildProfile,
    lines: list[tuple[int, str]],
    *,
    stat_classes: frozenset[int] | None = None,
) -> RollQuality:
    """Weighted average roll position of the item's relevant rolled stats.

    *stat_classes* optionally restricts which tooltip text classes count as
    stat lines (unmatched-line reporting only; matching is by text).
    """

    rolled: list[RolledStat] = []
    unmatched: list[str] = []
    for (text_class, _), (parsed, stat_id) in zip(lines, match_tooltip_stats(index, lines)):
        if stat_id is None:
            if parsed.roll_range is not None and (
                stat_classes is None or text_class in stat_classes
            ):
                unmatched.append(parsed.text)
            continue
        percentile = roll_percentile(parsed)
        if percentile is None:
            continue
        points = _points(profile_weight_for_semantic_id(profile, stat_id))
        if points <= 0:
            continue
        rolled.append(RolledStat(parsed.text, stat_id, percentile, points))
    total = sum(item.points for item in rolled)
    value = sum(item.percentile * item.points for item in rolled) / total if total else None
    return RollQuality(value, tuple(rolled), tuple(unmatched))


def tooltip_label(grade: str, quality: float | None) -> str:
    """At most 7 characters, e.g. "A 87%" or "S++100%"."""

    if quality is None:
        return grade[:MAX_LABEL_LENGTH]
    percent = f"{round(quality * 100)}%"
    label = f"{grade} {percent}"
    if len(label) > MAX_LABEL_LENGTH:
        label = f"{grade}{percent}"
    return label[:MAX_LABEL_LENGTH]


@dataclass
class LootFilterSettings:
    """Hide items whose whole-item grade is below their rarity's threshold.

    A missing or None threshold never hides that rarity class.
    """

    enabled: bool = False
    thresholds: dict[str, str | None] = field(default_factory=dict)

    def should_hide(self, grade: str, rarity_class: str) -> bool:
        if not self.enabled:
            return False
        threshold = self.thresholds.get(rarity_class)
        if threshold is None:
            return False
        return GRADE_ORDER.index(grade) < GRADE_ORDER.index(threshold)

    def to_dict(self) -> dict[str, object]:
        return {"enabled": self.enabled, "thresholds": dict(self.thresholds)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> LootFilterSettings:
        thresholds = payload.get("thresholds", {})
        if not isinstance(thresholds, Mapping):
            thresholds = {}
        clean = {
            str(rarity): (str(grade) if grade in GRADE_ORDER else None)
            for rarity, grade in thresholds.items()
            if rarity in RARITY_CLASSES
        }
        return cls(bool(payload.get("enabled", False)), clean)


assert tuple(GRADE_THRESHOLDS) == tuple(reversed(GRADE_ORDER[1:]))
