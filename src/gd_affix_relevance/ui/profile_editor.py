"""Build-profile editing view."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.domain import BuildProfile
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
        layout.addLayout(name_row)

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
            accordion.weight_changed.connect(lambda *_: self.profile_changed.emit())
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
        self.profile_changed.emit()
