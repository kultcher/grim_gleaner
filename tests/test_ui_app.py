from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gd_affix_relevance.ui.app import (
    DOCUMENTS_ROOT_ENVIRONMENT_VARIABLE,
    SETTINGS_ROOT_ENVIRONMENT_VARIABLE,
    _application_settings,
    _entrypoint_runtime_paths,
    _user_settings_root,
)


def test_compiled_entrypoint_explicitly_selects_packaged_resources(
    tmp_path,
) -> None:
    root = tmp_path / "Grim Gleaner"

    paths = _entrypoint_runtime_paths(
        SimpleNamespace(containing_dir=str(root.parent)),
        executable=root / "grim_gleaner.exe",
    )

    assert paths.mode == "release"
    assert paths.application_root == root.resolve()
    assert paths.catalog_root == root.resolve() / "catalog"
    assert paths.tags_root == root.resolve() / "tags"


def test_settings_root_override_isolates_fresh_install_state(tmp_path) -> None:
    settings = _application_settings(
        {SETTINGS_ROOT_ENVIRONMENT_VARIABLE: str(tmp_path / "settings")}
    )

    settings.setValue("paths/grim_dawn_folder", "isolated")
    settings.sync()

    assert Path(settings.fileName()) == (
        tmp_path / "settings" / "grim-gleaner.ini"
    ).resolve()
    assert settings.value("paths/grim_dawn_folder") == "isolated"


def test_documents_root_override_avoids_live_user_settings(tmp_path) -> None:
    documents = tmp_path / "Documents"
    expected = documents / "My Games" / "Grim Dawn" / "Settings"
    expected.mkdir(parents=True)

    actual = _user_settings_root(
        {DOCUMENTS_ROOT_ENVIRONMENT_VARIABLE: str(documents)}
    )

    assert actual == expected.resolve()
