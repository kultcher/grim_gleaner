"""Analyze scalar stat magnitude and level-pool changes in extracted game data.

This is a research helper rather than part of the runtime application.  It
deliberately ignores loot jitter and reduces only simple one-dimensional
statlines to numbers.  Chance, duration, proc, and other compound effects are
excluded instead of being assigned an arbitrary magnitude.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
from statistics import median
import sys
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gd_affix_relevance.importers.affix_discovery import supported_affix_kind
from gd_affix_relevance.normalization.field_inventory import active_value_kind
from gd_affix_relevance.normalization.field_policy import fields_for_semantic_analysis
from gd_affix_relevance.normalization.mapping_proposals import (
    chance_damage_bundle_keys,
    contextualize_damage_chance,
    propose_field_mapping,
)
from gd_affix_relevance.normalization.sample_report import (
    _propagate_gear_slots,
    _referenced_item_dbr,
    _relevant_item_locations,
    format_gear_slots,
)
from gd_affix_relevance.records import RecordRepository
from gd_affix_relevance.slots import slot_sort_key


COMPOUND_ROLE_MARKERS = (
    "chance",
    "duration",
    "seconds",
    "global_flag",
    "level_equation",
    "trigger_controller",
)
PAIR_ROLES = (
    ("damage_min", "damage_max"),
    ("percent_min", "percent_max"),
)
SINGLE_ROLES = (
    "damage_percent",
    "percent",
    "flat",
    "reduction_percent",
    "reduction_flat",
    "skill_level",
    "value",
)
DISTINGUISHING_ROLES = (
    "source_damage_type",
    "destination_damage_type",
    "skill_reference",
    "mastery_reference",
    "race_reference",
)
EXCLUDED_PROPERTIES = frozenset(
    {
        "base_attack_speed",
        "granted_item_skill",
        "pet_bonus",
        "unmapped",
        "unresolved_composite",
    }
)


def number(value: Any) -> float | None:
    try:
        parsed = float(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def integer(record: Any, field: str) -> int:
    parsed = number(record.first_value(field))
    return int(parsed) if parsed is not None else 0


def scalar_from_attributes(
    property_id: str,
    property_key: str,
    attributes: dict[str, str],
) -> tuple[str, float] | None:
    """Return a stable stat identity and midpoint value for a simple bundle."""

    if property_id in EXCLUDED_PROPERTIES or property_id.startswith("chance_"):
        return None
    roles = set(attributes)
    if any(marker in role for role in roles for marker in COMPOUND_ROLE_MARKERS):
        return None

    candidates: list[float] = []
    used_roles: set[str] = set()
    for low_role, high_role in PAIR_ROLES:
        low = number(attributes.get(low_role))
        high = number(attributes.get(high_role))
        if low is None and high is None:
            continue
        if low is None:
            low = high
        if high is None:
            high = low
        assert low is not None and high is not None
        candidates.append((low + high) / 2.0)
        used_roles.update({low_role, high_role} & roles)

    for role in SINGLE_ROLES:
        parsed = number(attributes.get(role))
        if parsed is not None:
            candidates.append(parsed)
            used_roles.add(role)

    # Multiple independent numbers mean the statline is not one-dimensional.
    if len(candidates) != 1:
        return None
    value = candidates[0]
    if value <= 0:
        return None

    qualifiers = tuple(
        f"{role}={str(attributes[role]).strip().casefold()}"
        for role in DISTINGUISHING_ROLES
        if attributes.get(role)
    )
    identity = (
        property_id
        if property_id
        in {
            "damage_conversion",
            "mastery_bonus",
            "racial_damage_bonus",
            "racial_defense_bonus",
            "skill_bonus",
        }
        else property_key
    )
    if qualifiers:
        identity += "|" + "|".join(qualifiers)
    return identity, value


def record_scalar_properties(record: Any) -> dict[str, float]:
    mapped: list[tuple[Any, str]] = []
    for field in fields_for_semantic_analysis(record):
        if active_value_kind(field.value) is None:
            continue
        proposal = propose_field_mapping(field.key)
        if (
            proposal is None
            or proposal.status == "ignored"
            or proposal.component_requirement == "metadata"
        ):
            continue
        mapped.append((proposal, field.value))

    chance_bundles = chance_damage_bundle_keys(proposal for proposal, _ in mapped)
    bundles: dict[str, dict[str, str]] = defaultdict(dict)
    property_ids: dict[str, str] = {}
    for raw_proposal, value in mapped:
        proposal = contextualize_damage_chance(raw_proposal, chance_bundles)
        property_ids[proposal.bundle_key] = proposal.property_id
        bundles[proposal.bundle_key][proposal.value_role] = value

    scalars: dict[str, float] = {}
    for bundle_key, attributes in bundles.items():
        result = scalar_from_attributes(
            property_ids[bundle_key], bundle_key, attributes
        )
        if result is not None:
            identity, value = result
            scalars[identity] = value
    return scalars


def affix_observations(
    repository: RecordRepository,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    edges: dict[str, set[str]] = defaultdict(set)
    affixes: dict[str, tuple[Any, Any]] = {}
    for location in _relevant_item_locations(repository):
        record = repository.load(location)
        for field in record.fields:
            reference = _referenced_item_dbr(field.value)
            if reference is not None:
                edges[location.logical_path].add(reference)
        if supported_affix_kind(record) is not None:
            affixes[location.logical_path] = (location, record)

    slots_by_record = _propagate_gear_slots(edges)
    tiers: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    for logical_path, (location, record) in affixes.items():
        slots = slots_by_record.get(logical_path)
        tag = (record.first_value("lootRandomizerName") or "").strip()
        kind = supported_affix_kind(record) or ""
        if not slots or not tag or not kind:
            continue
        applicable = tuple(sorted(slots, key=slot_sort_key))
        gear_slot = format_gear_slots(set(applicable))
        level = integer(record, "levelRequirement")
        rarity = (record.first_value("itemClassification") or "").strip()
        family = (kind, tag, gear_slot)
        tier = {
            "family": family,
            "kind": kind,
            "tag": tag,
            "gear_slot": gear_slot,
            "rarity": rarity,
            "level": level,
            "source": f"{location.source}:{logical_path}",
        }
        tiers.append(tier)
        for stat_id, value in record_scalar_properties(record).items():
            rows.append(
                {
                    **tier,
                    "stat_id": stat_id,
                    "value": value,
                }
            )
    return tiers, rows


def item_observations(catalog_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = json.loads((catalog_root / "equipment.json").read_text(encoding="utf-8"))
    variants: list[dict[str, Any]] = []
    scalar_rows: list[dict[str, Any]] = []
    for item in payload["items"]:
        for variant in item["variants"]:
            category = str(variant.get("category", ""))
            rarity = str(variant.get("rarity", ""))
            if category == "monster_infrequent":
                item_type = "Monster Infrequent"
            elif rarity == "Epic":
                item_type = "Epic"
            elif rarity == "Legendary":
                item_type = "Legendary"
            else:
                continue
            row = {
                "family": item["item_id"],
                "display_name": item["display_name"],
                "record_path": variant["record_path"],
                "level": int(variant.get("level_requirement", 0)),
                "item_level": int(variant.get("item_level", 0)),
                "gear_slot": variant.get("gear_slot", ""),
                "item_type": item_type,
                "rarity": rarity,
            }
            variants.append(row)
            for prop in variant.get("properties", []):
                result = scalar_from_attributes(
                    str(prop.get("property_id", "")),
                    str(prop.get("property_key", "")),
                    dict(prop.get("attributes", {})),
                )
                if result is None:
                    continue
                stat_id, value = result
                scalar_rows.append({**row, "stat_id": stat_id, "value": value})
    return variants, scalar_rows


def collapse_values(
    rows: Iterable[dict[str, Any]],
    identity_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    representatives: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[field] for field in identity_fields)
        grouped[key].append(float(row["value"]))
        representatives.setdefault(key, row)
    collapsed = []
    for key, values in grouped.items():
        collapsed.append({**representatives[key], "value": median(values)})
    return collapsed


def midrank_percentiles(values: list[float]) -> list[float]:
    if len(values) <= 1:
        return [0.5] * len(values)
    ordered = sorted(values)
    positions: dict[float, list[int]] = defaultdict(list)
    for index, value in enumerate(ordered):
        positions[value].append(index)
    ranks = {
        value: (sum(indices) / len(indices)) / (len(values) - 1)
        for value, indices in positions.items()
    }
    return [ranks[value] for value in values]


def percentile_consistency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    collapsed = collapse_values(
        rows,
        ("family", "level", "stat_id", "kind", "rarity", "gear_slot"),
    )
    peers: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in collapsed:
        peers[
            (
                row["level"],
                row["stat_id"],
                row["kind"],
                row["rarity"],
                row["gear_slot"],
            )
        ].append(row)

    ranked: list[dict[str, Any]] = []
    peer_sizes = Counter()
    for peer_key, group in peers.items():
        peer_sizes[len(group)] += 1
        if len(group) < 4:
            continue
        percentiles = midrank_percentiles([row["value"] for row in group])
        ranked.extend(
            {**row, "percentile": percentile}
            for row, percentile in zip(group, percentiles, strict=True)
        )

    trajectories: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in ranked:
        trajectories[(row["family"], row["stat_id"])].append(row)
    usable = [sorted(group, key=lambda row: row["level"]) for group in trajectories.values() if len(group) >= 2]

    percentile_spans: list[float] = []
    first_last_moves: list[float] = []
    same_quartile = 0
    within_15 = 0
    unchanged = 0
    monotonic_transitions = 0
    transitions = 0
    for trajectory in usable:
        percentiles = [row["percentile"] for row in trajectory]
        percentile_spans.append(max(percentiles) - min(percentiles))
        move = abs(percentiles[-1] - percentiles[0])
        first_last_moves.append(move)
        if int(min(percentiles[0] * 4, 3)) == int(min(percentiles[-1] * 4, 3)):
            same_quartile += 1
        if move <= 0.15:
            within_15 += 1
        if move == 0:
            unchanged += 1
        for before, after in zip(trajectory, trajectory[1:]):
            transitions += 1
            if after["value"] >= before["value"]:
                monotonic_transitions += 1

    def pct(count: int, total: int) -> float:
        return round(100 * count / total, 1) if total else 0.0

    return {
        "scalar_observations": len(rows),
        "collapsed_observations": len(collapsed),
        "peer_groups": len(peers),
        "peer_groups_with_at_least_4": sum(1 for group in peers.values() if len(group) >= 4),
        "ranked_observations": len(ranked),
        "multilevel_family_stat_trajectories": len(usable),
        "median_percentile_span": round(median(percentile_spans), 4) if percentile_spans else None,
        "median_first_last_percentile_move": round(median(first_last_moves), 4) if first_last_moves else None,
        "first_last_within_15_percentile_points_pct": pct(within_15, len(usable)),
        "first_last_percentile_unchanged_pct": pct(unchanged, len(usable)),
        "first_last_same_quartile_pct": pct(same_quartile, len(usable)),
        "nondecreasing_raw_transitions_pct": pct(monotonic_transitions, transitions),
        "trajectory_transition_count": transitions,
        "peer_size_distribution": dict(sorted(peer_sizes.items())),
        "trajectories": usable,
    }


def cohort_magnitude_steps(
    rows: list[dict[str, Any]],
    peer_fields: tuple[str, ...],
    *,
    minimum_cohort: int = 3,
) -> dict[int, dict[str, Any]]:
    by_peer_level: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in peer_fields) + (row["level"],)
        by_peer_level[key].append(float(row["value"]))
    timelines: dict[tuple[Any, ...], list[tuple[int, float, int]]] = defaultdict(list)
    for key, values in by_peer_level.items():
        peer = key[:-1]
        level = int(key[-1])
        if len(values) >= minimum_cohort:
            timelines[peer].append((level, median(values), len(values)))

    changes: dict[int, list[float]] = defaultdict(list)
    for timeline in timelines.values():
        ordered = sorted(timeline)
        for (_, before, _), (level, after, _) in zip(ordered, ordered[1:]):
            if before > 0:
                changes[level].append((after / before) - 1.0)

    result: dict[int, dict[str, Any]] = {}
    for level, values in sorted(changes.items()):
        result[level] = {
            "comparable_peer_groups": len(values),
            "median_change_pct": round(100 * median(values), 1),
            "groups_up_at_least_10_pct": sum(value >= 0.10 for value in values),
            "groups_up_at_least_20_pct": sum(value >= 0.20 for value in values),
            "groups_down_more_than_10_pct": sum(value <= -0.10 for value in values),
        }
    return result


def entry_counts(rows: list[dict[str, Any]], family_field: str) -> dict[int, dict[str, int]]:
    levels_by_family: dict[Any, set[int]] = defaultdict(set)
    variants_by_level = Counter()
    for row in rows:
        level = int(row["level"])
        levels_by_family[row[family_field]].add(level)
        variants_by_level[level] += 1
    firsts = Counter()
    later = Counter()
    for levels in levels_by_family.values():
        ordered = sorted(levels)
        if not ordered:
            continue
        firsts[ordered[0]] += 1
        for level in ordered[1:]:
            later[level] += 1
    return {
        level: {
            "variants": variants_by_level[level],
            "first_family_entries": firsts[level],
            "later_family_tiers": later[level],
        }
        for level in sorted(set(variants_by_level) | set(firsts) | set(later))
    }


def selected_trajectory_examples(result: dict[str, Any]) -> dict[str, Any]:
    trajectories = result.pop("trajectories")
    property_summary: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
    for trajectory in trajectories:
        stat_id = trajectory[0]["stat_id"]
        property_summary[stat_id].append(trajectory)

    summaries = []
    for stat_id, groups in property_summary.items():
        if len(groups) < 5:
            continue
        moves = [abs(group[-1]["percentile"] - group[0]["percentile"]) for group in groups]
        same_quartile = sum(
            int(min(group[0]["percentile"] * 4, 3))
            == int(min(group[-1]["percentile"] * 4, 3))
            for group in groups
        )
        summaries.append(
            {
                "stat_id": stat_id,
                "trajectories": len(groups),
                "median_first_last_move": round(median(moves), 4),
                "same_quartile_pct": round(100 * same_quartile / len(groups), 1),
            }
        )
    result["property_summaries"] = sorted(
        summaries, key=lambda row: (-row["trajectories"], row["stat_id"])
    )

    def summarize_groups(fields: tuple[str, ...]) -> list[dict[str, Any]]:
        grouped: dict[tuple[Any, ...], list[list[dict[str, Any]]]] = defaultdict(list)
        for trajectory in trajectories:
            grouped[tuple(trajectory[0][field] for field in fields)].append(trajectory)
        rows = []
        for key, groups in grouped.items():
            if len(groups) < 5:
                continue
            moves = [
                abs(group[-1]["percentile"] - group[0]["percentile"])
                for group in groups
            ]
            rows.append(
                {
                    **dict(zip(fields, key, strict=True)),
                    "trajectories": len(groups),
                    "median_first_last_move": round(median(moves), 4),
                    "within_15_percentile_points_pct": round(
                        100 * sum(move <= 0.15 for move in moves) / len(groups), 1
                    ),
                    "same_quartile_pct": round(
                        100
                        * sum(
                            int(min(group[0]["percentile"] * 4, 3))
                            == int(min(group[-1]["percentile"] * 4, 3))
                            for group in groups
                        )
                        / len(groups),
                        1,
                    ),
                }
            )
        return sorted(rows, key=lambda row: (-row["trajectories"], tuple(str(row[field]) for field in fields)))

    result["kind_rarity_summaries"] = summarize_groups(("kind", "rarity"))
    result["slot_summaries"] = summarize_groups(("gear_slot",))

    lightning = [
        group
        for group in trajectories
        if group[0]["stat_id"].split("|", 1)[0] == "lightning_damage_percent"
    ]
    result["lightning_damage_percent_trajectories"] = [
        [
            {
                "family": list(row["family"]),
                "level": row["level"],
                "value": row["value"],
                "percentile": round(row["percentile"], 4),
                "kind": row["kind"],
                "rarity": row["rarity"],
                "gear_slot": row["gear_slot"],
            }
            for row in group
        ]
        for group in lightning
    ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=ROOT / "game_data")
    parser.add_argument("--catalog-root", type=Path, default=ROOT / "artifacts" / "catalog")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "magnitude-level-analysis.json")
    args = parser.parse_args()

    repository = RecordRepository(args.data_root)
    affix_tiers, affix_rows = affix_observations(repository)
    item_variants, item_rows = item_observations(args.catalog_root)

    affix_family_levels = collapse_values(
        affix_rows,
        ("family", "level", "kind", "rarity", "gear_slot", "stat_id"),
    )
    consistency = selected_trajectory_examples(percentile_consistency(affix_rows))
    result = {
        "method": {
            "jitter": "ignored",
            "ranges": "arithmetic midpoint of min and max",
            "compound_effects": "excluded",
            "affix_peer_group": ["stat", "prefix_or_suffix", "rarity", "exact_slot", "required_level"],
            "item_peer_group": ["stat", "item_type", "slot", "required_level"],
        },
        "counts": {
            "affix_scalar_observations": len(affix_rows),
            "affix_tier_records": len(affix_tiers),
            "item_variants": len(item_variants),
            "item_scalar_observations": len(item_rows),
        },
        "affix_relative_consistency": consistency,
        "affix_entries": entry_counts(affix_tiers, "family"),
        "item_entries": entry_counts(item_variants, "family"),
        "affix_magnitude_steps": cohort_magnitude_steps(
            affix_family_levels,
            ("stat_id", "kind", "rarity", "gear_slot"),
        ),
        "item_magnitude_steps": cohort_magnitude_steps(
            item_rows,
            ("stat_id", "item_type", "gear_slot"),
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
