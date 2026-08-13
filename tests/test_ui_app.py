from __future__ import annotations

from types import SimpleNamespace

from gd_affix_relevance.ui.app import _entrypoint_runtime_paths


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
