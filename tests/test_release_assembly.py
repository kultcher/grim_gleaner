from __future__ import annotations

import json
from pathlib import Path

import pytest

from gd_affix_relevance.catalog import CATALOG_SCHEMA_VERSION
from gd_affix_relevance.release_assembly import TAG_SOURCES, assemble_release


CATALOG_DATA_FILES = (
    "affixes.json",
    "skills.json",
    "strings.en.json",
    "equipment.json",
    "components.json",
    "augments.json",
    "relics.json",
    "runes.json",
    "consumables.json",
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_minimal_catalog(root: Path) -> None:
    counts = {
        "affixes": 0,
        "affix_variants": 0,
        "skills": 0,
        "strings": 0,
        "equipment": 0,
        "components": 0,
        "augments": 0,
        "relics": 0,
        "runes": 0,
        "consumables": 0,
        "items": 0,
        "item_variants": 0,
    }
    _write_json(
        root / "manifest.json",
        {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "game_version": "test",
            "locale": "en",
            "sources": ["base", "gdx1", "gdx2", "gdx3"],
            "files": list(CATALOG_DATA_FILES),
            "counts": counts,
            "affix_scope": "test",
            "skill_scope": "test",
            "item_scope": "test",
        },
    )
    _write_json(
        root / "strings.en.json",
        {"schema_version": CATALOG_SCHEMA_VERSION, "locale": "en", "strings": {}},
    )
    _write_json(
        root / "skills.json",
        {"schema_version": CATALOG_SCHEMA_VERSION, "skills": []},
    )
    _write_json(
        root / "affixes.json",
        {"schema_version": CATALOG_SCHEMA_VERSION, "affixes": []},
    )
    for filename in CATALOG_DATA_FILES[3:]:
        _write_json(
            root / filename,
            {"schema_version": CATALOG_SCHEMA_VERSION, "items": []},
        )


def _write_tag_sources(data_root: Path, *, value: str = "Value") -> None:
    for source, filename in TAG_SOURCES.items():
        path = data_root / source / "text_en" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"tag{source}={value}\n", encoding="utf-8")


def _project_fixture(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    (project / "README.md").parent.mkdir(parents=True)
    (project / "README.md").write_text("# Test release\n", encoding="utf-8")
    _write_minimal_catalog(project / "artifacts" / "catalog")
    _write_tag_sources(project / "game_data")
    output = project / "dist" / "Grim Gleaner"
    output.mkdir(parents=True)
    return project, output


def test_assembly_installs_resources_and_preserves_unmanaged_files(
    tmp_path: Path,
) -> None:
    project, output = _project_fixture(tmp_path)
    (output / "grim_gleaner.exe").write_bytes(b"exe")
    (output / "_internal").mkdir()
    (output / "_internal" / "runtime.dat").write_bytes(b"runtime")
    (output / "backups").mkdir()
    (output / "backups" / "user-copy.txt").write_text("keep", encoding="utf-8")
    (output / "Profiles").mkdir()
    (output / "Profiles" / "lightning.json").write_text("{}", encoding="utf-8")

    result = assemble_release(project)

    assert result.output_root == output.resolve()
    assert result.catalog_files == 10
    assert result.tag_files == 4
    assert result.tag_entries == 4
    assert (output / "catalog" / "manifest.json").is_file()
    assert (output / "tags" / "tagsgdx3_items.txt").is_file()
    assert (output / "README.txt").read_text(encoding="utf-8") == "# Test release\n"
    assert (output / "release-manifest.json").is_file()
    assert (output / "Profiles").is_dir()
    assert (output / "grim_gleaner.exe").read_bytes() == b"exe"
    assert (output / "_internal" / "runtime.dat").read_bytes() == b"runtime"
    assert (output / "backups" / "user-copy.txt").read_text(encoding="utf-8") == "keep"
    assert (output / "Profiles" / "lightning.json").read_text(encoding="utf-8") == "{}"


def test_reassembly_replaces_only_managed_contents(tmp_path: Path) -> None:
    project, output = _project_fixture(tmp_path)
    assemble_release(project)
    (output / "catalog" / "stale.json").write_text("stale", encoding="utf-8")
    (output / "tags" / "stale.txt").write_text("stale", encoding="utf-8")
    (output / "staging").mkdir()
    (output / "staging" / "keep.txt").write_text("keep", encoding="utf-8")
    _write_tag_sources(project / "game_data", value="Updated")

    assemble_release(project)

    assert not (output / "catalog" / "stale.json").exists()
    assert not (output / "tags" / "stale.txt").exists()
    assert "Updated" in (output / "tags" / "tags_items.txt").read_text(
        encoding="utf-8"
    )
    assert (output / "staging" / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_validation_failure_leaves_existing_release_untouched(tmp_path: Path) -> None:
    project, output = _project_fixture(tmp_path)
    sentinel = output / "catalog" / "existing.txt"
    sentinel.parent.mkdir()
    sentinel.write_text("keep", encoding="utf-8")
    (project / "game_data" / "gdx3" / "text_en" / "tagsgdx3_items.txt").unlink()

    with pytest.raises(FileNotFoundError, match="tagsgdx3_items.txt"):
        assemble_release(project)

    assert sentinel.read_text(encoding="utf-8") == "keep"
