"""Classify item-localization tags and trace their exact DBR consumers."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ITEM_TAG_FILES = {
    "base": "tags_items.txt",
    "gdx1": "tagsgdx1_items.txt",
    "gdx2": "tagsgdx2_items.txt",
    "gdx3": "tagsgdx3_items.txt",
}


@dataclass(frozen=True, slots=True)
class ItemTagDefinition:
    source: str
    section: str
    tag: str
    value: str
    source_path: Path
    line_number: int


@dataclass(frozen=True, slots=True)
class ItemTagReference:
    source: str
    record_path: str
    field: str

    @property
    def branch(self) -> str:
        parts = self.record_path.split("/")
        return "/".join(parts[:3]) if len(parts) >= 3 else self.record_path


@dataclass(frozen=True, slots=True)
class ItemTagAuditEntry:
    definition: ItemTagDefinition
    references: tuple[ItemTagReference, ...]


@dataclass(frozen=True, slots=True)
class ItemTagComparison:
    source: str
    reference_count: int
    comparison_count: int
    missing_from_comparison: tuple[str, ...]
    extra_in_comparison: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemTagAuditResult:
    entries: tuple[ItemTagAuditEntry, ...]
    definition_sources: tuple[str, ...]
    scan_sources: tuple[str, ...]
    dbr_files_scanned: int
    comparisons: tuple[ItemTagComparison, ...]

    @property
    def unique_tags(self) -> frozenset[str]:
        return frozenset(entry.definition.tag for entry in self.entries)

    @property
    def referenced_unique_tags(self) -> frozenset[str]:
        return frozenset(
            entry.definition.tag for entry in self.entries if entry.references
        )


def build_item_tag_audit(
    data_root: Path,
    *,
    definition_sources: tuple[str, ...] = ("base", "gdx1", "gdx2"),
    scan_sources: tuple[str, ...] = ("base", "gdx1", "gdx2", "gdx3"),
    comparison_root: Path | None = None,
) -> ItemTagAuditResult:
    """Load complete item-tag files and find exact references in DBR values."""

    root = Path(data_root)
    definitions: list[ItemTagDefinition] = []
    by_tag: dict[str, list[ItemTagDefinition]] = defaultdict(list)
    for source in definition_sources:
        path = _item_tag_path(root, source)
        for definition in _read_sectioned_item_tags(path, source):
            definitions.append(definition)
            by_tag[definition.tag].append(definition)

    references: dict[str, list[ItemTagReference]] = defaultdict(list)
    files_scanned = 0
    sought_tags = frozenset(by_tag)
    for source in scan_sources:
        source_root = root / source
        if not source_root.is_dir():
            continue
        for path in source_root.rglob("*.dbr"):
            files_scanned += 1
            record_path = path.relative_to(source_root).as_posix()
            for field, value in _read_dbr_fields(path):
                if value in sought_tags:
                    references[value].append(
                        ItemTagReference(
                            source=source,
                            record_path=record_path,
                            field=field,
                        )
                    )

    entries = tuple(
        ItemTagAuditEntry(
            definition=definition,
            references=tuple(references.get(definition.tag, ())),
        )
        for definition in definitions
    )
    comparisons = (
        _build_comparisons(root, Path(comparison_root), definition_sources)
        if comparison_root is not None
        else ()
    )
    return ItemTagAuditResult(
        entries=entries,
        definition_sources=definition_sources,
        scan_sources=scan_sources,
        dbr_files_scanned=files_scanned,
        comparisons=comparisons,
    )


def write_item_tag_audit(result: ItemTagAuditResult, output_dir: Path) -> None:
    """Write Markdown summary and one row per localization definition."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "item-tag-audit.md").write_text(
        format_item_tag_audit_report(result), encoding="utf-8"
    )
    with (destination / "item-tag-entries.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "source",
                "section",
                "tag",
                "value",
                "referenced_by_dbr",
                "reference_count",
                "fields",
                "branches",
                "example_records",
                "localization_source",
                "line_number",
            )
        )
        for entry in result.entries:
            fields = Counter(ref.field for ref in entry.references)
            branches = Counter(ref.branch for ref in entry.references)
            examples = tuple(
                dict.fromkeys(
                    f"{ref.source}:{ref.record_path}" for ref in entry.references
                )
            )[:5]
            definition = entry.definition
            writer.writerow(
                (
                    definition.source,
                    definition.section,
                    definition.tag,
                    definition.value,
                    "yes" if entry.references else "no",
                    len(entry.references),
                    "; ".join(f"{key} ({count})" for key, count in fields.most_common()),
                    "; ".join(
                        f"{key} ({count})" for key, count in branches.most_common()
                    ),
                    "; ".join(examples),
                    definition.source_path.as_posix(),
                    definition.line_number,
                )
            )


