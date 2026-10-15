from __future__ import annotations

from pathlib import Path

import pytest

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.live.evaluator import EvaluationRecorder, LiveEvaluator
from gd_affix_relevance.live.grade_table import build_grade_table, write_grade_table
from gd_affix_relevance.live.protocol import FilterDecision, HoveredItem, parse_message
from gd_affix_relevance.live.scoring import (
    LiveCatalog,
    LootFilterSettings,
    RecordInfo,
    item_rarity_class,
    roll_quality,
    score_live_item,
    tooltip_label,
)
from gd_affix_relevance.live.stat_lines import (
    StatLineIndex,
    is_pet_heading,
    line_key,
    match_tooltip_stats,
    parse_line,
)
from gd_affix_relevance.scoring import score_semantic_stat_ids

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).parent / "fixtures" / "live" / "tags_ui_sample.txt"
RUNECARVED_LINES = [
    (5, "Runecarved Exalted Leggings of Blood"),
    (66, "Rare Pants"),
    (18, "911 Armor"),
    (19, "+39% ^EElemental Damage [29-40]"),
    (19, "+61% ^EBleeding Damage [54-62]"),
    (19, "+39% ^EBurn Damage [29-40]"),
    (19, "+218 ^EHealth [170-230]"),
    (19, "29% ^EElemental Resistance [24-32]"),
    (19, "22% ^EBleeding Resistance [19-25]"),
    (20, "Required Player Level: 70"),
]


@pytest.fixture(scope="module")
def index() -> StatLineIndex:
    return StatLineIndex.from_tags_file(TEMPLATES)


@pytest.fixture(scope="module")
def bundle() -> CatalogBundle:
    return CatalogBundle.load(PROJECT_ROOT / "artifacts" / "catalog")


def test_line_and_template_keys_agree(index: StatLineIndex) -> None:
    assert line_key("+39% ^EElemental Damage [29-40]") == "#% elemental damage"
    assert line_key("12-30 ^EFire Damage") == "# fire damage"
    assert line_key("45 Bleeding Damage over 3 Seconds") == "# bleeding damage"
    assert index.stat_for("+39% ^EElemental Damage [29-40]") == "elemental_damage_percent"
    assert index.stat_for("+218 Health") == "health"
    assert index.stat_for("+5-7 Health") == "health"
    assert index.stat_for("12-30 ^EFire Damage") == "flat_fire_damage"
    assert index.stat_for("45 ^EBleeding Damage over 3 Seconds") == "flat_bleeding_damage"
    assert index.stat_for("+10% Damage to Undead") == "racial_damage_bonus_vs_undead"
    assert index.stat_for("Required Player Level: 70") is None


def test_parse_line_reads_value_and_detail_range() -> None:
    parsed = parse_line("+218 ^EHealth [170-230]")
    assert parsed.values == (218.0,)
    assert parsed.roll_range == (170.0, 230.0)
    assert parse_line("911 Armor").roll_range is None


def test_pet_section_switches_to_pet_stats(index: StatLineIndex) -> None:
    lines = [
        (19, "+50 Offensive Ability"),
        (70, "Bonus to All Pets:"),
        (71, "+20% Fire Damage"),
        (71, "+40 Offensive Ability"),
        (20, "Required Player Level: 70"),
    ]
    stats = [stat for _, stat in match_tooltip_stats(index, lines)]
    assert stats == [
        "offensive_ability",
        None,
        "pet_fire_damage_percent",
        None,  # pet_offensive_ability is not a registered stat
        None,
    ]
    assert is_pet_heading("bonus to all pets:")
    assert not is_pet_heading("#% pet damage")


