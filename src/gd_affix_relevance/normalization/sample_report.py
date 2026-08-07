"""Human-readable random affix samples for normalization stress testing."""

from __future__ import annotations

import random
import re
import secrets
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.affix_discovery import supported_affix_kind
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.normalization.field_inventory import active_value_kind
from gd_affix_relevance.normalization.field_policy import fields_for_semantic_analysis
from gd_affix_relevance.normalization.mapping_proposals import (
    FieldMappingProposal,
    propose_field_mapping,
)
from gd_affix_relevance.slots import (
    ARMOR_SLOTS,
    SLOT_AMULET,
    SLOT_CHEST,
    SLOT_FEET,
    SLOT_HANDS,
    SLOT_HEAD,
    SLOT_LABELS,
    SLOT_LEGS,
    SLOT_MEDAL,
    SLOT_OFF_HAND,
    SLOT_RING,
    SLOT_SHIELD,
    SLOT_SHOULDERS,
    SLOT_WAIST,
    SLOT_WEAPON_1H_CASTER,
    SLOT_WEAPON_1H_MELEE,
    SLOT_WEAPON_1H_RANGED,
    SLOT_WEAPON_2H_MELEE,
    SLOT_WEAPON_2H_RANGED,
    slot_sort_key,
)

DEFAULT_DATA_SOURCES = ("base", "gdx1", "gdx2", "gdx3")
PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True, slots=True)
class AffixSampleCandidate:
    display_name: str
    localization_tag: str
    affix_kind: str
    gear_slot: str
    stat_lines: tuple[str, ...]
    representative_source: str
    variant_count: int = 1
    level_requirements: tuple[int, ...] = ()
    stat_layout_count: int = 1
    semantic_properties: tuple[str, ...] = ()
    semantic_components: tuple[tuple[str, str, str], ...] = ()
    applicable_slots: tuple[str, ...] = ()


@dataclass(slots=True)
class _CandidateGroup:
    display_name: str
    localization_tag: str
    affix_kind: str
    gear_slot: str
    applicable_slots: tuple[str, ...]
    semantic_fingerprint: tuple[tuple[str, str, str], ...]
    preferred_source: str
    representative_record: RawDbrRecord
    sources: set[str] = field(default_factory=set)
    level_requirements: set[int] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class SampleBuildResult:
    candidates: tuple[AffixSampleCandidate, ...]
    seed: int
    candidate_pool_size: int
    unresolved_name_records_skipped: int
    unknown_slot_records_skipped: int