def format_item_tag_audit_report(result: ItemTagAuditResult) -> str:
    """Render a section, field, and record-branch coverage report."""

    unique_tags = result.unique_tags
    referenced = result.referenced_unique_tags
    duplicate_definition_count = len(result.entries) - len(unique_tags)
    lines = [
        "# Item localization tag audit",
        "",
        f"Definition sources: {', '.join(result.definition_sources)}",
        f"DBR scan sources: {', '.join(result.scan_sources)}",
        f"Localization definitions: {len(result.entries):,}",
        f"Unique tags: {len(unique_tags):,}",
        f"Duplicate cross-file definitions: {duplicate_definition_count:,}",
        f"Unique tags referenced directly by a DBR: {len(referenced):,}",
        f"Unique tags without an exact DBR reference: {len(unique_tags - referenced):,}",
        f"DBR files scanned: {result.dbr_files_scanned:,}",
        "",
        "An absent DBR reference does not make a tag safe to omit. Some labels are consumed by level/map assets, engine composition, UI code, or retained compatibility data.",
    ]

    if result.comparisons:
        lines.extend(["", "## Comparison tag sets", ""])
        for comparison in result.comparisons:
            lines.append(
                f"- {comparison.source}: reference {comparison.reference_count:,}; "
                f"comparison {comparison.comparison_count:,}; missing "
                f"{len(comparison.missing_from_comparison):,}; extra "
                f"{len(comparison.extra_in_comparison):,}."
            )

    lines.extend(
        [
            "",
            "## Localization sections",
            "",
            "| Source | Section | Definitions | DBR-referenced | Reference uses | Top fields | Top record branches |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    section_entries: dict[tuple[str, str], list[ItemTagAuditEntry]] = defaultdict(list)
    for entry in result.entries:
        section_entries[(entry.definition.source, entry.definition.section)].append(entry)
    for (source, section), entries in section_entries.items():
        fields = Counter(ref.field for entry in entries for ref in entry.references)
        branches = Counter(ref.branch for entry in entries for ref in entry.references)
        direct = sum(bool(entry.references) for entry in entries)
        uses = sum(len(entry.references) for entry in entries)
        lines.append(
            f"| {source} | {_escape_table(section)} | {len(entries)} | {direct} | "
            f"{uses} | {_format_counter(fields, 3)} | {_format_counter(branches, 2)} |"
        )

    all_fields = Counter(
        ref.field for entry in result.entries for ref in entry.references
    )
    all_branches = Counter(
        ref.branch for entry in result.entries for ref in entry.references
    )
    lines.extend(["", "## DBR fields consuming item tags", ""])
    lines.extend(
        f"- `{field}`: {count:,} reference uses"
        for field, count in all_fields.most_common()
    )
    lines.extend(["", "## DBR branches consuming item tags", ""])
    lines.extend(
        f"- `{branch}`: {count:,} reference uses"
        for branch, count in all_branches.most_common()
    )
    return "\n".join(lines) + "\n"


def _item_tag_path(data_root: Path, source: str) -> Path:
    try:
        filename = DEFAULT_ITEM_TAG_FILES[source]
    except KeyError as error:
        raise ValueError(f"unknown item-tag source: {source}") from error
    path = data_root / source / "text_en" / filename
    if not path.is_file():
        raise FileNotFoundError(f"item localization file not found: {path}")
    return path


def _read_sectioned_item_tags(
    path: Path, source: str
) -> tuple[ItemTagDefinition, ...]:
    section = "(preamble)"
    definitions: list[ItemTagDefinition] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        stripped = raw_line.strip()
        if stripped.startswith("#"):
            section = stripped[1:].strip() or "(comment)"
            continue
        if "=" not in raw_line:
            continue
        tag, value = raw_line.split("=", maxsplit=1)
        if not tag:
            continue
        definitions.append(
            ItemTagDefinition(
                source=source,
                section=section,
                tag=tag,
                value=value,
                source_path=path,
                line_number=line_number,
            )
        )
    return tuple(definitions)


def _read_dbr_fields(path: Path) -> tuple[tuple[str, str], ...]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        return ()
    fields: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        separator = raw_line.find(",")
        if separator < 1:
            continue
        value = raw_line[separator + 1 :]
        if value.endswith(","):
            value = value[:-1]
        fields.append((raw_line[:separator], value))
    return tuple(fields)


def _build_comparisons(
    data_root: Path,
    comparison_root: Path,
    sources: tuple[str, ...],
) -> tuple[ItemTagComparison, ...]:
    comparisons: list[ItemTagComparison] = []
    for source in sources:
        filename = DEFAULT_ITEM_TAG_FILES[source]
        reference = {
            definition.tag
            for definition in _read_sectioned_item_tags(
                _item_tag_path(data_root, source), source
            )
        }
        comparison_path = comparison_root / filename
        comparison = (
            {
                definition.tag
                for definition in _read_sectioned_item_tags(
                    comparison_path, source
                )
            }
            if comparison_path.is_file()
            else set()
        )
        comparisons.append(
            ItemTagComparison(
                source=source,
                reference_count=len(reference),
                comparison_count=len(comparison),
                missing_from_comparison=tuple(sorted(reference - comparison)),
                extra_in_comparison=tuple(sorted(comparison - reference)),
            )
        )
    return tuple(comparisons)


def _format_counter(counter: Counter[str], limit: int) -> str:
    if not counter:
        return ""
    return _escape_table(
        ", ".join(f"{key} ({count})" for key, count in counter.most_common(limit))
    )


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|")