def test_roll_quality_weights_by_relevance_points(index: StatLineIndex) -> None:
    profile = BuildProfile(weights={"burn_damage_percent": 4, "health": 2})
    quality = roll_quality(index, profile, RUNECARVED_LINES)
    burn = (39 - 29) / (40 - 29)
    health = (218 - 170) / (230 - 170)
    assert quality.value == pytest.approx((burn * 4.0 + health * 1.0) / 5.0)
    assert {stat.stat_id for stat in quality.rolled} == {"burn_damage_percent", "health"}
    assert roll_quality(index, BuildProfile(), RUNECARVED_LINES).value is None


def test_tooltip_label_fits_seven_characters() -> None:
    assert tooltip_label("A", 0.874) == "A 87%"
    assert tooltip_label("S++", 1.0) == "S++100%"
    assert tooltip_label("S+", None) == "S+"
    assert all(
        len(tooltip_label(grade, quality)) <= 7
        for grade in ("F", "D", "S+", "S++")
        for quality in (None, 0.0, 0.05, 0.999, 1.0)
    )


def test_rarity_class_rules() -> None:
    common = RecordInfo("item", "common", "Leggings", ())
    epic = RecordInfo("item", "epic", "Epic", ())
    rare = RecordInfo("prefix", "rare", "Runecarved", ())
    magic = RecordInfo("suffix", "magic", "of Blood", ())
    assert item_rarity_class(common, [rare, magic]) == "rare"
    assert item_rarity_class(common, [magic]) == "magic"
    assert item_rarity_class(common, []) == "common"
    assert item_rarity_class(epic, [rare]) == "epic"
    assert item_rarity_class(None, []) == "other"


def test_loot_filter_thresholds_per_rarity() -> None:
    settings = LootFilterSettings(True, {"magic": "B", "rare": "C"})
    assert settings.should_hide("C", "magic")
    assert not settings.should_hide("B", "magic")
    assert settings.should_hide("D", "rare")
    assert not settings.should_hide("F", "epic")
    assert not LootFilterSettings(False, {"magic": "S++"}).should_hide("F", "magic")
    restored = LootFilterSettings.from_dict(settings.to_dict())
    assert restored == settings


def test_whole_item_score_is_union_of_records(bundle: CatalogBundle) -> None:
    profile = BuildProfile(weights={"bleeding_damage_percent": 4, "armor": 2})
    catalog = LiveCatalog.build(bundle, profile)
    base = "records/items/gearlegs/a02_legs01.dbr"
    suffix = "records/items/lootaffixes/suffix/a035e_off_dmg%bleed_06_ar.dbr"
    live = score_live_item(catalog, profile, base, "", suffix)
    expected = score_semantic_stat_ids(
        tuple(sorted(set(catalog.get(base).stat_ids) | set(catalog.get(suffix).stat_ids))),
        profile,
    )
    assert live.score == expected
    assert live.rarity_class == "magic"
    assert live.unknown_records == ()
    assert score_live_item(catalog, profile, "records/missing.dbr").unknown_records


def test_grade_table_format(bundle: CatalogBundle, index: StatLineIndex, tmp_path: Path) -> None:
    profile = BuildProfile(weights={"fire_damage_percent": 4})
    table = build_grade_table(
        LiveCatalog.build(bundle, profile),
        profile,
        index,
        LootFilterSettings(True, {"magic": "C"}),
    )
    lines = table.text.splitlines()
    assert lines[0] == f"GGT1\t{table.table_id}"
    assert lines[-1] == "end"
    assert "filter\t1" in lines and "hide\tmagic\tC" in lines
    assert any(line.startswith("rec\trecords/items/") for line in lines)
    assert any(line.startswith("line\t#% fire damage\t") for line in lines)
    path = write_grade_table(table, tmp_path / "table.txt")
    assert path.read_text(encoding="utf-8") == table.text


