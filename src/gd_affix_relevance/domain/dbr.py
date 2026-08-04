"""Lossless-enough domain representations for extracted DBR records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RawDbrField:
    """One parsed DBR field in its original record order."""

    key: str
    value: str
    line_number: int
    raw_line: str


@dataclass(frozen=True, slots=True)
class DbrParseWarning:
    """A recoverable problem encountered while parsing a DBR record."""

    source_path: Path
    line_number: int
    message: str
    raw_line: str


@dataclass(frozen=True, slots=True)
class RawDbrRecord:
    """An ordered DBR record that retains duplicates and parse warnings."""

    source_path: Path
    fields: tuple[RawDbrField, ...]
    warnings: tuple[DbrParseWarning, ...] = ()

    def values_for(self, key: str) -> list[str]:
        """Return every value for *key* in source order."""

        return [field.value for field in self.fields if field.key == key]

    def first_value(self, key: str) -> str | None:
        """Return the first value for *key*, or ``None`` when absent."""

        for field in self.fields:
            if field.key == key:
                return field.value
        return None

    def fields_for(self, key: str) -> list[RawDbrField]:
        """Return every complete field object for *key* in source order."""

        return [field for field in self.fields if field.key == key]

