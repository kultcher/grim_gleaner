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
    assert plain_display_name("^kSearing Ember") == "Searing Ember"
    assert plain_display_name("^w^nComponent description") == (
        "Component description"
    )


def test_plain_display_name_strips_standalone_leading_dollar_marker() -> None:
    assert plain_display_name("$пламени Ульзуина") == "пламени Ульзуина"
    assert plain_display_name("${%_3a0}{%_s3}") == "${%_3a0}{%_s3}"


def test_first_duplicate_localization_definition_wins_deterministically() -> None:
    entries = parse_localization_text("tagExample=First\ntagExample=Second\n")

    lookup = first_entry_lookup(entries)

    assert lookup["tagExample"].value == "First"


def test_plain_display_name_strips_single_gender_marker() -> None:
    # A base item name carries exactly one bracketed gender marker (the
    # item's own inherent gender), not a packed set of variants.
    assert plain_display_name("[fs]заточка") == "заточка"
    assert plain_display_name("[ms]тупой") == "тупой"


def test_plain_display_name_picks_masculine_singular_from_packed_variants() -> None:
    # Quality/affix adjectives pack all four grammatical forms into one
    # value; masculine singular is the canonical display default.
    packed = "[ms]тупой[fs]тупая[ns]тупое[np]тупые"

    assert plain_display_name(packed) == "тупой"


def test_plain_display_name_falls_back_when_masculine_singular_missing() -> None:
    assert plain_display_name("[fs]тупая[np]тупые") == "тупая"


def test_plain_display_name_ignores_unrelated_bracket_codes() -> None:
    # Grade-tier labels such as "[A2]" are not gender markers and must be
    # preserved, matching test_plain_display_name_removes_rainbow_controls.
    assert plain_display_name("[A2] Charged") == "[A2] Charged"
