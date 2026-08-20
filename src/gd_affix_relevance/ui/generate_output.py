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
from gd_affix_relevance.domain import ENGLISH_LOCALE, BuildProfile, LocaleSpec
from gd_affix_relevance.game_localization import prepare_game_item_tags
from gd_affix_relevance.grade_export import (
    GradeExportResult,
    backup_available,
    export_grades_to_game,
    grim_dawn_text_root,
    restore_game_backup,
)
from gd_affix_relevance.output import build_affix_markers, build_unique_item_markers
from gd_affix_relevance.runtime_paths import ITEM_TAG_FILENAMES
from gd_affix_relevance.ui.i18n import t
from gd_affix_relevance.ui.settings import GAME_FOLDER_SETTING

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
        locale: LocaleSpec = ENGLISH_LOCALE,
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
        self.locale = locale
        self.last_result: GradeExportResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        heading = QLabel(t("export.title"), self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        explanation = QLabel(
            t(
                "export.explanation",
                directory=self.locale.game_text_directory,
            ),
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
        self.generate_button = QPushButton(t("export.generate_button"), self)
        self.generate_button.setObjectName("primaryAction")
        self.generate_button.setEnabled(catalog is not None)
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.generate_button)

        self.restore_button = QPushButton(t("export.restore_button"), self)
        self.restore_button.setObjectName("profileAction")
        self.restore_button.clicked.connect(self.restore_backup)
        action_row.addWidget(self.restore_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        if catalog is None:
            self.status.setText(catalog_status or t("export.no_catalog"))
        else:
            self.status.setText(catalog_status)
        layout.addWidget(self.status)

        last_export_row = QHBoxLayout()
        last_export_label = QLabel(t("export.last_exported_label"), self)
        last_export_label.setObjectName("fieldLabel")
        last_export_row.addWidget(last_export_label)
        self.last_exported_profile = QLabel(self._last_exported_profile_name(), self)
        self.last_exported_profile.setObjectName("lastExportedProfile")
        last_export_row.addWidget(self.last_exported_profile)
        last_export_row.addStretch()
        layout.addLayout(last_export_row)
        layout.addStretch()
        self.refresh_game_location()

    def set_locale(
        self,
        locale: LocaleSpec,
        *,
        source_root: Path,
        output_root: Path,
    ) -> None:
        """Switch export resources without changing the application UI locale."""

        self.locale = locale
        self.bundled_source_root = Path(source_root)
        self.staging_root = Path(output_root)
        self.last_result = None
        self.refresh_game_location(update_status=True)

    def generate(self, _checked: bool = False) -> None:
        if self.catalog is None:
            return
        try:
            game_folder = self._configured_game_folder()
            grim_dawn_text_root(
                game_folder,
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, t("export.error_title"), str(error))
            return

        affix_count = len(build_affix_markers(self.catalog, self.profile))
        unique_count = len(build_unique_item_markers(self.items, self.profile))
        choice = QMessageBox.question(
            self,
            t("export.title"),
            t(
                "export.confirm_body",
                affix_count=affix_count,
                unique_count=unique_count,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            self._prepare_missing_localization(game_folder)
            result = export_grades_to_game(
                game_folder,
                self.bundled_source_root,
                self.staging_root,
                self.backups_root,
                self.catalog,
                self.profile,
                items=self.items,
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            )
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(self, t("export.error_title"), str(error))
            return

        self.last_result = result
        backup_status = (
            t("export.backup_created")
            if result.backup_created
            else t("export.backup_preserved")
        )
        self.status.setText(
            t(
                "export.success_status",
                backup_status=backup_status,
                target=result.target_root,
                annotated_lines=result.generation.annotated_lines,
            )
        )
        exported_name = self.profile.name.strip() or t("export.unnamed_profile")
        self.last_exported_profile.setText(exported_name)
        if self.settings is not None:
            self.settings.setValue(LAST_EXPORTED_PROFILE_SETTING, exported_name)
            self.settings.sync()
        self.refresh_game_location(update_status=False)

    def _prepare_missing_localization(self, game_folder: Path) -> None:
        """Extract the selected language on demand before its first export."""

        if any(
            (self.bundled_source_root / filename).is_file()
            for filename in ITEM_TAG_FILENAMES
        ):
            return
        prepare_game_item_tags(
            game_folder,
            self.bundled_source_root,
            locale=self.locale,
        )

    def restore_backup(self, _checked: bool = False) -> None:
        try:
            game_folder = self._configured_game_folder()
            if not backup_available(
                game_folder,
                self.backups_root,
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            ):
                raise ValueError(t("export.no_backup_error"))
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, t("export.restore_error_title"), str(error))
            return

        choice = QMessageBox.question(
            self,
            t("export.restore_title"),
            t(
                "export.restore_confirm_body",
                directory=self.locale.game_text_directory,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        try:
            result = restore_game_backup(
                game_folder,
                self.backups_root,
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, t("export.restore_error_title"), str(error))
            return
        if result.original_existed:
            message = t(
                "export.restore_success",
                count=result.restored_files,
                target=result.target_root,
            )
        else:
            message = t(
                "export.restore_clean_success",
                target=result.target_root,
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
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            )
        except (OSError, ValueError):
            self.target_label.setText(t("export.target_not_configured"))
            self.generate_button.setEnabled(False)
            self.restore_button.setEnabled(False)
            if update_status:
                self.status.setText(t("export.game_folder_required"))
            return
        self.target_label.setText(t("export.target", target=target))
        self.generate_button.setEnabled(self.catalog is not None)
        self.restore_button.setEnabled(
            backup_available(
                game_folder,
                self.backups_root,
                locale=self.locale,
                user_settings_root=self.user_settings_root,
            )
        )

    def _configured_game_folder(self) -> Path:
        if self.settings is None:
            raise ValueError(t("export.set_game_folder_first"))
        raw_path = self.settings.value(GAME_FOLDER_SETTING, "", type=str).strip()
        if not raw_path:
            raise ValueError(t("export.set_game_folder_first"))
        return Path(raw_path)

    def _last_exported_profile_name(self) -> str:
        none_label = t("export.none")
        if self.settings is None:
            return none_label
        return self.settings.value(
            LAST_EXPORTED_PROFILE_SETTING,
            none_label,
            type=str,
        )
