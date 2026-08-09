"""Reusable profile-editor widgets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.domain import MAX_STAT_WEIGHT, WEIGHT_LABELS
from gd_affix_relevance.conversions import (
    CONVERSION_DAMAGE_LABELS,
    conversion_sources_for,
)
from gd_affix_relevance.ui.catalog import PackageDefinition, StatDefinition


class WeightControl(QWidget):
    """Horizontal arrow and star control for an integer weight from 0 through 4."""

    value_changed = Signal(int)

    def __init__(self, value: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.decrement_button = QToolButton(self)
        self.decrement_button.setObjectName("weightArrow")
        self.decrement_button.setText("◀")
        self.decrement_button.setToolTip("Decrease weight")
        self.decrement_button.setAutoRepeat(True)
        self.decrement_button.clicked.connect(self.decrement)
        layout.addWidget(self.decrement_button)

        self.star_buttons: list[QToolButton] = []
        for index in range(MAX_STAT_WEIGHT):
            button = QToolButton(self)
            button.setObjectName("weightStar")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, selected=index + 1: self.set_value(selected)
            )
            self.star_buttons.append(button)
            layout.addWidget(button)

        self.increment_button = QToolButton(self)
        self.increment_button.setObjectName("weightArrow")
        self.increment_button.setText("▶")
        self.increment_button.setToolTip("Increase weight")
        self.increment_button.setAutoRepeat(True)
        self.increment_button.clicked.connect(self.increment)
        layout.addWidget(self.increment_button)

        self.set_value(value, emit=False)

    @property
    def value(self) -> int:
        return self._value

    def set_value(self, value: int, *, emit: bool = True) -> None:
        if not 0 <= value <= MAX_STAT_WEIGHT:
            raise ValueError(f"weight must be between 0 and {MAX_STAT_WEIGHT}")
        changed = value != self._value
        self._value = value
        self._refresh()
        if changed and emit:
            self.value_changed.emit(value)

    def increment(self) -> None:
        self.set_value(min(MAX_STAT_WEIGHT, self._value + 1))

    def decrement(self) -> None:
        self.set_value(max(0, self._value - 1))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.increment()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.decrement()
            event.accept()
            return
        super().keyPressEvent(event)

    def _refresh(self) -> None:
        label = WEIGHT_LABELS[self._value]
        self.setAccessibleName(f"Weight {self._value} of {MAX_STAT_WEIGHT}: {label}")
        self.setToolTip(f"{self._value} — {label}")
        self.decrement_button.setEnabled(self._value > 0)
        self.increment_button.setEnabled(self._value < MAX_STAT_WEIGHT)
        for index, button in enumerate(self.star_buttons, start=1):
            filled = index <= self._value
            button.setText("★" if filled else "☆")
            button.setProperty("filled", filled)
            button.setAccessibleName(f"Set weight to {index}: {WEIGHT_LABELS[index]}")
            button.style().unpolish(button)
            button.style().polish(button)


class StatRow(QWidget):
    value_changed = Signal(str, int)

    def __init__(
        self,
        definition: StatDefinition,
        value: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 5, 10, 5)
        label = QLabel(definition.label, self)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(label)
        self.weight_control = WeightControl(value, self)
        self.weight_control.value_changed.connect(
            lambda weight: self.value_changed.emit(definition.stat_id, weight)
        )
        layout.addWidget(self.weight_control)


class ConversionStatRow(QWidget):
    """Weighted conversion destination with nested source-type filters."""

    value_changed = Signal(str, int)
    source_changed = Signal(str, str, bool)

    def __init__(
        self,
        definition: StatDefinition,
        value: int,
        source_enabled: Callable[[str, str], bool],
        set_source_enabled: Callable[[str, str, bool], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self.destination = definition.stat_id.removeprefix(
            "damage_conversion_to_"
        )
        self._source_enabled = source_enabled
        self._set_source_enabled = set_source_enabled

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_row = QWidget(self)
        main_layout = QHBoxLayout(main_row)
        main_layout.setContentsMargins(12, 5, 10, 5)
        label = QLabel(definition.label, main_row)
        label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        main_layout.addWidget(label)
        self.sources_button = QToolButton(main_row)
        self.sources_button.setObjectName("conversionSourcesButton")
        self.sources_button.setCheckable(True)
        self.sources_button.setAutoRaise(True)
        self.sources_button.toggled.connect(self._set_sources_expanded)
        main_layout.addWidget(self.sources_button)
        self.weight_control = WeightControl(value, main_row)
        self.weight_control.value_changed.connect(
            lambda weight: self.value_changed.emit(definition.stat_id, weight)
        )
        main_layout.addWidget(self.weight_control)
        layout.addWidget(main_row)

        self.sources_body = QFrame(self)
        self.sources_body.setObjectName("conversionSourcesBody")
        sources_layout = QGridLayout(self.sources_body)
        sources_layout.setContentsMargins(32, 4, 12, 9)
        sources_layout.setHorizontalSpacing(18)
        sources_layout.setVerticalSpacing(5)
        self.source_checkboxes: dict[str, QCheckBox] = {}
        for index, source in enumerate(
            conversion_sources_for(self.destination)
        ):
            checkbox = QCheckBox(
                CONVERSION_DAMAGE_LABELS[source], self.sources_body
            )
            checkbox.toggled.connect(
                lambda checked, selected=source: self._source_toggled(
                    selected, checked
                )
            )
            if source == "specific_skill":
                checkbox.setToolTip(
                    "Include conversions that apply only to a specific skill."
                )
            sources_layout.addWidget(checkbox, index // 3, index % 3)
            self.source_checkboxes[source] = checkbox
        layout.addWidget(self.sources_body)
        self.refresh_sources()
        self._set_sources_expanded(False)

    def refresh_sources(self) -> None:
        for source, checkbox in self.source_checkboxes.items():
            blocker = QSignalBlocker(checkbox)
            checkbox.setChecked(
                self._source_enabled(self.destination, source)
            )
            del blocker
        self._refresh_sources_button()

    def _set_sources_expanded(self, expanded: bool) -> None:
        self.sources_button.setChecked(expanded)
        self.sources_body.setVisible(expanded)
        self._refresh_sources_button()

    def _source_toggled(self, source: str, checked: bool) -> None:
        self._set_source_enabled(self.destination, source, checked)
        self._refresh_sources_button()
        self.source_changed.emit(self.destination, source, checked)

    def _refresh_sources_button(self) -> None:
        enabled = sum(
            checkbox.isChecked()
            for checkbox in self.source_checkboxes.values()
        )
        total = len(self.source_checkboxes)
        indicator = "\u25be" if self.sources_button.isChecked() else "\u25b8"
        self.sources_button.setText(f"{indicator} Sources {enabled}/{total}")
        self.sources_button.setToolTip(
            "Choose which incoming damage types make this conversion relevant."
        )


class PackageModifyControl(QWidget):
    """Compact control that adjusts every weight in one package."""

    increment_requested = Signal()
    decrement_requested = Signal()
    value_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("packageModifyControl")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(3)
        label = QLabel("Modify All", self)
        label.setObjectName("packageModifyLabel")
        layout.addWidget(label)

        self.decrement_button = QToolButton(self)
        self.decrement_button.setObjectName("weightArrow")
        self.decrement_button.setText("◀")
        self.decrement_button.setToolTip("Decrease every stat in this package")
        self.decrement_button.clicked.connect(self.decrement_requested)
        layout.addWidget(self.decrement_button)

        self.star_buttons: list[QToolButton] = []
        for index in range(MAX_STAT_WEIGHT):
            button = QToolButton(self)
            button.setObjectName("weightStar")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, selected=index + 1: self.value_requested.emit(
                    selected
                )
            )
            self.star_buttons.append(button)
            layout.addWidget(button)

        self.increment_button = QToolButton(self)
        self.increment_button.setObjectName("weightArrow")
        self.increment_button.setText("▶")
        self.increment_button.setToolTip("Increase every stat in this package")
        self.increment_button.clicked.connect(self.increment_requested)
        layout.addWidget(self.increment_button)

    def refresh(self, values: tuple[int, ...]) -> None:
        common = values[0] if values and len(set(values)) == 1 else None
        minimum = min(values, default=0)
        maximum = max(values, default=0)
        self.decrement_button.setEnabled(maximum > 0)
        self.increment_button.setEnabled(minimum < MAX_STAT_WEIGHT)
        state = f"weight {common}" if common is not None else "mixed weights"
        self.setToolTip(
            f"Package has {state}. Arrows adjust each stat by one; stars set all stats."
        )
        for index, button in enumerate(self.star_buttons, start=1):
            filled = common is not None and index <= common
            button.setText("★" if filled else "☆")
            button.setProperty("filled", filled)
            button.setAccessibleName(f"Set every package stat to {index}")
            button.style().unpolish(button)
            button.style().polish(button)


class PackageAccordion(QFrame):
    """Package whose nonzero values pin its contents open."""

    weight_changed = Signal(str, int)
    conversion_source_changed = Signal(str, str, bool)

    def __init__(
        self,
        definition: PackageDefinition,
        weight_for: Callable[[str], int],
        set_weight: Callable[[str, int], None],
        parent: QWidget | None = None,
        *,
        conversion_source_enabled: Callable[[str, str], bool] | None = None,
        set_conversion_source_enabled: (
            Callable[[str, str, bool], None] | None
        ) = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self._weight_for = weight_for
        self._set_weight = set_weight
        self.setObjectName("packageAccordion")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_row = QWidget(self)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)
        self.header = QPushButton(header_row)
        self.header.setObjectName("packageHeader")
        self.header.setCheckable(True)
        self.header.clicked.connect(self._header_clicked)
        header_layout.addWidget(self.header, 1)
        self.modify_all = PackageModifyControl(header_row)
        self.modify_all.increment_requested.connect(lambda: self._modify_all(1))
        self.modify_all.decrement_requested.connect(lambda: self._modify_all(-1))
        self.modify_all.value_requested.connect(self._set_all)
        header_layout.addWidget(self.modify_all)
        layout.addWidget(header_row)

        self.body = QWidget(self)
        self.body.setObjectName("packageBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 3, 0, 7)
        body_layout.setSpacing(0)
        self.rows: dict[str, StatRow | ConversionStatRow] = {}
        for stat_definition in definition.stats:
            if (
                stat_definition.stat_id.startswith("damage_conversion_to_")
                and conversion_source_enabled is not None
                and set_conversion_source_enabled is not None
            ):
                row = ConversionStatRow(
                    stat_definition,
                    weight_for(stat_definition.stat_id),
                    conversion_source_enabled,
                    set_conversion_source_enabled,
                    self.body,
                )
                row.source_changed.connect(self.conversion_source_changed)
            else:
                row = StatRow(
                    stat_definition,
                    weight_for(stat_definition.stat_id),
                    self.body,
                )
            row.value_changed.connect(self._weight_changed)
            body_layout.addWidget(row)
            self.rows[stat_definition.stat_id] = row
        layout.addWidget(self.body)

        should_expand = definition.default_expanded or self.nonzero_count > 0
        self.set_expanded(should_expand)
        self._refresh_header()

    @property
    def stat_ids(self) -> tuple[str, ...]:
        return tuple(definition.stat_id for definition in self.definition.stats)

    @property
    def nonzero_count(self) -> int:
        return sum(self._weight_for(stat_id) > 0 for stat_id in self.stat_ids)

    @property
    def is_pinned(self) -> bool:
        return self.definition.default_expanded or self.nonzero_count > 0

    @property
    def is_expanded(self) -> bool:
        return self.body.isVisibleTo(self)

    def set_expanded(self, expanded: bool) -> None:
        if not expanded and self.is_pinned:
            expanded = True
        self.header.setChecked(expanded)
        self.body.setVisible(expanded)
        self.modify_all.setVisible(expanded)
        self._refresh_header()

    def refresh_from_profile(self) -> None:
        """Refresh every row after the backing profile is replaced in place."""

        for stat_id, row in self.rows.items():
            row.weight_control.set_value(self._weight_for(stat_id), emit=False)
            if isinstance(row, ConversionStatRow):
                row.refresh_sources()
        self.set_expanded(self.is_pinned)
        self._refresh_header()

    def _modify_all(self, delta: int) -> None:
        values = {
            stat_id: max(
                0, min(MAX_STAT_WEIGHT, row.weight_control.value + delta)
            )
            for stat_id, row in self.rows.items()
        }
        self._apply_bulk(values)

    def _set_all(self, weight: int) -> None:
        self._apply_bulk({stat_id: weight for stat_id in self.rows})

    def _apply_bulk(self, values: dict[str, int]) -> None:
        changed = False
        for stat_id, weight in values.items():
            row = self.rows[stat_id]
            if row.weight_control.value == weight:
                continue
            self._set_weight(stat_id, weight)
            row.weight_control.set_value(weight, emit=False)
            changed = True
        if any(weight > 0 for weight in values.values()):
            self.set_expanded(True)
        self._refresh_header()
        if changed and self.stat_ids:
            first = self.stat_ids[0]
            self.weight_changed.emit(first, self._weight_for(first))

    def _header_clicked(self, checked: bool) -> None:
        self.set_expanded(checked)

    def _weight_changed(self, stat_id: str, weight: int) -> None:
        self._set_weight(stat_id, weight)
        if weight > 0:
            self.set_expanded(True)
        self._refresh_header()
        self.weight_changed.emit(stat_id, weight)

    def _refresh_header(self) -> None:
        count = self.nonzero_count
        expanded = self.header.isChecked()
        indicator = "▾" if expanded else "▸"
        summary = f"  ·  {count} weighted" if count else ""
        default = "  ·  Always shown" if self.definition.default_expanded else ""
        self.header.setText(f"{indicator}  {self.definition.label}{summary}{default}")
        if self.is_pinned:
            self.header.setToolTip("This package stays open while it contains weighted stats.")
        else:
            self.header.setToolTip("Expand or collapse this package.")
        self.modify_all.refresh(
            tuple(row.weight_control.value for row in self.rows.values())
        )