def build_sample_candidates(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...],
    *,
    source_names: tuple[str, ...] = DEFAULT_DATA_SOURCES,
    count: int | None = None,
    seed: int | None = None,
    rank_key: Callable[[tuple[str, ...]], tuple[float, ...]] | None = None,
) -> SampleBuildResult:
    """Build reachable name/slot/stat-fingerprint candidates.

    Logical record paths use expansion overlay semantics: a later source in
    ``source_names`` replaces an earlier definition at the same path.
    """

    root = Path(data_root)
    localization_lookup = first_entry_lookup(localization_entries)
    edges: dict[str, set[str]] = defaultdict(set)
    affix_records: dict[str, tuple[str, RawDbrRecord]] = {}

    for source_name in source_names:
        source_root = root / source_name
        items_root = source_root / "records" / "items"
        if not items_root.exists():
            continue

        for source_path in _relevant_item_paths(items_root):
            logical_path = _logical_path(source_path.relative_to(source_root))
            record = parse_dbr_file(source_path)
            record_edges: set[str] = set()
            for raw_field in record.fields:
                reference = _referenced_item_dbr(raw_field.value)
                if reference is not None:
                    record_edges.add(reference)
            edges[logical_path] = record_edges
            if supported_affix_kind(record) is not None:
                affix_records[logical_path] = (source_name, record)

    slots_by_record = _propagate_gear_slots(edges)
    grouped: dict[
        tuple[str, str, str, tuple[tuple[str, str, str], ...]], _CandidateGroup
    ] = {}
    unresolved_name_records_skipped = 0
    unknown_slot_records_skipped = 0

    for logical_path, (source_name, record) in sorted(affix_records.items()):
        if logical_path not in slots_by_record:
            continue
        localization_tag = record.first_value("lootRandomizerName") or ""
        localization_entry = localization_lookup.get(localization_tag)
        if localization_entry is None:
            unresolved_name_records_skipped += 1
            continue

        applicable_slots = tuple(
            sorted(slots_by_record[logical_path], key=slot_sort_key)
        )
        gear_slot = format_gear_slots(set(applicable_slots))
        if not gear_slot:
            unknown_slot_records_skipped += 1
            continue

        display_name = plain_display_name(localization_entry.value)
        semantic_fingerprint = record_semantic_fingerprint(record)
        kind = supported_affix_kind(record) or ""
        key = (localization_tag, kind, gear_slot, semantic_fingerprint)
        group = grouped.setdefault(
            key,
            _CandidateGroup(
                display_name=display_name,
                localization_tag=localization_tag,
                affix_kind=kind,
                gear_slot=gear_slot,
                applicable_slots=applicable_slots,
                semantic_fingerprint=semantic_fingerprint,
                preferred_source=source_name,
                representative_record=record,
            ),
        )
        group.sources.add(f"{source_name}:{logical_path}")
        if level_requirement := _parse_level_requirement(record):
            group.level_requirements.add(level_requirement)

    pool = sorted(
        grouped.values(),
        key=lambda group: (
            group.display_name.lower(),
            group.gear_slot,
            group.semantic_fingerprint,
        ),
    )
    layout_counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for group in pool:
        layout_counts[
            (group.localization_tag, group.affix_kind, group.gear_slot)
        ] += 1
    actual_seed = secrets.randbits(32) if seed is None else seed
    if rank_key is not None:
        ranked_pool = sorted(
            pool,
            key=lambda group: rank_key(
                _semantic_properties(group.semantic_fingerprint)
            ),
            reverse=True,
        )
        chosen_groups = ranked_pool if count is None else ranked_pool[:count]
    elif count is None:
        chosen_groups = pool
    else:
        if count < 1:
            raise ValueError("count must be at least 1")
        if count > len(pool):
            raise ValueError(
                f"count {count} exceeds the {len(pool)} available candidates"
            )
        chosen_groups = random.Random(actual_seed).sample(pool, count)

    resolver = RecordResolver(root, source_names)
    candidates: list[AffixSampleCandidate] = []
    for group in chosen_groups:
        stat_lines = normalize_record_stat_lines(
            group.representative_record,
            preferred_source=group.preferred_source,
            resolver=resolver,
            localization_lookup=localization_lookup,
        )
        if not stat_lines:
            stat_lines = ("[No active normalized stats]",)
        candidates.append(
            AffixSampleCandidate(
                display_name=group.display_name,
                localization_tag=group.localization_tag,
                affix_kind=group.affix_kind,
                gear_slot=group.gear_slot,
                stat_lines=stat_lines,
                representative_source=min(group.sources),
                variant_count=len(group.sources),
                level_requirements=tuple(sorted(group.level_requirements)),
                stat_layout_count=layout_counts[
                    (group.localization_tag, group.affix_kind, group.gear_slot)
                ],
                semantic_properties=_semantic_properties(
                    group.semantic_fingerprint
                ),
                semantic_components=group.semantic_fingerprint,
                applicable_slots=group.applicable_slots,
            )
        )
    return SampleBuildResult(
        candidates=tuple(candidates),
        seed=actual_seed,
        candidate_pool_size=len(pool),
        unresolved_name_records_skipped=unresolved_name_records_skipped,
        unknown_slot_records_skipped=unknown_slot_records_skipped,
    )


