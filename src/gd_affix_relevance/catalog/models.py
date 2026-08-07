"""Immutable runtime representation of compiled Grim Dawn data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_SCHEMA_VERSION = 3

ITEM_CATALOG_FILES = (
    "equipment.json",
    "components.json",
    "augments.json",
    "relics.json",
    "runes.json",
    "consumables.json",
)


@dataclass(frozen=True, slots=True)
class CatalogManifest:
    schema_version: int
    game_version: str
    locale: str
    sources: tuple[str, ...]
    files: tuple[str, ...]
    counts: dict[str, int]
    affix_scope: str
    skill_scope: str
    item_scope: str


@dataclass(frozen=True, slots=True)
class StringCatalog:
    locale: str
    strings: dict[str, str]

    def resolve(self, tag: str) -> str | None:
        return self.strings.get(tag)


@dataclass(frozen=True, slots=True)
class SkillDefinition:
    skill_id: str
    source: str
    category: str
    name_tag: str
    display_name: str
    name_resolution: str
    description_tag: str
    mastery_id: str
    mastery_name: str
    mastery_level_required: int
    max_level: int
    is_mastery: bool


@dataclass(frozen=True, slots=True)
class SkillCatalog:
    skills: tuple[SkillDefinition, ...]

    def by_id(self) -> dict[str, SkillDefinition]:
        return {skill.skill_id: skill for skill in self.skills}


@dataclass(frozen=True, slots=True)
class AffixProperty:
    property_id: str
    property_key: str
    attributes: dict[str, str]


@dataclass(frozen=True, slots=True)
class AffixVariantDefinition:
    gear_slot: str
    level_requirements: tuple[int, ...]
    properties: tuple[AffixProperty, ...]
    stat_lines: tuple[str, ...]
    representative_source: str
    source_record_count: int
    stat_layout_count: int
    applicable_slots: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AffixDefinition:
    affix_id: str
    localization_tag: str
    display_name: str
    kind: str
    variants: tuple[AffixVariantDefinition, ...]


@dataclass(frozen=True, slots=True)
class AffixCatalog:
    affixes: tuple[AffixDefinition, ...]

    def by_id(self) -> dict[str, AffixDefinition]:
        return {affix.affix_id: affix for affix in self.affixes}


@dataclass(frozen=True, slots=True)
class ItemProperty:
    property_id: str
    property_key: str
    attributes: dict[str, str]


@dataclass(frozen=True, slots=True)
class ItemSkillModifier:
    modified_skill_reference: str
    modified_skill_name: str
    modifier_reference: str
    properties: tuple[ItemProperty, ...]
    stat_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ItemVariantDefinition:
    source: str
    record_path: str
    category: str
    rarity: str
    item_class: str
    gear_slot: str
    item_level: int
    level_requirement: int
    applicable_slots: tuple[str, ...]
    set_reference: str
    set_name: str
    granted_skill_reference: str
    granted_skill_name: str
    effect_skill_reference: str
    effect_skill_name: str
    effect_properties: tuple[ItemProperty, ...]
    effect_stat_lines: tuple[str, ...]
    completion_bonus_reference: str
    properties: tuple[ItemProperty, ...]
    stat_lines: tuple[str, ...]
    skill_modifiers: tuple[ItemSkillModifier, ...]
    acquisition_source: str = "Random Drop"


@dataclass(frozen=True, slots=True)
class ItemDefinition:
    item_id: str
    family: str
    localization_tag: str
    display_name: str
    name_resolution: str
    description_tag: str
    description: str
    variants: tuple[ItemVariantDefinition, ...]


@dataclass(frozen=True, slots=True)
class ItemCatalog:
    equipment: tuple[ItemDefinition, ...]
    components: tuple[ItemDefinition, ...]
    augments: tuple[ItemDefinition, ...]
    relics: tuple[ItemDefinition, ...]
    runes: tuple[ItemDefinition, ...]
    consumables: tuple[ItemDefinition, ...]

    def all_items(self) -> tuple[ItemDefinition, ...]:
        return tuple(
            item
            for family in (
                self.equipment,
                self.components,
                self.augments,
                self.relics,
                self.runes,
                self.consumables,
            )
            for item in family
        )

    def by_id(self) -> dict[str, ItemDefinition]:
        return {item.item_id: item for item in self.all_items()}


@dataclass(frozen=True, slots=True)
class CatalogBundle:
    manifest: CatalogManifest
    strings: StringCatalog
    skills: SkillCatalog
    affixes: AffixCatalog
    items: ItemCatalog

    @classmethod
    def load(cls, root: Path) -> CatalogBundle:
        catalog_root = Path(root)
        manifest_payload = _load_json(catalog_root / "manifest.json")
        _require_schema(manifest_payload, "manifest.json")
        manifest = CatalogManifest(
            schema_version=manifest_payload["schema_version"],
            game_version=manifest_payload["game_version"],
            locale=manifest_payload["locale"],
            sources=tuple(manifest_payload["sources"]),
            files=tuple(manifest_payload["files"]),
            counts={
                str(key): int(value)
                for key, value in manifest_payload["counts"].items()
            },
            affix_scope=manifest_payload["affix_scope"],
            skill_scope=manifest_payload.get(
                "skill_scope", "all_named_skill_records"
            ),
            item_scope=manifest_payload.get("item_scope", "none"),
        )

        strings_payload = _load_json(catalog_root / "strings.en.json")
        skills_payload = _load_json(catalog_root / "skills.json")
        affixes_payload = _load_json(catalog_root / "affixes.json")
        for filename, payload in (
            ("strings.en.json", strings_payload),
            ("skills.json", skills_payload),
            ("affixes.json", affixes_payload),
        ):
            _require_schema(payload, filename)

        item_payloads = {
            filename: _load_json(catalog_root / filename)
            for filename in ITEM_CATALOG_FILES
        }
        for filename, payload in item_payloads.items():
            _require_schema(payload, filename)

        strings = StringCatalog(
            locale=strings_payload["locale"],
            strings={
                str(key): str(value)
                for key, value in strings_payload["strings"].items()
            },
        )
        skills = SkillCatalog(
            tuple(_skill_from_dict(payload) for payload in skills_payload["skills"])
        )
        affixes = AffixCatalog(
            tuple(_affix_from_dict(payload) for payload in affixes_payload["affixes"])
        )
        item_families = {
            filename.removesuffix(".json"): tuple(
                _item_from_dict(payload) for payload in item_payloads[filename]["items"]
            )
            for filename in ITEM_CATALOG_FILES
        }
        items = ItemCatalog(**item_families)
        bundle = cls(manifest, strings, skills, affixes, items)
        bundle.validate()
        return bundle

    def validate(self) -> None:
        if self.manifest.locale != self.strings.locale:
            raise ValueError("manifest and string catalog locales do not match")
        if len(self.affixes.affixes) != self.manifest.counts.get("affixes"):
            raise ValueError("affix count does not match manifest")
        if len(self.skills.skills) != self.manifest.counts.get("skills"):
            raise ValueError("skill count does not match manifest")
        if len(self.strings.strings) != self.manifest.counts.get("strings"):
            raise ValueError("string count does not match manifest")
        for family_name in (
            "equipment",
            "components",
            "augments",
            "relics",
            "runes",
            "consumables",
        ):
            actual = len(getattr(self.items, family_name))
            if actual != self.manifest.counts.get(family_name):
                raise ValueError(f"{family_name} count does not match manifest")
        if len(self.items.all_items()) != self.manifest.counts.get("items"):
            raise ValueError("item count does not match manifest")
        item_variant_count = sum(
            len(item.variants) for item in self.items.all_items()
        )
        if item_variant_count != self.manifest.counts.get("item_variants"):
            raise ValueError("item variant count does not match manifest")
        affix_variant_count = sum(
            len(affix.variants) for affix in self.affixes.affixes
        )
        if affix_variant_count != self.manifest.counts.get("affix_variants"):
            raise ValueError("affix variant count does not match manifest")
        if len(self.affixes.by_id()) != len(self.affixes.affixes):
            raise ValueError("duplicate affix IDs in catalog")
        if len(self.skills.by_id()) != len(self.skills.skills):
            raise ValueError("duplicate skill IDs in catalog")
        if len(self.items.by_id()) != len(self.items.all_items()):
            raise ValueError("duplicate item IDs in catalog")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return payload


def _require_schema(payload: dict[str, Any], filename: str) -> None:
    if payload.get("schema_version") != CATALOG_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema in {filename}: {payload.get('schema_version')}"
        )


def _skill_from_dict(payload: dict[str, Any]) -> SkillDefinition:
    return SkillDefinition(
        skill_id=payload["skill_id"],
        source=payload["source"],
        category=payload["category"],
        name_tag=payload["name_tag"],
        display_name=payload["display_name"],
        name_resolution=payload.get("name_resolution", "localized"),
        description_tag=payload.get("description_tag", ""),
        mastery_id=payload.get("mastery_id", ""),
        mastery_name=payload.get("mastery_name", ""),
        mastery_level_required=int(payload.get("mastery_level_required", 0)),
        max_level=int(payload.get("max_level", 0)),
        is_mastery=bool(payload.get("is_mastery", False)),
    )


def _property_from_dict(payload: dict[str, Any]) -> AffixProperty:
    return AffixProperty(
        property_id=payload["property_id"],
        property_key=payload["property_key"],
        attributes={str(key): str(value) for key, value in payload["attributes"].items()},
    )


def _variant_from_dict(payload: dict[str, Any]) -> AffixVariantDefinition:
    return AffixVariantDefinition(
        gear_slot=payload["gear_slot"],
        level_requirements=tuple(payload["level_requirements"]),
        properties=tuple(
            _property_from_dict(component) for component in payload["properties"]
        ),
        stat_lines=tuple(payload["stat_lines"]),
        representative_source=payload["representative_source"],
        source_record_count=payload["source_record_count"],
        stat_layout_count=payload["stat_layout_count"],
        applicable_slots=tuple(payload.get("applicable_slots", ())),
    )


def _affix_from_dict(payload: dict[str, Any]) -> AffixDefinition:
    return AffixDefinition(
        affix_id=payload["affix_id"],
        localization_tag=payload["localization_tag"],
        display_name=payload["display_name"],
        kind=payload["kind"],
        variants=tuple(_variant_from_dict(variant) for variant in payload["variants"]),
    )


def _item_property_from_dict(payload: dict[str, Any]) -> ItemProperty:
    return ItemProperty(
        property_id=payload["property_id"],
        property_key=payload["property_key"],
        attributes={str(key): str(value) for key, value in payload["attributes"].items()},
    )


def _item_skill_modifier_from_dict(payload: dict[str, Any]) -> ItemSkillModifier:
    return ItemSkillModifier(
        modified_skill_reference=payload["modified_skill_reference"],
        modified_skill_name=payload["modified_skill_name"],
        modifier_reference=payload["modifier_reference"],
        properties=tuple(
            _item_property_from_dict(item) for item in payload["properties"]
        ),
        stat_lines=tuple(payload["stat_lines"]),
    )


def _item_variant_from_dict(payload: dict[str, Any]) -> ItemVariantDefinition:
    return ItemVariantDefinition(
        source=payload["source"],
        record_path=payload["record_path"],
        category=payload["category"],
        rarity=payload["rarity"],
        item_class=payload["item_class"],
        gear_slot=payload["gear_slot"],
        item_level=payload["item_level"],
        level_requirement=payload["level_requirement"],
        applicable_slots=tuple(payload["applicable_slots"]),
        set_reference=payload["set_reference"],
        set_name=payload["set_name"],
        granted_skill_reference=payload["granted_skill_reference"],
        granted_skill_name=payload["granted_skill_name"],
        effect_skill_reference=payload["effect_skill_reference"],
        effect_skill_name=payload["effect_skill_name"],
        effect_properties=tuple(
            _item_property_from_dict(item) for item in payload["effect_properties"]
        ),
        effect_stat_lines=tuple(payload["effect_stat_lines"]),
        completion_bonus_reference=payload["completion_bonus_reference"],
        properties=tuple(
            _item_property_from_dict(item) for item in payload["properties"]
        ),
        stat_lines=tuple(payload["stat_lines"]),
        skill_modifiers=tuple(
            _item_skill_modifier_from_dict(item)
            for item in payload["skill_modifiers"]
        ),
        acquisition_source=payload.get("acquisition_source", "Random Drop"),
    )


def _item_from_dict(payload: dict[str, Any]) -> ItemDefinition:
    return ItemDefinition(
        item_id=payload["item_id"],
        family=payload["family"],
        localization_tag=payload["localization_tag"],
        display_name=payload["display_name"],
        name_resolution=payload["name_resolution"],
        description_tag=payload["description_tag"],
        description=payload["description"],
        variants=tuple(
            _item_variant_from_dict(variant) for variant in payload["variants"]
        ),
    )
