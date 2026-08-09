"""Build-profile editing view."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import SkillCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import load_profile, save_profile
from gd_affix_relevance.ui.catalog import PROFILE_TABS, TabDefinition
from gd_affix_relevance.ui.widgets import PackageAccordion
from gd_affix_relevance.ui.skills_editor import SkillsEditor


class ProfileEditor(QWidget):
    profile_changed = Signal()
    profile_path_changed = Signal(object)
    view_matches_requested = Signal()

    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
        *,
        skills: SkillCatalog | None = None,
        profile_path: Path | None = None,
        startup_notice: str = "",
    ) -> None:
        super().__init__(parent)
        self.profile = profile or BuildProfile()
        self.accordions: dict[str, PackageAccordion] = {}
        self.current_profile_path = Path(profile_path) if profile_path else None
        self.is_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        heading_row = QHBoxLayout()
        heading = QLabel("Build Profile", self)
        heading.setObjectName("pageTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        legend = QLabel(
            "☆ Ignored   ★ Incidental   ★★ Useful   ★★★ Emphasized   ★★★★ Core",
            self,
        )
        legend.setObjectName("weightLegend")
        heading_row.addWidget(legend)
        layout.addLayout(heading_row)

        name_row = QHBoxLayout()
        name_label = QLabel("Profile name", self)
        name_label.setObjectName("fieldLabel")
        name_row.addWidget(name_label)
        self.name_edit = QLineEdit(self.profile.name, self)
        self.name_edit.setObjectName("profileName")
        self.name_edit.textChanged.connect(self._name_changed)
        name_row.addWidget(self.name_edit, 1)
        self.new_button = QPushButton("New Profile", self)
        self.new_button.setObjectName("profileAction")
        self.new_button.setToolTip("Start a blank build profile")
        self.new_button.clicked.connect(self.new_profile)
        name_row.addWidget(self.new_button)
        self.load_button = QPushButton("Load...", self)
        self.load_button.setObjectName("profileAction")
        self.load_button.setToolTip("Load build profile from a JSON file")
        self.load_button.clicked.connect(self._choose_profile_to_load)
        name_row.addWidget(self.load_button)
        self.save_button = QPushButton("Save...", self)
        self.save_button.setObjectName("profileAction")
        self.save_button.setToolTip("Save build profile to a JSON file")
        self.save_button.clicked.connect(self._choose_profile_to_save)
        name_row.addWidget(self.save_button)
        layout.addLayout(name_row)

        initial_status = (
            f"Loaded: {self.current_profile_path.name}"
            if self.current_profile_path is not None
            else startup_notice or "Not saved"
        )
        self.file_status = QLabel(initial_status, self)
        self.file_status.setObjectName("profileFileStatus")
        if self.current_profile_path is not None:
            self.file_status.setToolTip(str(self.current_profile_path))
        layout.addWidget(self.file_status)

        hint_row = QHBoxLayout()
        hint = QLabel(
            "All packages remain visible. Optional packages start collapsed and stay "
            "open whenever they contain a nonzero weight.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        hint_row.addWidget(hint, 1)
        self.view_matches_button = QPushButton("View Matches", self)
        self.view_matches_button.setObjectName("primaryAction")
        self.view_matches_button.clicked.connect(self.view_matches_requested)
        hint_row.addWidget(self.view_matches_button)
        layout.addLayout(hint_row)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("profileTabs")
        for definition in PROFILE_TABS:
            self.tabs.addTab(self._build_tab(definition), definition.label)
        self.skills_editor = SkillsEditor(
            self.profile, skills or SkillCatalog(()), self
        )
        self.skills_editor.changed.connect(self._skills_changed)
        self.tabs.addTab(self.skills_editor, "Skills")
        layout.addWidget(self.tabs, 1)

    def _build_tab(self, definition: TabDefinition) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 12, 8, 12)
        content_layout.setSpacing(10)
        for package in definition.packages:
            accordion = PackageAccordion(
                package,
                self.profile.weight_for,
                self.profile.set_weight,
                content,
            )
            accordion.weight_changed.connect(self._weights_changed)
            content_layout.addWidget(accordion)
            self.accordions[package.package_id] = accordion
        content_layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _placeholder(self, title: str, message: str) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 44, 36, 44)
        title_label = QLabel(title, page)
        title_label.setObjectName("placeholderTitle")
        layout.addWidget(title_label)
        message_label = QLabel(message, page)
        message_label.setObjectName("pageHint")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        layout.addStretch()
        return page

    def _name_changed(self, name: str) -> None:
        self.profile.name = name
        self._mark_unsaved()
        self.profile_changed.emit()

    def _weights_changed(self, _stat_id: str, _weight: int) -> None:
        self._mark_unsaved()
        self.profile_changed.emit()

    def _skills_changed(self) -> None:
        self._mark_unsaved()
        self.profile_changed.emit()

    def save_to_path(self, path: Path) -> Path:
        """Save the active profile, primarily for UI actions and tests."""

        destination = save_profile(self.profile, path)
        self.current_profile_path = destination
        self.is_dirty = False
        self.file_status.setText(f"Saved: {destination.name}")
        self.file_status.setToolTip(str(destination))
        self.profile_path_changed.emit(destination)
        return destination

    def load_from_path(self, path: Path) -> BuildProfile:
        """Load *path* into the existing profile object and refresh controls."""

        loaded = load_profile(path)
        self.profile.name = loaded.name
        self.profile.weights.clear()
        for stat_id, weight in loaded.weights.items():
            self.profile.set_weight(stat_id, weight)
        self.profile.masteries = loaded.masteries
        self.profile.skill_weights.clear()
        for skill_id, weight in loaded.skill_weights.items():
            self.profile.set_skill_weight(skill_id, weight)

        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(self.profile.name)
        del blocker
        for accordion in self.accordions.values():
            accordion.refresh_from_profile()
        self.skills_editor.refresh_from_profile()

        self.current_profile_path = Path(path)
        self.is_dirty = False
        self.file_status.setText(f"Loaded: {self.current_profile_path.name}")
        self.file_status.setToolTip(str(self.current_profile_path))
        self.profile_path_changed.emit(self.current_profile_path)
        self.profile_changed.emit()
        return self.profile

    def new_profile(self) -> bool:
        """Reset every profile field after resolving unsaved changes."""

        if self.is_dirty:
            action = self._prompt_unsaved_action()
            if action == QMessageBox.StandardButton.Cancel:
                return False
            if action == QMessageBox.StandardButton.Save and not self._save_before_reset():
                return False

        baseline = BuildProfile()
        self.profile.name = baseline.name
        self.profile.weights.clear()
        self.profile.masteries = baseline.masteries
        self.profile.skill_weights.clear()
        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(self.profile.name)
        del blocker
        for accordion in self.accordions.values():
            accordion.refresh_from_profile()
        self.skills_editor.refresh_from_profile()
        self.current_profile_path = None
        self.is_dirty = False
        self.file_status.setText("New profile — not saved")
        self.file_status.setToolTip("")
        self.profile_path_changed.emit(None)
        self.profile_changed.emit()
        return True

    def confirm_close(self) -> bool:
        """Resolve unsaved profile changes before the application closes."""

        if not self.is_dirty:
            return True
        action = self._prompt_exit_unsaved_action()
        if action == QMessageBox.StandardButton.Cancel:
            return False
        if action == QMessageBox.StandardButton.Save:
            return self._save_before_reset()
        return True

    def _prompt_unsaved_action(self) -> QMessageBox.StandardButton:
        return QMessageBox.warning(
            self,
            "Unsaved Profile",
            "Save changes to the current profile before starting a new one?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _prompt_exit_unsaved_action(self) -> QMessageBox.StandardButton:
        return QMessageBox.warning(
            self,
            "Unsaved Profile",
            "Save changes to the current profile before exiting?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

    def _save_before_reset(self) -> bool:
        if self.current_profile_path is None:
            return self._choose_profile_to_save()
        try:
            self.save_to_path(self.current_profile_path)
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))
            return False
        return True

    def _choose_profile_to_save(self) -> bool:
        suggested = str(
            self.current_profile_path
            or Path(f"{self.profile.name.strip() or 'build-profile'}.json")
        )
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Build Profile",
            suggested,
            "Grim Gleaner Profiles (*.json);;All Files (*)",
        )
        if not selected:
            return False
        try:
            self.save_to_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))
            return False
        return True

    def _choose_profile_to_load(self) -> bool:
        starting_path = str(self.current_profile_path or Path.cwd())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load Build Profile",
            starting_path,
            "Grim Gleaner Profiles (*.json);;All Files (*)",
        )
        if not selected:
            return False
        try:
            self.load_from_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Load Profile", str(error))
            return False
        return True

    def _mark_unsaved(self) -> None:
        self.is_dirty = True
        if self.current_profile_path is None:
            self.file_status.setText("Not saved")
            self.file_status.setToolTip("")
        else:
            self.file_status.setText(
                f"Unsaved changes: {self.current_profile_path.name}"
            )
            self.file_status.setToolTip(str(self.current_profile_path))
