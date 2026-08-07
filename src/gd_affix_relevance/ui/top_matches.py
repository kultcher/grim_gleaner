"""Per-slot affix recommendations backed by the compiled affix catalog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
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
    rank_affixes_for_slot,
)
from gd_affix_relevance.slots import (
    FILTER_LABELS,
    SLOT_FILTERS,
    SLOT_GROUPS,
    SLOT_LABELS,
)
from gd_affix_relevance.ui.catalog import all_stat_definitions

STAT_LABELS = {
    definition.stat_id: definition.label for definition in all_stat_definitions()
}
RESULTS_PER_TABLE = 5


class AffixSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.matches: tuple[RankedAffixVariant, ...] = ()
        self._updating = False
        self.setObjectName("affixSlotTable")
        self.setHorizontalHeaderLabels(("Grade", "Affix", "Score", "Coverage"))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.setMinimumHeight(190)
        self.setMaximumHeight(205)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(self, matches: tuple[RankedAffixVariant, ...]) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            values = (
                match.marker,
                match.affix.display_name,
                str(score.weighted_match),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if column == 0 and match.has_level_variations:
                    item.setToolTip(
                        "The highest-level layout is shown; lower tiers may have "
                        "a different stat breakdown."
                    )
                self.setItem(row, column, item)
        self._updating = False

    def _selection_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if not self._updating and 0 <= current_row < len(self.matches):
            self.match_selected.emit(self.matches[current_row])


class AffixSlotRow(QFrame):
    def __init__(self, slot_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("affixSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(10)

        slot_label = QLabel(SLOT_LABELS[slot_id], self)
        slot_label.setObjectName("affixSlotName")
        slot_label.setFixedWidth(100)
        layout.addWidget(slot_label)

        self.tables: dict[str, AffixSlotTable] = {}
        for kind in ("prefix", "suffix"):
            section = QWidget(self)
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(5)
            title = QLabel(f"{kind.title()}es" if kind == "prefix" else "Suffixes")
            title.setObjectName("affixTableTitle")
            section_layout.addWidget(title)
            table = AffixSlotTable(section)
            section_layout.addWidget(table)
            layout.addWidget(section, 1)
            self.tables[kind] = table


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
        self.tables: dict[tuple[str, str], AffixSlotTable] = {}
        self.slot_rows: dict[str, AffixSlotRow] = {}
        self.category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self._selected_table: AffixSlotTable | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Top Affix Matches", self)
        heading.setObjectName("pageTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch()
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("profileAction")
        self.refresh_button.clicked.connect(self.refresh)
        heading_row.addWidget(self.refresh_button)
        layout.addLayout(heading_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        upper = QWidget(splitter)
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        filter_frame = QFrame(upper)
        filter_frame.setObjectName("slotFilterBar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 7, 10, 7)
        filter_layout.addWidget(QLabel("Show item slots:", filter_frame))
        self.slot_filters: dict[str, QCheckBox] = {}
        for filter_id, label in FILTER_LABELS:
            checkbox = QCheckBox(label, filter_frame)
            checkbox.setObjectName(f"slotFilter_{filter_id}")
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._filter_changed)
            filter_layout.addWidget(checkbox)
            self.slot_filters[filter_id] = checkbox
        filter_layout.addStretch()
        upper_layout.addWidget(filter_frame)

        scroll = QScrollArea(upper)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 4, 8, 8)
        content_layout.setSpacing(10)
        for category_label, slot_ids in SLOT_GROUPS:
            category = QLabel(category_label, content)
            category.setObjectName("affixCategoryTitle")
            content_layout.addWidget(category)
            self.category_widgets.append((category, slot_ids))
            for slot_id in slot_ids:
                row = AffixSlotRow(slot_id, content)
                for kind, table in row.tables.items():
                    table.match_selected.connect(
                        lambda match, selected=table, slot=slot_id: self._show_match(
                            selected, slot, match
                        )
                    )
                    self.tables[(slot_id, kind)] = table
                self.slot_rows[slot_id] = row
                content_layout.addWidget(row)
        content_layout.addStretch()
        scroll.setWidget(content)
        upper_layout.addWidget(scroll, 1)
        splitter.addWidget(upper)

        self.details = QPlainTextEdit(splitter)
        self.details.setObjectName("matchDetails")
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Select an affix to inspect its matched stats.")
        splitter.addWidget(self.details)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter, 1)
        self.refresh()

    def set_catalog(self, catalog: AffixCatalog | None, status: str = "") -> None:
        self.catalog = catalog
        self.catalog_status = status
        self.refresh()

    def refresh(self, _value: int | bool = False) -> None:
        self.details.clear()
        self.matches = ()
        self._selected_table = None
        for table in self.tables.values():
            table.set_matches(())
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

        all_matches: list[RankedAffixVariant] = []
        for (slot_id, kind), table in self.tables.items():
            matches = rank_affixes_for_slot(
                self.catalog,
                self.profile,
                slot_id=slot_id,
                kind=kind,
                limit=RESULTS_PER_TABLE,
            )
            table.set_matches(matches)
            all_matches.extend(matches)
        self.matches = tuple(all_matches)
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()

    def _filter_changed(self, _checked: bool) -> None:
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()

    def _apply_slot_filters(self) -> None:
        enabled = {
            filter_id
            for filter_id, checkbox in self.slot_filters.items()
            if checkbox.isChecked()
        }
        for slot_id, row in self.slot_rows.items():
            required = SLOT_FILTERS.get(slot_id, frozenset())
            row.setVisible(required <= enabled)
        for heading, slot_ids in self.category_widgets:
            heading.setVisible(
                any(not self.slot_rows[slot].isHidden() for slot in slot_ids)
            )

    def _update_status(self) -> None:
        visible_matches = sum(
            len(table.matches)
            for (slot_id, _), table in self.tables.items()
            if not self.slot_rows[slot_id].isHidden()
        )
        source_note = f" {self.catalog_status}" if self.catalog_status else ""
        self.status.setText(
            f"{self.profile.name}: showing {visible_matches} ranked slot entries, "
            f"up to {RESULTS_PER_TABLE} prefixes and suffixes per slot. "
            "! marks an affix whose stat layout changes across level tiers."
            f"{source_note}"
        )

    def _select_first_visible_match(self) -> None:
        for _, slot_ids in SLOT_GROUPS:
            for slot_id in slot_ids:
                if self.slot_rows[slot_id].isHidden():
                    continue
                for kind in ("prefix", "suffix"):
                    table = self.tables[(slot_id, kind)]
                    if table.matches:
                        table.selectRow(0)
                        return
        self.details.clear()

    def _show_match(
        self,
        table: AffixSlotTable,
        slot_id: str,
        match: RankedAffixVariant,
    ) -> None:
        if self._selected_table is not table:
            for other in self.tables.values():
                if other is not table:
                    other.clearSelection()
            self._selected_table = table
        self._show_details(match, slot_id)

    def _show_details(self, match: RankedAffixVariant, slot_id: str) -> None:
        score = match.score
        matched_lines = [
            f"- {self._label_for(stat_id)}: "
            f"weight {profile_weight_for_semantic_id(self.profile, stat_id)}"
            for stat_id in score.matched_stat_ids
        ]
        lines = [
            f"{match.marker} {match.affix.display_name}",
            f"{match.affix.kind.title()} for {SLOT_LABELS[slot_id]}",
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
        if match.has_level_variations:
            lines.extend(
                [
                    "",
                    "!: Highest-level stat layout shown. This affix has different "
                    "stat categories at lower level tiers.",
                ]
            )
        lines.extend(
            [
                "",
                f"Full applicability: {match.variant.gear_slot}",
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
