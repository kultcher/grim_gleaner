"""Versioned compiled catalog models and loading."""

from gd_affix_relevance.catalog.models import (
    CATALOG_SCHEMA_VERSION,
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
    CatalogBundle,
    CatalogManifest,
    ItemCatalog,
    ItemDefinition,
    ItemProperty,
    ItemSkillModifier,
    ItemVariantDefinition,
    SkillCatalog,
    SkillDefinition,
    StringCatalog,
)
from gd_affix_relevance.catalog.compiler import (
    CatalogCompileResult,
    compile_catalog_bundle,
)

__all__ = [
    "CATALOG_SCHEMA_VERSION",
    "AffixCatalog",
    "AffixDefinition",
    "AffixProperty",
    "AffixVariantDefinition",
    "CatalogBundle",
    "CatalogCompileResult",
    "CatalogManifest",
    "ItemCatalog",
    "ItemDefinition",
    "ItemProperty",
    "ItemSkillModifier",
    "ItemVariantDefinition",
    "SkillCatalog",
    "SkillDefinition",
    "StringCatalog",
    "compile_catalog_bundle",
]
