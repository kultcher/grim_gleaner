from pathlib import Path

from gd_affix_relevance.normalization.item_tag_audit import (
    build_item_tag_audit,
    format_item_tag_audit_report,
    write_item_tag_audit,
)


def test_item_tag_audit_preserves_sections_and_traces_exact_dbr_values(
    tmp_path: Path,
) -> None:
    localization = tmp_path / "base/text_en/tags_items.txt"
    localization.parent.mkdir(parents=True)
    localization.write_text(
        "#ArmorHead\n"
        "tagTestHelm=Test Helm\n"
        "#LootChests\n"
        "tagTestCorpse=Slain Test Subject\n"
        "tagMapOnly=Map Asset Label\n",
        encoding="utf-8",
    )
    item = tmp_path / "base/records/items/gearhead/test.dbr"
    item.parent.mkdir(parents=True)
    item.write_text("itemNameTag,tagTestHelm,\n", encoding="utf-8")
    chest = tmp_path / "gdx3/records/items/lootchests/test.dbr"
    chest.parent.mkdir(parents=True)
    chest.write_text("description,tagTestCorpse,\n", encoding="utf-8")

    result = build_item_tag_audit(
        tmp_path,
        definition_sources=("base",),
        scan_sources=("base", "gdx3"),
    )

    by_tag = {entry.definition.tag: entry for entry in result.entries}
    assert by_tag["tagTestHelm"].definition.section == "ArmorHead"
    assert by_tag["tagTestHelm"].references[0].field == "itemNameTag"
    assert by_tag["tagTestCorpse"].references[0].branch == "records/items/lootchests"
    assert by_tag["tagMapOnly"].references == ()
    assert result.unique_tags == {
        "tagTestHelm",
        "tagTestCorpse",
        "tagMapOnly",
    }

    report = format_item_tag_audit_report(result)
    assert "Unique tags without an exact DBR reference: 1" in report
    assert "| base | LootChests | 2 | 1 | 1 |" in report


def test_item_tag_audit_compares_complete_tag_key_sets_and_writes_csv(
    tmp_path: Path,
) -> None:
    official = tmp_path / "base/text_en/tags_items.txt"
    official.parent.mkdir(parents=True)
    official.write_text("#Items\ntagOne=One\ntagTwo=Two\n", encoding="utf-8")
    comparison = tmp_path / "rainbow/tags_items.txt"
    comparison.parent.mkdir(parents=True)
    comparison.write_text("tagOne={^W}One\ntagExtra=Extra\n", encoding="utf-8")

    result = build_item_tag_audit(
        tmp_path,
        definition_sources=("base",),
        scan_sources=("base",),
        comparison_root=tmp_path / "rainbow",
    )

    assert result.comparisons[0].missing_from_comparison == ("tagTwo",)
    assert result.comparisons[0].extra_in_comparison == ("tagExtra",)

    output = tmp_path / "output"
    write_item_tag_audit(result, output)
    assert (output / "item-tag-audit.md").is_file()
    csv_text = (output / "item-tag-entries.csv").read_text(encoding="utf-8-sig")
    assert "tagOne" in csv_text
    assert "tagTwo" in csv_text
