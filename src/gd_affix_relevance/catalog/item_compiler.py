"""Compile concrete item records into deterministic family payloads."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
from typing import Any

from gd_affix_relevance.catalog.drop_sources import discover_drop_sources
from gd_affix_relevance.catalog.value_parsing import (
    integer_value,
    optional_float_value,
)
from gd_affix_relevance.domain import LocalizationEntry, RawDbrRecord
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
    normalize_record_stat_lines,
)
from gd_affix_relevance.records import RecordLocation, RecordRepository


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
    repository: RecordRepository,
    exact_names: dict[str, LocalizationEntry],
    folded_names: dict[str, LocalizationEntry],
    strings: dict[str, str],
) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    """Compile requested concrete item families and return coverage counts."""

    resolver = repository
    localization_lookup = dict(exact_names)
    for folded, entry in folded_names.items():
        localization_lookup.setdefault(folded, entry)

    records = _discover_records(resolver)
    crafted_item_paths = _discover_crafted_item_paths(resolver)
    random_blueprint_item_paths, special_vendor_blueprint_item_paths = (
        _discover_component_blueprint_distribution(resolver)
    )
    faction_vendor_sources = _discover_faction_vendor_sources(resolver)
    drop_sources = discover_drop_sources(
        resolver, exact_names, folded_names
    )
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = {
        family: defaultdict(list) for family in ITEM_FAMILIES
    }
    identity: dict[tuple[str, str], tuple[str, str, str, str]] = {}
    unresolved_names = 0

    for family in ITEM_FAMILIES:
        for location in records[family]:
            source = location.source
            logical_path = location.logical_path
            record = resolver.load(location)
            if family == "equipment" and _is_blank_equipment_template(
                record, logical_path
            ):
                continue
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

            properties = compile_record_properties(
                record,
                resolver=resolver,
                localization_lookup=localization_lookup,
            )
            lines = list(
                line
                for line in normalize_record_stat_lines(
                    record,
                    resolver=resolver,
                    localization_lookup=localization_lookup,
                )
                if not line.startswith("[Needs mapping]")
            )
            mastery_lines = _mastery_stat_lines(
                record, resolver, localization_lookup
            )
            lines.extend(mastery_lines)
            skill_modifiers = _skill_modifier_payloads(
                record, resolver, localization_lookup
            )
            for modifier in skill_modifiers:
                lines.extend(
                    f"Skill Modifier for {modifier['modified_skill_name']}: {line}"
                    for line in modifier["stat_lines"]
                )

            granted_reference = (record.first_value("itemSkillName") or "").strip()
            granted_name = (
                resolver.resolve_skill_name(
                    granted_reference, localization_lookup
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
                    effect_reference, localization_lookup
                )
                resolved_effect = resolver.resolve(effect_reference)
                if resolved_effect is not None:
                    _, effect_record = resolved_effect
                    effect_properties = compile_record_properties(
                        effect_record,
                        resolver=resolver,
                        localization_lookup=localization_lookup,
                        modifier=True,
                    )
                    effect_stat_lines = tuple(
                        line
                        for line in normalize_record_stat_lines(
                            effect_record,
                            resolver=resolver,
                            localization_lookup=localization_lookup,
                        )
                        if not line.startswith("[Needs mapping]")
                    )
            set_reference = (record.first_value("itemSetName") or "").strip()
            set_name = ""
            if set_reference:
                resolved_set = resolver.resolve(set_reference)
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
            discovered_monsters = drop_sources.monster_sources.get(
                logical_path, ()
            )
            monster_sources = [
                {
                    "name": monster.name,
                    "localization_tag": monster.localization_tag,
                    "classification": monster.classification,
                }
                for monster in discovered_monsters
            ]
            for monster in discovered_monsters:
                strings[monster.localization_tag] = monster.name
            discovered_containers = drop_sources.container_sources.get(
                logical_path, ()
            )
            container_sources = [
                {
                    "name": container.name,
                    "localization_tag": container.localization_tag,
                }
                for container in discovered_containers
            ]
            for container in discovered_containers:
                strings[container.localization_tag] = container.name
            variant = {
                "source": source,
                "record_path": logical_path,
                "category": _item_category(family, logical_path, record),
                "rarity": (record.first_value("itemClassification") or "").strip(),
                "item_class": (record.first_value("Class") or "").strip(),
                "gear_slot": _gear_slot(record),
                "item_level": integer_value(record.first_value("itemLevel")),
                "level_requirement": integer_value(
                    record.first_value("levelRequirement")
                ),
                "attribute_scale_percent": optional_float_value(
                    record.first_value("attributeScalePercent")
                ),
                "loot_randomizer_jitter": optional_float_value(
                    record.first_value("lootRandomizerJitter")
                ),
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
                    family == "components"
                    and logical_path in random_blueprint_item_paths,
                    family == "components"
                    and logical_path in special_vendor_blueprint_item_paths,
                    specific_monster_drop=bool(monster_sources),
                    specific_container_drop=bool(container_sources),
                ),
                "faction_source": faction_source,
                "faction_name": faction_name,
                "vendor_sources": vendor_sources,
                "monster_sources": monster_sources,
                "container_sources": container_sources,
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
    repository: RecordRepository,
) -> frozenset[str]:
    targets: set[str] = set()
    for location in repository.iter_overlaid(
        "records/items/crafting/blueprints"
    ):
        reference = (
            repository.load(location).first_value("artifactName") or ""
        )
        logical = reference.strip().lower().replace("\\", "/")
        if logical.startswith("records/items/") and logical.endswith(".dbr"):
            targets.add(logical)
    return frozenset(targets)


def _discover_component_blueprint_distribution(
    repository: RecordRepository,
) -> tuple[frozenset[str], frozenset[str]]:
    """Find component recipes distributed as drops or by special vendors.

    Every blacksmith recipe has a blueprint record, including recipes known by
    default.  Placement of that record in a blueprint loot table distinguishes
    discoverable recipes from the default recipe list.  Non-faction vendor
    tables are retained separately so they are not reported as random drops.
    """

    random_targets: set[str] = set()
    vendor_targets: set[str] = set()
    for location in repository.iter_overlaid(
        "records/items/loottables/blueprints"
    ):
        destination = (
            vendor_targets
            if "vendor" in location.path.stem.casefold()
            else random_targets
        )
        table = repository.load(location)
        for field in table.fields:
            for raw_reference in field.value.split(";"):
                reference = raw_reference.strip().lower().replace("\\", "/")
                if (
                    "/crafting/blueprints/component/" not in reference
                    or not reference.endswith(".dbr")
                ):
                    continue
                target = _resolve_blueprint_target(repository, reference)
                if target:
                    destination.add(target)
    return frozenset(random_targets), frozenset(vendor_targets)


def _acquisition_source(
    logical_path: str,
    category: str,
    crafted_item_paths: frozenset[str],
    faction_source: str = "",
    faction_component_vendor: bool = False,
    random_component_blueprint: bool = False,
    special_vendor_component_blueprint: bool = False,
    specific_monster_drop: bool = False,
    specific_container_drop: bool = False,
) -> str:
    if category == "faction" or faction_source:
        return "Purchased"
    if random_component_blueprint and special_vendor_component_blueprint:
        if faction_component_vendor:
            return "Random Blueprint / Special Vendor / Faction Vendor"
        return "Random Blueprint / Special Vendor"
    if random_component_blueprint and faction_component_vendor:
        return "Random Blueprint / Faction Vendor"
    if random_component_blueprint:
        return "Random Blueprint"
    if special_vendor_component_blueprint:
        return "Special Vendor Blueprint"
    if faction_component_vendor and logical_path in crafted_item_paths:
        return "Faction Vendor Blueprint"
    if faction_component_vendor:
        return "Faction Vendor"
    if category == "component" and logical_path in crafted_item_paths:
        return "Default Recipe"
    if category == "crafted" or logical_path in crafted_item_paths:
        return "Crafted"
    if specific_monster_drop:
        return "Specific Monster Drop"
    if specific_container_drop:
        return "Lootable Container"
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
    repository: RecordRepository,
) -> dict[str, tuple[tuple[str, str], ...]]:
    """Trace faction merchant tiers to direct items or blueprint outputs."""

    tier_fields = (
        ("friendlyNormalTable", "Friendly"),
        ("honoredNormalTable", "Honored"),
        ("respectedNormalTable", "Respected"),
        ("reveredNormalTable", "Revered"),
    )
    discovered: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for location in repository.iter_overlaid(
        "records/creatures/npcs/merchants"
    ):
        merchant = repository.load(location)
        market_reference = (merchant.first_value("marketFileName") or "").strip()
        faction_reference = (merchant.first_value("factions") or "").strip()
        if not market_reference or not faction_reference:
            continue
        resolved_faction = repository.resolve(faction_reference)
        resolved_market = repository.resolve(market_reference)
        if resolved_faction is None or resolved_market is None:
            continue
        _, faction_record = resolved_faction
        _, market_record = resolved_market
        faction_source = (faction_record.first_value("myFaction") or "").strip()
        if not faction_source:
            continue
        for field, reputation in tier_fields:
            tier_reference = (market_record.first_value(field) or "").strip()
            if not tier_reference:
                continue
            resolved_tier = repository.resolve(tier_reference)
            if resolved_tier is None:
                continue
            _, tier_record = resolved_tier
            static_items = (tier_record.first_value("marketStaticItems") or "")
            for offered_reference in static_items.split(";"):
                offered_reference = offered_reference.strip().lower().replace(
                    "\\", "/"
                )
                if not offered_reference:
                    continue
                target = offered_reference
                if "/crafting/blueprints/" in offered_reference:
                    target = _resolve_blueprint_target(
                        repository, offered_reference
                    )
                if target.startswith("records/items/") and target.endswith(
                    ".dbr"
                ):
                    discovered[target].add((faction_source, reputation))
    return {
        target: tuple(sorted(sources))
        for target, sources in sorted(discovered.items())
    }


def _resolve_blueprint_target(
    repository: RecordRepository,
    blueprint_reference: str,
) -> str:
    resolved = repository.resolve(blueprint_reference)
    if resolved is None:
        return ""
    _, blueprint = resolved
    target = (
        blueprint.first_value("artifactName")
        or blueprint.first_value("forcedRandomArtifactName")
        or ""
    ).strip().lower().replace("\\", "/")
    if target.startswith("records/items/") and target.endswith(".dbr"):
        return target
    return ""


def _discover_records(
    repository: RecordRepository,
) -> dict[str, tuple[RecordLocation, ...]]:
    overlaid: dict[str, dict[str, RecordLocation]] = {
        family: {} for family in ITEM_FAMILIES
    }
    for branch in EQUIPMENT_BRANCHES:
        for location in repository.iter_overlaid(
            f"records/items/{branch}", recursive=branch != "crafting"
        ):
            overlaid["equipment"][location.logical_path] = location

    for family, branch in (
        ("components", "materia"),
        ("relics", "gearrelic"),
        ("augments", "enchants"),
        ("runes", "enchants/runes"),
    ):
        for location in repository.iter_overlaid(f"records/items/{branch}"):
            overlaid[family][location.logical_path] = location

    for branch in ("crafting/consumables", "misc", "faction/booster"):
        for location in repository.iter_overlaid(f"records/items/{branch}"):
            overlaid["consumables"][location.logical_path] = location

    discovered: dict[str, tuple[RecordLocation, ...]] = {}
    for family, candidates in overlaid.items():
        selected: list[RecordLocation] = []
        for logical_path, location in sorted(candidates.items()):
            record = repository.load(location)
            if _belongs_to_family(record, family, logical_path):
                selected.append(location)
        discovered[family] = tuple(selected)
    return discovered


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


def _is_blank_equipment_template(
    record: RawDbrRecord, logical_path: str
) -> bool:
    """Reject generic equipment templates that borrow a real item's name tag."""

    description = (record.first_value("FileDescription") or "").strip()
    if "base blank" in description.casefold():
        return True
    if description:
        return False
    stem = Path(logical_path).stem.casefold()
    return re.match(r"^[bc]\d00(?:_|$)", stem) is not None


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


