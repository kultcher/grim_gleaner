"""Immutable runtime representation of compiled Grim Dawn data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CATALOG_SCHEMA_VERSION = 1


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
class CatalogBundle:
    manifest: CatalogManifest
    strings: StringCatalog
    skills: SkillCatalog
    affixes: AffixCatalog

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
        bundle = cls(manifest, strings, skills, affixes)
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
        affix_variant_count = sum(
            len(affix.variants) for affix in self.affixes.affixes
        )
        if affix_variant_count != self.manifest.counts.get("affix_variants"):
            raise ValueError("affix variant count does not match manifest")
        if len(self.affixes.by_id()) != len(self.affixes.affixes):
            raise ValueError("duplicate affix IDs in catalog")
        if len(self.skills.by_id()) != len(self.skills.skills):
            raise ValueError("duplicate skill IDs in catalog")


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
    )


def _affix_from_dict(payload: dict[str, Any]) -> AffixDefinition:
    return AffixDefinition(
        affix_id=payload["affix_id"],
        localization_tag=payload["localization_tag"],
        display_name=payload["display_name"],
        kind=payload["kind"],
        variants=tuple(_variant_from_dict(variant) for variant in payload["variants"]),
    )
