"""Compile extracted game data into a small, versioned runtime catalog."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gd_affix_relevance.catalog.magnitude import compile_magnitude_payload
from gd_affix_relevance.catalog.models import (
    CATALOG_SCHEMA_VERSION,
    MAGNITUDE_CATALOG_FILE,
)
from gd_affix_relevance.catalog.mastery_trees import (
    MasteryTreeRelationship,
    load_mastery_tree_relationships,
)
from gd_affix_relevance.catalog.item_compiler import (
    ITEM_FAMILIES,
    ITEM_SCOPE,
    compile_record_properties,
    compile_item_payloads,
)
from gd_affix_relevance.catalog.value_parsing import integer_value
from gd_affix_relevance.domain import LocalizationEntry
from gd_affix_relevance.io_utils import atomic_write_text
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.normalization.sample_report import (
    AffixSampleCandidate,
    build_sample_candidates,
    normalize_record_stat_lines,
    record_semantic_fingerprint,
)
from gd_affix_relevance.records import (
    DEFAULT_DATA_SOURCES,
    RecordLocation,
    RecordRepository,
)

AFFIX_SCOPE = "structurally_reachable_magic_and_rare"
SKILL_SCOPE = "named_player_pet_and_item_granted_with_mastery_tree_metadata"
TREE_PROXY_REFERENCE_FIELDS = frozenset({"buffSkillName", "petSkillName"})


@dataclass(frozen=True, slots=True)
class CatalogCompileResult:
    output_dir: Path
    affix_count: int
    affix_variant_count: int
    skill_count: int
    string_count: int
    unresolved_skill_name_count: int
    unresolved_affix_record_count: int
    item_counts: dict[str, int]
    item_variant_count: int
    unresolved_item_record_count: int
    magnitude_entry_count: int
    magnitude_property_count: int


def compile_catalog_bundle(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...],
    output_dir: Path,
    *,
    game_version: str = "1.3.0.6",
    source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
    mastery_tree_root: Path | None = None,
) -> CatalogCompileResult:
    """Compile official English names, all named skills, and reachable affixes.

    Sources are ordered from oldest to newest for DBR overlay behavior. The
    localization entries should be supplied newest to oldest because their
    first definition wins.
    """

    root = Path(data_root)
    repository = RecordRepository(root, source_names)
    destination = Path(output_dir)
    exact_names = first_entry_lookup(localization_entries)
    folded_names: dict[str, LocalizationEntry] = {}
    for entry in localization_entries:
        folded_names.setdefault(entry.tag.casefold(), entry)

    strings: dict[str, str] = {}
    mastery_tree_relationships = load_mastery_tree_relationships(
        mastery_tree_root
    )
    skill_payloads, unresolved_skill_names = _compile_skills(
        repository,
        exact_names,
        folded_names,
        strings,
        mastery_tree_relationships,
    )

    sample_result = build_sample_candidates(
        root,
        localization_entries,
        source_names=source_names,
        count=None,
        repository=repository,
    )
    affix_payloads = _compile_affixes(
        sample_result.candidates,
        strings,
        repository,
        exact_names,
    )
    affix_variant_count = sum(
        len(affix["variants"]) for affix in affix_payloads
    )
    item_payloads, item_variant_count, unresolved_item_names = (
        compile_item_payloads(
            repository,
            exact_names,
            folded_names,
            strings,
        )
    )
    magnitude_payload = compile_magnitude_payload(
        affix_payloads, item_payloads
    )
    magnitude_entry_count = len(magnitude_payload["entries"])
    magnitude_property_count = sum(
        len(entry["properties"])
        for entry in magnitude_payload["entries"]
    )

    destination.mkdir(parents=True, exist_ok=True)
    item_files = tuple(f"{family}.json" for family in ITEM_FAMILIES)
    files = (
        "affixes.json",
        "skills.json",
        "strings.en.json",
        *item_files,
        MAGNITUDE_CATALOG_FILE,
    )
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
    for family in ITEM_FAMILIES:
        _write_json(
            destination / f"{family}.json",
            {"schema_version": CATALOG_SCHEMA_VERSION, "items": item_payloads[family]},
        )
    _write_json(
        destination / MAGNITUDE_CATALOG_FILE,
        {"schema_version": CATALOG_SCHEMA_VERSION, **magnitude_payload},
    )
    item_counts = {
        family: len(item_payloads[family]) for family in ITEM_FAMILIES
    }
    counts = {
        "affixes": len(affix_payloads),
        "affix_variants": affix_variant_count,
        "skills": len(skill_payloads),
        "strings": len(strings),
        "unresolved_skill_names": unresolved_skill_names,
        "items": sum(item_counts.values()),
        "item_variants": item_variant_count,
        "unresolved_item_records": unresolved_item_names,
        "magnitude_entries": magnitude_entry_count,
        "magnitude_properties": magnitude_property_count,
        **item_counts,
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
            "item_scope": ITEM_SCOPE,
        },
    )
    from gd_affix_relevance.catalog.models import CatalogBundle
    from gd_affix_relevance.scoring.catalog_scorer import (
        unregistered_catalog_stat_ids,
    )

    unregistered = unregistered_catalog_stat_ids(CatalogBundle.load(destination))
    if unregistered:
        raise ValueError(
            "compiled scoreable stats are missing from the registry: "
            + ", ".join(unregistered)
        )
    return CatalogCompileResult(
        output_dir=destination,
        affix_count=len(affix_payloads),
        affix_variant_count=affix_variant_count,
        skill_count=len(skill_payloads),
        string_count=len(strings),
        unresolved_skill_name_count=unresolved_skill_names,
        unresolved_affix_record_count=sample_result.unresolved_name_records_skipped,
        item_counts=item_counts,
        item_variant_count=item_variant_count,
        unresolved_item_record_count=unresolved_item_names,
        magnitude_entry_count=magnitude_entry_count,
        magnitude_property_count=magnitude_property_count,
    )


def _compile_skills(
    repository: RecordRepository,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
    mastery_tree_relationships: tuple[MasteryTreeRelationship, ...],
) -> tuple[list[dict[str, Any]], int]:
    records_by_path = {
        location.logical_path: (location.source, repository.load(location))
        for location in repository.iter_overlaid("records/skills")
    }
    prepared: list[tuple[str, str, Any, str, str, str, str]] = []
    unresolved = 0
    for logical_path, (source_name, record) in records_by_path.items():
        category = _skill_category(logical_path)
        if category is None:
            continue
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
        prepared.append(
            (
                logical_path,
                source_name,
                record,
                category,
                name_tag,
                display_name,
                name_resolution,
            )
        )

    mastery_names = {
        _mastery_id(logical_path): display_name
        for logical_path, _, _, category, _, display_name, _ in prepared
        if category == "player"
        and Path(logical_path).stem.startswith("_classtraining")
        and display_name
    }
    named_skill_ids = {item[0] for item in prepared}
    tree_orders = _mastery_tree_orders(records_by_path, named_skill_ids)
    skills: list[dict[str, Any]] = []
    for (
        logical_path,
        source_name,
        record,
        category,
        name_tag,
        display_name,
        name_resolution,
    ) in prepared:
        mastery_id = _mastery_id(logical_path)
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
                "mastery_id": mastery_id,
                "mastery_name": mastery_names.get(mastery_id, ""),
                "mastery_level_required": integer_value(
                    record.first_value("skillMasteryLevelRequired")
                ),
                "max_level": integer_value(record.first_value("skillMaxLevel")),
                "skill_tier": integer_value(record.first_value("skillTier")),
                "tree_order": tree_orders.get(logical_path, 0),
                "parent_skill_id": "",
                "is_mastery": Path(logical_path).stem.startswith(
                    "_classtraining"
                ),
            }
        )
    _apply_curated_mastery_relationships(skills, mastery_tree_relationships)
    return skills, unresolved


def _mastery_tree_orders(
    records_by_path: dict[str, tuple[str, Any]],
    named_skill_ids: set[str],
) -> dict[str, int]:
    orders: dict[str, int] = {}
    for logical_path, (_, tree_record) in records_by_path.items():
        if not Path(logical_path).stem.startswith("_classtree_"):
            continue
        indexed_references: list[tuple[int, str]] = []
        for field in tree_record.fields:
            match = re.fullmatch(r"skillName(\d+)", field.key)
            if match is None or "_classtraining_" in field.value.casefold():
                continue
            indexed_references.append((int(match.group(1)), field.value))
        for order, reference in sorted(indexed_references):
            skill_id = _resolve_named_tree_skill_id(
                reference,
                records_by_path,
                named_skill_ids,
            )
            if not skill_id:
                continue
            orders[skill_id] = min(order, orders.get(skill_id, order))
    return orders


def _resolve_named_tree_skill_id(
    reference: str,
    records_by_path: dict[str, tuple[str, Any]],
    named_skill_ids: set[str],
) -> str:
    pending = [_logical_skill_reference(reference)]
    seen: set[str] = set()
    matches: set[str] = set()
    while pending:
        current = pending.pop(0)
        if not current or current in seen:
            continue
        seen.add(current)
        if current in named_skill_ids:
            matches.add(current)
            continue
        resolved = records_by_path.get(current)
        if resolved is None:
            continue
        _, record = resolved
        for field in record.fields:
            if field.key not in TREE_PROXY_REFERENCE_FIELDS:
                continue
            child = _logical_skill_reference(field.value)
            if child:
                pending.append(child)
    if len(matches) > 1:
        raise ValueError(
            f"mastery tree node {reference!r} resolves to multiple named skills: "
            + ", ".join(sorted(matches))
        )
    return next(iter(matches), "")


def _logical_skill_reference(value: str) -> str:
    logical = value.replace("\\", "/").strip().lower()
    if not logical.startswith("records/skills/") or not logical.endswith(".dbr"):
        return ""
    return logical


def _apply_curated_mastery_relationships(
    skills: list[dict[str, Any]],
    relationships: tuple[MasteryTreeRelationship, ...],
) -> None:
    if not relationships:
        return
    tree_names: dict[tuple[str, str], list[str]] = defaultdict(list)
    for skill in skills:
        if int(skill["tree_order"]) <= 0 or not skill["display_name"]:
            continue
        key = (
            str(skill["mastery_id"]),
            str(skill["display_name"]).casefold(),
        )
        tree_names[key].append(str(skill["skill_id"]))

    parent_by_child: dict[str, str] = {}
    for relationship in relationships:
        parent_ids = tree_names.get(
            (relationship.mastery_id, relationship.parent_name.casefold()), []
        )
        child_ids = tree_names.get(
            (relationship.mastery_id, relationship.child_name.casefold()), []
        )
        if len(parent_ids) != 1 or len(child_ids) != 1:
            raise ValueError(
                f"{relationship.source}: mastery relationship must resolve to one "
                f"tree node; parent {relationship.parent_name!r} -> {parent_ids}, "
                f"child {relationship.child_name!r} -> {child_ids}"
            )
        child_id = child_ids[0]
        parent_id = parent_ids[0]
        existing = parent_by_child.get(child_id)
        if existing is not None and existing != parent_id:
            raise ValueError(
                f"{relationship.source}: child {relationship.child_name!r} "
                "resolves to multiple parent skill IDs"
            )
        parent_by_child[child_id] = parent_id

    for skill in skills:
        skill["parent_skill_id"] = parent_by_child.get(
            str(skill["skill_id"]), ""
        )


def _compile_affixes(
    candidates: tuple[AffixSampleCandidate, ...],
    strings: dict[str, str],
    resolver: RecordRepository,
    localization_lookup: dict[str, LocalizationEntry],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[AffixSampleCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate.affix_kind, candidate.localization_tag)].append(candidate)
        strings[candidate.localization_tag] = candidate.display_name

    affixes: list[dict[str, Any]] = []
    for (kind, localization_tag), variants in grouped.items():
        rarities = {variant.rarity for variant in variants if variant.rarity}
        if len(rarities) != 1:
            raise ValueError(
                f"affix {localization_tag!r} must have one rarity, found "
                f"{sorted(rarities)}"
            )
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
                "rarity": next(iter(rarities)),
                "tiers": _affix_tier_payloads(
                    ordered_variants,
                    resolver,
                    localization_lookup,
                ),
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


def _affix_tier_payloads(
    candidates: list[AffixSampleCandidate],
    resolver: RecordRepository,
    localization_lookup: dict[str, LocalizationEntry],
) -> list[dict[str, Any]]:
    """Preserve every concrete reachable affix record and its raw values."""

    tiers: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        source_records = candidate.source_records or (
            candidate.representative_source,
        )
        for source_record in source_records:
            source, separator, logical_path = source_record.partition(":")
            if not separator or source not in resolver.source_names:
                continue
            path = resolver.data_root / source / Path(logical_path)
            if not path.is_file():
                continue
            location = RecordLocation(source, logical_path, path)
            record = resolver.load(location)
            tier_id = f"{source}:{logical_path}"
            tiers[tier_id] = {
                "tier_id": tier_id,
                "source": source,
                "record_path": logical_path,
                "gear_slot": candidate.gear_slot,
                "applicable_slots": list(candidate.applicable_slots),
                "level_requirement": integer_value(
                    record.first_value("levelRequirement")
                ),
                "properties": compile_record_properties(
                    record,
                    resolver=resolver,
                    localization_lookup=localization_lookup,
                ),
                "stat_lines": list(
                    line
                    for line in normalize_record_stat_lines(
                        record,
                        resolver=resolver,
                        localization_lookup=localization_lookup,
                    )
                    if not line.startswith("[Needs mapping]")
                ),
            }
    return sorted(
        tiers.values(),
        key=lambda tier: (
            str(tier["gear_slot"]).casefold(),
            int(tier["level_requirement"]),
            str(tier["source"]),
            str(tier["record_path"]),
        ),
    )


def _variant_payload(
    candidate: AffixSampleCandidate,
    resolver: RecordRepository,
    localization_lookup: dict[str, LocalizationEntry],
) -> dict[str, Any]:
    components: dict[str, dict[str, str]] = {}
    for property_key, role, value in candidate.semantic_components:
        attributes = components.setdefault(property_key, {})
        if value:
            attributes[role] = value
            if role == "skill_reference":
                attributes["display_name"] = resolver.resolve_skill_name(
                    value,
                    localization_lookup,
                )
    if "pet_bonus" in components:
        pet_components = _pet_bonus_components(candidate, resolver)
        if pet_components:
            del components["pet_bonus"]
            components.update(pet_components)
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
        "applicable_slots": list(candidate.applicable_slots),
        "level_requirements": list(candidate.level_requirements),
        "properties": properties,
        "stat_lines": list(candidate.stat_lines),
        "representative_source": candidate.representative_source,
        "source_record_count": candidate.variant_count,
        "stat_layout_count": candidate.stat_layout_count,
    }


def _pet_bonus_components(
    candidate: AffixSampleCandidate,
    resolver: RecordRepository,
) -> dict[str, dict[str, str]]:
    """Expand an affix's referenced pet package into scoreable pet stats."""

    _, record_path = candidate.representative_source.split(":", 1)
    resolved_affix = resolver.resolve(record_path)
    if resolved_affix is None:
        return {}
    _, affix_record = resolved_affix
    pet_reference = (affix_record.first_value("petBonusName") or "").strip()
    resolved_pet = resolver.resolve(pet_reference)
    if resolved_pet is None:
        return {}
    _, pet_record = resolved_pet

    components: dict[str, dict[str, str]] = {}
    for property_key, role, value in record_semantic_fingerprint(pet_record):
        if property_key.startswith("unmapped:"):
            continue
        pet_property_key = f"pet_{property_key}"
        attributes = components.setdefault(
            pet_property_key,
            {"record_reference": pet_reference.lower().replace("\\", "/")},
        )
        if value:
            attributes[role] = value
    return components


def _property_id(property_key: str) -> str:
    if property_key.startswith("unmapped:"):
        return "unmapped"
    return property_key.split(":", maxsplit=1)[0]


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


def _mastery_id(logical_path: str) -> str:
    return next(
        (
            part
            for part in logical_path.split("/")
            if part.startswith("playerclass")
        ),
        "",
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
