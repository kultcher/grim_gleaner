import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import AffixCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import save_profile
from gd_affix_relevance.ui.catalog import PackageDefinition, stat
from gd_affix_relevance.ui.main_window import MainWindow
from gd_affix_relevance.ui.widgets import PackageAccordion, WeightControl


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_weight_control_restricts_value_and_supports_buttons() -> None:
    _application()
    control = WeightControl()

    control.increment_button.click()
    control.star_buttons[2].click()

    assert control.value == 3
    assert [button.text() for button in control.star_buttons] == ["★", "★", "★", "☆"]
    control.set_value(4)
    assert not control.increment_button.isEnabled()
    control.set_value(0)
    assert not control.decrement_button.isEnabled()


def test_optional_accordion_is_pinned_by_nonzero_data() -> None:
    _application()
    profile = BuildProfile()
    definition = PackageDefinition("test", "Test", (stat("health", "Health"),))
    accordion = PackageAccordion(
        definition,
        profile.weight_for,
        profile.set_weight,
    )
    accordion.show()

    assert not accordion.is_expanded
    accordion.rows["health"].weight_control.set_value(2)
    assert accordion.is_expanded
    assert accordion.is_pinned

    accordion.set_expanded(False)
    assert accordion.is_expanded

    accordion.rows["health"].weight_control.set_value(0)
    accordion.set_expanded(False)
    assert not accordion.is_expanded


def test_package_modify_all_adjusts_every_stat_and_only_shows_when_expanded() -> None:
    _application()
    profile = BuildProfile()
    definition = PackageDefinition(
        "test",
        "Test",
        (stat("health", "Health"), stat("movement_speed", "Movement Speed")),
    )
    accordion = PackageAccordion(
        definition,
        profile.weight_for,
        profile.set_weight,
    )
    changes: list[tuple[str, int]] = []
    accordion.weight_changed.connect(
        lambda stat_id, weight: changes.append((stat_id, weight))
    )
    accordion.show()

    assert accordion.modify_all.isHidden()
    accordion.set_expanded(True)
    assert not accordion.modify_all.isHidden()
    accordion.modify_all.increment_button.click()
    assert profile.weights == {"health": 1, "movement_speed": 1}
    assert len(changes) == 1
    accordion.modify_all.star_buttons[2].click()
    assert profile.weights == {"health": 3, "movement_speed": 3}
    accordion.modify_all.decrement_button.click()
    assert profile.weights == {"health": 2, "movement_speed": 2}


def test_main_window_reserves_top_matches_navigation() -> None:
    _application()
    window = MainWindow(catalog=AffixCatalog(()))

    assert window.navigation.count() == 3
    assert window.navigation.item(0).text() == "Build Profile"
    assert window.navigation.item(1).text() == "Top Matches"
    assert window.navigation.item(2).text() == "Generate Output"
    assert window.profile_editor.tabs.count() == 6
    assert window.profile_editor.tabs.tabText(4) == "Pets"
    assert window.profile_editor.tabs.tabText(5) == "Skills"
    assert {
        "pets_damage",
        "pets_defenses",
        "pets_utility",
    } <= window.profile_editor.accordions.keys()
    assert all(
        window.profile_editor.accordions[package_id].is_pinned
        for package_id in ("pets_damage", "pets_defenses", "pets_utility")
    )
    assert window.focusPolicy() == Qt.FocusPolicy.NoFocus

    window.profile_editor.view_matches_button.click()
    assert window.navigation.currentRow() == 1


def test_main_window_restores_and_tracks_last_active_profile(tmp_path: Path) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    saved = save_profile(
        BuildProfile("Remembered", {"health": 4}),
        tmp_path / "remembered.json",
    )
    settings.setValue("profiles/active_path", str(saved))
    settings.sync()

    window = MainWindow(catalog=AffixCatalog(()), settings=settings)
    assert window.profile_editor.profile.name == "Remembered"
    assert window.profile_editor.current_profile_path == saved

    replacement = window.profile_editor.save_to_path(tmp_path / "replacement.json")
    assert settings.value("profiles/active_path") == str(replacement.resolve())
    window.profile_editor.new_profile()
    assert settings.value("profiles/active_path") is None


def test_missing_last_profile_falls_back_to_blank_profile(tmp_path: Path) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    settings.setValue("profiles/active_path", str(tmp_path / "missing.json"))
    settings.sync()

    window = MainWindow(catalog=AffixCatalog(()), settings=settings)

    assert window.profile_editor.profile.name == "New Build Profile"
    assert "could not be found" in window.profile_editor.file_status.text()
    assert settings.value("profiles/active_path") is None
