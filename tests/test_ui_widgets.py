import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.domain import BuildProfile
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


def test_main_window_reserves_top_matches_navigation() -> None:
    _application()
    window = MainWindow()

    assert window.navigation.count() == 2
    assert window.navigation.item(0).text() == "Build Profile"
    assert window.navigation.item(1).text() == "Top Matches"
    assert window.profile_editor.tabs.count() == 6
    assert window.profile_editor.tabs.tabText(4) == "Pets"
    assert window.profile_editor.tabs.tabText(5) == "Skills"
    assert window.focusPolicy() == Qt.FocusPolicy.NoFocus
