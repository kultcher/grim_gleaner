from pathlib import Path

from gd_affix_relevance.importers.dbr_parser import parse_dbr_file
from gd_affix_relevance.normalization.field_policy import (
    SEMANTIC_FINGERPRINT_IGNORED_FIELDS,
    fields_for_semantic_analysis,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "dbr"


def test_metadata_is_retained_raw_but_excluded_from_semantic_analysis() -> None:
    record = parse_dbr_file(FIXTURE_ROOT / "charged_level_50_reduced.dbr")

    semantic_keys = {field.key for field in fields_for_semantic_analysis(record)}

    assert record.first_value("levelRequirement") == "50"
    assert record.first_value("lootRandomizerJitter") == "10.000000"
    assert not semantic_keys.intersection(SEMANTIC_FINGERPRINT_IGNORED_FIELDS)
    assert "offensiveLightningMin" in semantic_keys
    assert "conversionPercentage" in semantic_keys


def test_granted_skill_bundle_survives_coarse_field_policy() -> None:
    record = parse_dbr_file(
        FIXTURE_ROOT / "thunderstruck_weapon_1h_level_5_reduced.dbr"
    )

    semantic_values = {
        field.key: field.value for field in fields_for_semantic_analysis(record)
    }

    assert semantic_values["itemSkillName"] == (
        "records/skills/itemskills/item_lightningbolt_01.dbr"
    )
    assert semantic_values["itemSkillLevelEq"] == "(itemLevel/4)+1"
    assert semantic_values["itemSkillAutoController"].endswith(
        "cast_@enemyonanyhit_20%.dbr"
    )

