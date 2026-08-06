from pathlib import Path

from gd_affix_relevance.normalization.affix_reachability import (
    build_affix_reference_statuses,
)


def _write_dbr(path: Path, fields: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key},{value},\n" for key, value in fields),
        encoding="utf-8",
    )


def _affix_fields(tag: str) -> list[tuple[str, str]]:
    return [
        ("Class", "LootRandomizer"),
        ("itemClassification", "Magical"),
        ("lootRandomizerName", tag),
    ]


def test_affix_reference_status_distinguishes_reachable_and_orphaned_records(
    tmp_path: Path,
) -> None:
    source = tmp_path / "base"
    prefix = source / "records" / "items" / "lootaffixes" / "prefix"
    live = prefix / "live.dbr"
    table_only = prefix / "table_only.dbr"
    unreferenced = prefix / "unreferenced.dbr"
    live_table = prefix / "prefixtables" / "live_table.dbr"
    orphan_table = prefix / "prefixtables" / "orphan_table.dbr"
    loottable = source / "records" / "items" / "loottables" / "root.dbr"

    _write_dbr(live, _affix_fields("tagLive"))
    _write_dbr(table_only, _affix_fields("tagTableOnly"))
    _write_dbr(unreferenced, _affix_fields("tagUnreferenced"))
    _write_dbr(
        live_table,
        [("randomizerName1", "records/items/lootaffixes/prefix/live.dbr")],
    )
    _write_dbr(
        orphan_table,
        [
            (
                "randomizerName1",
                "records/items/lootaffixes/prefix/table_only.dbr",
            )
        ],
    )
    _write_dbr(
        loottable,
        [
            (
                "prefixTableName1",
                "records/items/lootaffixes/prefix/prefixtables/live_table.dbr",
            )
        ],
    )

    statuses = {
        status.localization_tag: status
        for status in build_affix_reference_statuses(tmp_path, source_names=("base",))
    }

    assert statuses["tagLive"].reference_status == "reachable_from_item_loottable"
    assert (
        statuses["tagTableOnly"].reference_status
        == "referenced_only_by_unreachable_records"
    )
    assert statuses["tagUnreferenced"].reference_status == "no_incoming_item_reference"
