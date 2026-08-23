"""Concise in-application usage guide."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class GuidePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Guide", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        introduction = QLabel(
            "Grim Gleaner grades item names according to the priorities in your "
            "build profile. It is a quick relevance guide, not a replacement "
            "for comparing the complete stats of two equipped items.",
            self,
        )
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
            "Basic workflow",
            "1. Set your Grim Dawn installation folder under Settings.\n"
            "2. Create or load a Build Profile and assign 0-4 star priorities.\n"
            "3. Choose your masteries and add any build-relevant skills.\n"
            "4. Review Gear Grades for affixes, unique items, and add-ons.\n"
            "5. Use Export Grades to apply the active profile's labels in game.\n"
            "6. Use Restore Backups to return item localization to its pre-export state.",
            content,
        )
        _add_section(
            content_layout,
            "Assigning weights",
            "Assign stars to each stat modifier based on how important the stat is to your build. Use the following as a guideline:"
            "\n0 stars: Stats that are totally irrelevant to your build."
            "\n1 star: Stats that have minimal or only occasional impact, such as damage types that you deal only incidentally."
            "\n2 stars: Baseline stats that are generally useful, but not core to your build."
            "\n3 stars: Important stats you're always happy to have."
            "\n4 stars: Core stats that you want as much of as possible.",
            content,   
        )
        _add_section(
            content_layout,
            "Reading grades",
            "Grades run from F for no measured relevance through D, C, B, A, "
            "S, S+, and S++. The number in ordinary grade tags is the count of "
            "matched stat categories. An asterisk (*) flags a granted skill, "
            "and an exclamation point (!) flags a modifier for one of your "
            "selected build skills.",
            content,
        )

        _add_section(
            content_layout,
            "Export and profiles",
            "Save and Load default to Grim Gleaner's Profiles folder. Export "
            "uses existing Rainbow Filters/gdse item files when present and "
            "prepared clean localization files for anything missing. The first "
            "export preserves an "
            "original-state backup; repeated exports do not overwrite it.",
            content,
        )
        _add_section(
            content_layout,
            "Current limitations",
            "- Grades use the highest affix or fixed-item version available "
            "within the profile's selected level band.\n"
            "- Granted skills are flagged but their usefulness is not evaluated.\n"
            "- Skill modifiers receive relevance from the selected skill, but "
            "their exact mechanical value is not yet evaluated.\n"
            "- Monster Infrequents are graded on fixed base stats; possible random "
            "affixes are listed separately.\n"
            "- Grim Gleaner does not compare against currently equipped gear or "
            "decide whether a complete dropped item is an upgrade.\n"
            "- Game patches may require an updated Grim Gleaner catalog.",
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
