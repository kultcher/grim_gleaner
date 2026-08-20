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

from gd_affix_relevance.domain import (
    ENGLISH_LOCALE,
    SUPPORTED_LOCALES,
    LocaleSpec,
    locale_for_code,
)
from gd_affix_relevance.game_localization import prepare_game_item_tags
from gd_affix_relevance.grade_export import validate_grim_dawn_folder
from gd_affix_relevance.runtime_paths import RuntimePaths, resolve_runtime_paths
from gd_affix_relevance.ui.i18n import t

GAME_FOLDER_SETTING = "paths/grim_dawn_folder"
GAME_LOCALE_SETTING = "localization/game_locale"
UI_LOCALE_SETTING = "localization/ui_locale"


class SettingsPage(QWidget):
    """Store application paths that are not part of a build profile."""

    game_folder_changed = Signal(str)
    game_locale_changed = Signal(str)
    ui_locale_changed = Signal(str)

    def __init__(
        self,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
        *,
        runtime_paths: RuntimePaths | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.runtime_paths = runtime_paths or resolve_runtime_paths()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel(t("settings.title"), self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        hint = QLabel(t("settings.hint"), self)
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
        self.browse_button = QPushButton(t("settings.browse"), path_row)
        self.browse_button.setObjectName("profileAction")
        self.browse_button.clicked.connect(self._browse_game_folder)
        path_layout.addWidget(self.browse_button)
        form.addRow(t("settings.game_folder_row"), path_row)

        self.ui_locale_combo = QComboBox(self)
        for locale in SUPPORTED_LOCALES:
            self.ui_locale_combo.addItem(locale.display_name, locale.code)
        saved_ui_locale = self._saved_ui_locale()
        self.ui_locale_combo.setCurrentIndex(
            self.ui_locale_combo.findData(saved_ui_locale.code)
        )
        self.ui_locale_combo.currentIndexChanged.connect(self._save_ui_locale)
        form.addRow(t("settings.ui_locale_row"), self.ui_locale_combo)

        self.game_locale_combo = QComboBox(self)
        for locale in SUPPORTED_LOCALES:
            self.game_locale_combo.addItem(locale.display_name, locale.code)
        saved_locale = self._saved_game_locale()
        self.game_locale_combo.setCurrentIndex(
            self.game_locale_combo.findData(saved_locale.code)
        )
        self.game_locale_combo.currentIndexChanged.connect(self._save_game_locale)
        form.addRow(t("settings.game_locale_row"), self.game_locale_combo)
        layout.addLayout(form)

        self.ui_locale_status = QLabel(self)
        self.ui_locale_status.setObjectName("pageHint")
        self.ui_locale_status.setWordWrap(True)
        layout.addWidget(self.ui_locale_status)

        self.game_folder_status = QLabel(self)
        self.game_folder_status.setWordWrap(True)
        layout.addWidget(self.game_folder_status)

        self.prepare_localization_button = QPushButton(
            t("settings.prepare_localization_button"),
            self,
        )
        self.prepare_localization_button.setObjectName("profileAction")
        self.prepare_localization_button.clicked.connect(
            self._prepare_game_localization
        )
        layout.addWidget(self.prepare_localization_button)

        self.localization_status = QLabel(self)
        self.localization_status.setObjectName("pageHint")
        self.localization_status.setWordWrap(True)
        layout.addWidget(self.localization_status)

        note = QLabel(t("settings.export_note"), self)
        note.setObjectName("pageHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()
        self._refresh_game_folder_status()

    def _saved_game_folder(self) -> str:
        if self.settings is None:
            return ""
        return self.settings.value(GAME_FOLDER_SETTING, "", type=str)

    def _saved_game_locale(self) -> LocaleSpec:
        if self.settings is None:
            return self.runtime_paths.locale
        code = self.settings.value(
            GAME_LOCALE_SETTING,
            self.runtime_paths.locale.code,
            type=str,
        )
        try:
            return locale_for_code(code)
        except ValueError:
            return ENGLISH_LOCALE

    def selected_game_locale(self) -> LocaleSpec:
        return locale_for_code(self.game_locale_combo.currentData())

    def _save_game_locale(self, _index: int = -1) -> None:
        locale = self.selected_game_locale()
        self.runtime_paths = self.runtime_paths.for_locale(locale)
        if self.settings is not None:
            self.settings.setValue(GAME_LOCALE_SETTING, locale.code)
            self.settings.sync()
        self.localization_status.setText(
            t("settings.export_target_status", directory=locale.game_text_directory)
        )
        self.game_locale_changed.emit(locale.code)

    def _saved_ui_locale(self) -> LocaleSpec:
        if self.settings is None:
            return ENGLISH_LOCALE
        code = self.settings.value(
            UI_LOCALE_SETTING,
            ENGLISH_LOCALE.code,
            type=str,
        )
        try:
            return locale_for_code(code)
        except ValueError:
            return ENGLISH_LOCALE

    def selected_ui_locale(self) -> LocaleSpec:
        return locale_for_code(self.ui_locale_combo.currentData())

    def _save_ui_locale(self, _index: int = -1) -> None:
        locale = self.selected_ui_locale()
        if self.settings is not None:
            self.settings.setValue(UI_LOCALE_SETTING, locale.code)
            self.settings.sync()
        self.ui_locale_status.setText(
            t("settings.ui_locale_restart_notice", locale=locale.display_name)
        )
        self.ui_locale_changed.emit(locale.code)
        # Convenience default: choosing a UI language also points the Grim
        # Dawn item language at the same locale, since that is what most
        # users mean by "switch to Russian". The two settings stay stored
        # and editable independently; this only nudges the second combo.
        game_index = self.game_locale_combo.findData(locale.code)
        if game_index >= 0 and self.game_locale_combo.currentIndex() != game_index:
            self.game_locale_combo.setCurrentIndex(game_index)

    def _prepare_game_localization(self) -> None:
        try:
            game, error = self._game_folder_validation()
            if game is None:
                raise ValueError(error)
            locale = self.selected_game_locale()
            paths = self.runtime_paths.for_locale(locale)
            result = prepare_game_item_tags(
                game,
                paths.tags_root,
                locale=locale,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(
                self,
                t("settings.prepare_localization_error_title"),
                str(error),
            )
            return
        self.localization_status.setText(
            t(
                "settings.prepare_localization_success",
                count=len(result.files_written),
                output_root=result.output_root,
            )
        )

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
            t("settings.select_folder_dialog_title"),
            starting_path,
        )
        if not selected:
            return False
        self.game_folder_edit.setText(selected)
        self._save_game_folder()
        if not self.has_valid_game_folder():
            QMessageBox.warning(
                self,
                t("settings.game_not_found_title"),
                t("settings.game_not_found_body"),
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
                t("settings.game_folder_confirmed", path=game)
            )
        self.game_folder_status.style().unpolish(self.game_folder_status)
        self.game_folder_status.style().polish(self.game_folder_status)

    def _game_folder_validation(self) -> tuple[Path | None, str]:
        value = self.game_folder_edit.text().strip()
        if not value:
            return None, t("settings.game_folder_not_configured")
        try:
            return validate_grim_dawn_folder(Path(value)), ""
        except (OSError, ValueError) as error:
            return None, t("settings.game_folder_not_confirmed", error=error)
