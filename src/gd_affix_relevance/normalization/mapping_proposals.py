"""Deprecated location of the raw DBR field mapping table.

The mapping rules are production data used by the catalog compiler, so they
now live in :mod:`gd_affix_relevance.stats.field_mappings`, next to the stat
registry they feed. This module only re-exports them for older scripts.
"""

from gd_affix_relevance.stats.field_mappings import *  # noqa: F401,F403
from gd_affix_relevance.stats.field_mappings import (  # noqa: F401
    FieldMappingProposal,
    chance_damage_bundle_keys,
    contextualize_damage_chance,
    propose_field_mapping,
)
