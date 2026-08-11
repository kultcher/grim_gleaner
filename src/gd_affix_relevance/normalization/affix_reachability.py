"""Diagnostic reference tracing for supported affix definitions.

This report is deliberately informational. A DBR can exist and localize correctly
while no retained item loot table can reach it. That is evidence of legacy or
orphaned data, but not sufficient reason to discard the record automatically.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry
from gd_affix_relevance.importers.affix_discovery import supported_affix_kind
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.records import (
    DEFAULT_DATA_SOURCES,
    RecordRepository,
    normalize_record_path,
)



@dataclass(slots=True)
class _AffixReferenceGroup:
    localization_tag: str
    display_name: str
    kinds: set[str] = field(default_factory=set)
    logical_record_paths: set[str] = field(default_factory=set)
    source_records: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class AffixReferenceStatus:
    localization_tag: str
    display_name: str
    affix_kinds: str
    reference_status: str
    logical_record_count: int
    source_record_count: int
    directly_referenced_record_count: int
    loottable_reachable_record_count: int
    incoming_reference_count: int
    referenced_by: str
    record_paths: str


def build_affix_reference_statuses(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...] = (),
    *,
    source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
) -> tuple[AffixReferenceStatus, ...]:
    """Trace affix DBRs through retained item-record references.

    Every DBR under ``records/items/loottables`` is treated as a diagnostic root.
    This establishes structural reachability, not an exact drop guarantee.
    Expansion records are merged by their logical ``records/items/...`` path so
    references can cross database-source boundaries.
    """

    root = Path(data_root)
    repository = RecordRepository(root, source_names)
    localization_lookup = first_entry_lookup(localization_entries)
    edges: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    affixes: dict[str, _AffixReferenceGroup] = {}

    for location in repository.iter_overlaid("records/items"):
        source_name = location.source
        logical_path = location.logical_path
        record = repository.load(location)
        edges.setdefault(logical_path, set())

        for raw_field in record.fields:
            referenced_path = _referenced_item_dbr(raw_field.value)
            if referenced_path is None:
                continue
            edges[logical_path].add(referenced_path)
            incoming[referenced_path].add(logical_path)

        kind = supported_affix_kind(record)
        if kind is None:
            continue

        localization_tag = record.first_value("lootRandomizerName") or ""
        localization_entry = localization_lookup.get(localization_tag)
        display_name = (
            plain_display_name(localization_entry.value)
            if localization_entry is not None
            else ""
        )
        group = affixes.setdefault(
            localization_tag,
            _AffixReferenceGroup(localization_tag, display_name),
        )
        group.kinds.add(kind)
        group.logical_record_paths.add(logical_path)
        group.source_records.add(f"{source_name}:{logical_path}")

    reachable = _reachable_from_item_loottables(edges)
    rows: list[AffixReferenceStatus] = []
    for group in affixes.values():
        directly_referenced = {
            path for path in group.logical_record_paths if incoming.get(path)
        }
        reachable_records = group.logical_record_paths & reachable
        referrers = {
            parent
            for path in group.logical_record_paths
            for parent in incoming.get(path, ())
        }
        if reachable_records:
            status = "reachable_from_item_loottable"
        elif directly_referenced:
            status = "referenced_only_by_unreachable_records"
        else:
            status = "no_incoming_item_reference"

        rows.append(
            AffixReferenceStatus(
                localization_tag=group.localization_tag,
                display_name=group.display_name,
                affix_kinds="; ".join(sorted(group.kinds)),
                reference_status=status,
                logical_record_count=len(group.logical_record_paths),
                source_record_count=len(group.source_records),
                directly_referenced_record_count=len(directly_referenced),
                loottable_reachable_record_count=len(reachable_records),
                incoming_reference_count=sum(
                    len(incoming.get(path, ()))
                    for path in group.logical_record_paths
                ),
                referenced_by="; ".join(sorted(referrers)),
                record_paths="; ".join(sorted(group.source_records)),
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row.reference_status,
                row.display_name.lower(),
                row.localization_tag.lower(),
            ),
        )
    )


def write_affix_reference_report(
    statuses: tuple[AffixReferenceStatus, ...], output_path: Path
) -> None:
    """Write the informational affix-reference diagnostic as CSV."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(AffixReferenceStatus.__dataclass_fields__)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for status in statuses:
            writer.writerow(
                {field_name: getattr(status, field_name) for field_name in fieldnames}
            )


def _referenced_item_dbr(value: str) -> str | None:
    normalized = normalize_record_path(value)
    if not normalized.startswith("records/items/") or not normalized.endswith(".dbr"):
        return None
    return normalized


def _reachable_from_item_loottables(edges: dict[str, set[str]]) -> set[str]:
    pending = [
        path for path in edges if path.startswith("records/items/loottables/")
    ]
    reachable = set(pending)
    while pending:
        parent = pending.pop()
        for child in edges.get(parent, ()):
            if child in reachable:
                continue
            reachable.add(child)
            pending.append(child)
    return reachable
