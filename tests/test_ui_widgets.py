import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QLabel

from gd_affix_relevance.catalog import AffixCatalog
from gd_affix_relevance.domain import BuildProfile, RUSSIAN_LOCALE
from gd_affix_relevance.grade_export import LOCALIZATION_LOCATION_USER
from gd_affix_relevance.profile_store import save_profile
from gd_affix_relevance.runtime_paths import RuntimePaths
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
    assert changes == [("health", 1), ("movement_speed", 1)]
    accordion.modify_all.star_buttons[2].click()
    assert profile.weights == {"health": 3, "movement_speed": 3}
    accordion.modify_all.decrement_button.click()
    assert profile.weights == {"health": 2, "movement_speed": 2}
    assert changes == [
        ("health", 1),
        ("movement_speed", 1),
        ("health", 3),
        ("movement_speed", 3),
        ("health", 2),
        ("movement_speed", 2),
    ]


def test_conversion_row_folds_sources_and_persists_unchecked_types() -> None:
    _application()
    profile = BuildProfile(weights={"damage_conversion_to_fire": 4})
    definition = PackageDefinition(
        "fire",
        "Fire",
        (stat("damage_conversion_to_fire", "Damage Converted to Fire"),),
    )
    accordion = PackageAccordion(
        definition,
        profile.weight_for,
        profile.set_weight,
        conversion_source_enabled=profile.conversion_source_enabled,
        set_conversion_source_enabled=profile.set_conversion_source_enabled,
    )
    changes: list[tuple[str, str, bool]] = []
    accordion.conversion_source_changed.connect(
        lambda destination, source, enabled: changes.append(
            (destination, source, enabled)
        )
    )
    accordion.show()

    row = accordion.rows["damage_conversion_to_fire"]
    assert row.sources_button.text().endswith("Sources 10/10")
    assert row.source_checkboxes["specific_skill"].text() == "Specific Skill"
    assert row.source_checkboxes["specific_skill"].isChecked()
    assert row.sources_body.isHidden()
    row.sources_button.click()
    assert not row.sources_body.isHidden()
    row.source_checkboxes["physical"].setChecked(False)

    assert not profile.conversion_source_enabled("fire", "physical")
    assert row.sources_button.text().endswith("Sources 9/10")
    assert changes == [("fire", "physical", False)]


def test_main_window_exposes_gear_grade_subnavigation_and_settings() -> None:
    _application()
    window = MainWindow(catalog=AffixCatalog(()))

    assert window.navigation.count() == 8
    assert window.navigation.item(0).text() == "Build Profile"
    assert window.navigation.item(1).text() == "Gear Grades"
    assert window.navigation.item(2).text().strip() == "Affixes"
    assert window.navigation.item(3).text().strip() == "Uniques"
    assert window.navigation.item(4).text().strip() == "Add-ons"
    assert window.navigation.item(5).text() == "Export Grades"
    assert window.navigation.item(6).text() == "Settings"
    assert window.navigation.item(7).text() == "Guide"
    assert (
        window.navigation.item(2).font().pointSizeF()
        < window.navigation.item(1).font().pointSizeF()
    )
    assert window.profile_editor.tabs.count() == 6
    assert window.profile_editor.tabs.tabText(4) == "Pets"
    assert window.profile_editor.tabs.tabText(5) == "Skills"
    assert window.profile_editor.level_band_combo.currentData() == "90+"
    assert window.sidebar_profile_name.text() == "New Build Profile"
    assert window.sidebar_profile_level.text() == "Profile level: 90+"
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

    window.profile_editor.name_edit.setText("Sidebar Test")
    window.profile_editor.level_band_combo.setCurrentIndex(
        window.profile_editor.level_band_combo.findData("50-64")
    )
    assert window.sidebar_profile_name.text() == "Sidebar Test"
    assert window.sidebar_profile_level.text() == "Profile level: 50-64"

    window.profile_editor.view_matches_button.click()
    assert window.navigation.currentRow() == 1
    assert window.pages.currentWidget() is window.top_matches_page

    window.navigation.setCurrentRow(3)
    assert window.pages.currentWidget() is window.top_matches_page
    assert window.top_matches_page.tabs.currentIndex() == 1

    window.top_matches_page.tabs.setCurrentIndex(2)
    assert window.navigation.currentRow() == 4

    window.navigation.setCurrentRow(5)
    assert window.pages.currentWidget() is window.generate_output_page
    window.navigation.setCurrentRow(6)
    assert window.pages.currentWidget() is window.settings_page
    window.navigation.setCurrentRow(7)
    assert window.pages.currentWidget() is window.guide_page
    assert window.guide_page.findChild(QLabel, "pageTitle").text() == "Guide"


