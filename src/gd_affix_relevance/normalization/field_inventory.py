"""Scan supported affix records and produce normalization review reports."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.affix_discovery import supported_affix_kind
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.normalization.field_policy import (
    fields_for_semantic_analysis,
)
from gd_affix_relevance.normalization.mapping_proposals import (
    FieldMappingProposal,
    propose_field_mapping,
)

DEFAULT_DATA_SOURCES = ("base", "gdx1", "gdx2", "gdx3")
MAX_EXAMPLES_PER_FIELD = 5


@dataclass(frozen=True, slots=True)
class FieldExample:
    source: str
    affix_name: str
    localization_tag: str
    source_path: str
    value: str


@dataclass(slots=True)
class FieldSummary:
    raw_field: str
    occurrence_count: int = 0
    record_paths: set[str] = field(default_factory=set)
    sources: Counter[str] = field(default_factory=Counter)
    classifications: Counter[str] = field(default_factory=Counter)
    value_kinds: Counter[str] = field(default_factory=Counter)
    examples: list[FieldExample] = field(default_factory=list)

    @property
    def record_count(self) -> int:
        return len(self.record_paths)


@dataclass(frozen=True, slots=True)
class InventoryResult:
    records_scanned: int
    supported_records: int
    parse_warning_count: int
    unresolved_localization_tags: int
    unresolved_localization: tuple[tuple[str, str, int], ...]
    fields: tuple[FieldSummary, ...]


def active_value_kind(value: str) -> str | None:
    """Classify a meaningful value, returning ``None`` for empty/numeric zero."""

    stripped = value.strip()
    if not stripped:
        return None

    try:
        numeric_value = Decimal(stripped)
    except InvalidOperation:
        if stripped.lower().endswith(".dbr"):
            return "record_reference"
        if "itemLevel" in stripped or any(operator in stripped for operator in ("+", "*", "/")):
            return "expression"
        return "string"

    return None if numeric_value == 0 else "numeric"


def build_field_inventory(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...] = (),
    *,
    source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
) -> InventoryResult:
    """Inventory active fields from supported affixes across database sources."""

    localization_lookup = first_entry_lookup(localization_entries)
    summaries: dict[str, FieldSummary] = {}
    records_scanned = 0
    supported_records = 0
    parse_warning_count = 0
    unresolved_tags: dict[str, Counter[str]] = {}

    for source_name in source_names:
        lootaffix_root = (
            Path(data_root) / source_name / "records" / "items" / "lootaffixes"
        )
        for kind in ("prefix", "suffix"):
            kind_root = lootaffix_root / kind
            if not kind_root.exists():
                continue

            for source_path in sorted(kind_root.glob("*.dbr")):
                records_scanned += 1
                record = parse_dbr_file(source_path)
                parse_warning_count += len(record.warnings)
                if supported_affix_kind(record) is None:
                    continue

                supported_records += 1
                _add_record_fields(
                    summaries,
                    record,
                    source_name=source_name,
                    data_root=Path(data_root),
                    localization_lookup=localization_lookup,
                    unresolved_tags=unresolved_tags,
                )

    ordered_fields = tuple(
        sorted(
            summaries.values(),
            key=lambda summary: (-summary.record_count, summary.raw_field.lower()),
        )
    )
    return InventoryResult(
        records_scanned=records_scanned,
        supported_records=supported_records,
        parse_warning_count=parse_warning_count,
        unresolved_localization_tags=len(unresolved_tags),
        unresolved_localization=tuple(
            (tag, source, count)
            for tag, source_counts in sorted(unresolved_tags.items())
            for source, count in sorted(source_counts.items())
        ),
        fields=ordered_fields,
    )


def _add_record_fields(
    summaries: dict[str, FieldSummary],
    record: RawDbrRecord,
    *,
    source_name: str,
    data_root: Path,
    localization_lookup: dict[str, LocalizationEntry],
    unresolved_tags: dict[str, Counter[str]],
) -> None:
    localization_tag = record.first_value("lootRandomizerName") or ""
    localization_entry = localization_lookup.get(localization_tag)
    if localization_entry is None:
        unresolved_tags.setdefault(localization_tag, Counter())[source_name] += 1
        affix_name = ""
    else:
        affix_name = plain_display_name(localization_entry.value)

    classification = record.first_value("itemClassification") or ""
    relative_path = str(record.source_path.relative_to(data_root))
    seen_fields: set[str] = set()

    for raw_field in fields_for_semantic_analysis(record):
        value_kind = active_value_kind(raw_field.value)
        if value_kind is None:
            continue

        summary = summaries.setdefault(raw_field.key, FieldSummary(raw_field=raw_field.key))
        summary.occurrence_count += 1
        summary.record_paths.add(str(record.source_path))
        summary.sources[source_name] += 1
        summary.classifications[classification] += 1
        summary.value_kinds[value_kind] += 1

        if raw_field.key not in seen_fields and len(summary.examples) < MAX_EXAMPLES_PER_FIELD:
            summary.examples.append(
                FieldExample(
                    source=source_name,
                    affix_name=affix_name,
                    localization_tag=localization_tag,
                    source_path=relative_path,
                    value=raw_field.value,
                )
            )
        seen_fields.add(raw_field.key)


def write_inventory_reports(result: InventoryResult, output_dir: Path) -> None:
    """Write CSV and JSON reports for normalization review."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    rows = [_inventory_row(summary) for summary in result.fields]
    _write_csv(destination / "field_inventory.csv", rows)

    mapped_rows = [row for row in rows if row["mapping_status"]]
    _write_csv(destination / "mapping_proposals.csv", mapped_rows)

    bundle_rows = _bundle_relationship_rows(mapped_rows)
    _write_csv(destination / "bundle_relationships.csv", bundle_rows)

    review_rows = [
        row
        for row in mapped_rows
        if row["confidence"] == "needs_review" and row["mapping_status"] != "ignored"
    ]
    _write_csv(destination / "review_needed.csv", review_rows)

    inferred_rows = [
        row
        for row in mapped_rows
        if row["confidence"] == "strongly_inferred"
        and row["mapping_status"] != "ignored"
    ]
    _write_csv(destination / "inferred_mappings.csv", inferred_rows)

    unmapped_rows = [row for row in rows if not row["mapping_status"]]
    _write_csv(destination / "unmapped_fields.csv", unmapped_rows)
    unresolved_rows = [
        {"localization_tag": tag, "source": source, "record_count": count}
        for tag, source, count in result.unresolved_localization
    ]
    _write_csv(destination / "unresolved_localization_tags.csv", unresolved_rows)

    proposals = [
        asdict(proposal)
        for summary in result.fields
        if (proposal := propose_field_mapping(summary.raw_field)) is not None
    ]
    (destination / "proposed_normalization_rules.json").write_text(
        json.dumps(proposals, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary_payload = {
        "records_scanned": result.records_scanned,
        "supported_records": result.supported_records,
        "parse_warning_count": result.parse_warning_count,
        "unresolved_localization_tags": result.unresolved_localization_tags,
        "active_raw_fields": len(result.fields),
        "proposed_fields": len(mapped_rows),
        "inferred_fields": len(inferred_rows),
        "review_fields": len(review_rows),
        "unmapped_fields": len(unmapped_rows),
    }
    (destination / "summary.json").write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _inventory_row(summary: FieldSummary) -> dict[str, str | int]:
    proposal = propose_field_mapping(summary.raw_field)
    examples = " | ".join(_format_example(example) for example in summary.examples)
    return {
        "raw_field": summary.raw_field,
        "record_count": summary.record_count,
        "occurrence_count": summary.occurrence_count,
        "sources": _format_counter(summary.sources),
        "classifications": _format_counter(summary.classifications),
        "value_kinds": _format_counter(summary.value_kinds),
        "property_id": proposal.property_id if proposal else "",
        "bundle_key": proposal.bundle_key if proposal else "",
        "display_label": proposal.display_label if proposal else "",
        "value_role": proposal.value_role if proposal else "",
        "component_requirement": proposal.component_requirement if proposal else "",
        "mapping_status": proposal.status if proposal else "",
        "confidence": proposal.confidence if proposal else "",
        "display_template": proposal.display_template if proposal else "",
        "notes": proposal.notes if proposal else "",
        "examples": examples,
    }


def _format_counter(counter: Counter[str]) -> str:
    return "; ".join(f"{key}:{count}" for key, count in sorted(counter.items()))


def _bundle_relationship_rows(
    mapped_rows: list[dict[str, str | int]],
) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str | int]]] = {}
    for row in mapped_rows:
        if row["mapping_status"] == "ignored":
            continue
        grouped.setdefault(str(row["bundle_key"]), []).append(row)

    rows: list[dict[str, str]] = []
    for bundle_key, components in sorted(grouped.items()):
        components.sort(key=lambda row: str(row["raw_field"]))
        rows.append(
            {
                "bundle_key": bundle_key,
                "property_id": str(components[0]["property_id"]),
                "display_label": str(components[0]["display_label"]),
                "display_template": next(
                    (
                        str(row["display_template"])
                        for row in components
                        if row["display_template"]
                    ),
                    "",
                ),
                "components": "; ".join(
                    f"{row['raw_field']}={row['value_role']}[{row['component_requirement']}]"
                    for row in components
                ),
            }
        )
    return rows


def _format_example(example: FieldExample) -> str:
    name = example.affix_name or "<unresolved>"
    return (
        f"{example.source}:{name} [{example.localization_tag}] "
        f"{example.value} ({example.source_path})"
    )


def _write_csv(path: Path, rows: list[dict[str, str | int]]) -> None:
    fieldnames = list(rows[0]) if rows else ["raw_field"]
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
