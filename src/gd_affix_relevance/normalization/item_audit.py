"""Exploratory audit for fixed item stat packages and MI skill modifiers."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    plain_display_name,
)
from gd_affix_relevance.normalization.field_inventory import active_value_kind
from gd_affix_relevance.normalization.mapping_proposals import propose_field_mapping
from gd_affix_relevance.normalization.sample_report import (
    RecordResolver,
    normalize_record_stat_lines,
)


TARGET_GROUPS = frozenset(
    {"monster_infrequent", "crafted_rare", "epic", "legendary"}
)

# Active item-template fields that describe the object rather than an intrinsic
# gameplay bonus. They remain available to a future ItemCatalog, but they do not
# represent categories that should be added to the affix/profile scorer.
ITEM_METADATA_FIELDS = frozenset(
    {
        "Class",
        "FileDescription",
        "armor",
        "armorClassification",
        "armorNativeBase",
        "armorNativeMax",
        "attributeScalePercent",
        "bitmap",
        "castsShadows",
        "dropSound",
        "dropSound3D",
        "dropSoundWater",
        "itemClassification",
        "itemCostName",
        "itemLevel",
        "itemNameTag",
        "itemSetName",
        "itemStyleTag",
        "itemText",
        "levelRequirement",
        "marketAdjustmentPercent",
        "maxTransparency",
        "mesh",
        "outlineThickness",
        "physicsFriction",
        "physicsMass",
        "scale",
        "shader",
        "templateName",
    }
)
ITEM_METADATA_PREFIXES = (
    "actor",
    "armorFemale",
    "armorMale",
    "armorNative",
    "baseTexture",
    "bump",
    "equipSound",
    "lootRandomizer",
    "physics",
    "selfIllumination",
    "specular",
    "texture",
    "glowTexture",
    "unequipSound",
)
ITEM_METADATA_SUFFIXES = (
    "Requirement",
    "RequirementEquation",
)

SPECIAL_GAMEPLAY_FIELDS = {
    "characterDeflectProjectile": "projectile_deflection",
    "offensiveSlowTotalSpeedChance": "total_speed_reduction",
    "offensiveSlowTotalSpeedDurationMin": "total_speed_reduction",
    "offensiveSlowTotalSpeedMin": "total_speed_reduction",
    "racialBonusPercentDefense": "racial_defense_bonus",
    "retaliationConfusionMin": "confusion_retaliation",
    "retaliationSlowManaLeachDurationMin": "energy_burn_retaliation",
    "retaliationSlowManaLeachMin": "energy_burn_retaliation",
}

MODIFIER_SPECIAL_FIELDS = {
    "skillActiveDuration": "skill_modifier_duration",
    "skillCooldownTime": "skill_modifier_cooldown",
    "weaponDamagePct": "skill_modifier_weapon_damage",
}


@dataclass(frozen=True, slots=True)
class ItemAuditRecord:
    source_path: str
    filename_family: str
    group: str
    classification: str
    name_tag: str
    display_name: str
    description: str
    item_set: str
    mapped_property_ids: tuple[str, ...]
    new_property_ids: tuple[str, ...]
    stat_lines: tuple[str, ...]
    skill_modifier_pairs: tuple[tuple[str, str], ...]
    unresolved_gameplay_fields: tuple[str, ...]
    modifier_reference_failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemAuditResult:
    source: str
    item_directory: str
    records: tuple[ItemAuditRecord, ...]
    affix_property_ids: tuple[str, ...]

    @property
    def target_records(self) -> tuple[ItemAuditRecord, ...]:
        return tuple(record for record in self.records if record.group in TARGET_GROUPS)


def build_item_audit(
    data_root: Path,
    localization_entries: tuple[LocalizationEntry, ...] = (),
    *,
    source_name: str = "base",
    item_directory: str = "gearhead",
    affix_property_ids: set[str] | frozenset[str] = frozenset(),
    source_names: tuple[str, ...] = ("base", "gdx1", "gdx2", "gdx3"),
) -> ItemAuditResult:
    """Audit one extracted item directory without compiling an ItemCatalog."""

    root = Path(data_root)
    item_root = root / source_name / "records" / "items" / item_directory
    if not item_root.is_dir():
        raise FileNotFoundError(f"item directory not found: {item_root}")

    localization_lookup = first_entry_lookup(localization_entries)
    resolver = RecordResolver(root, source_names)
    records: list[ItemAuditRecord] = []
    for path in sorted(item_root.glob("*.dbr")):
        raw = parse_dbr_file(path)
        group = _classify_item(path, raw)
        mapped, new, skill_pairs, unknown, failures = _semantic_details(
            raw,
            source_name=source_name,
            resolver=resolver,
            affix_property_ids=affix_property_ids,
        )
        raw_lines = normalize_record_stat_lines(
            raw,
            preferred_source=source_name,
            resolver=resolver,
            localization_lookup=localization_lookup,
        )
        lines = [line for line in raw_lines if not line.startswith("[Needs mapping]")]
        for modified_skill, modifier_record in skill_pairs:
            skill_name = resolver.resolve_skill_name(
                modified_skill, source_name, localization_lookup
            )
            resolved = resolver.resolve(modifier_record, source_name)
            if resolved is None:
                lines.append(f"Skill Modifier for {skill_name}: [unresolved record]")
                continue
            modifier_source, modifier = resolved
            nested = normalize_record_stat_lines(
                modifier,
                preferred_source=modifier_source,
                resolver=resolver,
                localization_lookup=localization_lookup,
            )
            nested = tuple(
                line for line in nested if not line.startswith("[Needs mapping]")
            )
            if nested:
                lines.extend(f"Skill Modifier for {skill_name}: {line}" for line in nested)
            else:
                lines.append(f"Skill Modifier for {skill_name}: [no mapped stats]")

        for property_id in sorted(new):
            if property_id == "mastery_bonus":
                lines.append("+[x] to All Skills in a Mastery")
            elif property_id == "projectile_deflection":
                lines.append("+[x]% Chance to Deflect Projectiles")

        name_tag = raw.first_value("itemNameTag") or ""
        entry = localization_lookup.get(name_tag)
        description = raw.first_value("FileDescription") or ""
        display_name = (
            plain_display_name(entry.value)
            if entry is not None
            else description or f"[{name_tag or path.stem}]"
        )
        records.append(
            ItemAuditRecord(
                source_path=path.relative_to(root).as_posix(),
                filename_family=path.name[:1].lower(),
                group=group,
                classification=raw.first_value("itemClassification") or "",
                name_tag=name_tag,
                display_name=display_name,
                description=description,
                item_set=raw.first_value("itemSetName") or "",
                mapped_property_ids=tuple(sorted(mapped)),
                new_property_ids=tuple(sorted(new)),
                stat_lines=tuple(dict.fromkeys(lines)),
                skill_modifier_pairs=tuple(skill_pairs),
                unresolved_gameplay_fields=tuple(sorted(unknown)),
                modifier_reference_failures=tuple(sorted(failures)),
            )
        )

    return ItemAuditResult(
        source=source_name,
        item_directory=item_directory,
        records=tuple(records),
        affix_property_ids=tuple(sorted(affix_property_ids)),
    )


def format_item_audit_report(result: ItemAuditResult) -> str:
    """Render a compact Markdown feasibility report."""

    prefix_class = Counter(
        (record.filename_family, record.classification) for record in result.records
    )
    group_records: dict[str, list[ItemAuditRecord]] = defaultdict(list)
    for record in result.records:
        group_records[record.group].append(record)

    lines = [
        f"# Item stat audit: {result.source}/{result.item_directory}",
        "",
        "This treats an item's fixed intrinsic bonuses as a stat package. Random prefix/suffix affixes and base armor/requirements are outside this count.",
        "",
        "## Filename families",
        "",
        "| Initial | DBR classification | Records |",
        "|---|---|---:|",
    ]
    for (initial, classification), count in sorted(prefix_class.items()):
        lines.append(f"| `{initial}` | {classification or '(blank)'} | {count} |")

    lines.extend(
        [
            "",
            "## Target coverage",
            "",
            "| Group | Records | Unique name tags | Unique stat layouts | Records with mapped stats | Sets |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for group in ("monster_infrequent", "crafted_rare", "epic", "legendary"):
        records = group_records.get(group, [])
        name_tags = {record.name_tag for record in records if record.name_tag}
        layouts = {
            (
                record.mapped_property_ids,
                record.new_property_ids,
                record.skill_modifier_pairs,
                record.unresolved_gameplay_fields,
            )
            for record in records
        }
        mapped_count = sum(bool(record.mapped_property_ids) for record in records)
        sets = {record.item_set for record in records if record.item_set}
        lines.append(
            f"| {_group_label(group)} | {len(records)} | {len(name_tags)} | "
            f"{len(layouts)} | {mapped_count} | {len(sets)} |"
        )
    placeholder_count = len(group_records.get("placeholder", []))
    if placeholder_count:
        lines.extend(
            [
                "",
                f"Excluded from target coverage: {placeholder_count} `BASE BLANK` placeholder record(s).",
            ]
        )

    new_fields = Counter()
    unresolved = Counter()
    modifier_pairs = 0
    modifier_failures = 0
    for record in result.target_records:
        new_fields.update(record.new_property_ids)
        unresolved.update(record.unresolved_gameplay_fields)
        modifier_pairs += len(record.skill_modifier_pairs)
        modifier_failures += len(record.modifier_reference_failures)

    lines.extend(
        [
            "",
            "## New machinery or mappings",
            "",
            f"- MI skill-modifier pairs: {modifier_pairs} across "
            f"{sum(bool(record.skill_modifier_pairs) for record in result.target_records)} records; "
            f"unresolved modifier records: {modifier_failures}.",
        ]
    )
    if new_fields:
        lines.append(
            "- Meaningful properties absent from, or structurally different from, the current affix catalog: "
            + ", ".join(f"`{field}` ({count})" for field, count in new_fields.most_common())
            + "."
        )
    else:
        lines.append("- No new meaningful property families were found.")
    if unresolved:
        lines.append(
            "- Still-unclassified active gameplay candidates: "
            + ", ".join(f"`{field}` ({count})" for field, count in unresolved.most_common())
            + "."
        )
    else:
        lines.append("- No active gameplay-looking fields remain unclassified.")

    lines.extend(["", "## Representative items"])
    for group in ("monster_infrequent", "crafted_rare", "epic", "legendary"):
        records = group_records.get(group, [])
        if not records:
            continue
        lines.extend(["", f"### {_group_label(group)}"])
        representatives = _representatives(records, limit=3)
        for record in representatives:
            lines.extend(
                [
                    "",
                    f"- **{record.display_name}** (`{Path(record.source_path).name}`)",
                    *(
                        [f"  - {stat_line}" for stat_line in record.stat_lines]
                        if record.stat_lines
                        else ["  - No currently mapped intrinsic stats"]
                    ),
                ]
            )

    lines.extend(
        [
            "",
            "## Feasibility read",
            "",
            "- Epic and Legendary fixed stats mostly reuse the existing normalization and weighting categories. They principally need ItemCatalog records, set metadata, mastery-wide skill bonuses, and a small number of additional field mappings.",
            "- Crafted Rare fixed packages are the same easy case; the filename initial alone does not identify them.",
            "- Monster Infrequents are moderate rather than prohibitive: their direct stats already normalize, while skill modifiers require resolving and scoring the referenced modifier DBR in the context of its modified player skill.",
            "- `m` is not a rarity in this sample. Its records are Common model/tint variants sharing ordinary base-item name tags.",
        ]
    )
    return "\n".join(lines) + "\n"


def _classify_item(path: Path, record: RawDbrRecord) -> str:
    initial = path.name[:1].lower()
    classification = (record.first_value("itemClassification") or "").casefold()
    description = (record.first_value("FileDescription") or "").casefold()
    if "base blank" in description:
        return "placeholder"
    if classification == "epic":
        return "epic"
    if classification == "legendary":
        return "legendary"
    if initial == "b" and classification == "rare":
        return "crafted_rare" if "crafted" in description else "monster_infrequent"
    if initial == "m":
        return "model_variant"
    if initial == "b":
        return "common_b_variant"
    if initial == "a":
        return "common_base"
    return "other"


def _semantic_details(
    record: RawDbrRecord,
    *,
    source_name: str,
    resolver: RecordResolver,
    affix_property_ids: set[str] | frozenset[str],
) -> tuple[set[str], set[str], list[tuple[str, str]], set[str], set[str]]:
    mapped: set[str] = set()
    new: set[str] = set()
    unknown: set[str] = set()
    failures: set[str] = set()

    active = {
        field.key: field.value
        for field in record.fields
        if active_value_kind(field.value) is not None
    }
    skill_pairs = _indexed_reference_pairs(
        active, "modifiedSkillName", "modifierSkillName"
    )
    handled = {
        key
        for prefix in ("modifiedSkillName", "modifierSkillName")
        for key in active
        if key.startswith(prefix)
    }
    mastery_pairs = _indexed_reference_pairs(
        active, "augmentMasteryName", "augmentMasteryLevel"
    )
    if mastery_pairs:
        new.add("mastery_bonus")
    handled.update(
        key
        for prefix in ("augmentMasteryName", "augmentMasteryLevel")
        for key in active
        if key.startswith(prefix)
    )

    for field in record.fields:
        if field.key in handled or active_value_kind(field.value) is None:
            continue
        special = SPECIAL_GAMEPLAY_FIELDS.get(field.key)
        if special is not None:
            new.add(special)
            continue
        proposal = propose_field_mapping(field.key)
        if proposal is not None:
            if proposal.status != "ignored" and proposal.component_requirement != "metadata":
                mapped.add(proposal.property_id)
                if affix_property_ids and proposal.property_id not in affix_property_ids:
                    new.add(proposal.property_id)
            continue
        if _is_item_metadata(field.key):
            continue
        unknown.add(field.key)

    if skill_pairs:
        new.add("skill_modifier")
    for _, modifier_reference in skill_pairs:
        resolved = resolver.resolve(modifier_reference, source_name)
        if resolved is None:
            failures.add(modifier_reference)
            continue
        _, modifier = resolved
        for field in modifier.fields:
            if active_value_kind(field.value) is None:
                continue
            special = MODIFIER_SPECIAL_FIELDS.get(field.key)
            if special is not None:
                new.add(special)
                continue
            proposal = propose_field_mapping(field.key)
            if proposal is None:
                if not _is_modifier_metadata(field.key):
                    unknown.add(f"modifier:{field.key}")
                continue
            if proposal.status == "ignored" or proposal.component_requirement == "metadata":
                continue
            mapped.add(proposal.property_id)
            if affix_property_ids and proposal.property_id not in affix_property_ids:
                new.add(proposal.property_id)

    return mapped, new, skill_pairs, unknown, failures


def _indexed_reference_pairs(
    active: dict[str, str], left_prefix: str, right_prefix: str
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, value in sorted(active.items()):
        match = re.fullmatch(re.escape(left_prefix) + r"(\d+)", key)
        if match is None:
            continue
        other = active.get(f"{right_prefix}{match.group(1)}")
        if other:
            pairs.append((value, other))
    return pairs


def _is_item_metadata(key: str) -> bool:
    return (
        key in ITEM_METADATA_FIELDS
        or key.startswith(ITEM_METADATA_PREFIXES)
        or key.endswith(ITEM_METADATA_SUFFIXES)
    )


def _is_modifier_metadata(key: str) -> bool:
    return _is_item_metadata(key) or key in {
        "Axe",
        "Mace",
        "Magical",
        "Shield",
        "Spear",
        "Staff",
        "Sword",
        "dualWieldOnly",
        "excludeRacialDamage",
        "fxChanges",
        "isPetDisplayable",
        "skillMasteryLevelRequired",
        "skillMaxLevel",
    }


def _representatives(
    records: list[ItemAuditRecord], *, limit: int
) -> tuple[ItemAuditRecord, ...]:
    chosen: list[ItemAuditRecord] = []
    seen_layouts: set[tuple[object, ...]] = set()
    for record in records:
        layout = (
            record.mapped_property_ids,
            record.new_property_ids,
            record.skill_modifier_pairs,
            record.unresolved_gameplay_fields,
        )
        if layout in seen_layouts:
            continue
        seen_layouts.add(layout)
        chosen.append(record)
        if len(chosen) == limit:
            break
    return tuple(chosen)


def _group_label(group: str) -> str:
    return {
        "monster_infrequent": "Monster Infrequent candidates",
        "crafted_rare": "Crafted Rare",
        "epic": "Epic",
        "legendary": "Legendary",
    }.get(group, group.replace("_", " ").title())
