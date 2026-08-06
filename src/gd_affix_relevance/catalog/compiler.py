"""Compile extracted game data into a small, versioned runtime catalog."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gd_affix_relevance.catalog.models import CATALOG_SCHEMA_VERSION
from gd_affix_relevance.domain import LocalizationEntry
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.normalization.sample_report import (
    DEFAULT_DATA_SOURCES,
    AffixSampleCandidate,
    RecordResolver,
    build_sample_candidates,
)

AFFIX_SCOPE = "structurally_reachable_magic_and_rare"
SKILL_SCOPE = "named_player_pet_and_item_granted"


@dataclass(frozen=True, slots=True)
class CatalogCompileResult:
    output_dir: Path
    affix_count: int
    affix_variant_count: int
    skill_count: int
    string_count: int
    unresolved_skill_name_count: int
    unresolved_affix_record_count: int


def compile_catalog_bundle(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...],
    output_dir: Path,
    *,
    game_version: str = "unknown",
    source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
) -> CatalogCompileResult:
    """Compile official English names, all named skills, and reachable affixes.

    Sources are ordered from oldest to newest for DBR overlay behavior. The
    localization entries should be supplied newest to oldest because their
    first definition wins.
    """

    root = Path(data_root)
    destination = Path(output_dir)
    exact_names = first_entry_lookup(localization_entries)
    folded_names: dict[str, LocalizationEntry] = {}
    for entry in localization_entries:
        folded_names.setdefault(entry.tag.casefold(), entry)

    strings: dict[str, str] = {}
    skill_payloads, unresolved_skill_names = _compile_skills(
        root,
        source_names,
        exact_names,
        folded_names,
        strings,
    )

    sample_result = build_sample_candidates(
        root,
        localization_entries,
        source_names=source_names,
        count=None,
    )
    affix_payloads = _compile_affixes(
        sample_result.candidates,
        strings,
        RecordResolver(root, source_names),
        exact_names,
    )
    affix_variant_count = sum(
        len(affix["variants"]) for affix in affix_payloads
    )

    destination.mkdir(parents=True, exist_ok=True)
    files = ("affixes.json", "skills.json", "strings.en.json")
    _write_json(
        destination / "strings.en.json",
        {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "locale": "en",
            "strings": dict(
                sorted(strings.items(), key=lambda pair: pair[0].casefold())
            ),
        },
    )
    _write_json(
        destination / "skills.json",
        {"schema_version": CATALOG_SCHEMA_VERSION, "skills": skill_payloads},
    )
    _write_json(
        destination / "affixes.json",
        {"schema_version": CATALOG_SCHEMA_VERSION, "affixes": affix_payloads},
    )
    counts = {
        "affixes": len(affix_payloads),
        "affix_variants": affix_variant_count,
        "skills": len(skill_payloads),
        "strings": len(strings),
        "unresolved_skill_names": unresolved_skill_names,
    }
    _write_json(
        destination / "manifest.json",
        {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "game_version": game_version,
            "locale": "en",
            "sources": list(source_names),
            "files": list(files),
            "counts": counts,
            "affix_scope": AFFIX_SCOPE,
            "skill_scope": SKILL_SCOPE,
        },
    )
    return CatalogCompileResult(
        output_dir=destination,
        affix_count=len(affix_payloads),
        affix_variant_count=affix_variant_count,
        skill_count=len(skill_payloads),
        string_count=len(strings),
        unresolved_skill_name_count=unresolved_skill_names,
        unresolved_affix_record_count=sample_result.unresolved_name_records_skipped,
    )


def _compile_skills(
    data_root: Path,
    source_names: tuple[str, ...],
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> tuple[list[dict[str, Any]], int]:
    overlaid_paths: dict[str, tuple[str, Path]] = {}
    for source_name in source_names:
        source_root = data_root / source_name
        skills_root = source_root / "records" / "skills"
        if not skills_root.exists():
            continue
        for path in sorted(skills_root.rglob("*.dbr")):
            logical_path = _logical_record_path(path.relative_to(source_root))
            overlaid_paths[logical_path] = (source_name, path)

    skills: list[dict[str, Any]] = []
    unresolved = 0
    for logical_path, (source_name, path) in sorted(overlaid_paths.items()):
        category = _skill_category(logical_path)
        if category is None:
            continue
        record = parse_dbr_file(path)
        name_tag = (record.first_value("skillDisplayName") or "").strip()
        if not name_tag:
            continue
        entry = exact_names.get(name_tag) or folded_names.get(name_tag.casefold())
        if entry is not None:
            display_name = plain_display_name(entry.value)
            name_resolution = "localized"
        elif not name_tag.casefold().startswith(("tag", "xtag")):
            display_name = name_tag
            name_resolution = "literal"
        else:
            display_name = ""
            name_resolution = "unresolved"
        if display_name:
            strings[name_tag] = display_name
        else:
            unresolved += 1
        skills.append(
            {
                "skill_id": logical_path,
                "source": source_name,
                "category": category,
                "name_tag": name_tag,
                "display_name": display_name,
                "name_resolution": name_resolution,
                "description_tag": (
                    record.first_value("skillBaseDescription") or ""
                ).strip(),
            }
        )
    return skills, unresolved


def _compile_affixes(
    candidates: tuple[AffixSampleCandidate, ...],
    strings: dict[str, str],
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[AffixSampleCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate.affix_kind, candidate.localization_tag)].append(candidate)
        strings[candidate.localization_tag] = candidate.display_name

    affixes: list[dict[str, Any]] = []
    for (kind, localization_tag), variants in grouped.items():
        ordered_variants = sorted(
            variants,
            key=lambda candidate: (
                candidate.gear_slot.casefold(),
                candidate.level_requirements,
                candidate.semantic_components,
                candidate.representative_source,
            ),
        )
        affixes.append(
            {
                "affix_id": f"{kind}:{localization_tag}",
                "localization_tag": localization_tag,
                "display_name": ordered_variants[0].display_name,
                "kind": kind,
                "variants": [
                    _variant_payload(variant, resolver, localization_lookup)
                    for variant in ordered_variants
                ],
            }
        )
    return sorted(
        affixes,
        key=lambda affix: (
            str(affix["display_name"]).casefold(),
            str(affix["kind"]),
            str(affix["localization_tag"]).casefold(),
        ),
    )


def _variant_payload(
    candidate: AffixSampleCandidate,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> dict[str, Any]:
    components: dict[str, dict[str, str]] = {}
    for property_key, role, value in candidate.semantic_components:
        attributes = components.setdefault(property_key, {})
        if value:
            attributes[role] = value
            if role == "skill_reference":
                preferred_source = candidate.representative_source.split(":", 1)[0]
                attributes["display_name"] = resolver.resolve_skill_name(
                    value,
                    preferred_source,
                    localization_lookup,
                )
    properties = [
        {
            "property_id": _property_id(property_key),
            "property_key": property_key,
            "attributes": dict(sorted(attributes.items())),
        }
        for property_key, attributes in sorted(components.items())
    ]
    return {
        "gear_slot": candidate.gear_slot,
        "level_requirements": list(candidate.level_requirements),
        "properties": properties,
        "stat_lines": list(candidate.stat_lines),
        "representative_source": candidate.representative_source,
        "source_record_count": candidate.variant_count,
        "stat_layout_count": candidate.stat_layout_count,
    }


def _property_id(property_key: str) -> str:
    if property_key.startswith("unmapped:"):
        return "unmapped"
    return property_key.split(":", maxsplit=1)[0]


def _logical_record_path(path: Path) -> str:
    return path.as_posix().lower()


def _skill_category(logical_path: str) -> str | None:
    parts = logical_path.split("/")
    if len(parts) < 3:
        return None
    branch = parts[2]
    if not branch.startswith(("playerclass", "itemskills")):
        return None
    if any(part in {"pet", "pets"} for part in parts[3:-1]):
        return "pet"
    if branch.startswith("playerclass"):
        return "player"
    return "item_granted"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
