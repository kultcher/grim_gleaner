import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import save_profile
from gd_affix_relevance.ui.profile_editor import ProfileEditor


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_editor_saves_and_loads_profile_into_existing_controls(
    tmp_path: Path,
) -> None:
    _application()
    original = BuildProfile("Original", {"health": 1})
    editor = ProfileEditor(original)
    editor.show()

    saved_path = editor.save_to_path(tmp_path / "original")

    assert saved_path.name == "original.json"
    assert editor.current_profile_path == saved_path
    assert editor.file_status.text() == "Saved: original.json"

    loaded_path = save_profile(
        BuildProfile("Loaded Build", {"health": 4, "movement_speed": 2}),
        tmp_path / "loaded.json",
    )
    returned = editor.load_from_path(loaded_path)

    assert returned is original
    assert editor.profile is original
    assert editor.name_edit.text() == "Loaded Build"
    assert original.weights == {"health": 4, "movement_speed": 2}
    assert (
        editor.accordions["core_health"].rows["health"].weight_control.value
        == 4
    )
    assert (
        editor.accordions["core_speed"]
        .rows["movement_speed"]
        .weight_control.value
        == 2
    )
    assert editor.accordions["core_health"].is_expanded
    assert editor.file_status.text() == "Loaded: loaded.json"

    editor.accordions["core_health"].rows["health"].weight_control.set_value(3)
    assert editor.file_status.text() == "Unsaved changes: loaded.json"
