from pathlib import Path

from gd_affix_relevance.importers.localization_parser import parse_localization_text
from gd_affix_relevance.normalization.sample_report import (
    _format_damage_conversion,
    _format_generic_bundle,
    abstract_display_template,
    build_sample_candidates,
    format_gear_slots,
)
from gd_affix_relevance.normalization.mapping_proposals import propose_field_mapping


def _write_dbr(path: Path, fields: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key},{value},\n" for key, value in fields),
        encoding="utf-8",
    )


def test_template_abstraction_reuses_placeholders() -> None:
    assert abstract_display_template(
        "{chance}% Chance of {minimum}-{maximum} Damage for {minimum} Seconds"
    ) == "[x]% Chance of [y]-[z] Damage for [y] Seconds"


def test_gear_slot_formatting_compresses_common_groups() -> None:
    assert format_gear_slots({"Ring", "Amulet"}) == "Rings, Amulets"
    assert format_gear_slots(
        {"Head", "Shoulders", "Chest", "Hands", "Legs", "Feet"}
    ) == "All armor"


def test_generic_dot_keeps_duration_and_conversion_uses_player_name() -> None:
    dot_min = propose_field_mapping("offensiveSlowBleedingMin")
    dot_duration = propose_field_mapping("offensiveSlowBleedingDurationMin")
    source = propose_field_mapping("conversionInType")
    destination = propose_field_mapping("conversionOutType")
    percent = propose_field_mapping("conversionPercentage")

    assert dot_min is not None and dot_duration is not None
    assert _format_generic_bundle(
        [(dot_min, "10"), (dot_duration, "3")]
    ) == "[x] Bleeding Damage over [y] Seconds"
    assert source is not None and destination is not None and percent is not None
    assert _format_damage_conversion(
        [(source, "Physical"), (destination, "Life"), (percent, "25")]
    ) == "[x]% Physical Damage converted to Vitality Damage"


def test_build_candidates_uses_live_loot_path_and_groups_leveled_variants(
    tmp_path: Path,
) -> None:
    source = tmp_path / "base"
    affix_root = source / "records" / "items" / "lootaffixes" / "prefix"
    table = affix_root / "prefixtables" / "prefix_ring.dbr"
    loottable = source / "records" / "items" / "loottables" / "gearaccessories" / "lt_ring.dbr"
    common_fields = [
        ("Class", "LootRandomizer"),
        ("itemClassification", "Magical"),
        ("lootRandomizerName", "tagTestAcid"),
        ("levelRequirement", "5"),
        ("offensivePoisonModifier", "25.000000"),
    ]
    _write_dbr(affix_root / "acid_01.dbr", common_fields)
    _write_dbr(affix_root / "acid_02.dbr", common_fields)
    _write_dbr(
        table,
        [
            ("randomizerName1", "records/items/lootaffixes/prefix/acid_01.dbr"),
            ("randomizerName2", "records/items/lootaffixes/prefix/acid_02.dbr"),
        ],
    )
    _write_dbr(
        loottable,
        [
            (
                "prefixTableName1",
                "records/items/lootaffixes/prefix/prefixtables/prefix_ring.dbr",
            )
        ],
    )
    localization = parse_localization_text("tagTestAcid={^Y}Corrosive\n")

    result = build_sample_candidates(
        tmp_path, localization, source_names=("base",)
    )

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.display_name == "Corrosive"
    assert candidate.gear_slot == "Ring"
    assert candidate.stat_lines == ("+[x]% Acid Damage",)
    assert candidate.variant_count == 2
    assert candidate.level_requirements == (5,)

    first = build_sample_candidates(
        tmp_path, localization, source_names=("base",), count=1, seed=42
    )
    second = build_sample_candidates(
        tmp_path, localization, source_names=("base",), count=1, seed=42
    )
    assert first.seed == 42
    assert first.candidates == second.candidates
