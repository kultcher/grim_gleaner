from pathlib import Path

from gd_affix_relevance.importers.localization_parser import (
    first_entry_lookup,
    parse_localization_text,
    plain_display_name,
)


def test_localization_parser_splits_only_first_equals() -> None:
    entries = parse_localization_text(
        "# comment\n"
        "tagPrefixAO007=XY{^O}Charged\n"
        "tagWithExpression={%_s0}={%_s1}\n"
        "malformed line\n",
        source_path=Path("tags_items.txt"),
    )

    assert [(entry.tag, entry.value) for entry in entries] == [
        ("tagPrefixAO007", "XY{^O}Charged"),
        ("tagWithExpression", "{%_s0}={%_s1}"),
    ]
    assert entries[0].line_number == 2
    assert entries[0].source_path == Path("tags_items.txt")


def test_plain_display_name_removes_rainbow_controls_for_reports() -> None:
    assert plain_display_name("XY{^O}Charged") == "Charged"
    assert plain_display_name("{^G}Thunderstruck") == "Thunderstruck"
    assert plain_display_name("{^O}[A2] {^Y}Charged") == "[A2] Charged"


def test_first_duplicate_localization_definition_wins_deterministically() -> None:
    entries = parse_localization_text("tagExample=First\ntagExample=Second\n")

    lookup = first_entry_lookup(entries)

    assert lookup["tagExample"].value == "First"
