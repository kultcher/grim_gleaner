"""Compile concrete item records into deterministic family payloads."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any, Iterable

from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.importers.localization_parser import plain_display_name
from gd_affix_relevance.normalization.field_inventory import active_value_kind
from gd_affix_relevance.normalization.field_policy import fields_for_semantic_analysis
from gd_affix_relevance.normalization.item_audit import (
    MODIFIER_SPECIAL_FIELDS,
    SPECIAL_GAMEPLAY_FIELDS,
)
from gd_affix_relevance.normalization.mapping_proposals import (
    chance_damage_bundle_keys,
    contextualize_damage_chance,
    propose_field_mapping,
)
from gd_affix_relevance.normalization.sample_report import (
    RecordResolver,
    normalize_record_stat_lines,
    record_semantic_fingerprint,
)


ITEM_SCOPE = "named_equipment_components_augments_relics_runes_and_consumables"
ITEM_FAMILIES = (
    "equipment",
    "components",
    "augments",
    "relics",
    "runes",
    "consumables",
)

EQUIPMENT_BRANCHES = (
    "gearhead",
    "gearshoulders",
    "geartorso",
    "gearhands",
    "gearlegs",
    "gearfeet",
    "gearweapons",
    "gearaccessories",
    "upgraded",
    "awakened",
    "faction",
    "crafting",
    "questitems",
)

EQUIPMENT_SLOTS = {
    "ArmorProtective_Head": "Head",
    "ArmorProtective_Shoulders": "Shoulders",
    "ArmorProtective_Chest": "Chest",
    "ArmorProtective_Hands": "Hands",
    "ArmorProtective_Legs": "Legs",
    "ArmorProtective_Feet": "Feet",
    "ArmorProtective_Waist": "Waist",
    "ArmorJewelry_Ring": "Ring",
    "ArmorJewelry_Amulet": "Amulet",
    "ArmorJewelry_Medal": "Medal",
    "WeaponArmor_Shield": "Shield",
    "WeaponArmor_Offhand": "Off-hand",
}

APPLICABLE_SLOT_FIELDS = {
    "amulet": "Amulet",
    "axe": "Axe",
    "axe2h": "Two-handed axe",
    "bracelet": "Ring",
    "chest": "Chest",
    "dagger": "Dagger",
    "feet": "Feet",
    "hands": "Hands",
    "head": "Head",
    "legs": "Legs",
    "mace": "Mace",
    "mace2h": "Two-handed mace",
    "medal": "Medal",
    "offhand": "Off-hand",
    "ranged1h": "One-handed ranged weapon",
    "ranged2h": "Two-handed ranged weapon",
    "ring": "Ring",
    "scepter": "Scepter",
    "shield": "Shield",
    "shoulders": "Shoulders",
    "spear": "Spear",
    "spear2h": "Two-handed spear",
    "staff": "Staff",
    "sword": "Sword",
    "sword2h": "Two-handed sword",
    "waist": "Waist",
}

CONSUMABLE_CLASSES = frozenset(
    {
        "ItemAttributeReset",
        "ItemDevotionReset",
        "ItemDifficultyUnlock",
        "ItemFactionBooster",
        "ItemFactionWarrant",
        "ItemUsableSkill",
        "OneShot_Food",
        "OneShot_PotionHealth",
        "OneShot_PotionMana",
        "OneShot_Scroll",
    }
)

ITEM_REFERENCE_FIELDS = frozenset(
    {
        "itemSkillAutoController",
        "itemSkillLevelEq",
        "itemSkillName",
    }
)


def compile_item_payloads(
    data_root: Path,
    source_names: tuple[str, ...],
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    """Compile requested concrete item families and return coverage counts."""

    root = Path(data_root)
    resolver = RecordResolver(root, source_names)
    localization_lookup = dict(exact_names)
    for folded, entry in folded_names.items():
        localization_lookup.setdefault(folded, entry)

    records = _discover_records(root, source_names)
    crafted_item_paths = _discover_crafted_item_paths(root, source_names)
    faction_vendor_sources = _discover_faction_vendor_sources(
        root, source_names, resolver
    )
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        family: defaultdict(list) for family in ITEM_FAMILIES
    }
    identity: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    unresolved_names = 0

    for family in ITEM_FAMILIES:
        for source, logical_path, path in records[family]:
            record = parse_dbr_file(path)
            name_tag = _name_tag(record, family)
            if not name_tag:
                continue
            name_entry = exact_names.get(name_tag) or folded_names.get(name_tag.casefold())
            if name_entry is None:
                unresolved_names += 1
                continue
            display_name = plain_display_name(name_entry.value)
            name_resolution = "localized"
            strings[name_tag] = display_name

            description_tag = (record.first_value("itemText") or "").strip()
            description = ""
            if description_tag:
                description_entry = exact_names.get(description_tag) or folded_names.get(
                    description_tag.casefold()
                )
                if description_entry is not None:
                    description = plain_display_name(description_entry.value)
                    strings[description_tag] = description

            properties = _property_payloads(
                record,
                source=source,
                resolver=resolver,
                localization_lookup=localization_lookup,
            )
            lines = list(
                line
                for line in normalize_record_stat_lines(
                    record,
                    preferred_source=source,
                    resolver=resolver,
                    localization_lookup=localization_lookup,
                )
                if not line.startswith("[Needs mapping]")
            )
            mastery_lines = _mastery_stat_lines(
                record, source, resolver, localization_lookup
            )
            lines.extend(mastery_lines)
            skill_modifiers = _skill_modifier_payloads(
                record, source, resolver, localization_lookup
            )
            for modifier in skill_modifiers:
                lines.extend(
                    f"Skill Modifier for {modifier['modified_skill_name']}: {line}"
                    for line in modifier["stat_lines"]
                )

            granted_reference = (record.first_value("itemSkillName") or "").strip()
            granted_name = (
                resolver.resolve_skill_name(
                    granted_reference, source, localization_lookup
                )
                if granted_reference
                else ""
            )
            effect_reference = (record.first_value("skillName") or "").strip()
            effect_name = ""
            effect_properties: list[dict[str, Any]] = []
            effect_stat_lines: tuple[str, ...] = ()
            if effect_reference:
                effect_name = resolver.resolve_skill_name(
                    effect_reference, source, localization_lookup
                )
                resolved_effect = resolver.resolve(effect_reference, source)
                if resolved_effect is not None:
                    effect_source, effect_record = resolved_effect
                    effect_properties = _property_payloads(
                        effect_record,
                        source=effect_source,
                        resolver=resolver,
                        localization_lookup=localization_lookup,
                        modifier=True,
                    )
                    effect_stat_lines = tuple(
                        line
                        for line in normalize_record_stat_lines(
                            effect_record,
                            preferred_source=effect_source,
                            resolver=resolver,
                            localization_lookup=localization_lookup,
                        )
                        if not line.startswith("[Needs mapping]")
                    )
            set_reference = (record.first_value("itemSetName") or "").strip()
            set_name = ""
            if set_reference:
                resolved_set = resolver.resolve(set_reference, source)
                if resolved_set is not None:
                    _, set_record = resolved_set
                    set_tag = (set_record.first_value("setName") or "").strip()
                    set_entry = exact_names.get(set_tag) or folded_names.get(
                        set_tag.casefold()
                    )
                    if set_entry is not None:
                        set_name = plain_display_name(set_entry.value)
                        strings[set_tag] = set_name
            faction_source, faction_name = _faction_metadata(
                record,
                exact_names,
                folded_names,
                strings,
            )
            vendor_sources = _vendor_source_payloads(
                faction_vendor_sources.get(logical_path, ()),
                exact_names,
                folded_names,
                strings,
            )
            variant = {
                "source": source,
                "record_path": logical_path,
                "category": _item_category(family, logical_path, record),
                "rarity": (record.first_value("itemClassification") or "").strip(),
                "item_class": (record.first_value("Class") or "").strip(),
                "gear_slot": _gear_slot(record),
                "item_level": _integer_field(record, "itemLevel"),
                "level_requirement": _integer_field(record, "levelRequirement"),
                "applicable_slots": list(_applicable_slots(record)),
                "set_reference": set_reference,
                "set_name": set_name,
                "granted_skill_reference": granted_reference,
                "granted_skill_name": granted_name,
                "effect_skill_reference": effect_reference,
                "effect_skill_name": effect_name,
                "effect_properties": effect_properties,
                "effect_stat_lines": list(effect_stat_lines),
                "completion_bonus_reference": (
                    record.first_value("bonusTableName") or ""
                ).strip(),
                "properties": properties,
                "stat_lines": list(dict.fromkeys(lines)),
                "skill_modifiers": skill_modifiers,
                "acquisition_source": _acquisition_source(
                    logical_path,
                    _item_category(family, logical_path, record),
                    crafted_item_paths,
                    faction_source,
                    bool(vendor_sources) and family == "components",
                ),
                "faction_source": faction_source,
                "faction_name": faction_name,
                "vendor_sources": vendor_sources,
            }
            grouped[family][name_tag].append(variant)
            identity[(family, name_tag)] = (
                display_name,
                name_resolution,
                description_tag,
                description,
            )

    payloads: dict[str, list[dict[str, Any]]] = {}
    variant_count = 0
    for family in ITEM_FAMILIES:
        items: list[dict[str, Any]] = []
        for name_tag, variants in grouped[family].items():
            display_name, resolution, description_tag, description = identity[
                (family, name_tag)
            ]
            ordered_variants = sorted(
                variants,
                key=lambda variant: (
                    variant["level_requirement"],
                    variant["item_level"],
                    variant["source"],
                    variant["record_path"],
                ),
            )
            variant_count += len(ordered_variants)
            items.append(
                {
                    "item_id": f"{family}:{name_tag}",
                    "family": family,
                    "localization_tag": name_tag,
                    "display_name": display_name,
                    "name_resolution": resolution,
                    "description_tag": description_tag,
                    "description": description,
                    "variants": ordered_variants,
                }
            )
        payloads[family] = sorted(
            items,
            key=lambda item: (
                str(item["display_name"]).casefold(),
                str(item["localization_tag"]).casefold(),
            ),
        )
    return payloads, variant_count, unresolved_names


def _discover_crafted_item_paths(
    data_root: Path,
    source_names: tuple[str, ...],
) -> frozenset[str]:
    targets: set[str] = set()
    for source in source_names:
        blueprints = (
            data_root
            / source
            / "records"
            / "items"
            / "crafting"
            / "blueprints"
        )
        if not blueprints.is_dir():
            continue
        for path in blueprints.rglob("*.dbr"):
            reference = (parse_dbr_file(path).first_value("artifactName") or "")
            logical = reference.strip().lower().replace("\\", "/")
            if logical.startswith("records/items/") and logical.endswith(".dbr"):
                targets.add(logical)
    return frozenset(targets)


def _acquisition_source(
    logical_path: str,
    category: str,
    crafted_item_paths: frozenset[str],
    faction_source: str = "",
    faction_component_vendor: bool = False,
) -> str:
    if category == "faction" or faction_source:
        return "Purchased"
    if faction_component_vendor and logical_path in crafted_item_paths:
        return "Crafted / Faction Vendor"
    if faction_component_vendor:
        return "Faction Vendor"
    if category == "crafted" or logical_path in crafted_item_paths:
        return "Crafted"
    if category == "monster_infrequent":
        return "Specific Monster Drop"
    return "Random Drop"


def _faction_metadata(
    record: RawDbrRecord,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> tuple[str, str]:
    faction_source = (record.first_value("factionSource") or "").strip()
    if not faction_source:
        return "", ""
    return faction_source, _localized_faction_name(
        faction_source, exact_names, folded_names, strings
    )


def _localized_faction_name(
    faction_source: str,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> str:
    faction_tag = f"tagFaction{faction_source}"
    entry = exact_names.get(faction_tag) or folded_names.get(
        faction_tag.casefold()
    )
    if entry is None:
        return faction_source
    faction_name = plain_display_name(entry.value)
    strings[faction_tag] = faction_name
    return faction_name


def _vendor_source_payloads(
    sources: tuple[tuple[str, str], ...],
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> list[dict[str, str]]:
    return [
        {
            "faction_source": faction_source,
            "faction_name": _localized_faction_name(
                faction_source, exact_names, folded_names, strings
            ),
            "reputation": reputation,
        }
        for faction_source, reputation in sources
    ]


def _discover_faction_vendor_sources(
    data_root: Path,
    source_names: tuple[str, ...],
    resolver: RecordResolver,
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Trace faction merchant tiers to direct items or blueprint outputs."""

    merchants: dict[str, tuple[str, Path]] = {}
    for source in source_names:
        source_root = data_root / source
        merchant_root = source_root / "records/creatures/npcs/merchants"
        if not merchant_root.is_dir():
            continue
        for path in merchant_root.rglob("*.dbr"):
            logical = path.relative_to(source_root).as_posix().lower()
            merchants[logical] = (source, path)

    tier_fields = (
        ("friendlyNormalTable", "Friendly"),
        ("honoredNormalTable", "Honored"),
        ("respectedNormalTable", "Respected"),
        ("reveredNormalTable", "Revered"),
    )
    discovered: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for source, path in merchants.values():
        merchant = parse_dbr_file(path)
        market_reference = (merchant.first_value("marketFileName") or "").strip()
        faction_reference = (merchant.first_value("factions") or "").strip()
        if not market_reference or not faction_reference:
            continue
        resolved_faction = resolver.resolve(faction_reference, source)
        resolved_market = resolver.resolve(market_reference, source)
        if resolved_faction is None or resolved_market is None:
            continue
        _, faction_record = resolved_faction
        market_source, market_record = resolved_market
        faction_source = (faction_record.first_value("myFaction") or "").strip()
        if not faction_source:
            continue
        for field, reputation in tier_fields:
            tier_reference = (market_record.first_value(field) or "").strip()
            if not tier_reference:
                continue
            resolved_tier = resolver.resolve(tier_reference, market_source)
            if resolved_tier is None:
                continue
            tier_source, tier_record = resolved_tier
            static_items = (tier_record.first_value("marketStaticItems") or "")
            for offered_reference in static_items.split(";"):
                offered_reference = offered_reference.strip().lower().replace(
                    "\\", "/"
                )
                if not offered_reference:
                    continue
                target = offered_reference
                if "/crafting/blueprints/" in offered_reference:
                    resolved_blueprint = resolver.resolve(
                        offered_reference, tier_source
                    )
                    if resolved_blueprint is None:
                        continue
                    _, blueprint = resolved_blueprint
                    target = (
                        blueprint.first_value("artifactName")
                        or blueprint.first_value("forcedRandomArtifactName")
                        or ""
                    ).strip().lower().replace("\\", "/")
                if target.startswith("records/items/") and target.endswith(
                    ".dbr"
                ):
                    discovered[target].add((faction_source, reputation))
    return {
        target: tuple(sorted(sources))
        for target, sources in sorted(discovered.items())
    }