def test_evaluator_compares_with_dll_verdict(bundle: CatalogBundle, index: StatLineIndex, tmp_path: Path) -> None:
    profile = BuildProfile(weights={"bleeding_damage_percent": 4, "armor": 2})
    evaluator = LiveEvaluator(bundle, profile, index)
    table = evaluator.refresh()
    base = "records/items/gearlegs/a02_legs01.dbr"
    suffix = "records/items/lootaffixes/suffix/a035e_off_dmg%bleed_06_ar.dbr"
    plain = HoveredItem(calls=1, seed=7, base_record=base, suffix_record=suffix)
    good = evaluator.evaluate(plain)
    assert good.mismatches == ()
    score = good.relevance.score
    agreeing = HoveredItem(
        calls=1, seed=7, base_record=base, suffix_record=suffix,
        attributes={
            "grade": score.grade, "score": f"{score.effective_score:.6f}",
            "matched": str(score.matched_count), "total": str(score.total_category_count),
            "rarity": good.relevance.rarity_class, "rq": "-", "table": table.table_id,
        },
    )
    assert evaluator.evaluate(agreeing).mismatches == ()
    disagreeing = HoveredItem(
        calls=1, seed=7, base_record=base, suffix_record=suffix,
        attributes={**agreeing.attributes, "grade": "S++", "table": "old"},
    )
    mismatches = evaluator.evaluate(disagreeing).mismatches
    assert any("grade" in problem for problem in mismatches)
    assert any("stale" in problem for problem in mismatches)
    recorder = EvaluationRecorder(tmp_path / "log.jsonl")
    recorder.record(good)
    assert '"seed": 7' in (tmp_path / "log.jsonl").read_text(encoding="utf-8")


def test_protocol_attributes_and_filter_messages() -> None:
    message = parse_message(
        "GG1\titem\t3\t9\trecords/a.dbr\t\t\t\t\t\t\t\t\t\t@grade=A\t@rq=0.875\t19:+5% Fire Damage".encode()
    )
    assert isinstance(message, HoveredItem)
    assert message.attributes == {"grade": "A", "rq": "0.875"}
    assert [line.text for line in message.lines] == ["+5% Fire Damage"]
    decision = parse_message(b"GG1\tfilter\t9\trecords/a.dbr\t\t\tD\tmagic\t1\tabc")
    assert decision == FilterDecision(9, "records/a.dbr", "", "", "D", "magic", True, "abc")


def test_listener_reports_app_and_dll_verdicts(bundle: CatalogBundle, index: StatLineIndex) -> None:
    from gd_affix_relevance.live.listener import ListenerState, RecordNames
    from gd_affix_relevance.live.protocol import FilterDecision, TableStatus

    profile = BuildProfile(weights={"bleeding_damage_percent": 4, "health": 2})
    evaluator = LiveEvaluator(bundle, profile, index, LootFilterSettings(True, {"magic": "S++"}))
    table = evaluator.refresh()
    base = "records/items/gearlegs/a02_legs01.dbr"
    suffix = "records/items/lootaffixes/suffix/a035e_off_dmg%bleed_06_ar.dbr"
    expected = evaluator.evaluate(HoveredItem(calls=1, seed=7, base_record=base, suffix_record=suffix))
    score = expected.relevance.score
    fields = ["1", "7", base, "", suffix] + [""] * 7
    fields += [
        f"@grade={score.grade}", f"@score={score.effective_score:.6f}",
        f"@matched={score.matched_count}", f"@total={score.total_category_count}",
        f"@rarity={expected.relevance.rarity_class}", "@rq=-", f"@label={score.grade}",
        f"@table={table.table_id}", "@detail=1", "@injected=1",
        "19:+61% ^EBleeding Damage",
    ]
    state = ListenerState(RecordNames.from_catalog(bundle), evaluator)
    text = state.handle(parse_message(("GG1\titem\t" + "\t".join(fields)).encode()))
    assert "app: " in text and "dll agrees" in text and "label injected" in text
    assert "filter would hide" in text
    hidden = state.handle(FilterDecision(7, base, "", suffix, "D", "magic", True, table.table_id))
    assert hidden.startswith("Loot filter hid: Leggings")
    assert "loaded grade table abc" in state.handle(TableStatus("abc", True, "filter=1"))
