"""Reusable profile-editor widgets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.domain import MAX_STAT_WEIGHT, WEIGHT_LABELS
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


class PackageAccordion(QFrame):
    """Package whose nonzero values pin its contents open."""

    weight_changed = Signal(str, int)

    def __init__(
        self,
        definition: PackageDefinition,
        weight_for: Callable[[str], int],
        set_weight: Callable[[str, int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.definition = definition
        self._weight_for = weight_for
        self._set_weight = set_weight
        self.setObjectName("packageAccordion")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QPushButton(self)
        self.header.setObjectName("packageHeader")
        self.header.setCheckable(True)
        self.header.clicked.connect(self._header_clicked)
        layout.addWidget(self.header)

        self.body = QWidget(self)
        self.body.setObjectName("packageBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 3, 0, 7)
        body_layout.setSpacing(0)
        self.rows: dict[str, StatRow] = {}
        for stat_definition in definition.stats:
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
        self._refresh_header()

    def refresh_from_profile(self) -> None:
        """Refresh every row after the backing profile is replaced in place."""

        for stat_id, row in self.rows.items():
            row.weight_control.set_value(self._weight_for(stat_id), emit=False)
        self.set_expanded(self.is_pinned)
        self._refresh_header()

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
