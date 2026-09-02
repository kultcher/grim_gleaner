"""Concise in-application usage guide."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.ui.i18n import t


class GuidePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel(t("guide.title"), self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        introduction = QLabel(t("guide.introduction"), self)
        introduction.setObjectName("pageHint")
        introduction.setWordWrap(True)
        layout.addWidget(introduction)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 8, 12, 8)
        content_layout.setSpacing(18)

        _add_section(
            content_layout,
            t("guide.workflow_title"),
            t("guide.workflow_body"),
            content,
        )
        _add_section(
            content_layout,
            t("guide.weights_title"),
            t("guide.weights_body"),
            content,
        )
        _add_section(
            content_layout,
            t("guide.grades_title"),
            t("guide.grades_body"),
            content,
        )

        _add_section(
            content_layout,
            t("guide.export_title"),
            t("guide.export_body"),
            content,
        )
        _add_section(
            content_layout,
            t("guide.limitations_title"),
            t("guide.limitations_body"),
            content,
        )
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)


def _add_section(
    layout: QVBoxLayout,
    title: str,
    text: str,
    parent: QWidget,
) -> None:
    title_label = QLabel(title, parent)
    title_label.setObjectName("guideSectionTitle")
    layout.addWidget(title_label)
    body = QLabel(text, parent)
    body.setObjectName("guideBody")
    body.setWordWrap(True)
    layout.addWidget(body)
