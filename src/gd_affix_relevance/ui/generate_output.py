"""Install and restore graded Grim Dawn item localization."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.grade_export import (
    GradeExportResult,
    LOCALIZATION_LOCATION_AUTO,
    LOCALIZATION_LOCATION_CHOICES,
    backup_available,
    export_grades_to_game,
    grim_dawn_text_root,
    restore_game_backup,
)
from gd_affix_relevance.output import build_affix_markers, build_unique_item_markers
from gd_affix_relevance.ui.settings import (
    GAME_FOLDER_SETTING,
    LOCALIZATION_LOCATION_SETTING,
)

LAST_EXPORTED_PROFILE_SETTING = "export/last_profile_name"


class GenerateOutputPage(QWidget):
    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        items: ItemCatalog | None = None,
        source_root: Path,
        output_root: Path,
        backups_root: Path,
        user_settings_root: Path | None = None,
        catalog_status: str = "",
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.items = items or ItemCatalog((), (), (), (), (), ())
        self.profile = profile
        self.catalog_status = catalog_status
        self.settings = settings
        self.bundled_source_root = Path(source_root)
        self.staging_root = Path(output_root)
        self.backups_root = Path(backups_root)
        self.user_settings_root = (
            Path(user_settings_root) if user_settings_root is not None else None
        )
        self.last_result: GradeExportResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        heading = QLabel("Export Grades", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        explanation = QLabel(
            "Export Grades applies the active profile's affix and unique-item "
            "grades directly to Grim Dawn's item names. Existing Rainbow item "
            "files are retained as the source, while Grim Gleaner's bundled "
            "files supply anything missing. Before the first export, the "
            "current localization folder is backed up so it can be restored here.",
            self,
        )
        explanation.setObjectName("pageHint")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.target_label = QLabel(self)
        self.target_label.setObjectName("fieldLabel")
        self.target_label.setWordWrap(True)
        layout.addWidget(self.target_label)

        action_row = QHBoxLayout()
        self.generate_button = QPushButton("Export Grades", self)
        self.generate_button.setObjectName("primaryAction")
        self.generate_button.setEnabled(catalog is not None)
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.generate_button)

        self.restore_button = QPushButton("Restore Backups", self)
        self.restore_button.setObjectName("profileAction")
        self.restore_button.clicked.connect(self.restore_backup)
        action_row.addWidget(self.restore_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        if catalog is None:
            self.status.setText(catalog_status or "No compiled catalog is available.")
        else:
            self.status.setText(catalog_status)
        layout.addWidget(self.status)

        last_export_row = QHBoxLayout()
        last_export_label = QLabel("Last Exported Profile:", self)
        last_export_label.setObjectName("fieldLabel")
        last_export_row.addWidget(last_export_label)
        self.last_exported_profile = QLabel(self._last_exported_profile_name(), self)
        self.last_exported_profile.setObjectName("lastExportedProfile")
        last_export_row.addWidget(self.last_exported_profile)
        last_export_row.addStretch()
        layout.addLayout(last_export_row)
        layout.addStretch()
        self.refresh_game_location()

    def generate(self, _checked: bool = False) -> None:
        if self.catalog is None:
            return
        try:
            game_folder = self._configured_game_folder()
            grim_dawn_text_root(
                game_folder,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Export Grades", str(error))
            return

        affix_count = len(build_affix_markers(self.catalog, self.profile))
        unique_count = len(build_unique_item_markers(self.items, self.profile))
        choice = QMessageBox.question(
            self,
            "Export Grades",
            "About to apply grade tags to "
            f"{affix_count} affix and {unique_count} unique item entries. "
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = export_grades_to_game(
                game_folder,
                self.bundled_source_root,
                self.staging_root,
                self.backups_root,
                self.catalog,
                self.profile,
                items=self.items,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Export Grades", str(error))
            return

        self.last_result = result
        backup_status = (
            "Created the original-state backup."
            if result.backup_created
            else "Preserved the existing original-state backup."
        )
        self.status.setText(
            f"{backup_status}"
            f"\nExported grades to {result.target_root}. "
            f"\nUpdated {result.generation.annotated_lines} localization entries. "
        )
        exported_name = self.profile.name.strip() or "Unnamed Profile"
        self.last_exported_profile.setText(exported_name)
        if self.settings is not None:
            self.settings.setValue(LAST_EXPORTED_PROFILE_SETTING, exported_name)
            self.settings.sync()
        self.refresh_game_location(update_status=False)

    def restore_backup(self, _checked: bool = False) -> None:
        try:
            game_folder = self._configured_game_folder()
            target = grim_dawn_text_root(
                game_folder,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
            if not backup_available(
                game_folder,
                self.backups_root,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            ):
                raise ValueError(
                    "No original-state backup exists for the configured Grim Dawn folder."
                )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Restore Backup", str(error))
            return

        choice = QMessageBox.question(
            self,
            "Restore Backup",
            f"Restoring {target} to its original state.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = restore_game_backup(
                game_folder,
                self.backups_root,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Restore Backup", str(error))
            return
        if result.original_existed:
            message = f"Restored {result.restored_files} files to {result.target_root}."
        else:
            message = (
                "Restored the clean-install state by removing Grim Gleaner's "
                f"generated folder at {result.target_root}."
            )
        self.status.setText(message)
        self.last_result = None
        self.refresh_game_location(update_status=False)

    def refresh_game_location(
        self,
        _game_folder: str = "",
        *,
        update_status: bool = False,
    ) -> None:
        try:
            game_folder = self._configured_game_folder()
            target = grim_dawn_text_root(
                game_folder,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
        except (OSError, ValueError) as error:
            message = str(error)
            if not (
                "Localization files exist in both" in message
                or "Documents/My Games Grim Dawn Settings" in message
            ):
                message = "Set a valid Grim Dawn folder on the Settings page."
            self.target_label.setText(f"Target unavailable: {message}")
            self.generate_button.setEnabled(False)
            self.restore_button.setEnabled(False)
            if update_status:
                self.status.setText("A valid Grim Dawn folder is required.")
            return
        self.target_label.setText(f"Target: {target}")
        self.generate_button.setEnabled(self.catalog is not None)
        self.restore_button.setEnabled(
            backup_available(
                game_folder,
                self.backups_root,
                user_settings_root=self.user_settings_root,
                location_preference=self._localization_location_preference(),
            )
        )

    def _localization_location_preference(self) -> str:
        if self.settings is None:
            return LOCALIZATION_LOCATION_AUTO
        value = self.settings.value(
            LOCALIZATION_LOCATION_SETTING,
            LOCALIZATION_LOCATION_AUTO,
            type=str,
        )
        return (
            value
            if value in LOCALIZATION_LOCATION_CHOICES
            else LOCALIZATION_LOCATION_AUTO
        )

    def _configured_game_folder(self) -> Path:
        if self.settings is None:
            raise ValueError("Set the Grim Dawn folder on the Settings page first.")
        raw_path = self.settings.value(GAME_FOLDER_SETTING, "", type=str).strip()
        if not raw_path:
            raise ValueError("Set the Grim Dawn folder on the Settings page first.")
        return Path(raw_path)

    def _last_exported_profile_name(self) -> str:
        if self.settings is None:
            return "None"
        return self.settings.value(
            LAST_EXPORTED_PROFILE_SETTING,
            "None",
            type=str,
        )