def _discover_records(
    data_root: Path, source_names: tuple[str, ...]
) -> dict[str, tuple[tuple[str, str, Path], ...]]:
    overlaid: dict[str, dict[str, tuple[str, Path]]] = {
        family: {} for family in ITEM_FAMILIES
    }
    for source in source_names:
        items_root = data_root / source / "records" / "items"
        if not items_root.is_dir():
            continue
        for branch in EQUIPMENT_BRANCHES:
            branch_root = items_root / branch
            if not branch_root.is_dir():
                continue
            paths: Iterable[Path]
            if branch == "crafting":
                paths = branch_root.glob("*.dbr")
            else:
                paths = branch_root.rglob("*.dbr")
            for path in paths:
                _overlay_candidate(overlaid["equipment"], source, items_root, path)

        for family, branch in (
            ("components", "materia"),
            ("relics", "gearrelic"),
            ("augments", "enchants"),
            ("runes", "enchants/runes"),
        ):
            branch_root = items_root / branch
            if not branch_root.is_dir():
                continue
            for path in branch_root.rglob("*.dbr"):
                _overlay_candidate(overlaid[family], source, items_root, path)

        for branch in ("crafting/consumables", "misc", "faction/booster"):
            branch_root = items_root / branch
            if not branch_root.is_dir():
                continue
            for path in branch_root.rglob("*.dbr"):
                _overlay_candidate(overlaid["consumables"], source, items_root, path)

    discovered: dict[str, tuple[tuple[str, str, Path], ...]] = {}
    for family, candidates in overlaid.items():
        selected: list[tuple[str, str, Path]] = []
        for logical_path, (source, path) in sorted(candidates.items()):
            record = parse_dbr_file(path)
            if _belongs_to_family(record, family, logical_path):
                selected.append((source, logical_path, path))
        discovered[family] = tuple(selected)
    return discovered


