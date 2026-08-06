"""Read Rainbow or official Grim Dawn localization text files."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry

COLOR_CODE_PATTERN = re.compile(r"\{\^[^}]+\}")
RAINBOW_LEADING_MARKER_PATTERN = re.compile(r"^(?:XY|X|Y)(?=\{\^[^}]+\})")


def parse_localization_text(
    text: str,
    *,
    source_path: Path = Path("<memory>"),
) -> tuple[LocalizationEntry, ...]:
    """Parse localization entries, preserving raw values and source locations."""

    entries: list[LocalizationEntry] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line or raw_line.lstrip().startswith("#"):
            continue
        if "=" not in raw_line:
            continue

        tag, value = raw_line.split("=", maxsplit=1)
        if not tag:
            continue

        entries.append(
            LocalizationEntry(
                tag=tag,
                value=value,
                source_path=source_path,
                line_number=line_number,
                raw_line=raw_line,
            )
        )
    return tuple(entries)


def parse_localization_file(
    path: Path,
    *,
    encoding: str = "utf-8-sig",
) -> tuple[LocalizationEntry, ...]:
    """Read and parse one localization text file."""

    source_path = Path(path)
    return parse_localization_text(
        source_path.read_text(encoding=encoding),
        source_path=source_path,
    )


def load_localization_directory(root: Path) -> tuple[LocalizationEntry, ...]:
    """Recursively load all localization ``.txt`` files under *root*."""

    entries: list[LocalizationEntry] = []
    for path in sorted(Path(root).rglob("*.txt")):
        entries.extend(parse_localization_file(path))
    return tuple(entries)


def first_entry_lookup(
    entries: Iterable[LocalizationEntry],
) -> dict[str, LocalizationEntry]:
    """Build a deterministic lookup, retaining the first duplicate definition."""

    lookup: dict[str, LocalizationEntry] = {}
    for entry in entries:
        lookup.setdefault(entry.tag, entry)
    return lookup


def plain_display_name(value: str) -> str:
    """Remove Rainbow control prefixes and color codes for report display only."""

    without_marker = RAINBOW_LEADING_MARKER_PATTERN.sub("", value, count=1)
    return COLOR_CODE_PATTERN.sub("", without_marker).strip()

