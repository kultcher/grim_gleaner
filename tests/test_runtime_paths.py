from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

from gd_affix_relevance.domain import RUSSIAN_LOCALE
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
    assert paths.i18n_root == tmp_path.resolve() / "resources" / "i18n"


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
    assert paths.i18n_root == root.resolve() / "resources" / "i18n"


def test_russian_runtime_paths_use_locale_specific_resources(tmp_path: Path) -> None:
    development = resolve_runtime_paths(
        project_root=tmp_path,
        frozen=False,
        environment={},
        locale=RUSSIAN_LOCALE,
    )
    release = resolve_runtime_paths(
        application_root=tmp_path / "release",
        environment={},
        locale=RUSSIAN_LOCALE,
    )

    assert development.tags_root == tmp_path.resolve() / "artifacts" / "text_ru"
    assert development.locale is RUSSIAN_LOCALE
    assert development.staging_output_root == (
        tmp_path.resolve() / "artifacts" / "generated" / "text_ru"
    )
    assert release.tags_root == (tmp_path / "release" / "tags" / "ru").resolve()
    assert release.staging_output_root == (
        tmp_path / "release" / "staging" / "text_ru"
    ).resolve()
    assert release.as_dict()["locale"] == "ru"
    assert release.for_locale(RUSSIAN_LOCALE) == release


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


def test_export_sources_select_russian_game_directory(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    russian = game / "settings" / "text_ru"
    english = game / "settings" / "text_en"
    russian.mkdir(parents=True)
    english.mkdir(parents=True)
    (russian / "tags_items.txt").write_text(
        "tagExample=Пример\n",
        encoding="utf-8-sig",
    )
    (english / "tags_items.txt").write_text(
        "tagExample=Example\n",
        encoding="utf-8-sig",
    )

    selection = resolve_export_sources(
        game,
        tmp_path / "russian-tags",
        locale=RUSSIAN_LOCALE,
    )

    assert selection.game_text_root == russian.resolve()
    assert selection.primary_root == russian.resolve()
    assert selection.game_files == ("tags_items.txt",)


def test_export_sources_accept_nested_user_localization_root(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    user_text = tmp_path / "Documents" / "Settings" / "text_ru"
    nested = user_text / "aom"
    nested.mkdir(parents=True)
    (nested / "rainbow-items.txt").write_text("tag=value\n", encoding="utf-8")
    bundled = tmp_path / "bundled"

    selection = resolve_export_sources(
        game,
        bundled,
        locale=RUSSIAN_LOCALE,
        installed_text_root=user_text,
    )

    assert selection.primary_root == user_text.resolve()
    assert selection.fallback_root == bundled.resolve()
    assert selection.game_files == ("aom/rainbow-items.txt",)