def _overlay_candidate(
    destination: dict[str, tuple[str, Path]],
    source: str,
    items_root: Path,
    path: Path,
) -> None:
    logical = "records/items/" + path.relative_to(items_root).as_posix().lower()
    destination[logical] = (source, path)


def _belongs_to_family(
    record: RawDbrRecord, family: str, logical_path: str
) -> bool:
    item_class = (record.first_value("Class") or "").strip()
    if family == "equipment":
        return item_class in EQUIPMENT_SLOTS or item_class.startswith(
            ("WeaponMelee_", "WeaponHunting_")
        )
    if family == "components":
        return item_class == "ItemRelic"
    if family == "relics":
        return item_class == "ItemArtifact"
    if family == "runes":
        return item_class == "ItemEnchantment" and "/enchants/runes/" in logical_path
    if family == "augments":
        return item_class == "ItemEnchantment" and "/enchants/runes/" not in logical_path
    return item_class in CONSUMABLE_CLASSES


def _name_tag(record: RawDbrRecord, family: str) -> str:
    field = "itemNameTag" if family == "equipment" else "description"
    return (record.first_value(field) or "").strip()


def _item_category(family: str, logical_path: str, record: RawDbrRecord) -> str:
    if family != "equipment":
        return family.removesuffix("s")
    rarity = (record.first_value("itemClassification") or "").casefold()
    description = (record.first_value("FileDescription") or "").casefold()
    filename = Path(logical_path).name.casefold()
    if "/awakened/" in logical_path:
        return "awakened"
    if "/faction/" in logical_path:
        return "faction"
    if "/crafting/" in logical_path or "crafted" in description:
        return "crafted"
    if rarity == "legendary":
        return "legendary"
    if rarity == "epic":
        return "epic"
    if rarity == "rare" and filename.startswith("b"):
        return "monster_infrequent"
    if rarity == "rare":
        return "rare"
    return "base"


