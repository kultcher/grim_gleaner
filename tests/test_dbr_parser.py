from pathlib import Path

from gd_affix_relevance.domain import RawDbrRecord
from gd_affix_relevance.importers.dbr_parser import (
    parse_dbr_file,
    parse_dbr_text,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "dbr"

METADATA_KEYS = {
    "templateName",
    "Class",
    "itemClassification",
    "levelRequirement",
    "lootRandomizerCost",
    "lootRandomizerJitter",
    "lootRandomizerName",
    "marketAdjustmentPercent",
}


def fixture_record(name: str) -> RawDbrRecord:
    return parse_dbr_file(FIXTURE_ROOT / name)


def reduced_property_values(record: RawDbrRecord) -> dict[str, str]:
    """Return active fields from a fixture that contains no template defaults."""

    return {
        field.key: field.value
        for field in record.fields
        if field.key not in METADATA_KEYS
    }


def test_parse_reduced_charged_fixture() -> None:
    fixture = FIXTURE_ROOT / "charged_level_50_reduced.dbr"

    record = parse_dbr_file(fixture)

    assert record.source_path == fixture
    assert record.warnings == ()
    assert record.first_value("Class") == "LootRandomizer"
    assert record.first_value("lootRandomizerName") == "tagPrefixAO007"
    assert record.first_value("itemClassification") == "Magical"
    assert record.first_value("levelRequirement") == "50"
    assert record.first_value("lootRandomizerJitter") == "10.000000"
    assert record.first_value("offensiveLightningMin") == "6.000000"
    assert record.first_value("offensiveLightningMax") == "42.000000"
    assert record.first_value("conversionInType") == "Physical"
    assert record.first_value("conversionOutType") == "Lightning"
    assert record.first_value("conversionPercentage") == "35.000000"


def test_blank_lines_and_missing_terminal_commas_are_tolerated() -> None:
    record = parse_dbr_text("\nClass,LootRandomizer\n\nlevelRequirement,50,\n")

    assert [(field.key, field.value) for field in record.fields] == [
        ("Class", "LootRandomizer"),
        ("levelRequirement", "50"),
    ]
    assert record.warnings == ()


def test_duplicate_keys_are_preserved_in_source_order() -> None:
    record = parse_dbr_text(
        "randomizerName1,first.dbr,\n"
        "randomizerName1,second.dbr,\n"
    )

    assert record.values_for("randomizerName1") == [
        "first.dbr",
        "second.dbr",
    ]
    assert [field.line_number for field in record.fields_for("randomizerName1")] == [
        1,
        2,
    ]


def test_negative_numeric_and_nonnumeric_values_remain_strings() -> None:
    record = parse_dbr_text(
        "negativeValue,-12.500000,\n"
        "recordReference,records/skills/example.dbr,\n"
        "damageType,Lightning,\n"
    )

    assert record.first_value("negativeValue") == "-12.500000"
    assert record.first_value("recordReference") == "records/skills/example.dbr"
    assert record.first_value("damageType") == "Lightning"


def test_only_first_and_terminal_commas_are_structural() -> None:
    record = parse_dbr_text("example,alpha,beta=gamma,\n")

    assert record.first_value("example") == "alpha,beta=gamma"
    assert record.fields[0].raw_line == "example,alpha,beta=gamma,"


def test_malformed_line_warns_and_following_fields_still_parse() -> None:
    source = Path("broken_fixture.dbr")

    record = parse_dbr_text(
        "Class,LootRandomizer,\n"
        "this line has no comma\n"
        ",value without a key,\n"
        "lootRandomizerName,tagPrefixTest,\n",
        source_path=source,
    )

    assert record.first_value("Class") == "LootRandomizer"
    assert record.first_value("lootRandomizerName") == "tagPrefixTest"
    assert len(record.warnings) == 2
    assert record.warnings[0].source_path == source
    assert record.warnings[0].line_number == 2
    assert record.warnings[0].raw_line == "this line has no comma"
    assert record.warnings[1].line_number == 3
    assert record.warnings[1].message == "Field key is empty"


def test_unknown_fields_are_not_filtered() -> None:
    record = parse_dbr_text(
        "knownField,0.000000,\n"
        "futureUnknownField,surprising-value,\n"
    )

    assert record.first_value("knownField") == "0.000000"
    assert record.first_value("futureUnknownField") == "surprising-value"


def test_thunderstruck_weapon_variants_share_tag_and_property_fields() -> None:
    one_handed = fixture_record("thunderstruck_weapon_1h_level_5_reduced.dbr")
    two_handed = fixture_record("thunderstruck_weapon_2h_level_5_reduced.dbr")

    assert one_handed.first_value("lootRandomizerName") == (
        "tagPrefixB024_WpnMelee1h_A"
    )
    assert two_handed.first_value("lootRandomizerName") == (
        "tagPrefixB024_WpnMelee1h_A"
    )
    assert one_handed.first_value("levelRequirement") == "5"
    assert two_handed.first_value("levelRequirement") == "5"

    one_handed_properties = reduced_property_values(one_handed)
    two_handed_properties = reduced_property_values(two_handed)

    assert one_handed_properties.keys() == two_handed_properties.keys()
    assert one_handed_properties != two_handed_properties
    assert one_handed_properties["conversionInType"] == "Physical"
    assert one_handed_properties["conversionOutType"] == "Lightning"


def test_thunderstruck_equipment_families_have_distinct_tags_and_fields() -> None:
    records = [
        fixture_record("thunderstruck_weapon_1h_level_5_reduced.dbr"),
        fixture_record("thunderstruck_armor_level_5_reduced.dbr"),
        fixture_record("thunderstruck_shield_009_level_5_reduced.dbr"),
        fixture_record("thunderstruck_shield_014_level_5_reduced.dbr"),
    ]

    tags = {record.first_value("lootRandomizerName") for record in records}
    property_fingerprints = {
        frozenset(reduced_property_values(record)) for record in records
    }

    assert tags == {
        "tagPrefixB024_WpnMelee1h_A",
        "tagPrefixB031_Ar_A",
        "tagPrefixB009_Sh_A",
        "tagPrefixB014_Sh_A",
    }
    assert len(property_fingerprints) == 4
    assert all(record.warnings == () for record in records)
    assert all(record.first_value("itemClassification") == "Rare" for record in records)
    assert all(record.first_value("levelRequirement") == "5" for record in records)


def test_thunderstruck_skill_reference_is_preserved() -> None:
    shield = fixture_record("thunderstruck_shield_009_level_5_reduced.dbr")

    assert shield.first_value("augmentSkillLevel1") == "2"
    assert shield.first_value("augmentSkillName1") == (
        "records/skills/playerclass06/squall2.dbr"
    )


def test_skill_boost_reference_chain_reaches_display_tag() -> None:
    shield = fixture_record("thunderstruck_shield_009_level_5_reduced.dbr")
    skill_modifier = fixture_record("skills/squall2_reduced.dbr")
    pet_skill = fixture_record("skills/petskill_whirlwind_exposure_reduced.dbr")

    assert shield.first_value("augmentSkillName1") == (
        "records/skills/playerclass06/squall2.dbr"
    )
    assert skill_modifier.first_value("petSkillName") == (
        "records/skills/playerclass06/pets/petskill_whirlwind_exposure.dbr"
    )
    assert pet_skill.first_value("skillDisplayName") == "tagClass06SkillName04B"


def test_granted_item_skill_reference_reaches_display_tag() -> None:
    weapon = fixture_record("thunderstruck_weapon_1h_level_5_reduced.dbr")
    granted_skill = fixture_record("skills/item_lightningbolt_01_reduced.dbr")

    assert weapon.first_value("itemSkillName") == (
        "records/skills/itemskills/item_lightningbolt_01.dbr"
    )
    assert granted_skill.first_value("skillDisplayName") == "tagItemSkillB025Name"