def compile_record_properties(
    record: RawDbrRecord,
    *,
    resolver: RecordRepository,
    localization_lookup: dict[str, LocalizationEntry],
    modifier: bool = False,
) -> list[dict[str, Any]]:
    bundles: dict[str, dict[str, str]] = defaultdict(dict)
    property_ids: dict[str, str] = {}
    racial_fields = frozenset(
        {
            "racialBonusRace",
            "racialBonusPercentDamage",
            "racialBonusPercentDefense",
        }
    )
    race_reference = (record.first_value("racialBonusRace") or "").strip()
    for property_id, raw_field in (
        ("racial_damage_bonus", "racialBonusPercentDamage"),
        ("racial_defense_bonus", "racialBonusPercentDefense"),
    ):
        value = (record.first_value(raw_field) or "").strip()
        if active_value_kind(value) is None:
            continue
        property_ids[property_id] = property_id
        bundles[property_id]["percent"] = value
        if race_reference:
            bundles[property_id]["race_reference"] = race_reference
    chance_bundles = chance_damage_bundle_keys(
        proposal
        for field in fields_for_semantic_analysis(record)
        if active_value_kind(field.value) is not None
        if (proposal := propose_field_mapping(field.key)) is not None
    )
    for field in fields_for_semantic_analysis(record):
        if active_value_kind(field.value) is None:
            continue
        if field.key in racial_fields:
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
        resolved_pet = resolver.resolve(pet_reference)
        if resolved_pet is not None:
            del bundles["pet_bonus"]
            del property_ids["pet_bonus"]
            _, pet_record = resolved_pet
            nested_properties = compile_record_properties(
                pet_record,
                resolver=resolver,
                localization_lookup=localization_lookup,
                modifier=modifier,
            )
            for nested in nested_properties:
                if nested["property_id"] in {
                    "unmapped",
                    "unresolved_composite",
                }:
                    continue
                nested_key = f"pet_{nested['property_key']}"
                property_ids[nested_key] = f"pet_{nested['property_id']}"
                bundles[nested_key].update(nested["attributes"])
                bundles[nested_key]["record_reference"] = pet_reference

    payloads: list[dict[str, Any]] = []
    for property_key, attributes in sorted(bundles.items()):
        reference = attributes.get("skill_reference") or attributes.get(
            "mastery_reference"
        )
        if reference:
            attributes["display_name"] = resolver.resolve_skill_name(
                reference, localization_lookup
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
    resolver: RecordRepository,
    localization_lookup: dict[str, LocalizationEntry],
) -> tuple[str, ...]:
    lines: list[str] = []
    for field in record.fields:
        match = re.fullmatch(r"augmentMasteryName(\d+)", field.key)
        if match is None or not field.value:
            continue
        level = record.first_value(f"augmentMasteryLevel{match.group(1)}") or ""
        name = resolver.resolve_skill_name(field.value, localization_lookup)
        lines.append(
            f"+{int(float(level))} to All Skills in {name}"
            if level
            else f"Bonus to {name}"
        )
    return tuple(lines)


def _skill_modifier_payloads(
    record: RawDbrRecord,
    resolver: RecordRepository,
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
            field.value, localization_lookup
        )
        properties: list[dict[str, Any]] = []
        stat_lines: tuple[str, ...] = ()
        resolved = resolver.resolve(modifier_reference)
        if resolved is not None:
            _, modifier_record = resolved
            properties = compile_record_properties(
                modifier_record,
                resolver=resolver,
                localization_lookup=localization_lookup,
                modifier=True,
            )
            stat_lines = tuple(
                line
                for line in normalize_record_stat_lines(
                    modifier_record,
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
