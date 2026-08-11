from pathlib import Path

from gd_affix_relevance.records import RecordRepository


def _write_record(root: Path, source: str, logical: str, text: str) -> Path:
    path = root / source / Path(logical)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_uses_newest_overlay(
    tmp_path: Path,
) -> None:
    logical = "records/skills/example.dbr"
    _write_record(tmp_path, "base", logical, "skillDisplayName,tagOld,")
    _write_record(tmp_path, "gdx1", logical, "skillDisplayName,tagNew,")
    repository = RecordRepository(tmp_path, ("base", "gdx1"))

    resolved = repository.resolve(logical)

    assert resolved is not None
    source, record = resolved
    assert source == "gdx1"
    assert record.first_value("skillDisplayName") == "tagNew"


def test_iter_overlaid_returns_unique_newest_locations(tmp_path: Path) -> None:
    shared = "records/items/shared.dbr"
    base_only = "records/items/base_only.dbr"
    _write_record(tmp_path, "base", shared, "value,old,")
    _write_record(tmp_path, "base", base_only, "value,base,")
    _write_record(tmp_path, "gdx1", shared, "value,new,")
    repository = RecordRepository(tmp_path, ("base", "gdx1"))

    locations = repository.iter_overlaid("records/items")

    assert [(entry.logical_path, entry.source) for entry in locations] == [
        (base_only, "base"),
        (shared, "gdx1"),
    ]


def test_resolve_and_branch_load_share_parsed_record_cache(
    tmp_path: Path,
) -> None:
    logical = "records/items/example.dbr"
    _write_record(tmp_path, "base", logical, "value,once,")
    repository = RecordRepository(tmp_path, ("base",))
    location = repository.iter_overlaid("records/items")[0]

    first = repository.load(location)
    resolved = repository.resolve(logical)

    assert resolved is not None
    assert resolved[1] is first
    assert repository.cached_record_count == 1
