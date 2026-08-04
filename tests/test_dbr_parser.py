from pathlib import Path

from gd_affix_relevance.importers.dbr_parser import (
    parse_dbr_file,
    parse_dbr_text,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "dbr"


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
