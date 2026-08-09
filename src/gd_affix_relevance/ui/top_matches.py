"""Per-slot affix and unique-equipment recommendations."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog, SkillCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import (
    RankedAffixVariant,
    RankedItemVariant,
    UNIQUE_ITEM_TYPES,
    UNIQUE_TYPE_LABELS,
    canonical_skill_reference,
    profile_weight_for_semantic_id,
    rank_affixes_for_slot,
    rank_unique_items_for_slot,
)
from gd_affix_relevance.slots import (
    FILTER_LABELS,
    SLOT_FILTERS,
    SLOT_GROUPS,
    SLOT_LABELS,
    WEAPON_SLOTS,
)
from gd_affix_relevance.ui.catalog import all_stat_definitions

STAT_LABELS = {
    definition.stat_id: definition.label for definition in all_stat_definitions()
}
RESULTS_PER_AFFIX_TABLE = 5
SKILL_RANK_HIGHLIGHT = QColor("#8bded7")
SKILL_MODIFIER_HIGHLIGHT = QColor("#66cdaa")
HIGHLIGHT_TEXT = QColor("#102528")
MATCHED_STAT_COLOR = "#82d99b"
UNMATCHED_STAT_COLOR = "#b7bec9"
SKILL_RANK_STAT_COLOR = "#8bded7"
SKILL_MODIFIER_STAT_COLOR = "#66cdaa"
STAT_CATEGORY_COLORS = {
    "elemental": "#f2d64b",
    "fire": "#ef922f",
    "acid": "#64e34b",
    "aether": "#42c7bd",
    "bleeding": "#c05b5b",
    "pierce": "#e47878",
    "chaos": "#e56acb",
    "cold": "#5ee8eb",
    "lightning": "#65bff2",
    "physical": "#cfaa79",
    "vitality": "#b987d6",
    "attribute": "#ed91c5",
    "ability": "#b8d85f",
    "health": "#f06b6b",
    "energy": "#319d98",
}
DETAIL_TITLE_COLORS = {
    "monster_infrequent": "#28613a",
    "epic": "#315b88",
    "legendary": "#60427f",
    "affix_rare": "#28613a",
    "affix_magical": "#786019",
    "affix": "#3a404b",
}


def _format_score(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _has_selected_skill_bonus(
    semantic_stat_ids: tuple[str, ...], profile: BuildProfile
) -> bool:
    selected_skills = {
        canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
    }
    selected_masteries = {mastery for mastery in profile.masteries if mastery}
    return any(
        (
            stat_id.startswith("skill_bonus:")
            and canonical_skill_reference(
                stat_id.removeprefix("skill_bonus:")
            )
            in selected_skills
        )
        or (
            bool(selected_skills)
            and stat_id.startswith("mastery_bonus:")
            and stat_id.removeprefix("mastery_bonus:") in selected_masteries
        )
        for stat_id in semantic_stat_ids
    )


def _highlight_item(item: QTableWidgetItem, kind: str) -> None:
    if kind == "modifier":
        item.setBackground(SKILL_MODIFIER_HIGHLIGHT)
        item.setToolTip(
            "Modifies an active build skill. Skill-modifier highlighting "
            "supersedes bonus-rank highlighting."
        )
    elif kind == "rank":
        item.setBackground(SKILL_RANK_HIGHLIGHT)
        item.setToolTip("Includes bonus ranks for an active build skill.")
    if kind:
        item.setForeground(HIGHLIGHT_TEXT)


def _html_line(text: str, *, color: str = "", bold: bool = False) -> str:
    if not text:
        return "<div><br></div>"
    style = []
    if color:
        style.append(f"color: {color}")
    if bold:
        style.append("font-weight: 600")
    style_attr = f' style="{"; ".join(style)}"' if style else ""
    return f"<div{style_attr}>{escape(text)}</div>"


def _semantic_stat_color(stat_id: str, *, matched: bool) -> str:
    """Return a Rainbow-inspired color without changing semantic scoring data."""

    if stat_id.startswith(("skill_bonus:", "mastery_bonus:")):
        return SKILL_RANK_STAT_COLOR

    # Specific damage families take precedence over broad core categories. This
    # also colors conversions, base weapon damage, retaliation, and resistances.
    damage_families = (
        (("elemental",), "elemental"),
        # Frostburn must be tested before the shorter "burn" token.
        (("cold", "frostburn"), "cold"),
        (("fire", "burn"), "fire"),
        (("acid", "poison"), "acid"),
        (("aether",), "aether"),
        (("bleeding",), "bleeding"),
        (("pierce",), "pierce"),
        (("chaos",), "chaos"),
        (("lightning", "electrocute"), "lightning"),
        (("physical", "internal_trauma"), "physical"),
        (("vitality", "vitality_decay"), "vitality"),
    )
    for tokens, family in damage_families:
        if any(token in stat_id for token in tokens):
            return STAT_CATEGORY_COLORS[family]

    if "offensive_ability" in stat_id or "defensive_ability" in stat_id:
        return STAT_CATEGORY_COLORS["ability"]
    if "health" in stat_id or "healing" in stat_id:
        return STAT_CATEGORY_COLORS["health"]
    if "energy" in stat_id or "mana" in stat_id:
        return STAT_CATEGORY_COLORS["energy"]
    if any(token in stat_id for token in ("physique", "cunning", "spirit")):
        return STAT_CATEGORY_COLORS["attribute"]
    return MATCHED_STAT_COLOR if matched else UNMATCHED_STAT_COLOR


def _stat_html(stat_id: str, label: str, *, matched: bool) -> str:
    color = _semantic_stat_color(stat_id, matched=matched)
    return _html_line(f"- {label}", color=color)


class MatchDetailPane(QFrame):
    """Fixed title bar over an independently scrolling rich-text body."""

    def __init__(self, placeholder: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("matchDetailPane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.title = QLabel(self)
        self.title.setObjectName("matchDetailTitle")
        self.title.setWordWrap(False)
        self.title.hide()
        layout.addWidget(self.title)
        self.body = QTextEdit(self)
        self.body.setObjectName("matchDetails")
        self.body.setReadOnly(True)
        self.body.setPlaceholderText(placeholder)
        layout.addWidget(self.body, 1)

    def clear(self) -> None:
        self.title.clear()
        self.title.hide()
        self.body.clear()

    def set_title(self, text: str, color: str) -> None:
        self.title.setText(text)
        self.title.setStyleSheet(
            f"background-color: {color}; color: #ffffff;"
        )
        self.title.show()


def _configure_table(table: QTableWidget, stretch_column: int) -> None:
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(26)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(stretch_column, QHeaderView.ResizeMode.Stretch)


class AffixSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 4, parent)
        self.matches: tuple[RankedAffixVariant, ...] = ()
        self._updating = False
        self.setObjectName("affixSlotTable")
        self.setHorizontalHeaderLabels(("Grade", "Affix", "Score", "Coverage"))
        _configure_table(self, 1)
        self.setMinimumHeight(190)
        self.setMaximumHeight(205)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(
        self,
        matches: tuple[RankedAffixVariant, ...],
        profile: BuildProfile | None = None,
    ) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            highlight = (
                "rank"
                if profile is not None
                and _has_selected_skill_bonus(match.semantic_stat_ids, profile)
                else ""
            )
            values = (
                match.marker,
                match.affix.display_name,
                _format_score(score.effective_score),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                _highlight_item(item, highlight)
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
            title = QLabel("Prefixes" if kind == "prefix" else "Suffixes")
            title.setObjectName("affixTableTitle")
            section_layout.addWidget(title)
            table = AffixSlotTable(section)
            section_layout.addWidget(table)
            layout.addWidget(section, 1)
            self.tables[kind] = table


class UniqueSlotTable(QTableWidget):
    match_selected = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 6, parent)
        self.matches: tuple[RankedItemVariant, ...] = ()
        self._updating = False
        self.setObjectName("uniqueSlotTable")
        self.setHorizontalHeaderLabels(
            ("Grade", "Item", "Type", "Source", "Score", "Coverage")
        )
        _configure_table(self, 1)
        self.setMinimumHeight(84)
        self.setMaximumHeight(420)
        self.currentCellChanged.connect(self._selection_changed)

    def set_matches(
        self,
        matches: tuple[RankedItemVariant, ...],
        profile: BuildProfile | None = None,
    ) -> None:
        self._updating = True
        self.matches = matches
        self.clearContents()
        self.setRowCount(len(matches))
        for row, match in enumerate(matches):
            score = match.score
            has_rank_bonus = profile is not None and _has_selected_skill_bonus(
                match.semantic_stat_ids, profile
            )
            highlight = (
                "modifier"
                if match.has_selected_skill_modifier
                else "rank" if has_rank_bonus else ""
            )
            values = (
                match.marker,
                match.item.display_name,
                UNIQUE_TYPE_LABELS[match.item_type],
                match.variant.acquisition_source,
                _format_score(score.effective_score),
                f"{score.matched_count}/{score.total_category_count}",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column != 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                _highlight_item(item, highlight)
                self.setItem(row, column, item)
        visible_rows = max(1, min(len(matches), 12))
        self.setFixedHeight(58 + visible_rows * 26)
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


class UniqueSlotRow(QFrame):
    def __init__(self, slot_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_id = slot_id
        self.setObjectName("uniqueSlotRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 9, 10, 10)
        layout.setSpacing(10)
        slot_label = QLabel(SLOT_LABELS[slot_id], self)
        slot_label.setObjectName("affixSlotName")
        slot_label.setFixedWidth(100)
        layout.addWidget(slot_label)
        self.table = UniqueSlotTable(self)
        layout.addWidget(self.table, 1)


class TopMatchesPage(QWidget):
    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        catalog_status: str = "",
        skills: SkillCatalog | None = None,
        items: ItemCatalog | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.items = items or ItemCatalog((), (), (), (), (), ())
        self.profile = profile
        self.catalog_status = catalog_status
        skill_catalog = skills or SkillCatalog(())
        self.skill_labels = {
            skill.skill_id: skill.display_name
            for skill in skill_catalog.skills
            if skill.display_name
        }
        self.canonical_skill_labels = {
            canonical_skill_reference(skill.skill_id): skill.display_name
            for skill in skill_catalog.skills
            if skill.display_name
        }
        self.mastery_labels = {
            skill.mastery_id: skill.mastery_name
            for skill in skill_catalog.skills
            if skill.mastery_id and skill.mastery_name
        }
        self.matches: tuple[RankedAffixVariant, ...] = ()
        self.unique_matches: tuple[RankedItemVariant, ...] = ()
        self.tables: dict[tuple[str, str], AffixSlotTable] = {}
        self.slot_rows: dict[str, AffixSlotRow] = {}
        self.unique_tables: dict[str, UniqueSlotTable] = {}
        self.unique_slot_rows: dict[str, UniqueSlotRow] = {}
        self.category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self.unique_category_widgets: list[tuple[QLabel, tuple[str, ...]]] = []
        self.weapon_filter_warnings: list[QLabel] = []
        self._selected_table: AffixSlotTable | None = None
        self._selected_unique_table: UniqueSlotTable | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        heading_row = QHBoxLayout()
        heading = QLabel("Top Gear Matches", self)
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

        highlight_legend = QLabel(
            "Pale turquoise: +ranks to active skills    "
            "Aquamarine: active-skill modifier",
            self,
        )
        highlight_legend.setObjectName("matchHighlightLegend")
        layout.addWidget(highlight_legend)

        filter_frame = QFrame(self)
        filter_frame.setObjectName("slotFilterBar")
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(10, 7, 10, 7)
        filter_layout.addWidget(QLabel("Show item slots:", filter_frame))
        self.slot_filters: dict[str, QCheckBox] = {}
        for filter_id, label in FILTER_LABELS:
            checkbox = QCheckBox(label, filter_frame)
            checkbox.setObjectName(f"slotFilter_{filter_id}")
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._slot_filter_changed)
            filter_layout.addWidget(checkbox)
            self.slot_filters[filter_id] = checkbox
            if filter_id == "two_handed":
                self.slot_filter_divider = QFrame(filter_frame)
                self.slot_filter_divider.setObjectName("slotFilterDivider")
                self.slot_filter_divider.setFrameShape(QFrame.Shape.VLine)
                self.slot_filter_divider.setFrameShadow(QFrame.Shadow.Sunken)
                filter_layout.addWidget(self.slot_filter_divider)
        filter_layout.addStretch()
        layout.addWidget(filter_frame)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("recommendationTabs")
        self.tabs.addTab(self._build_affix_tab(), "Affixes")
        self.tabs.addTab(self._build_unique_tab(), "Uniques")
        layout.addWidget(self.tabs, 1)
        self.refresh()

    def _build_affix_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        scroll = QScrollArea(splitter)
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
            if category_label == "Weapons":
                warning = self._weapon_filter_warning(content)
                self.weapon_filter_warnings.append(warning)
                content_layout.addWidget(warning)
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
        splitter.addWidget(scroll)
        self.affix_detail_pane = MatchDetailPane(
            "Select an affix to inspect its matched stats.", splitter
        )
        self.details = self.affix_detail_pane.body
        splitter.addWidget(self.affix_detail_pane)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter)
        return tab

    def _build_unique_tab(self) -> QWidget:
        tab = QWidget(self)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Vertical, tab)
        upper = QWidget(splitter)
        upper_layout = QVBoxLayout(upper)
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(8)

        type_frame = QFrame(upper)
        type_frame.setObjectName("typeFilterBar")
        type_layout = QHBoxLayout(type_frame)
        type_layout.setContentsMargins(10, 7, 10, 7)
        type_layout.addWidget(QLabel("Show types:", type_frame))
        self.type_filters: dict[str, QCheckBox] = {}
        for type_id in UNIQUE_ITEM_TYPES:
            checkbox = QCheckBox(UNIQUE_TYPE_LABELS[type_id], type_frame)
            checkbox.setChecked(True)
            checkbox.toggled.connect(self._type_filter_changed)
            type_layout.addWidget(checkbox)
            self.type_filters[type_id] = checkbox
        type_layout.addSpacing(14)
        type_layout.addWidget(QLabel("Minimum grade:", type_frame))
        self.minimum_grade = QComboBox(type_frame)
        self.minimum_grade.setObjectName("minimumGradeSelector")
        self.minimum_grade.addItems(("S", "A", "B"))
        self.minimum_grade.setCurrentText("A")
        self.minimum_grade.currentTextChanged.connect(
            self._minimum_grade_changed
        )
        type_layout.addWidget(self.minimum_grade)
        type_layout.addStretch()
        upper_layout.addWidget(type_frame)

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
            self.unique_category_widgets.append((category, slot_ids))
            if category_label == "Weapons":
                warning = self._weapon_filter_warning(content)
                self.weapon_filter_warnings.append(warning)
                content_layout.addWidget(warning)
            for slot_id in slot_ids:
                row = UniqueSlotRow(slot_id, content)
                row.table.match_selected.connect(
                    lambda match, selected=row.table, slot=slot_id: self._show_unique(
                        selected, slot, match
                    )
                )
                self.unique_tables[slot_id] = row.table
                self.unique_slot_rows[slot_id] = row
                content_layout.addWidget(row)
        content_layout.addStretch()
        scroll.setWidget(content)
        upper_layout.addWidget(scroll, 1)
        splitter.addWidget(upper)

        self.unique_detail_pane = MatchDetailPane(
            "Select an item to inspect its matched stats.", splitter
        )
        self.unique_details = self.unique_detail_pane.body
        splitter.addWidget(self.unique_detail_pane)
        splitter.setSizes((570, 230))
        layout.addWidget(splitter)
        return tab

    @staticmethod
    def _weapon_filter_warning(parent: QWidget) -> QLabel:
        warning = QLabel(
            "1H or 2H, and at least one weapon type must be selected to view "
            "weapons.",
            parent,
        )
        warning.setObjectName("weaponFilterWarning")
        warning.setWordWrap(True)
        warning.hide()
        return warning

    def set_catalog(self, catalog: AffixCatalog | None, status: str = "") -> None:
        self.catalog = catalog
        self.catalog_status = status
        self.refresh()

    def refresh(self, _value: int | bool = False) -> None:
        self.affix_detail_pane.clear()
        self.unique_detail_pane.clear()
        self.matches = ()
        self.unique_matches = ()
        self._selected_table = None
        self._selected_unique_table = None
        for table in self.tables.values():
            table.set_matches(())
        for table in self.unique_tables.values():
            table.set_matches(())
        if self.catalog is None:
            self.status.setText(
                self.catalog_status
                or "No compiled gear catalog is available for ranking."
            )
            return
        if not self.profile.weights and not any(
            weight > 0 for weight in self.profile.skill_weights.values()
        ):
            self.status.setText(
                "Set at least one nonzero build-profile weight to rank gear."
            )
            return

        all_affixes: list[RankedAffixVariant] = []
        for (slot_id, kind), table in self.tables.items():
            matches = rank_affixes_for_slot(
                self.catalog,
                self.profile,
                slot_id=slot_id,
                kind=kind,
                limit=RESULTS_PER_AFFIX_TABLE,
            )
            table.set_matches(matches, self.profile)
            all_affixes.extend(matches)
        self.matches = tuple(all_affixes)
        self._refresh_uniques()
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()
        self._select_first_visible_unique()

    def _refresh_uniques(self) -> None:
        enabled_types = frozenset(
            type_id
            for type_id, checkbox in self.type_filters.items()
            if checkbox.isChecked()
        )
        all_matches: list[RankedItemVariant] = []
        for slot_id, table in self.unique_tables.items():
            matches = rank_unique_items_for_slot(
                self.items,
                self.profile,
                slot_id=slot_id,
                enabled_types=enabled_types,
                minimum_grade=self.minimum_grade.currentText(),
            )
            table.set_matches(matches, self.profile)
            all_matches.extend(matches)
        self.unique_matches = tuple(all_matches)

    def _slot_filter_changed(self, _checked: bool) -> None:
        self._apply_slot_filters()
        self._update_status()
        self._select_first_visible_match()
        self._select_first_visible_unique()

    def _type_filter_changed(self, _checked: bool) -> None:
        self.unique_detail_pane.clear()
        self._selected_unique_table = None
        self._refresh_uniques()
        self._update_status()
        self._select_first_visible_unique()

    def _minimum_grade_changed(self, _grade: str) -> None:
        self._type_filter_changed(False)

    def _apply_slot_filters(self) -> None:
        enabled = {
            filter_id
            for filter_id, checkbox in self.slot_filters.items()
            if checkbox.isChecked()
        }
        has_handedness = bool(enabled & {"one_handed", "two_handed"})
        has_weapon_type = bool(enabled & {"melee", "caster", "ranged"})
        invalid_weapon_filters = not has_handedness or not has_weapon_type
        for warning in self.weapon_filter_warnings:
            warning.setVisible(invalid_weapon_filters)
        for slot_id in self.slot_rows:
            required = SLOT_FILTERS.get(slot_id, frozenset())
            visible = required <= enabled
            self.slot_rows[slot_id].setVisible(visible)
            self.unique_slot_rows[slot_id].setVisible(visible)
        for headings, rows in (
            (self.category_widgets, self.slot_rows),
            (self.unique_category_widgets, self.unique_slot_rows),
        ):
            for heading, slot_ids in headings:
                is_weapon_heading = bool(set(slot_ids) & set(WEAPON_SLOTS))
                heading.setVisible(
                    (is_weapon_heading and invalid_weapon_filters)
                    or any(not rows[slot].isHidden() for slot in slot_ids)
                )

    def _update_status(self) -> None:
        visible_affixes = sum(
            len(table.matches)
            for (slot_id, _), table in self.tables.items()
            if not self.slot_rows[slot_id].isHidden()
        )
        visible_uniques = sum(
            len(table.matches)
            for slot_id, table in self.unique_tables.items()
            if not self.unique_slot_rows[slot_id].isHidden()
        )
        source_note = f" {self.catalog_status}" if self.catalog_status else ""
        self.status.setText(
            f"{self.profile.name}: {visible_affixes} ranked affix entries and "
            f"{visible_uniques} {self.minimum_grade.currentText()}-or-better "
            "unique-item entries. Grades assume "
            f"the highest-level stat layout.{source_note}"
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
        self.affix_detail_pane.clear()

    def _select_first_visible_unique(self) -> None:
        for _, slot_ids in SLOT_GROUPS:
            for slot_id in slot_ids:
                if self.unique_slot_rows[slot_id].isHidden():
                    continue
                table = self.unique_tables[slot_id]
                if table.matches:
                    table.selectRow(0)
                    return
        self.unique_detail_pane.clear()

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
        score = match.score
        matched_ids = set(score.matched_stat_ids)
        unmatched_ids = [
            stat_id
            for stat_id in match.semantic_stat_ids
            if stat_id not in matched_ids
        ]
        rarity = match.affix.rarity.strip()
        affix_type = " ".join(
            part for part in (rarity, match.affix.kind.title()) if part
        )
        rarity_color = DETAIL_TITLE_COLORS.get(
            f"affix_{rarity.casefold()}", DETAIL_TITLE_COLORS["affix"]
        )
        self.affix_detail_pane.set_title(
            f"{match.marker}{match.affix.display_name} · "
            f"{SLOT_LABELS[slot_id]} · {affix_type}",
            rarity_color,
        )
        html = [
            _html_line(
                f"Effective score: {_format_score(score.effective_score)}"
            ),
            _html_line(f"Raw weight total: {score.weighted_match}"),
            _html_line(
                "Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})"
            ),
            _html_line(""),
            _html_line("Matched stats:", bold=True),
        ]
        if score.matched_stat_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    f"{self._label_for(stat_id)}: weight "
                    f"{profile_weight_for_semantic_id(self.profile, stat_id)}",
                    matched=True,
                )
                for stat_id in score.matched_stat_ids
            )
        else:
            html.append(_stat_html("", "None", matched=True))
        html.extend(
            (_html_line(""), _html_line("Remaining unmatched stats:", bold=True))
        )
        if unmatched_ids:
            html.extend(
                _stat_html(stat_id, self._label_for(stat_id), matched=False)
                for stat_id in unmatched_ids
            )
        else:
            html.append(_stat_html("", "None", matched=False))
        if match.variant.level_requirements:
            html.extend(
                (
                    _html_line(""),
                    _html_line(
                        "Level requirements for this layout: "
                        + ", ".join(map(str, match.variant.level_requirements))
                    ),
                )
            )
        html.extend(
            (
                _html_line(""),
                _html_line("Grades assume the highest-level stat layout."),
                _html_line(f"Full applicability: {match.variant.gear_slot}"),
                _html_line(f"Localization tag: {match.affix.localization_tag}"),
                _html_line(
                    f"Representative: {match.variant.representative_source}"
                ),
            )
        )
        self.details.setHtml("".join(html))

    def _show_unique(
        self,
        table: UniqueSlotTable,
        slot_id: str,
        match: RankedItemVariant,
    ) -> None:
        if self._selected_unique_table is not table:
            for other in self.unique_tables.values():
                if other is not table:
                    other.clearSelection()
            self._selected_unique_table = table
        score = match.score
        matched_ids = set(score.matched_stat_ids)
        unmatched_ids = [
            stat_id
            for stat_id in match.semantic_stat_ids
            if stat_id not in matched_ids
        ]
        self.unique_detail_pane.set_title(
            f"{match.marker}{match.item.display_name} · {SLOT_LABELS[slot_id]} · "
            f"{UNIQUE_TYPE_LABELS[match.item_type]}",
            DETAIL_TITLE_COLORS[match.item_type],
        )
        html = [
            _html_line(f"Source: {match.variant.acquisition_source}"),
            _html_line(
                f"Effective score: {_format_score(score.effective_score)}"
            ),
            _html_line(f"Raw weight total: {score.weighted_match}"),
            _html_line(
                "Coverage: "
                f"{score.matched_count}/{score.total_category_count} "
                f"({score.coverage_ratio:.0%})"
            ),
            _html_line(""),
            _html_line("Matched stats:", bold=True),
        ]
        if score.matched_stat_ids:
            html.extend(
                _stat_html(
                    stat_id,
                    f"{self._label_for(stat_id)}: weight "
                    f"{profile_weight_for_semantic_id(self.profile, stat_id)}",
                    matched=True,
                )
                for stat_id in score.matched_stat_ids
            )
        else:
            html.append(_stat_html("", "None", matched=True))
        html.extend(
            (_html_line(""), _html_line("Remaining unmatched stats:", bold=True))
        )
        if unmatched_ids:
            html.extend(
                _stat_html(stat_id, self._label_for(stat_id), matched=False)
                for stat_id in unmatched_ids
            )
        else:
            html.append(_stat_html("", "None", matched=False))
        if match.variant.set_name:
            html.extend((_html_line(""), _html_line(f"Set: {match.variant.set_name}")))
        if match.variant.granted_skill_name:
            html.extend(
                (
                    _html_line(""),
                    _html_line(
                        f"Granted skill: {match.variant.granted_skill_name}"
                    ),
                )
            )
        if match.variant.skill_modifiers:
            html.extend((_html_line(""), _html_line("Skill modifiers:", bold=True)))
            for modifier in match.variant.skill_modifiers:
                html.append(
                    _html_line(
                        f"- {modifier.modified_skill_name}",
                        color=SKILL_MODIFIER_STAT_COLOR,
                    )
                )
                html.extend(
                    _html_line(f"  - {line}", color=SKILL_MODIFIER_STAT_COLOR)
                    for line in modifier.stat_lines
                )
        if match.has_selected_skill_modifier:
            selected_modifiers = sorted(
                {
                    modifier.modified_skill_name
                    for modifier in match.variant.skill_modifiers
                    if canonical_skill_reference(
                        modifier.modified_skill_reference
                    )
                    in {
                        canonical_skill_reference(skill_id)
                        for skill_id in self.profile.skill_weights
                    }
                }
            )
            html.extend(
                (
                    _html_line(""),
                    _html_line(
                        "†: Modifies selected build skill(s): "
                        + ", ".join(selected_modifiers),
                        color=SKILL_MODIFIER_STAT_COLOR,
                    ),
                    _html_line(
                        "Skill modifiers and their conversions are flagged but are "
                        "not yet included in the numeric grade."
                    ),
                )
            )
        html.extend(
            (
                _html_line(""),
                _html_line(f"Required level: {match.variant.level_requirement}"),
                _html_line("Grades assume the highest-level item variant."),
                _html_line(f"Localization tag: {match.item.localization_tag}"),
                _html_line(
                    f"Record: {match.variant.source}:{match.variant.record_path}"
                ),
            )
        )
        self.unique_details.setHtml("".join(html))

    def _label_for(self, stat_id: str) -> str:
        for prefix, label in (
            ("skill_bonus:", "+Ranks to"),
            ("mastery_bonus:", "+Ranks to all skills in"),
        ):
            if stat_id.startswith(prefix):
                reference = stat_id[len(prefix) :]
                if prefix == "skill_bonus:":
                    reference = self.skill_labels.get(
                        reference,
                        self.canonical_skill_labels.get(
                            canonical_skill_reference(reference), reference
                        ),
                    )
                else:
                    reference = self.mastery_labels.get(reference, reference)
                return f"{label} {reference}"
        return STAT_LABELS.get(stat_id, stat_id)
