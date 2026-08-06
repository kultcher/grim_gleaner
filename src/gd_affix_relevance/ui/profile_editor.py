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

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import load_profile, save_profile
from gd_affix_relevance.ui.catalog import PROFILE_TABS, TabDefinition
from gd_affix_relevance.ui.widgets import PackageAccordion


class ProfileEditor(QWidget):
    profile_changed = Signal()

    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile or BuildProfile()
        self.accordions: dict[str, PackageAccordion] = {}
        self.current_profile_path: Path | None = None

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

        self.file_status = QLabel("Not saved", self)
        self.file_status.setObjectName("profileFileStatus")
        layout.addWidget(self.file_status)

        hint = QLabel(
            "All packages remain visible. Optional packages start collapsed and stay "
            "open whenever they contain a nonzero weight.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("profileTabs")
        for definition in PROFILE_TABS:
            self.tabs.addTab(self._build_tab(definition), definition.label)
        self.tabs.addTab(
            self._placeholder(
                "Pets",
                "Pet bonus records will be expanded into selectable pet stats in a later pass.",
            ),
            "Pets",
        )
        self.tabs.addTab(
            self._placeholder(
                "Skills",
                "Class, individual-skill, and granted-skill selection is reserved for a "
                "dedicated editor.",
            ),
            "Skills",
        )
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

    def save_to_path(self, path: Path) -> Path:
        """Save the active profile, primarily for UI actions and tests."""

        destination = save_profile(self.profile, path)
        self.current_profile_path = destination
        self.file_status.setText(f"Saved: {destination.name}")
        self.file_status.setToolTip(str(destination))
        return destination

    def load_from_path(self, path: Path) -> BuildProfile:
        """Load *path* into the existing profile object and refresh controls."""

        loaded = load_profile(path)
        self.profile.name = loaded.name
        self.profile.weights.clear()
        for stat_id, weight in loaded.weights.items():
            self.profile.set_weight(stat_id, weight)

        blocker = QSignalBlocker(self.name_edit)
        self.name_edit.setText(self.profile.name)
        del blocker
        for accordion in self.accordions.values():
            accordion.refresh_from_profile()

        self.current_profile_path = Path(path)
        self.file_status.setText(f"Loaded: {self.current_profile_path.name}")
        self.file_status.setToolTip(str(self.current_profile_path))
        self.profile_changed.emit()
        return self.profile

    def _choose_profile_to_save(self) -> None:
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
            return
        try:
            self.save_to_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Save Profile", str(error))

    def _choose_profile_to_load(self) -> None:
        starting_path = str(self.current_profile_path or Path.cwd())
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Load Build Profile",
            starting_path,
            "Grim Gleaner Profiles (*.json);;All Files (*)",
        )
        if not selected:
            return
        try:
            self.load_from_path(Path(selected))
        except (OSError, ValueError, TypeError) as error:
            QMessageBox.critical(self, "Could Not Load Profile", str(error))

    def _mark_unsaved(self) -> None:
        if self.current_profile_path is None:
            self.file_status.setText("Not saved")
            self.file_status.setToolTip("")
        else:
            self.file_status.setText(
                f"Unsaved changes: {self.current_profile_path.name}"
            )
            self.file_status.setToolTip(str(self.current_profile_path))
