"""Top-level Grim Gleaner application window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.profile_editor import ProfileEditor


class MainWindow(QMainWindow):
    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grim Gleaner")
        self.resize(1120, 780)
        self.setMinimumSize(880, 620)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.navigation = QListWidget(central)
        self.navigation.setObjectName("mainNavigation")
        self.navigation.setFixedWidth(190)
        self.navigation.setSpacing(2)
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.navigation)

        self.pages = QStackedWidget(central)
        layout.addWidget(self.pages, 1)

        self.profile_editor = ProfileEditor(profile, self.pages)
        self.pages.addWidget(self.profile_editor)
        self._add_navigation_item("Build Profile", "Set the stats this build values")

        self.top_matches_page = self._placeholder_page(
            "Top Matches",
            "This view is reserved for ranking every reachable affix against the "
            "current profile and surfacing the strongest matches.",
        )
        self.pages.addWidget(self.top_matches_page)
        self._add_navigation_item("Top Matches", "Affix benchmark view — coming later")

        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)

    def _add_navigation_item(self, title: str, tooltip: str) -> None:
        item = QListWidgetItem(title)
        item.setToolTip(tooltip)
        self.navigation.addItem(item)

    def _placeholder_page(self, title: str, message: str) -> QWidget:
        page = QWidget(self.pages)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 36, 40, 36)
        title_label = QLabel(title, page)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)
        message_label = QLabel(message, page)
        message_label.setObjectName("pageHint")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        layout.addStretch()
        return page