def test_settings_page_persists_grim_dawn_folder(tmp_path: Path) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    window = MainWindow(catalog=AffixCatalog(()), settings=settings)
    game_folder = str(tmp_path / "Grim Dawn")

    window.settings_page.game_folder_edit.setText(game_folder)
    window.settings_page.game_folder_edit.editingFinished.emit()

    assert settings.value("paths/grim_dawn_folder") == game_folder
    restored = MainWindow(catalog=AffixCatalog(()), settings=settings)
    assert restored.settings_page.game_folder_edit.text() == game_folder

    window.settings_page.localization_location_combo.setCurrentIndex(
        window.settings_page.localization_location_combo.findData(
            LOCALIZATION_LOCATION_USER
        )
    )
    assert settings.value("paths/localization_location") == (
        LOCALIZATION_LOCATION_USER
    )
    restored = MainWindow(catalog=AffixCatalog(()), settings=settings)
    assert restored.settings_page.localization_location_combo.currentData() == (
        LOCALIZATION_LOCATION_USER
    )


def test_settings_page_switches_export_to_russian_locale(tmp_path: Path) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    runtime_paths = RuntimePaths(
        mode="development",
        application_root=tmp_path,
        project_root=tmp_path,
        catalog_root=tmp_path / "artifacts" / "catalog",
        tags_root=tmp_path / "artifacts" / "text_en",
        staging_output_root=tmp_path / "artifacts" / "generated" / "text_en",
        backups_root=tmp_path / "artifacts" / "backups",
        profiles_root=tmp_path / "artifacts" / "profiles",
        i18n_root=tmp_path / "resources" / "i18n",
    )
    window = MainWindow(
        catalog=AffixCatalog(()),
        settings=settings,
        runtime_paths=runtime_paths,
    )

    window.settings_page.game_locale_combo.setCurrentIndex(
        window.settings_page.game_locale_combo.findData("ru")
    )

    assert settings.value("localization/game_locale") == "ru"
    assert window.runtime_paths.locale is RUSSIAN_LOCALE
    assert window.generate_output_page.locale is RUSSIAN_LOCALE
    assert window.generate_output_page.staging_root.name == "text_ru"


def test_game_folder_confirmation_controls_warning_and_export(
    tmp_path: Path,
) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    settings.setValue("paths/grim_dawn_folder", str(game))

    window = MainWindow(catalog=AffixCatalog(()), settings=settings)

    assert not window.game_location_warning.isHidden()
    assert not window.generate_output_page.generate_button.isEnabled()
    assert window.settings_page.game_folder_status.objectName() == (
        "gameFolderWarning"
    )

    (game / "Grim Dawn.exe").touch()
    window.settings_page.game_folder_edit.editingFinished.emit()

    assert window.game_location_warning.isHidden()
    assert window.generate_output_page.generate_button.isEnabled()
    assert window.settings_page.game_folder_status.objectName() == (
        "gameFolderConfirmed"
    )


def test_startup_game_folder_prompt_runs_once_and_opens_settings(
    tmp_path: Path,
) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    window = MainWindow(catalog=AffixCatalog(()), settings=settings)
    prompts: list[bool] = []
    window.settings_page.prompt_for_game_folder = lambda: prompts.append(True) or False

    window.prompt_for_game_folder_if_needed()
    window.prompt_for_game_folder_if_needed()

    assert prompts == [True]
    assert window.navigation.currentRow() == window.settings_navigation_row
    assert not window.game_location_warning.isHidden()


def test_missing_packaged_catalog_is_prominent_and_disables_export(
    tmp_path: Path,
) -> None:
    _application()
    root = tmp_path / "release"
    runtime_paths = RuntimePaths(
        mode="release",
        application_root=root,
        project_root=None,
        catalog_root=root / "catalog",
        tags_root=root / "tags",
        staging_output_root=root / "staging" / "text_en",
        backups_root=root / "backups",
        profiles_root=root / "Profiles",
        i18n_root=root / "resources" / "i18n",
    )
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )

    window = MainWindow(settings=settings, runtime_paths=runtime_paths)

    assert window.catalog_load_error
    assert not window.catalog_warning.isHidden()
    assert "packaged catalog is missing" in window.catalog_load_error
    assert not window.generate_output_page.generate_button.isEnabled()


def test_main_window_close_honors_profile_confirmation() -> None:
    _application()
    window = MainWindow(catalog=AffixCatalog(()))

    window.profile_editor.confirm_close = lambda: False
    cancelled = QCloseEvent()
    window.closeEvent(cancelled)
    assert not cancelled.isAccepted()

    window.profile_editor.confirm_close = lambda: True
    accepted = QCloseEvent()
    window.closeEvent(accepted)
    assert accepted.isAccepted()


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
