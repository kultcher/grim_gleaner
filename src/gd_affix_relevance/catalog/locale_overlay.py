"""Locale overlay for compiled-catalog display names.

The compiled catalog (``manifest.json``, ``affixes.json``, ``items.json``,
``skills.json``, ...) is compiled once from the official English game data
and bakes English display names directly into its records. Duplicating that
entire structural catalog per locale would be wasteful and would risk
drifting IDs, localization tags, and scoring behavior between languages.

Instead, a :class:`CatalogLocaleOverlay` holds a small ``localization tag ->
display name`` mapping read from the user's locally extracted item-tag
files (see ``game_localization.prepare_game_item_tags``). Callers resolve a
display name for one catalog entity by tag, falling back to the catalog's
baked-in English name when no local translation is available.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.catalog.models import (
    AffixCatalog,
    AffixDefinition,
    CatalogBundle,
    ItemCatalog,
    ItemDefinition,
    ItemVariantDefinition,
    SkillCatalog,
    SkillDefinition,
)
from gd_affix_relevance.domain import ENGLISH_LOCALE, LocaleSpec
from gd_affix_relevance.importers.localization_parser import (
    load_localization_directory,
    plain_display_name,
)
from gd_affix_relevance.records import normalize_record_path


@dataclass(frozen=True, slots=True)
class CatalogLocaleOverlay:
    """A tag-keyed set of locally sourced display-name translations."""

    locale: LocaleSpec
    strings: dict[str, str]

    def resolve(self, tag: str, fallback: str) -> str:
        """Return the overlay value for *tag*, or *fallback* when absent."""

        if not tag:
            return fallback
        value = self.strings.get(tag)
        return value if value else fallback

    def resolve_item(self, item: ItemDefinition) -> str:
        return self.resolve(item.localization_tag, item.display_name)

    def resolve_affix(self, affix: AffixDefinition) -> str:
        return self.resolve(affix.localization_tag, affix.display_name)

    def resolve_skill(self, skill: SkillDefinition) -> str:
        return self.resolve(skill.name_tag, skill.display_name)


EMPTY_OVERLAY = CatalogLocaleOverlay(locale=ENGLISH_LOCALE, strings={})


def load_catalog_locale_overlay(
    tags_root: Path,
    *,
    locale: LocaleSpec,
) -> CatalogLocaleOverlay:
    """Build an overlay from a locally extracted item-tag directory.

    Returns an empty overlay for English (the catalog's baked-in names are
    already English) and for any locale whose tag directory has not been
    prepared yet, so callers can unconditionally fall back to the catalog's
    English display names without special-casing missing data.
    """

    if locale.code == ENGLISH_LOCALE.code:
        return CatalogLocaleOverlay(locale=locale, strings={})

    root = Path(tags_root)
    if not root.is_dir():
        return CatalogLocaleOverlay(locale=locale, strings={})

    strings: dict[str, str] = {}
    for entry in load_localization_directory(root):
        if entry.tag in strings:
            continue
        value = plain_display_name(entry.value)
        if value:
            strings[entry.tag] = value
    return CatalogLocaleOverlay(locale=locale, strings=strings)


def localize_skill_catalog(
    skills: SkillCatalog,
    overlay: CatalogLocaleOverlay,
) -> SkillCatalog:
    """Return a copy of *skills* with display names resolved through *overlay*."""

    if not overlay.strings:
        return skills
    return SkillCatalog(
        tuple(
            dataclasses.replace(skill, display_name=overlay.resolve_skill(skill))
            for skill in skills.skills
        )
    )


def localize_affix_catalog(
    affixes: AffixCatalog,
    overlay: CatalogLocaleOverlay,
) -> AffixCatalog:
    """Return a copy of *affixes* with display names resolved through *overlay*."""

    if not overlay.strings:
        return affixes
    return AffixCatalog(
        tuple(
            dataclasses.replace(affix, display_name=overlay.resolve_affix(affix))
            for affix in affixes.affixes
        )
    )


def localize_item_catalog(
    items: ItemCatalog,
    overlay: CatalogLocaleOverlay,
    *,
    skill_names_by_id: dict[str, str] | None = None,
) -> ItemCatalog:
    """Return a copy of *items* with names resolved through *overlay*.

    Also re-resolves the granted/effect/modified skill names an item variant
    references, using *skill_names_by_id* (typically the already-localized
    skill catalog) so a Russian item's referenced skills read consistently.
    """

    if not overlay.strings:
        return items
    names_by_id = skill_names_by_id or {}

    def localized_variant(variant: ItemVariantDefinition) -> ItemVariantDefinition:
        updates: dict[str, object] = {}
        granted_name = _localized_skill_reference_name(
            variant.granted_skill_reference, variant.granted_skill_name, names_by_id
        )
        if granted_name != variant.granted_skill_name:
            updates["granted_skill_name"] = granted_name
        effect_name = _localized_skill_reference_name(
            variant.effect_skill_reference, variant.effect_skill_name, names_by_id
        )
        if effect_name != variant.effect_skill_name:
            updates["effect_skill_name"] = effect_name
        if variant.skill_modifiers:
            localized_modifiers = tuple(
                dataclasses.replace(
                    modifier,
                    modified_skill_name=_localized_skill_reference_name(
                        modifier.modified_skill_reference,
                        modifier.modified_skill_name,
                        names_by_id,
                    ),
                )
                for modifier in variant.skill_modifiers
            )
            if localized_modifiers != variant.skill_modifiers:
                updates["skill_modifiers"] = localized_modifiers
        return dataclasses.replace(variant, **updates) if updates else variant

    def localized_item(item: ItemDefinition) -> ItemDefinition:
        return dataclasses.replace(
            item,
            display_name=overlay.resolve_item(item),
            variants=tuple(
                localized_variant(variant) for variant in item.variants
            ),
        )

    return ItemCatalog(
        equipment=tuple(localized_item(item) for item in items.equipment),
        components=tuple(localized_item(item) for item in items.components),
        augments=tuple(localized_item(item) for item in items.augments),
        relics=tuple(localized_item(item) for item in items.relics),
        runes=tuple(localized_item(item) for item in items.runes),
        consumables=tuple(localized_item(item) for item in items.consumables),
    )


def localize_catalog_bundle(
    bundle: CatalogBundle,
    overlay: CatalogLocaleOverlay,
) -> CatalogBundle:
    """Return a copy of *bundle* with display names resolved through *overlay*.

    Structural data (IDs, localization tags, scoring-relevant fields, and the
    manifest) is untouched; only presentation names are replaced. When the
    overlay has no strings (English, or a locale not yet prepared locally)
    the original *bundle* is returned unchanged.
    """

    if not overlay.strings:
        return bundle
    skills = localize_skill_catalog(bundle.skills, overlay)
    skill_names_by_id = {
        skill.skill_id: skill.display_name for skill in skills.skills
    }
    localized = dataclasses.replace(
        bundle,
        skills=skills,
        affixes=localize_affix_catalog(bundle.affixes, overlay),
        items=localize_item_catalog(
            bundle.items, overlay, skill_names_by_id=skill_names_by_id
        ),
    )
    localized.validate()
    return localized


def _localized_skill_reference_name(
    reference: str,
    fallback: str,
    skill_names_by_id: dict[str, str],
) -> str:
    if not reference:
        return fallback
    localized = skill_names_by_id.get(normalize_record_path(reference))
    return localized or fallback
