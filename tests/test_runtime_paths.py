from __future__ import annotations

from pathlib import Path

from gd_affix_relevance.runtime_paths import (
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
    assert paths.tags_root == tmp_path.resolve() / "artifacts" / "text_en"
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
