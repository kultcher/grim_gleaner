"""Application-level settings page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.grade_export import (
    LOCALIZATION_LOCATION_AUTO,
    LOCALIZATION_LOCATION_CHOICES,
    LOCALIZATION_LOCATION_INSTALLATION,
    LOCALIZATION_LOCATION_USER,
    validate_grim_dawn_folder,
)

GAME_FOLDER_SETTING = "paths/grim_dawn_folder"
LOCALIZATION_LOCATION_SETTING = "paths/localization_location"


class SettingsPage(QWidget):
    """Store application paths that are not part of a build profile."""

    game_folder_changed = Signal(str)
    localization_location_changed = Signal(str)

    def __init__(
        self,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Settings", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        hint = QLabel(
            "Application-level paths and preferences. These settings are "
            "stored separately from build profiles.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.game_folder_edit = QLineEdit(self._saved_game_folder(), self)
        self.game_folder_edit.setObjectName("outputPath")
        self.game_folder_edit.setPlaceholderText(
            r"Example: C:\Program Files (x86)\Steam\steamapps\common\Grim Dawn"
        )
        self.game_folder_edit.editingFinished.connect(self._save_game_folder)

        path_row = QWidget(self)
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        path_layout.addWidget(self.game_folder_edit, 1)
        self.browse_button = QPushButton("Browse...", path_row)
        self.browse_button.setObjectName("profileAction")
        self.browse_button.clicked.connect(self._browse_game_folder)
        path_layout.addWidget(self.browse_button)
        form.addRow("Grim Dawn folder location", path_row)

        self.localization_location_combo = QComboBox(self)
        self.localization_location_combo.addItem(
            "Automatic (use the only existing localization)",
            LOCALIZATION_LOCATION_AUTO,
        )
        self.localization_location_combo.addItem(
            "Grim Dawn installation folder",
            LOCALIZATION_LOCATION_INSTALLATION,
        )
        self.localization_location_combo.addItem(
            "Documents / My Games",
            LOCALIZATION_LOCATION_USER,
        )
        saved_location = self._saved_localization_location()
        self.localization_location_combo.setCurrentIndex(
            self.localization_location_combo.findData(saved_location)
        )
        self.localization_location_combo.currentIndexChanged.connect(
            self._save_localization_location
        )
        form.addRow("Localization output location", self.localization_location_combo)
        layout.addLayout(form)

        self.game_folder_status = QLabel(self)
        self.game_folder_status.setWordWrap(True)
        layout.addWidget(self.game_folder_status)

        note = QLabel(
            "Automatic selection uses whichever supported location already "
            "contains localization files. If both the game folder and "
            "Documents contain them, choose one explicitly. Export preserves "
            "an original-state backup of the selected location.",
            self,
        )
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._refresh_game_folder_status()

    def _saved_game_folder(self) -> str:
        if self.settings is None:
            return ""
        return self.settings.value(GAME_FOLDER_SETTING, "", type=str)

    def _saved_localization_location(self) -> str:
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

    def _save_localization_location(self, _index: int = -1) -> None:
        value = str(self.localization_location_combo.currentData())
        if self.settings is not None:
            self.settings.setValue(LOCALIZATION_LOCATION_SETTING, value)
            self.settings.sync()
        self.localization_location_changed.emit(value)

    def _save_game_folder(self) -> None:
        value = self.game_folder_edit.text().strip()
        if self.settings is not None:
            if value:
                self.settings.setValue(GAME_FOLDER_SETTING, value)
            else:
                self.settings.remove(GAME_FOLDER_SETTING)
            self.settings.sync()
        self._refresh_game_folder_status()
        self.game_folder_changed.emit(value)

    def prompt_for_game_folder(self) -> bool:
        """Ask for an install root and return whether it was confirmed."""

        starting_path = self.game_folder_edit.text().strip() or str(Path.cwd())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Grim Dawn Folder (contains Grim Dawn.exe)",
            starting_path,
        )
        if not selected:
            return False
        self.game_folder_edit.setText(selected)
        self._save_game_folder()
        if not self.has_valid_game_folder():
            QMessageBox.warning(
                self,
                "Grim Dawn Not Found",
                "That folder does not contain Grim Dawn.exe. Select the Grim "
                "Dawn installation folder itself.",
            )
            return False
        return True

    def _browse_game_folder(self) -> None:
        self.prompt_for_game_folder()

    def has_valid_game_folder(self) -> bool:
        game, _ = self._game_folder_validation()
        return game is not None

    def _refresh_game_folder_status(self) -> None:
        game, error = self._game_folder_validation()
        if game is None:
            self.game_folder_status.setObjectName("gameFolderWarning")
            self.game_folder_status.setText(error)
        else:
            self.game_folder_status.setObjectName("gameFolderConfirmed")
            self.game_folder_status.setText(
                f"Confirmed Grim Dawn installation: {game}"
            )
        self.game_folder_status.style().unpolish(self.game_folder_status)
        self.game_folder_status.style().polish(self.game_folder_status)

    def _game_folder_validation(self) -> tuple[Path | None, str]:
        value = self.game_folder_edit.text().strip()
        if not value:
            return (
                None,
                "Not configured. Select the folder containing Grim Dawn.exe.",
            )
        try:
            return validate_grim_dawn_folder(Path(value)), ""
        except (OSError, ValueError) as error:
            return None, f"Not confirmed: {error}"