def format_sample_report(
    candidates: tuple[AffixSampleCandidate, ...],
    *,
    seed: int,
    candidate_pool_size: int | None = None,
    unresolved_name_records_skipped: int = 0,
    unknown_slot_records_skipped: int = 0,
) -> str:
    """Render a compact plain-text report for manual Grim Tools comparison."""

    lines = [
        f"Grim Gleaner affix sample (seed {seed})",
        f"Sample size: {len(candidates)}",
    ]
    if candidate_pool_size is not None:
        lines.append(f"Candidate pool: {candidate_pool_size}")
    if unresolved_name_records_skipped:
        lines.append(
            "Skipped records with unresolved affix names: "
            f"{unresolved_name_records_skipped}"
        )
    if unknown_slot_records_skipped:
        lines.append(
            f"Skipped reachable records with unknown gear slots: {unknown_slot_records_skipped}"
        )

    for index, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                "",
                f"{index}. {candidate.display_name}",
                f"   Type: {candidate.affix_kind.title()}",
                f"   Gear slot: {candidate.gear_slot}",
                *(
                    [
                        "   Level requirement(s) for this stat layout: "
                        + ", ".join(map(str, candidate.level_requirements))
                    ]
                    if candidate.level_requirements
                    else []
                ),
                *(
                    [
                        "   Distinct stat layouts for this affix/slot: "
                        f"{candidate.stat_layout_count}"
                    ]
                    if candidate.stat_layout_count > 1
                    else []
                ),
                "   Stats:",
            ]
        )
        lines.extend(f"   - {stat_line}" for stat_line in candidate.stat_lines)
        lines.extend(
            [
                f"   Localization: {candidate.localization_tag}",
                f"   Representative: {candidate.representative_source}",
                f"   Equivalent leveled/source variants: {candidate.variant_count}",
            ]
        )
    return "\n".join(lines) + "\n"


