"""Application-level settings page."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

GAME_FOLDER_SETTING = "paths/grim_dawn_folder"


class SettingsPage(QWidget):
    """Store application paths that are not part of a build profile."""

    game_folder_changed = Signal(str)

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
        layout.addLayout(form)

        note = QLabel(
            "Export Grades checks this folder's settings/text_en directory for "
            "existing item-tag files. Installed files take precedence and the "
            "bundled clean-install tags fill any missing files. Export writes "
            "the graded files there after preserving an original-state backup.",
            self,
        )
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

    def _saved_game_folder(self) -> str:
        if self.settings is None:
            return ""
        return self.settings.value(GAME_FOLDER_SETTING, "", type=str)

    def _save_game_folder(self) -> None:
        if self.settings is None:
            return
        value = self.game_folder_edit.text().strip()
        if value:
            self.settings.setValue(GAME_FOLDER_SETTING, value)
        else:
            self.settings.remove(GAME_FOLDER_SETTING)
        self.settings.sync()
        self.game_folder_changed.emit(value)

    def _browse_game_folder(self) -> None:
        starting_path = self.game_folder_edit.text().strip() or str(Path.cwd())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Grim Dawn Folder",
            starting_path,
        )
        if not selected:
            return
        self.game_folder_edit.setText(selected)
        self._save_game_folder()
