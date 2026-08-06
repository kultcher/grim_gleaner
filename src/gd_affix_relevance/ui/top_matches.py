"""Development-facing Top Matches view backed by the compiled affix catalog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, SkillCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import (
    RankedAffixVariant,
    profile_weight_for_semantic_id,
    rank_affix_catalog,
)
from gd_affix_relevance.ui.catalog import all_stat_definitions

STAT_LABELS = {
    definition.stat_id: definition.label for definition in all_stat_definitions()
}


class TopMatchesPage(QWidget):
    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        catalog_status: str = "",
        skills: SkillCatalog | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.profile = profile
        self.catalog_status = catalog_status
        self.skill_labels = {
            skill.skill_id: skill.display_name
            for skill in (skills or SkillCatalog(())).skills
            if skill.display_name
        }
        self.matches: tuple[RankedAffixVariant, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Top Matches", self)
        heading.setObjectName("pageTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        heading_row.addWidget(QLabel("Show", self))
        self.limit_spin = QSpinBox(self)
        self.limit_spin.setObjectName("matchLimit")
        self.limit_spin.setRange(5, 100)
        self.limit_spin.setValue(20)
        self.limit_spin.setSuffix(" affixes")
        self.limit_spin.valueChanged.connect(self.refresh)
        heading_row.addWidget(self.limit_spin)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("profileAction")
        self.refresh_button.clicked.connect(self.refresh)
        heading_row.addWidget(self.refresh_button)
        layout.addLayout(heading_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.table = QTableWidget(0, 7, self)
        self.table.setObjectName("topMatchesTable")
        self.table.setHorizontalHeaderLabels(
            ("Grade", "Affix", "Type", "Gear Slot", "Matched", "Score", "Coverage")
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.currentCellChanged.connect(self._selection_changed)
        layout.addWidget(self.table, 3)

        self.details = QPlainTextEdit(self)
        self.details.setObjectName("matchDetails")
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select an affix variant to inspect its stats.")
        layout.addWidget(self.details, 2)
        self.refresh()

    def set_catalog(self, catalog: AffixCatalog | None, status: str = "") -> None:
        self.catalog = catalog
        self.catalog_status = status
        self.refresh()

    def refresh(self, _value: int | bool = False) -> None:
        self.table.setRowCount(0)
        self.details.clear()
        self.matches = ()
        if self.catalog is None:
            self.status.setText(
                self.catalog_status
                or "No compiled affix catalog is available for ranking."
            )
            return
        if not self.profile.weights and not any(
            weight > 0 for weight in self.profile.skill_weights.values()
        ):
            self.status.setText(
                "Set at least one nonzero build-profile weight to rank affixes."
            )
            return

        self.matches = rank_affix_catalog(
            self.catalog,
            self.profile,
            limit=self.limit_spin.value(),
        )
        variant_count = sum(len(affix.variants) for affix in self.catalog.affixes)
        source_note = f" {self.catalog_status}" if self.catalog_status else ""
        self.status.setText(
            f"{self.profile.name}: showing {len(self.matches)} of "
            f"{variant_count} ranked variants.{source_note}"
        )
        self.table.setRowCount(len(self.matches))
        for row, match in enumerate(self.matches):
            score = match.score
            matched = ", ".join(
                self._label_for(stat_id)
                for stat_id in score.matched_stat_ids
            )
            values = (
                score.marker,
                match.affix.display_name,
                match.affix.kind.title(),
                match.variant.gear_slot,
                matched or "None",
                str(score.weighted_match),
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 5, 6}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        if self.matches:
            self.table.selectRow(0)
            self._show_details(self.matches[0])

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if 0 <= current_row < len(self.matches):
            self._show_details(self.matches[current_row])

    def _show_details(self, match: RankedAffixVariant) -> None:
        score = match.score
        matched_lines = [
            f"- {self._label_for(stat_id)}: "
            f"weight {profile_weight_for_semantic_id(self.profile, stat_id)}"
            for stat_id in score.matched_stat_ids
        ]
        lines = [
            f"{score.marker} {match.affix.display_name}",
            f"{match.affix.kind.title()} - {match.variant.gear_slot}",
            f"Weighted match: {score.weighted_match}",
            "Coverage: "
            f"{score.matched_count}/{score.total_category_count} "
            f"({score.coverage_ratio:.0%})",
            "",
            "Matched profile stats:",
            *(matched_lines or ["- None"]),
            "",
            "All affix stats:",
            *(f"- {line}" for line in match.variant.stat_lines),
        ]
        if match.variant.level_requirements:
            lines.extend(
                [
                    "",
                    "Level requirements for this layout: "
                    + ", ".join(map(str, match.variant.level_requirements)),
                ]
            )
        if match.variant.stat_layout_count > 1:
            lines.append(
                "Distinct layouts for this affix and slot: "
                f"{match.variant.stat_layout_count}"
            )
        lines.extend(
            [
                "",
                f"Localization tag: {match.affix.localization_tag}",
                f"Representative: {match.variant.representative_source}",
            ]
        )
        self.details.setPlainText("\n".join(lines))

    def _label_for(self, stat_id: str) -> str:
        prefix = "skill_bonus:"
        if stat_id.startswith(prefix):
            skill_id = stat_id[len(prefix) :]
            return f"+Ranks to {self.skill_labels.get(skill_id, skill_id)}"
        return STAT_LABELS.get(stat_id, stat_id)
