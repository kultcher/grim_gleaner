"""Dynamic two-mastery skill selection and weighting UI."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import SkillCatalog, SkillDefinition
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.widgets import WeightControl


@dataclass(frozen=True, slots=True)
class MasterySkills:
    mastery_id: str
    display_name: str
    skills: tuple[SkillDefinition, ...]


def build_mastery_skills(catalog: SkillCatalog) -> tuple[MasterySkills, ...]:
    """Group selectable player skill-tree nodes by localized mastery."""

    mastery_names = {
        skill.mastery_id: skill.mastery_name or skill.display_name
        for skill in catalog.skills
        if skill.is_mastery and skill.mastery_id and skill.display_name
    }
    grouped: dict[str, list[SkillDefinition]] = {
        mastery_id: [] for mastery_id in mastery_names
    }
    for skill in catalog.skills:
        if (
            skill.category != "player"
            or skill.is_mastery
            or not skill.mastery_id
            or not skill.display_name
        ):
            continue
        grouped.setdefault(skill.mastery_id, []).append(skill)

    masteries = [
        MasterySkills(
            mastery_id=mastery_id,
            display_name=mastery_names.get(mastery_id, mastery_id),
            skills=tuple(
                sorted(
                    skills,
                    key=lambda skill: (
                        skill.mastery_level_required,
                        skill.display_name.casefold(),
                        skill.skill_id,
                    ),
                )
            ),
        )
        for mastery_id, skills in grouped.items()
        if skills
    ]
    return tuple(
        sorted(
            masteries,
            key=lambda mastery: _mastery_sort_key(mastery.mastery_id),
        )
    )


class SkillWeightRow(QFrame):
    weight_changed = Signal(str, int)
    remove_requested = Signal(str)

    def __init__(
        self,
        skill: SkillDefinition,
        weight: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.skill = skill
        self.setObjectName("skillWeightRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 7, 5)
        layout.setSpacing(8)

        label = QLabel(skill.display_name, self)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        details = []
        if skill.mastery_level_required:
            details.append(f"Requires mastery level {skill.mastery_level_required}")
        if skill.max_level:
            details.append(f"Maximum rank {skill.max_level}")
        label.setToolTip("; ".join(details))
        layout.addWidget(label, 1)

        self.weight_control = WeightControl(weight, self)
        self.weight_control.value_changed.connect(
            lambda value: self.weight_changed.emit(skill.skill_id, value)
        )
        layout.addWidget(self.weight_control)

        self.remove_button = QPushButton("Remove", self)
        self.remove_button.setObjectName("skillRemove")
        self.remove_button.clicked.connect(
            lambda: self.remove_requested.emit(skill.skill_id)
        )
        layout.addWidget(self.remove_button)


class MasteryPanel(QFrame):
    mastery_change_requested = Signal(int, str)
    skill_add_requested = Signal(str)
    skill_remove_requested = Signal(str)
    skill_weight_changed = Signal(str, int)

    def __init__(self, slot: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot = slot
        self.setObjectName("masteryPanel")
        self._updating = False
        self._skill_lookup: dict[str, SkillDefinition] = {}
        self.rows: dict[str, SkillWeightRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 11, 12, 12)
        outer.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel(f"Mastery {slot + 1}", self)
        title.setObjectName("masteryTitle")
        header.addWidget(title)
        self.mastery_combo = QComboBox(self)
        self.mastery_combo.setObjectName("masterySelector")
        self.mastery_combo.setMinimumWidth(230)
        self.mastery_combo.currentIndexChanged.connect(self._mastery_changed)
        header.addWidget(self.mastery_combo)
        header.addStretch()
        outer.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setObjectName("skillSplitter")

        available = QWidget(splitter)
        available_layout = QVBoxLayout(available)
        available_layout.setContentsMargins(0, 0, 6, 0)
        available_layout.setSpacing(6)
        available_label = QLabel("Mastery Skills", available)
        available_label.setObjectName("skillSectionTitle")
        available_layout.addWidget(available_label)
        self.available_list = QListWidget(available)
        self.available_list.setObjectName("masterySkillList")
        self.available_list.itemSelectionChanged.connect(self._selection_changed)
        self.available_list.itemDoubleClicked.connect(
            lambda item: self.skill_add_requested.emit(
                str(item.data(Qt.ItemDataRole.UserRole))
            )
        )
        available_layout.addWidget(self.available_list, 1)
        self.add_button = QPushButton("Add", available)
        self.add_button.setObjectName("skillAdd")
        self.add_button.setEnabled(False)
        self.add_button.clicked.connect(self._add_selected)
        available_layout.addWidget(self.add_button)
        splitter.addWidget(available)

        selected = QWidget(splitter)
        selected_layout = QVBoxLayout(selected)
        selected_layout.setContentsMargins(6, 0, 0, 0)
        selected_layout.setSpacing(6)
        selected_label = QLabel("Build-Relevant Skills", selected)
        selected_label.setObjectName("skillSectionTitle")
        selected_layout.addWidget(selected_label)
        self.selected_scroll = QScrollArea(selected)
        self.selected_scroll.setWidgetResizable(True)
        self.selected_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.selected_content = QWidget(self.selected_scroll)
        self.selected_layout = QVBoxLayout(self.selected_content)
        self.selected_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_layout.setSpacing(4)
        self.selected_layout.addStretch()
        self.selected_scroll.setWidget(self.selected_content)
        selected_layout.addWidget(self.selected_scroll, 1)
        splitter.addWidget(selected)
        splitter.setSizes((360, 560))
        outer.addWidget(splitter, 1)

    def set_mastery_options(
        self,
        masteries: tuple[MasterySkills, ...],
        current_mastery_id: str,
    ) -> None:
        self._updating = True
        blocker = QSignalBlocker(self.mastery_combo)
        self.mastery_combo.clear()
        self.mastery_combo.addItem("Select a mastery...", "")
        for mastery in masteries:
            self.mastery_combo.addItem(mastery.display_name, mastery.mastery_id)
        index = self.mastery_combo.findData(current_mastery_id)
        self.mastery_combo.setCurrentIndex(max(index, 0))
        del blocker
        self._updating = False

    def set_skills(
        self,
        mastery: MasterySkills | None,
        selected_weights: dict[str, int],
    ) -> None:
        self._skill_lookup = {
            skill.skill_id: skill for skill in mastery.skills
        } if mastery is not None else {}
        self.available_list.clear()
        for skill in self._skill_lookup.values():
            if skill.skill_id in selected_weights:
                continue
            item = QListWidgetItem(skill.display_name)
            item.setData(Qt.ItemDataRole.UserRole, skill.skill_id)
            details = []
            if skill.mastery_level_required:
                details.append(f"Mastery {skill.mastery_level_required}")
            if skill.max_level:
                details.append(f"Max rank {skill.max_level}")
            item.setToolTip("; ".join(details))
            self.available_list.addItem(item)
        self._selection_changed()

        for row in self.rows.values():
            self.selected_layout.removeWidget(row)
            row.deleteLater()
        self.rows.clear()
        for skill in self._skill_lookup.values():
            if skill.skill_id not in selected_weights:
                continue
            row = SkillWeightRow(
                skill,
                selected_weights[skill.skill_id],
                self.selected_content,
            )
            row.weight_changed.connect(self.skill_weight_changed)
            row.remove_requested.connect(self.skill_remove_requested)
            self.selected_layout.insertWidget(self.selected_layout.count() - 1, row)
            self.rows[skill.skill_id] = row

    def _mastery_changed(self, _index: int) -> None:
        if self._updating:
            return
        self.mastery_change_requested.emit(
            self.slot, str(self.mastery_combo.currentData() or "")
        )

    def _selection_changed(self) -> None:
        self.add_button.setEnabled(bool(self.available_list.selectedItems()))

    def _add_selected(self) -> None:
        item = self.available_list.currentItem()
        if item is not None:
            self.skill_add_requested.emit(str(item.data(Qt.ItemDataRole.UserRole)))


class SkillsEditor(QWidget):
    changed = Signal()

    def __init__(
        self,
        profile: BuildProfile,
        catalog: SkillCatalog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.profile = profile
        self.masteries = build_mastery_skills(catalog)
        self.masteries_by_id = {
            mastery.mastery_id: mastery for mastery in self.masteries
        }

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(10)
        hint = QLabel(
            "Choose up to two different masteries, then add and weight the skills "
            "whose bonus ranks matter to this build.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        if not self.masteries:
            unavailable = QLabel(
                "No compiled player-skill catalog is available.", self
            )
            unavailable.setObjectName("pageHint")
            layout.addWidget(unavailable)

        self.panels = (MasteryPanel(0, self), MasteryPanel(1, self))
        for panel in self.panels:
            panel.mastery_change_requested.connect(self._change_mastery)
            panel.skill_add_requested.connect(self._add_skill)
            panel.skill_remove_requested.connect(self._remove_skill)
            panel.skill_weight_changed.connect(self._set_skill_weight)
            layout.addWidget(panel, 1)
        self.refresh_from_profile()

    def refresh_from_profile(self) -> None:
        for slot, panel in enumerate(self.panels):
            other_mastery = self.profile.masteries[1 - slot]
            choices = tuple(
                mastery
                for mastery in self.masteries
                if mastery.mastery_id != other_mastery
                or mastery.mastery_id == self.profile.masteries[slot]
            )
            panel.set_mastery_options(choices, self.profile.masteries[slot])
            panel.set_skills(
                self.masteries_by_id.get(self.profile.masteries[slot]),
                self.profile.skill_weights,
            )

    def _change_mastery(self, slot: int, mastery_id: str) -> None:
        if mastery_id == self.profile.masteries[slot]:
            return
        old_mastery_id = self.profile.masteries[slot]
        affected_skill_ids = self._selected_skill_ids_for_mastery(old_mastery_id)
        if affected_skill_ids and not self._confirm_mastery_change():
            self.refresh_from_profile()
            return
        for skill_id in affected_skill_ids:
            self.profile.remove_skill(skill_id)
        self.profile.set_mastery(slot, mastery_id)
        self.refresh_from_profile()
        self.changed.emit()

    def _selected_skill_ids_for_mastery(self, mastery_id: str) -> tuple[str, ...]:
        mastery = self.masteries_by_id.get(mastery_id)
        if mastery is None:
            return ()
        mastery_skill_ids = {skill.skill_id for skill in mastery.skills}
        return tuple(
            skill_id
            for skill_id in self.profile.skill_weights
            if skill_id in mastery_skill_ids
        )

    def _confirm_mastery_change(self) -> bool:
        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Warning)
        message.setWindowTitle("Change Mastery?")
        message.setText(
            "Changing masteries will erase the build-relevant skills list and all weights."
        )
        confirm = message.addButton("Confirm", QMessageBox.ButtonRole.AcceptRole)
        cancel = message.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        message.setDefaultButton(cancel)
        message.exec()
        return message.clickedButton() is confirm

    def _add_skill(self, skill_id: str) -> None:
        if skill_id in self.profile.skill_weights:
            return
        self.profile.set_skill_weight(skill_id, 0)
        self.refresh_from_profile()
        self.changed.emit()

    def _remove_skill(self, skill_id: str) -> None:
        self.profile.remove_skill(skill_id)
        self.refresh_from_profile()
        self.changed.emit()

    def _set_skill_weight(self, skill_id: str, weight: int) -> None:
        self.profile.set_skill_weight(skill_id, weight)
        self.changed.emit()


def _mastery_sort_key(mastery_id: str) -> tuple[int, str]:
    suffix = mastery_id.removeprefix("playerclass")
    try:
        return int(suffix), mastery_id
    except ValueError:
        return 999, mastery_id
