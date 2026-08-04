"""Parser for line-oriented DBR files extracted from Grim Dawn ARZ data."""

from __future__ import annotations

from pathlib import Path

from gd_affix_relevance.domain.dbr import (
    DbrParseWarning,
    RawDbrField,
    RawDbrRecord,
)

IN_MEMORY_SOURCE = Path("<memory>")


def parse_dbr_text(
    text: str,
    *,
    source_path: Path = IN_MEMORY_SOURCE,
) -> RawDbrRecord:
    """Parse DBR text while preserving field order, values, and duplicates.

    A DBR field occupies one line and uses the first comma to separate its key
    from its value. One final comma is treated as the record delimiter and is
    removed. Any other commas remain part of the value.

    Blank lines are ignored. Malformed lines are reported as warnings so one
    bad line does not prevent the remainder of the record from being loaded.
    """

    fields: list[RawDbrField] = []
    warnings: list[DbrParseWarning] = []

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip():
            continue

        separator_index = raw_line.find(",")
        if separator_index < 0:
            warnings.append(
                DbrParseWarning(
                    source_path=source_path,
                    line_number=line_number,
                    message="Missing key/value separator comma",
                    raw_line=raw_line,
                )
            )
            continue

        key = raw_line[:separator_index]
        value = raw_line[separator_index + 1 :]

        if not key:
            warnings.append(
                DbrParseWarning(
                    source_path=source_path,
                    line_number=line_number,
                    message="Field key is empty",
                    raw_line=raw_line,
                )
            )
            continue

        if value.endswith(","):
            value = value[:-1]

        fields.append(
            RawDbrField(
                key=key,
                value=value,
                line_number=line_number,
                raw_line=raw_line,
            )
        )

    return RawDbrRecord(
        source_path=source_path,
        fields=tuple(fields),
        warnings=tuple(warnings),
    )


def parse_dbr_file(path: Path, *, encoding: str = "utf-8-sig") -> RawDbrRecord:
    """Read and parse one extracted DBR file."""

    source_path = Path(path)
    text = source_path.read_text(encoding=encoding)
    return parse_dbr_text(text, source_path=source_path)

