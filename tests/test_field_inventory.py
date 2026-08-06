import json
from pathlib import Path

from gd_affix_relevance.importers.localization_parser import parse_localization_text
from gd_affix_relevance.normalization.field_inventory import (
    active_value_kind,
    build_field_inventory,
    write_inventory_reports,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "dbr"


def test_active_value_classification_preserves_references_and_expressions() -> None:
    assert active_value_kind("0.000000") is None
    assert active_value_kind("-2.500000") == "numeric"
    assert active_value_kind("records/skills/example.dbr") == "record_reference"
    assert active_value_kind("(itemLevel/4)+1") == "expression"
    assert active_value_kind("Physical") == "string"


def test_inventory_scans_supported_affix_and_writes_review_reports(
    tmp_path: Path,
) -> None:
    affix_dir = (
        tmp_path
        / "game_data"
        / "base"
        / "records"
        / "items"
        / "lootaffixes"
        / "prefix"
    )
    affix_dir.mkdir(parents=True)
    fixture_text = (
        FIXTURE_ROOT / "thunderstruck_weapon_1h_level_5_reduced.dbr"
    ).read_text(encoding="utf-8")
    (affix_dir / "thunderstruck.dbr").write_text(fixture_text, encoding="utf-8")

    localization_entries = parse_localization_text(
        "tagPrefixB024_WpnMelee1h_A={^G}Thunderstruck\n"
    )
    result = build_field_inventory(
        tmp_path / "game_data",
        localization_entries,
        source_names=("base",),
    )

    fields = {summary.raw_field: summary for summary in result.fields}
    assert result.records_scanned == 1
    assert result.supported_records == 1
    assert result.unresolved_localization_tags == 0
    assert "lootRandomizerCost" not in fields
    assert fields["itemSkillName"].examples[0].affix_name == "Thunderstruck"
    assert fields["characterOffensiveAbility"].record_count == 1

    output_dir = tmp_path / "reports"
    write_inventory_reports(result, output_dir)
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["supported_records"] == 1
    assert (output_dir / "field_inventory.csv").is_file()
    assert (output_dir / "mapping_proposals.csv").is_file()
    assert (output_dir / "bundle_relationships.csv").is_file()
    assert (output_dir / "review_needed.csv").is_file()
    assert (output_dir / "inferred_mappings.csv").is_file()
    assert (output_dir / "unmapped_fields.csv").is_file()
    assert (output_dir / "unresolved_localization_tags.csv").is_file()
    assert (output_dir / "proposed_normalization_rules.json").is_file()