def _gear_slot(record: RawDbrRecord) -> str:
    item_class = (record.first_value("Class") or "").strip()
    fixed = EQUIPMENT_SLOTS.get(item_class)
    if fixed is not None:
        return fixed
    if item_class.startswith(("WeaponMelee_", "WeaponHunting_")):
        return "Two-handed weapon" if item_class.endswith("2h") else "One-handed weapon"
    return ""


def _applicable_slots(record: RawDbrRecord) -> tuple[str, ...]:
    slots = {
        label
        for field, label in APPLICABLE_SLOT_FIELDS.items()
        if active_value_kind(record.first_value(field) or "") is not None
    }
    return tuple(sorted(slots))


def _integer_field(record: RawDbrRecord, field: str) -> int:
    raw = (record.first_value(field) or "").strip()
    try:
        return int(float(raw))
    except ValueError:
        return 0


def _property_payloads(
    record: RawDbrRecord,
    *,
    source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
    modifier: bool = False,
) -> list[dict[str, Any]]:
    bundles: dict[str, dict[str, str]] = defaultdict(dict)
    property_ids: dict[str, str] = {}
    chance_bundles = chance_damage_bundle_keys(
        proposal
        for field in fields_for_semantic_analysis(record)
        if active_value_kind(field.value) is not None
        if (proposal := propose_field_mapping(field.key)) is not None
    )
    for field in fields_for_semantic_analysis(record):
        if active_value_kind(field.value) is None:
            continue
        if re.fullmatch(r"(?:modifiedSkillName|modifierSkillName)\d+", field.key):
            continue
        mastery = re.fullmatch(r"augmentMastery(Name|Level)(\d+)", field.key)
        if mastery:
            bundle = f"mastery_bonus:{mastery.group(2)}"
            role = "mastery_reference" if mastery.group(1) == "Name" else "skill_level"
            property_ids[bundle] = "mastery_bonus"
            bundles[bundle][role] = field.value
            continue
        special = (
            MODIFIER_SPECIAL_FIELDS.get(field.key)
            if modifier
            else SPECIAL_GAMEPLAY_FIELDS.get(field.key)
        )
        if special is not None:
            property_ids[special] = special
            bundles[special]["value"] = field.value
            continue
        proposal = propose_field_mapping(field.key)
        if (
            proposal is None
            or proposal.status == "ignored"
            or proposal.component_requirement == "metadata"
        ):
            continue
        proposal = contextualize_damage_chance(proposal, chance_bundles)
        property_ids[proposal.bundle_key] = proposal.property_id
        bundles[proposal.bundle_key][proposal.value_role] = field.value

    pet_attributes = bundles.get("pet_bonus")
    if pet_attributes is not None:
        pet_reference = pet_attributes.get("record_reference", "")
        resolved_pet = resolver.resolve(pet_reference, source)
        if resolved_pet is not None:
            del bundles["pet_bonus"]
            del property_ids["pet_bonus"]
            _, pet_record = resolved_pet
            for property_key, role, value in record_semantic_fingerprint(
                pet_record
            ):
                if property_key.startswith("unmapped:"):
                    continue
                nested_key = f"pet_{property_key}"
                nested_id = f"pet_{property_key.split(':', 1)[0]}"
                property_ids[nested_key] = nested_id
                bundles[nested_key]["record_reference"] = pet_reference
                if value:
                    bundles[nested_key][role] = value

    payloads: list[dict[str, Any]] = []
    for property_key, attributes in sorted(bundles.items()):
        reference = attributes.get("skill_reference") or attributes.get(
            "mastery_reference"
        )
        if reference:
            attributes["display_name"] = resolver.resolve_skill_name(
                reference, source, localization_lookup
            )
        payloads.append(
            {
                "property_id": property_ids[property_key],
                "property_key": property_key,
                "attributes": dict(sorted(attributes.items())),
            }
        )
    return payloads


