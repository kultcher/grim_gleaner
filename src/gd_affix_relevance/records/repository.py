"""Cached, overlay-aware repository for extracted Grim Dawn DBR records."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import plain_display_name

DEFAULT_DATA_SOURCES = ("base", "gdx1", "gdx2", "gdx3")


def normalize_record_path(path: Path | str) -> str:
    """Return a stable logical DBR path independent of host separators/case."""

    return str(path).replace("\\", "/").strip().lstrip("/").casefold()


@dataclass(frozen=True, slots=True)
class RecordLocation:
    """One physical record selected for a logical path."""

    source: str
    logical_path: str
    path: Path


class RecordRepository:
    """Read extracted DBRs through newest-expansion overlay semantics.

    ``source_names`` must be ordered oldest to newest. A reference always
    resolves to the newest source that defines its logical path.
    """

    def __init__(
        self,
        data_root: Path,
        source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
    ) -> None:
        if len(set(source_names)) != len(source_names):
            raise ValueError("source_names must not contain duplicates")
        self.data_root = Path(data_root)
        self.source_names = tuple(source_names)
        self._record_cache: dict[tuple[str, str], RawDbrRecord] = {}
        self._resolution_cache: dict[str, RecordLocation | None] = {}
        self._branch_cache: dict[
            tuple[str, bool], tuple[RecordLocation, ...]
        ] = {}
        self._source_branch_cache: dict[
            tuple[str, str, bool], tuple[RecordLocation, ...]
        ] = {}

    def iter_overlaid(
        self,
        relative_root: Path | str,
        *,
        recursive: bool = True,
    ) -> tuple[RecordLocation, ...]:
        """Return newest visible DBRs below a logical directory."""

        normalized_root = normalize_record_path(relative_root).rstrip("/")
        cache_key = (normalized_root, recursive)
        cached = self._branch_cache.get(cache_key)
        if cached is not None:
            return cached

        visible: dict[str, RecordLocation] = {}
        for source in self.source_names:
            source_root = self.data_root / source
            branch_root = source_root / Path(normalized_root)
            if not branch_root.is_dir():
                continue
            paths = (
                branch_root.rglob("*.dbr")
                if recursive
                else branch_root.glob("*.dbr")
            )
            for path in paths:
                logical = normalize_record_path(path.relative_to(source_root))
                visible[logical] = RecordLocation(source, logical, path)

        result = tuple(visible[key] for key in sorted(visible))
        self._branch_cache[cache_key] = result
        return result

    def iter_source(
        self,
        source: str,
        relative_root: Path | str,
        *,
        recursive: bool = True,
    ) -> tuple[RecordLocation, ...]:
        """Return physical DBRs from one source without applying overlays."""

        if source not in self.source_names:
            raise ValueError(f"unknown record source: {source}")
        normalized_root = normalize_record_path(relative_root).rstrip("/")
        cache_key = (source, normalized_root, recursive)
        cached = self._source_branch_cache.get(cache_key)
        if cached is not None:
            return cached

        source_root = self.data_root / source
        branch_root = source_root / Path(normalized_root)
        locations: list[RecordLocation] = []
        if branch_root.is_dir():
            paths = (
                branch_root.rglob("*.dbr")
                if recursive
                else branch_root.glob("*.dbr")
            )
            locations.extend(
                RecordLocation(
                    source,
                    normalize_record_path(path.relative_to(source_root)),
                    path,
                )
                for path in paths
            )
        result = tuple(sorted(locations, key=lambda entry: entry.logical_path))
        self._source_branch_cache[cache_key] = result
        return result

    def load(self, location: RecordLocation) -> RawDbrRecord:
        """Load one selected record, parsing each physical DBR at most once."""

        cache_key = (location.source, location.logical_path)
        record = self._record_cache.get(cache_key)
        if record is None:
            record = parse_dbr_file(location.path)
            self._record_cache[cache_key] = record
        return record

    def resolve_location(
        self,
        reference: Path | str,
    ) -> RecordLocation | None:
        """Locate the newest visible definition for a logical DBR reference."""

        logical = normalize_record_path(reference)
        if logical in self._resolution_cache:
            return self._resolution_cache[logical]
        if not logical.endswith(".dbr"):
            self._resolution_cache[logical] = None
            return None

        for source in reversed(self.source_names):
            path = self.data_root / source / Path(logical)
            if path.is_file():
                location = RecordLocation(source, logical, path)
                self._resolution_cache[logical] = location
                return location
        self._resolution_cache[logical] = None
        return None

    def resolve(
        self,
        reference: Path | str,
    ) -> tuple[str, RawDbrRecord] | None:
        """Resolve and load the newest visible definition of a DBR reference."""

        location = self.resolve_location(reference)
        if location is None:
            return None
        return location.source, self.load(location)

    def resolve_skill_name(
        self,
        reference: str,
        localization_lookup: dict[str, LocalizationEntry],
    ) -> str:
        """Follow skill proxies and resolve the first localized display name."""

        pending: deque[tuple[str, int]] = deque([(reference, 0)])
        seen: set[str] = set()
        fallback_description = ""
        while pending:
            current_reference, depth = pending.popleft()
            logical = normalize_record_path(current_reference)
            if logical in seen or depth > 4:
                continue
            seen.add(logical)
            resolved = self.resolve(current_reference)
            if resolved is None:
                continue
            _, record = resolved
            display_tag = record.first_value("skillDisplayName")
            if display_tag:
                entry = localization_lookup.get(
                    display_tag
                ) or localization_lookup.get(display_tag.casefold())
                if entry is not None:
                    return plain_display_name(entry.value)
                return f"[{display_tag}]"
            description = record.first_value("FileDescription") or ""
            if description and not fallback_description:
                fallback_description = description
            for field in record.fields:
                nested = normalize_record_path(field.value)
                if nested.startswith("records/skills/") and nested.endswith(
                    ".dbr"
                ):
                    pending.append((nested, depth + 1))

        if fallback_description:
            concise = re.split(
                r"\s+with\s+",
                fallback_description,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            return concise.strip().title()
        return f"[unresolved skill: {reference}]"

    @property
    def cached_record_count(self) -> int:
        """Expose cache size for diagnostics and focused tests."""

        return len(self._record_cache)
