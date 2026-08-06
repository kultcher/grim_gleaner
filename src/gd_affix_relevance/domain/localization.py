"""Domain objects for localization tag files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalizationEntry:
    """One ``tag=value`` localization entry."""

    tag: str
    value: str
    source_path: Path
    line_number: int
    raw_line: str

