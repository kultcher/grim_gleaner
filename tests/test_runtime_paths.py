from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

from gd_affix_relevance.runtime_paths import (
    EXPORT_LOCALIZATION_SOURCES,
    resolve_export_sources,
    resolve_runtime_paths,
)


def test_development_paths_are_project_relative(tmp_path: Path) -> None:
    paths = resolve_runtime_paths(
        project_root=tmp_path,
        frozen=False,
        environment={},
    )

    assert paths.mode == "development"
    assert paths.application_root == tmp_path.resolve()
    assert paths.project_root == tmp_path.resolve()
    assert paths.catalog_root == tmp_path.resolve() / "artifacts" / "catalog"
    assert paths.tags_root == tmp_path.resolve() / "game_data"
    assert paths.staging_output_root == (
        tmp_path.resolve() / "artifacts" / "generated" / "text_en"
    )


def test_explicit_application_root_uses_release_layout(tmp_path: Path) -> None:
    root = tmp_path / "Grim Gleaner"
    paths = resolve_runtime_paths(
        application_root=root,
        project_root=tmp_path / "ignored",
        frozen=False,
        environment={},
    )

    assert paths.mode == "release"
    assert paths.project_root is None
    assert paths.catalog_root == root.resolve() / "catalog"
    assert paths.tags_root == root.resolve() / "tags"
    assert paths.staging_output_root == root.resolve() / "staging" / "text_en"
    assert paths.backups_root == root.resolve() / "backups"
    assert paths.profiles_root == root.resolve() / "Profiles"


def test_environment_override_selects_release_layout(tmp_path: Path) -> None:
    root = tmp_path / "portable"
    paths = resolve_runtime_paths(
        project_root=tmp_path / "source",
        frozen=False,
        environment={"GRIM_GLEANER_APP_ROOT": str(root)},
    )

    assert paths.mode == "release"
    assert paths.application_root == root.resolve()


def test_frozen_application_uses_executable_parent(tmp_path: Path) -> None:
    executable = tmp_path / "app" / "grim_gleaner.exe"
    paths = resolve_runtime_paths(
        frozen=True,
        executable=executable,
        environment={},
    )

    assert paths.mode == "release"
    assert paths.application_root == executable.parent.resolve()


def test_nuitka_application_uses_compiled_containing_directory(
    tmp_path: Path,
) -> None:
    root = tmp_path / "nuitka-output"
    paths = resolve_runtime_paths(
        frozen=False,
        nuitka_application_root=root,
        environment={},
    )

    assert paths.mode == "release"
    assert paths.application_root == root.resolve()
    assert paths.catalog_root == root.resolve() / "catalog"


def test_nuitka_marker_is_read_from_compiled_main_module(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "standalone"
    compiled_main = ModuleType("__main__")
    compiled_main.__compiled__ = SimpleNamespace(containing_dir=str(root))
    monkeypatch.setitem(sys.modules, "__main__", compiled_main)

    paths = resolve_runtime_paths(
        frozen=False,
        environment={},
    )

    assert paths.mode == "release"
    assert paths.application_root == root.resolve()
    assert paths.catalog_root == root.resolve() / "catalog"


def test_explicit_application_root_overrides_nuitka_directory(
    tmp_path: Path,
) -> None:
    explicit = tmp_path / "explicit"
    paths = resolve_runtime_paths(
        application_root=explicit,
        nuitka_application_root=tmp_path / "nuitka-output",
        frozen=False,
        environment={},
    )

    assert paths.application_root == explicit.resolve()


def test_export_sources_use_bundled_tags_when_game_has_none(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    text_root = game / "settings" / "text_en"
    text_root.mkdir(parents=True)
    (text_root / "unrelated.txt").write_text("tag=value\n", encoding="utf-8")
    bundled = tmp_path / "app" / "tags"

    selection = resolve_export_sources(game, bundled)

    assert selection.primary_root == text_root.resolve()
    assert selection.fallback_root == bundled.resolve()
    assert not selection.uses_game_files


def test_export_sources_prefer_installed_tags_with_bundled_fallback(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    text_root = game / "settings" / "text_en"
    text_root.mkdir(parents=True)
    (text_root / "tags_items.txt").write_text("tag=value\n", encoding="utf-8")
    bundled = tmp_path / "app" / "tags"

    selection = resolve_export_sources(game, bundled)

    assert selection.primary_root == text_root.resolve()
    assert selection.fallback_root == bundled.resolve()
    assert selection.game_files == ("tags_items.txt",)
    assert selection.uses_game_files


def test_export_sources_map_centralized_game_data_to_flat_filenames(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    for filename, relative_path in EXPORT_LOCALIZATION_SOURCES.items():
        source = game_data / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"{filename}=value\n", encoding="utf-8")

    selection = resolve_export_sources(None, game_data)

    assert selection.primary_root == game_data.resolve()
    assert selection.fallback_root is None
    assert selection.primary_files == tuple(
        ((game_data / relative_path).resolve(), Path(filename))
        for filename, relative_path in EXPORT_LOCALIZATION_SOURCES.items()
    )


def test_export_sources_reject_incomplete_centralized_game_data(
    tmp_path: Path,
) -> None:
    game_data = tmp_path / "game_data"
    first_relative = next(iter(EXPORT_LOCALIZATION_SOURCES.values()))
    source = game_data / first_relative
    source.parent.mkdir(parents=True)
    source.write_text("tag=value\n", encoding="utf-8")

    try:
        resolve_export_sources(None, game_data)
    except ValueError as error:
        assert "centralized game-data localization is incomplete" in str(error)
    else:
        raise AssertionError("incomplete centralized game data was accepted")
