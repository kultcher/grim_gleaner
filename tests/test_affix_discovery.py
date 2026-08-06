from dataclasses import replace
from pathlib import Path

from gd_affix_relevance.domain import RawDbrRecord
from gd_affix_relevance.importers.affix_discovery import supported_affix_kind
from gd_affix_relevance.importers.dbr_parser import parse_dbr_file, parse_dbr_text


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "dbr"


def fixture_at(name: str, source_path: str) -> RawDbrRecord:
    record = parse_dbr_file(FIXTURE_ROOT / name)
    return replace(record, source_path=Path(source_path))


def test_magic_and_rare_prefixes_are_supported() -> None:
    magical = fixture_at(
        "charged_level_50_reduced.dbr",
        "records/items/lootaffixes/prefix/charged.dbr",
    )
    rare = fixture_at(
        "thunderstruck_weapon_1h_level_5_reduced.dbr",
        "records/items/lootaffixes/prefix/thunderstruck.dbr",
    )

    assert supported_affix_kind(magical) == "prefix"
    assert supported_affix_kind(rare) == "prefix"


def test_standard_suffix_is_supported() -> None:
    record = fixture_at(
        "charged_level_50_reduced.dbr",
        "records/items/lootaffixes/suffix/example.dbr",
    )

    assert supported_affix_kind(record) == "suffix"


def test_unique_and_randomizer_table_records_are_excluded() -> None:
    unique = fixture_at(
        "thunderstruck_weapon_1h_level_5_reduced.dbr",
        "records/items/lootaffixes/prefixunique/thunderstruck.dbr",
    )
    table = fixture_at(
        "thunderstruck_weapon_1h_level_5_reduced.dbr",
        "records/items/lootaffixes/prefix/prefixtables/table.dbr",
    )

    assert supported_affix_kind(unique) is None
    assert supported_affix_kind(table) is None


def test_epic_and_legendary_records_are_excluded() -> None:
    for classification in ("Epic", "Legendary"):
        record = parse_dbr_text(
            "Class,LootRandomizer,\n"
            f"itemClassification,{classification},\n"
            "lootRandomizerName,tagOutOfScope,\n",
            source_path=Path("records/items/lootaffixes/prefix/out_of_scope.dbr"),
        )

        assert supported_affix_kind(record) is None


def test_record_requires_class_and_localization_tag() -> None:
    missing_tag = parse_dbr_text(
        "Class,LootRandomizer,\nitemClassification,Rare,\n",
        source_path=Path("records/items/lootaffixes/prefix/missing_tag.dbr"),
    )
    wrong_class = parse_dbr_text(
        "Class,ItemArtifact,\n"
        "itemClassification,Rare,\n"
        "lootRandomizerName,tagNotAnAffix,\n",
        source_path=Path("records/items/lootaffixes/prefix/wrong_class.dbr"),
    )

    assert supported_affix_kind(missing_tag) is None
    assert supported_affix_kind(wrong_class) is None