def normalize_record_stat_lines(
    record: RawDbrRecord,
    *,
    preferred_source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> tuple[str, ...]:
    """Turn active raw fields into number-free player-facing stat lines."""

    bundles: dict[str, list[tuple[FieldMappingProposal, str]]] = {}
    order: list[str] = []
    unresolved_fields: list[str] = []

    for raw_field in fields_for_semantic_analysis(record):
        if active_value_kind(raw_field.value) is None:
            continue
        proposal = propose_field_mapping(raw_field.key)
        if proposal is None:
            unresolved_fields.append(raw_field.key)
            continue
        if proposal.status == "ignored" or proposal.component_requirement == "metadata":
            continue
        if proposal.bundle_key not in bundles:
            bundles[proposal.bundle_key] = []
            order.append(proposal.bundle_key)
        bundles[proposal.bundle_key].append((proposal, raw_field.value))

    lines: list[str] = []
    for bundle_key in order:
        components = bundles[bundle_key]
        property_id = components[0][0].property_id
        if property_id == "skill_bonus":
            lines.append(
                _format_skill_bonus(
                    components, preferred_source, resolver, localization_lookup
                )
            )
        elif property_id == "granted_item_skill":
            lines.append(
                _format_granted_skill(
                    components, preferred_source, resolver, localization_lookup
                )
            )
        elif property_id == "pet_bonus":
            lines.extend(
                _format_pet_bonus(
                    components, preferred_source, resolver, localization_lookup
                )
            )
        elif property_id == "damage_conversion":
            lines.append(_format_damage_conversion(components))
        else:
            lines.append(_format_generic_bundle(components))

    lines.extend(f"[Needs mapping] {raw_field}" for raw_field in unresolved_fields)
    return tuple(dict.fromkeys(lines))


def format_gear_slots(slots: set[str] | frozenset[str]) -> str:
    """Compress atomic loot-table slots into Grim Tools-style applicability."""

    remaining = set(slots)
    labels: list[str] = []
    armor_slots = set(ARMOR_SLOTS)
    all_weapon_slots = {
        SLOT_WEAPON_1H_MELEE,
        SLOT_WEAPON_2H_MELEE,
        SLOT_WEAPON_1H_CASTER,
        SLOT_WEAPON_1H_RANGED,
        SLOT_WEAPON_2H_RANGED,
    }
    one_handed_slots = {
        SLOT_WEAPON_1H_MELEE,
        SLOT_WEAPON_1H_CASTER,
        SLOT_WEAPON_1H_RANGED,
    }
    two_handed_slots = {SLOT_WEAPON_2H_MELEE, SLOT_WEAPON_2H_RANGED}
    if armor_slots <= remaining:
        labels.append("All armor")
        remaining -= armor_slots
    if {SLOT_RING, SLOT_AMULET} <= remaining:
        labels.append("Rings, Amulets")
        remaining -= {SLOT_RING, SLOT_AMULET}
    if all_weapon_slots <= remaining:
        labels.append("All weapons")
        remaining -= all_weapon_slots
    else:
        if one_handed_slots <= remaining:
            labels.append("All one-handed weapons")
            remaining -= one_handed_slots
        if two_handed_slots <= remaining:
            labels.append("All two-handed weapons")
            remaining -= two_handed_slots
    labels.extend(
        SLOT_LABELS.get(slot, slot)
        for slot in sorted(remaining, key=slot_sort_key)
    )
    return "; ".join(labels)


def abstract_display_template(template: str) -> str:
    """Replace semantic placeholders with stable ``[x]``, ``[y]`` markers."""

    names: dict[str, str] = {}
    symbols = iter("xyzabcdefghijklmnopqrstuvw")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        names.setdefault(name, f"[{next(symbols)}]")
        return names[name]

    return PLACEHOLDER_PATTERN.sub(replace, template)


def _format_generic_bundle(
    components: list[tuple[FieldMappingProposal, str]],
) -> str:
    templates = [proposal.display_template for proposal, _ in components if proposal.display_template]
    if templates:
        template = max(templates, key=lambda value: len(set(PLACEHOLDER_PATTERN.findall(value))))
        return abstract_display_template(template)

    proposals = [proposal for proposal, _ in components]
    label = proposals[0].display_label
    roles = {proposal.value_role for proposal in proposals}
    if {"duration_min", "damage_min"} <= roles:
        damage = "[y]-[z]" if "damage_max" in roles else "[y]"
        duration = "[w]-[v]" if "duration_max" in roles else "[z]"
        prefix = "[x]% Chance of " if "chance_percent" in roles else ""
        if not prefix:
            damage = damage.replace("[y]", "[x]").replace("[z]", "[y]")
            duration = duration.replace("[z]", "[y]")
        return f"{prefix}{damage} {label} over {duration} Seconds"
    if {"damage_min", "damage_max"} <= roles:
        if "chance_percent" in roles:
            return f"[x]% Chance of [y]-[z] {label}"
        return f"[x]-[y] {label}"
    if "damage_min" in roles:
        if "chance_percent" in roles:
            return f"[x]% Chance of [y] {label}"
        return f"[x] {label}"
    if "damage_percent" in roles:
        line = f"+[x]% {label}"
        if "duration_percent" in roles:
            line += " with +[y]% Increased Duration"
        if "chance_percent" in roles:
            line = f"[z]% Chance of {line}"
        return line
    if any("percent" in role for role in roles):
        return f"+[x]% {label}"
    return f"+[x] {label}"


def _format_damage_conversion(
    components: list[tuple[FieldMappingProposal, str]],
) -> str:
    values = {proposal.value_role: value for proposal, value in components}
    source = _display_damage_type(values.get("source_damage_type", "Source"))
    destination = _display_damage_type(
        values.get("destination_damage_type", "Destination")
    )
    return f"[x]% {source} Damage converted to {destination} Damage"


def _display_damage_type(raw_damage_type: str) -> str:
    aliases = {
        "life": "Vitality",
        "poison": "Acid",
    }
    return aliases.get(raw_damage_type.lower(), raw_damage_type.title())


def _format_skill_bonus(
    components: list[tuple[FieldMappingProposal, str]],
    preferred_source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> str:
    reference = next(
        (value for proposal, value in components if proposal.value_role == "skill_reference"),
        "",
    )
    skill_name = resolver.resolve_skill_name(
        reference, preferred_source, localization_lookup
    )
    return f"+[x] to {skill_name}"


def _format_granted_skill(
    components: list[tuple[FieldMappingProposal, str]],
    preferred_source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> str:
    reference = next(
        (value for proposal, value in components if proposal.value_role == "skill_reference"),
        "",
    )
    skill_name = resolver.resolve_skill_name(
        reference, preferred_source, localization_lookup
    )
    return f"Granted Skill: {skill_name}"


def _format_pet_bonus(
    components: list[tuple[FieldMappingProposal, str]],
    preferred_source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> tuple[str, ...]:
    reference = next((value for _, value in components), "")
    resolved = resolver.resolve(reference, preferred_source)
    if resolved is None:
        return (f"Bonus to All Pets: [unresolved {reference}]",)
    source_name, pet_record = resolved
    nested = normalize_record_stat_lines(
        pet_record,
        preferred_source=source_name,
        resolver=resolver,
        localization_lookup=localization_lookup,
    )
    return tuple(f"Bonus to All Pets: {line}" for line in nested)


class RecordResolver:
    def __init__(self, data_root: Path, source_names: tuple[str, ...]) -> None:
        self.data_root = Path(data_root)
        self.source_names = source_names
        self._cache: dict[tuple[str, str], tuple[str, RawDbrRecord] | None] = {}

    def resolve(
        self, reference: str, preferred_source: str
    ) -> tuple[str, RawDbrRecord] | None:
        logical = _logical_path(reference)
        cache_key = (preferred_source, logical)
        if cache_key in self._cache:
            return self._cache[cache_key]
        if not logical.endswith(".dbr"):
            self._cache[cache_key] = None
            return None

        search_order = [preferred_source]
        search_order.extend(
            source
            for source in reversed(self.source_names)
            if source != preferred_source
        )
        for source_name in search_order:
            source_path = self.data_root / source_name / Path(logical)
            if source_path.is_file():
                result = (source_name, parse_dbr_file(source_path))
                self._cache[cache_key] = result
                return result
        self._cache[cache_key] = None
        return None

    def resolve_skill_name(
        self,
        reference: str,
        preferred_source: str,
        localization_lookup: dict[str, LocalizationEntry],
    ) -> str:
        pending: deque[tuple[str, str, int]] = deque(
            [(reference, preferred_source, 0)]
        )
        seen: set[str] = set()
        fallback_description = ""
        while pending:
            current_reference, current_source, depth = pending.popleft()
            logical = _logical_path(current_reference)
            if logical in seen or depth > 4:
                continue
            seen.add(logical)
            resolved = self.resolve(current_reference, current_source)
            if resolved is None:
                continue
            resolved_source, record = resolved
            display_tag = record.first_value("skillDisplayName")
            if display_tag:
                entry = localization_lookup.get(display_tag) or localization_lookup.get(
                    display_tag.casefold()
                )
                if entry is not None:
                    return plain_display_name(entry.value)
                return f"[{display_tag}]"
            description = record.first_value("FileDescription") or ""
            if description and not fallback_description:
                fallback_description = description
            for raw_field in record.fields:
                if raw_field.value.lower().startswith("records/skills/") and raw_field.value.lower().endswith(".dbr"):
                    pending.append((raw_field.value, resolved_source, depth + 1))

        if fallback_description:
            concise = re.split(r"\s+with\s+", fallback_description, maxsplit=1, flags=re.IGNORECASE)[0]
            return concise.strip().title()
        return f"[unresolved skill: {reference}]"


def _logical_path(path: Path | str) -> str:
    return str(path).replace("\\", "/").strip().lower()


def _referenced_item_dbr(value: str) -> str | None:
    normalized = _logical_path(value)
    if not normalized.startswith("records/items/") or not normalized.endswith(".dbr"):
        return None
    return normalized


def _relevant_item_paths(items_root: Path) -> tuple[Path, ...]:
    """Return only DBRs needed for affix reachability and sampling."""

    paths: set[Path] = set()
    loottables = items_root / "loottables"
    if loottables.exists():
        paths.update(loottables.rglob("*.dbr"))
    affix_root = items_root / "lootaffixes"
    for kind, table_directory in (
        ("prefix", "prefixtables"),
        ("suffix", "suffixtables"),
    ):
        kind_root = affix_root / kind
        if not kind_root.exists():
            continue
        paths.update(kind_root.glob("*.dbr"))
        tables = kind_root / table_directory
        if tables.exists():
            paths.update(tables.rglob("*.dbr"))
    return tuple(sorted(paths))


def record_semantic_fingerprint(
    record: RawDbrRecord,
) -> tuple[tuple[str, str, str], ...]:
    """Fingerprint stat presence before expensive reference humanization."""

    components: list[tuple[str, str, str]] = []
    for raw_field in fields_for_semantic_analysis(record):
        if active_value_kind(raw_field.value) is None:
            continue
        proposal = propose_field_mapping(raw_field.key)
        if proposal is None:
            components.append((f"unmapped:{raw_field.key}", "component", ""))
            continue
        if proposal.status == "ignored" or proposal.component_requirement == "metadata":
            continue
        distinguishing_value = ""
        if proposal.value_role in {
            "skill_reference",
            "source_damage_type",
            "destination_damage_type",
        }:
            distinguishing_value = _logical_path(raw_field.value)
        elif proposal.property_id == "pet_bonus":
            distinguishing_value = re.sub(
                r"_\d+(?=\.dbr$)", "_[tier]", _logical_path(raw_field.value)
            )
        components.append(
            (proposal.bundle_key, proposal.value_role, distinguishing_value)
        )
    return tuple(sorted(components))


def _semantic_properties(
    fingerprint: tuple[tuple[str, str, str], ...],
) -> tuple[str, ...]:
    return tuple(sorted({bundle_key for bundle_key, _, _ in fingerprint}))


def _parse_level_requirement(record: RawDbrRecord) -> int | None:
    raw_level = record.first_value("levelRequirement")
    if not raw_level:
        return None
    try:
        return int(float(raw_level))
    except ValueError:
        return None


def _propagate_gear_slots(edges: dict[str, set[str]]) -> dict[str, set[str]]:
    slots_by_record: dict[str, set[str]] = defaultdict(set)
    pending: deque[str] = deque()
    for logical_path in edges:
        slots = _slots_from_loottable_path(logical_path)
        if not slots:
            continue
        slots_by_record[logical_path].update(slots)
        pending.append(logical_path)

    while pending:
        parent = pending.popleft()
        parent_slots = slots_by_record[parent]
        for child in edges.get(parent, ()):
            added = parent_slots - slots_by_record[child]
            if not added:
                continue
            slots_by_record[child].update(added)
            pending.append(child)
    return slots_by_record


def _slots_from_loottable_path(logical_path: str) -> set[str]:
    prefix = "records/items/loottables/"
    if not logical_path.startswith(prefix):
        return set()
    relative = logical_path[len(prefix) :]
    filename = Path(relative).stem.lower()
    top_directory = relative.split("/", maxsplit=1)[0]
    fixed_directories = {
        "gearhead": SLOT_HEAD,
        "gearshoulders": SLOT_SHOULDERS,
        "geartorso": SLOT_CHEST,
        "gearhands": SLOT_HANDS,
        "gearlegs": SLOT_LEGS,
        "gearfeet": SLOT_FEET,
    }
    if top_directory in fixed_directories:
        return {fixed_directories[top_directory]}
    if top_directory == "gearaccessories":
        if "necklace" in filename:
            return {SLOT_AMULET}
        if "ring" in filename:
            return {SLOT_RING}
        if "medal" in filename:
            return {SLOT_MEDAL}
        if "waist" in filename:
            return {SLOT_WAIST}
    if top_directory in {"weapons", "damagetables"} or "damagetables/" in relative:
        if "shield+focus" in filename:
            return set()
        if "focus" in filename:
            return {SLOT_OFF_HAND}
        if "shield" in filename:
            return {SLOT_SHIELD}
        if "caster" in filename:
            return {SLOT_WEAPON_1H_CASTER}
        if "gun2h" in filename or "ranged2h" in filename:
            return {SLOT_WEAPON_2H_RANGED}
        if "gun1h" in filename or "ranged1h" in filename:
            return {SLOT_WEAPON_1H_RANGED}
        if "melee2h" in filename:
            return {SLOT_WEAPON_2H_MELEE}
        if "1h" in filename:
            return {SLOT_WEAPON_1H_MELEE}
    return set()
