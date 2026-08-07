import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import save_profile
from gd_affix_relevance.profile_store import load_profile
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


def test_new_profile_can_cancel_or_clear_every_profile_field() -> None:
    _application()
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    profile = BuildProfile(
        "Existing",
        {"health": 4},
        masteries=("playerclass01", "playerclass02"),
        skill_weights={skill_id: 3},
    )
    editor = ProfileEditor(profile)
    editor.name_edit.setText("Changed")
    assert editor.is_dirty

    editor._prompt_unsaved_action = (
        lambda: QMessageBox.StandardButton.Cancel
    )
    assert not editor.new_profile()
    assert profile.name == "Changed"
    assert profile.weights == {"health": 4}

    editor._prompt_unsaved_action = (
        lambda: QMessageBox.StandardButton.Discard
    )
    assert editor.new_profile()
    assert profile is editor.profile
    assert profile.name == "New Build Profile"
    assert profile.weights == {}
    assert profile.masteries == ("", "")
    assert profile.skill_weights == {}
    assert editor.current_profile_path is None
    assert not editor.is_dirty
    assert editor.accordions["core_health"].rows[
        "health"
    ].weight_control.value == 0


def test_new_profile_save_choice_writes_dirty_profile_before_reset(
    tmp_path: Path,
) -> None:
    _application()
    profile = BuildProfile("Saved Build", {"health": 2})
    editor = ProfileEditor(profile)
    destination = editor.save_to_path(tmp_path / "saved.json")
    editor.accordions["core_health"].rows[
        "health"
    ].weight_control.set_value(4)
    editor._prompt_unsaved_action = lambda: QMessageBox.StandardButton.Save

    assert editor.new_profile()
    assert load_profile(destination).weight_for("health") == 4
    assert editor.profile.weights == {}