def _mastery_stat_lines(
    record: RawDbrRecord,
    source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> tuple[str, ...]:
    lines: list[str] = []
    for field in record.fields:
        match = re.fullmatch(r"augmentMasteryName(\d+)", field.key)
        if match is None or not field.value:
            continue
        level = record.first_value(f"augmentMasteryLevel{match.group(1)}") or ""
        name = resolver.resolve_skill_name(field.value, source, localization_lookup)
        lines.append(
            f"+{int(float(level))} to All Skills in {name}"
            if level
            else f"Bonus to {name}"
        )
    return tuple(lines)


def _skill_modifier_payloads(
    record: RawDbrRecord,
    source: str,
    resolver: RecordResolver,
    localization_lookup: dict[str, LocalizationEntry],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for field in record.fields:
        match = re.fullmatch(r"modifiedSkillName(\d+)", field.key)
        if match is None or not field.value:
            continue
        modifier_reference = (
            record.first_value(f"modifierSkillName{match.group(1)}") or ""
        ).strip()
        modified_name = resolver.resolve_skill_name(
            field.value, source, localization_lookup
        )
        properties: list[dict[str, Any]] = []
        stat_lines: tuple[str, ...] = ()
        resolved = resolver.resolve(modifier_reference, source)
        if resolved is not None:
            modifier_source, modifier_record = resolved
            properties = _property_payloads(
                modifier_record,
                source=modifier_source,
                resolver=resolver,
                localization_lookup=localization_lookup,
                modifier=True,
            )
            stat_lines = tuple(
                line
                for line in normalize_record_stat_lines(
                    modifier_record,
                    preferred_source=modifier_source,
                    resolver=resolver,
                    localization_lookup=localization_lookup,
                )
                if not line.startswith("[Needs mapping]")
            )
        payloads.append(
            {
                "modified_skill_reference": field.value,
                "modified_skill_name": modified_name,
                "modifier_reference": modifier_reference,
                "properties": properties,
                "stat_lines": list(stat_lines),
            }
        )
    return payloads
