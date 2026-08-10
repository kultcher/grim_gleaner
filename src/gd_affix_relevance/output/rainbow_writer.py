"""Generate a complete Rainbow-derived localization staging folder."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.catalog import AffixCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import (
    score_semantic_stat_ids,
    variant_semantic_stat_ids,
)

UTF8_BOM = b"\xef\xbb\xbf"
COLOR_CODE_PATTERN = re.compile(r"\{\^[^}]+\}")
GENERATED_MARKER_PATTERN = re.compile(
    r"\((?:S\+\+|S\+|S|A|B|C|D|-|—)\*?\d+\)"
)


@dataclass(frozen=True, slots=True)
class LocalizationChange:
    relative_path: str
    line_number: int
    localization_tag: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class RainbowGenerationResult:
    source_root: Path
    output_root: Path
    files_written: int
    affix_tags_scored: int
    affix_tags_found: int
    annotated_lines: int
    missing_affix_tags: tuple[str, ...]
    changes: tuple[LocalizationChange, ...]


def build_affix_markers(
    catalog: AffixCatalog,
    profile: BuildProfile,
) -> dict[str, str]:
    """Build one conservative marker for each exact affix localization tag."""

    variant_sets_by_tag: dict[str, list[set[str]]] = defaultdict(list)
    for affix in catalog.affixes:
        for variant in affix.variants:
            variant_sets_by_tag[affix.localization_tag].append(
                set(variant_semantic_stat_ids(variant, profile))
            )

    markers: dict[str, str] = {}
    for localization_tag, variant_sets in sorted(variant_sets_by_tag.items()):
        common_stat_ids = tuple(sorted(set.intersection(*variant_sets)))
        score = score_semantic_stat_ids(common_stat_ids, profile)
        has_variant_difference = any(
            variant_set != variant_sets[0] for variant_set in variant_sets[1:]
        )
        ambiguity_marker = "*" if has_variant_difference else ""
        markers[localization_tag] = (
            f"({score.grade}{ambiguity_marker}{score.matched_count})"
        )
    return markers


def generate_rainbow_output(
    source_root: Path,
    output_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
) -> RainbowGenerationResult:
    """Clone a complete localization folder and annotate exact affix tags only."""

    source = Path(source_root).resolve()
    destination = Path(output_root).resolve()
    if not source.is_dir():
        raise ValueError(f"localization source is not a directory: {source}")
    if _paths_overlap(source, destination):
        raise ValueError("source and output directories must not overlap")

    source_files = tuple(sorted(path for path in source.rglob("*") if path.is_file()))
    if not source_files:
        raise ValueError(f"localization source contains no files: {source}")

    markers = build_affix_markers(catalog, profile)
    found_tags: set[str] = set()
    changes: list[LocalizationChange] = []
    for source_path in source_files:
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        raw_bytes = source_path.read_bytes()
        if source_path.suffix.casefold() == ".txt":
            output_bytes, file_changes, file_found_tags = _annotate_text_bytes(
                raw_bytes,
                markers,
                relative.as_posix(),
            )
            changes.extend(file_changes)
            found_tags.update(file_found_tags)
        else:
            output_bytes = raw_bytes
        _write_bytes_atomically(destination_path, output_bytes)

    missing = tuple(sorted(set(markers) - found_tags, key=str.casefold))
    return RainbowGenerationResult(
        source_root=source,
        output_root=destination,
        files_written=len(source_files),
        affix_tags_scored=len(markers),
        affix_tags_found=len(found_tags),
        annotated_lines=len(changes),
        missing_affix_tags=missing,
        changes=tuple(changes),
    )


def _annotate_text_bytes(
    raw_bytes: bytes,
    markers: dict[str, str],
    relative_path: str,
) -> tuple[bytes, tuple[LocalizationChange, ...], set[str]]:
    has_bom = raw_bytes.startswith(UTF8_BOM)
    text = raw_bytes.decode("utf-8-sig")
    output_lines: list[str] = []
    changes: list[LocalizationChange] = []
    found_tags: set[str] = set()
    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        body, ending = _split_line_ending(line)
        separator = body.find("=")
        if separator < 1:
            output_lines.append(line)
            continue
        tag = body[:separator]
        marker = markers.get(tag)
        if marker is None:
            output_lines.append(line)
            continue

        found_tags.add(tag)
        value = body[separator + 1 :]
        annotated_value = _replace_generated_marker(value, marker)
        annotated_body = f"{tag}={annotated_value}"
        output_lines.append(annotated_body + ending)
        if annotated_body != body:
            changes.append(
                LocalizationChange(
                    relative_path=relative_path,
                    line_number=line_number,
                    localization_tag=tag,
                    before=body,
                    after=annotated_body,
                )
            )

    output = "".join(output_lines).encode("utf-8")
    if has_bom:
        output = UTF8_BOM + output
    return output, tuple(changes), found_tags


def _replace_generated_marker(value: str, marker: str) -> str:
    color_match = COLOR_CODE_PATTERN.search(value)
    if color_match is not None:
        leading = value[: color_match.start()]
        existing = GENERATED_MARKER_PATTERN.search(leading)
        if existing is not None:
            value = value[: existing.start()] + value[existing.end() :]
            color_match = COLOR_CODE_PATTERN.search(value)
        insertion_index = color_match.start() if color_match is not None else 0
        return value[:insertion_index] + marker + value[insertion_index:]

    existing = GENERATED_MARKER_PATTERN.match(value)
    if existing is not None:
        value = value[existing.end() :]
    return marker + value


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith(("\r", "\n")):
        return line[:-1], line[-1:]
    return line, ""


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
