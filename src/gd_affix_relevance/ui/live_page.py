"""Live tab: items reported by the in-game hook, graded by the app.

Thin UI over the tested modules in ``gd_affix_relevance.live``:

- listens for the hook's UDP messages (QUdpSocket, no extra threads);
- evaluates each hovered item with :class:`LiveEvaluator` and compares the
  app's verdict with the DLL's;
- writes the grade table the DLL loads whenever the profile, loot filter or
  tooltip options change;
- optionally records every evaluation to a JSON-lines file for testing.
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtNetwork import QHostAddress, QUdpSocket
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.domain import ENGLISH_LOCALE, BuildProfile
from gd_affix_relevance.live.evaluator import (
    EvaluationRecorder,
    LiveEvaluation,
    LiveEvaluator,
)
from gd_affix_relevance.live.grade_table import build_grade_table, write_grade_table
from gd_affix_relevance.live.protocol import (
    DEFAULT_PORT,
    FilterDecision,
    HookError,
    HookStatus,
    HoveredItem,
    ProtocolError,
    TableStatus,
    parse_message,
)
from gd_affix_relevance.live.resources import find_ui_templates
from gd_affix_relevance.live.scoring import GRADE_ORDER, LootFilterSettings
from gd_affix_relevance.live.stat_lines import StatLineIndex, strip_color_codes
from gd_affix_relevance.ui.i18n import t

FILTER_SETTING = "live/loot_filter"
INJECT_SETTING = "live/inject_label"
DETAIL_SETTING = "live/detail_pass"
RECORD_SETTING = "live/record"
MAX_ROWS = 200
FILTERABLE_RARITIES = (
    "common",
    "magic",
    "rare",
    "monster_infrequent",
    "epic",
    "legendary",
)
COLUMNS = ("time", "item", "rarity", "grade", "score", "roll", "label", "dll")


class _MemorySettings:
    """Stand-in when the window runs without persistent settings (tests)."""

    def __init__(self) -> None:
        self._values: dict[str, object] = {}

    def value(self, key: str, default: object = None, type: object = None) -> object:  # noqa: A002
        return self._values.get(key, default)

    def setValue(self, key: str, value: object) -> None:  # noqa: N802 (Qt API)
        self._values[key] = value


def _bool_setting(settings: QSettings, key: str, default: bool) -> bool:
    value = settings.value(key, default)
    if isinstance(value, str):
        return value.casefold() in {"1", "true", "yes"}
    return bool(value)


class LivePage(QWidget):
    def __init__(
        self,
        bundle: object | None,
        profile: BuildProfile,
        settings: QSettings | None,
        runtime_paths: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bundle = bundle
        self.profile = profile
        settings = settings if settings is not None else _MemorySettings()
        self.settings = settings
        self.runtime_paths = runtime_paths
        self.evaluator: LiveEvaluator | None = None
        self.recorder: EvaluationRecorder | None = None
        self.evaluations: list[LiveEvaluation] = []
        self.hidden_count = 0
        self.socket: QUdpSocket | None = None
        self.hook_status = t("live.hook_not_connected")
        self.table_status = ""

        self._table_timer = QTimer(self)
        self._table_timer.setSingleShot(True)
        self._table_timer.setInterval(800)
        self._table_timer.timeout.connect(self.write_table)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        title = QLabel(t("live.title"), self)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel(t("live.intro"), self)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.listen_button = QPushButton(t("live.start_listening"), self)
        self.listen_button.setObjectName("primaryAction")
        self.listen_button.setCheckable(True)
        self.listen_button.toggled.connect(self._listen_toggled)
        controls.addWidget(self.listen_button)
        self.inject_checkbox = QCheckBox(t("live.inject_label"), self)
        self.inject_checkbox.setToolTip(t("live.inject_label_tooltip"))
        self.inject_checkbox.setChecked(_bool_setting(settings, INJECT_SETTING, True))
        self.inject_checkbox.toggled.connect(self._options_changed)
        controls.addWidget(self.inject_checkbox)
        self.detail_checkbox = QCheckBox(t("live.detail_pass"), self)
        self.detail_checkbox.setToolTip(t("live.detail_pass_tooltip"))
        self.detail_checkbox.setChecked(_bool_setting(settings, DETAIL_SETTING, True))
        self.detail_checkbox.toggled.connect(self._options_changed)
        controls.addWidget(self.detail_checkbox)
        self.record_checkbox = QCheckBox(t("live.record"), self)
        self.record_checkbox.setToolTip(t("live.record_tooltip", path=str(self._record_path())))
        self.record_checkbox.setChecked(_bool_setting(settings, RECORD_SETTING, False))
        self.record_checkbox.toggled.connect(self._record_toggled)
        controls.addWidget(self.record_checkbox)
        controls.addStretch(1)
        layout.addLayout(controls)

        layout.addWidget(self._build_filter_box())

        self.status = QLabel(self)
        self.status.setObjectName("liveStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.table = QTableWidget(0, len(COLUMNS), splitter)
        self.table.setObjectName("liveTable")
        self.table.setHorizontalHeaderLabels([t(f"live.column_{name}") for name in COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.currentCellChanged.connect(self._row_selected)
        splitter.addWidget(self.table)
        self.details = QTextEdit(splitter)
        self.details.setReadOnly(True)
        self.details.setObjectName("liveDetails")
        self.details.setPlaceholderText(t("live.details_placeholder"))
        splitter.addWidget(self.details)
        splitter.setSizes((420, 260))
        layout.addWidget(splitter, 1)

        if self.record_checkbox.isChecked():
            self.recorder = EvaluationRecorder(self._record_path())
        self._update_status()

    # --- loot filter -------------------------------------------------------

    def _build_filter_box(self) -> QFrame:
        box = QFrame(self)
        box.setObjectName("typeFilterBar")
        grid = QGridLayout(box)
        grid.setContentsMargins(10, 7, 10, 7)
        self.filter_checkbox = QCheckBox(t("live.filter_enabled"), box)
        self.filter_checkbox.setToolTip(t("live.filter_tooltip"))
        grid.addWidget(self.filter_checkbox, 0, 0, 1, 2)
        saved = self._load_filter_settings()
        self.filter_checkbox.setChecked(saved.enabled)
        self.filter_combos: dict[str, QComboBox] = {}
        for column, rarity in enumerate(FILTERABLE_RARITIES):
            label = QLabel(t(f"live.rarity_{rarity}"), box)
            combo = QComboBox(box)
            combo.addItem(t("live.never_hide"), None)
            for grade in GRADE_ORDER[1:]:
                combo.addItem(t("live.hide_below", grade=grade), grade)
            index = combo.findData(saved.thresholds.get(rarity))
            combo.setCurrentIndex(max(0, index))
            combo.currentIndexChanged.connect(self._options_changed)
            grid.addWidget(label, 1, column)
            grid.addWidget(combo, 2, column)
            self.filter_combos[rarity] = combo
        self.filter_checkbox.toggled.connect(self._options_changed)
        return box

    def _load_filter_settings(self) -> LootFilterSettings:
        raw = self.settings.value(FILTER_SETTING, "", type=str)
        try:
            return LootFilterSettings.from_dict(json.loads(raw)) if raw else LootFilterSettings()
        except (ValueError, TypeError):
            return LootFilterSettings()

    def filter_settings(self) -> LootFilterSettings:
        return LootFilterSettings(
            self.filter_checkbox.isChecked(),
            {
                rarity: combo.currentData()
                for rarity, combo in self.filter_combos.items()
                if combo.currentData() is not None
            },
        )

    # --- grade table ------------------------------------------------------

    def _ensure_evaluator(self) -> LiveEvaluator | None:
        if self.evaluator is not None:
            return self.evaluator
        if self.bundle is None:
            self.table_status = t("live.no_catalog")
            return None
        game_folder = self.settings.value("paths/grim_dawn_folder", "", type=str)
        try:
            templates = find_ui_templates(
                self.runtime_paths,  # type: ignore[arg-type]
                ENGLISH_LOCALE,
                game_folder=Path(game_folder) if game_folder else None,
            )
        except (OSError, ValueError) as error:
            self.table_status = t("live.templates_error", error=str(error))
            return None
        if templates is None:
            self.table_status = t("live.templates_missing")
            return None
        self.evaluator = LiveEvaluator(
            self.bundle,
            self.profile,
            StatLineIndex.from_tags_file(templates),
            self.filter_settings(),
        )
        return self.evaluator

    def write_table(self) -> None:
        evaluator = self._ensure_evaluator()
        if evaluator is None:
            self._update_status()
            return
        evaluator.filter_settings = self.filter_settings()
        evaluator.refresh()
        table = build_grade_table(
            evaluator.catalog,
            self.profile,
            evaluator.line_index,
            evaluator.filter_settings,
            inject_label=self.inject_checkbox.isChecked(),
            detail_pass=self.detail_checkbox.isChecked(),
        )
        evaluator.table = table
        try:
            path = write_grade_table(table)
        except OSError as error:
            self.table_status = t("live.table_write_failed", error=str(error))
        else:
            self.table_status = t(
                "live.table_written", table=table.table_id, path=str(path)
            )
        self._update_status()

    def schedule_table_update(self) -> None:
        """Debounced: profile edits arrive one star at a time."""

        if self.evaluator is not None or self.socket is not None:
            self._table_timer.start()

    def _options_changed(self, *_args: object) -> None:
        self.settings.setValue(FILTER_SETTING, json.dumps(self.filter_settings().to_dict()))
        self.settings.setValue(INJECT_SETTING, self.inject_checkbox.isChecked())
        self.settings.setValue(DETAIL_SETTING, self.detail_checkbox.isChecked())
        self._table_timer.start()

    # --- listening --------------------------------------------------------

    def _listen_toggled(self, enabled: bool) -> None:
        if enabled:
            socket = QUdpSocket(self)
            if not socket.bind(QHostAddress(QHostAddress.SpecialAddress.LocalHost), DEFAULT_PORT):
                self.hook_status = t("live.port_busy", port=DEFAULT_PORT)
                socket.deleteLater()
                self.listen_button.blockSignals(True)
                self.listen_button.setChecked(False)
                self.listen_button.blockSignals(False)
                self._update_status()
                return
            socket.readyRead.connect(self._read_datagrams)
            self.socket = socket
            self.listen_button.setText(t("live.stop_listening"))
            self.hook_status = t("live.waiting_for_hook")
            self.write_table()
        else:
            if self.socket is not None:
                self.socket.close()
                self.socket.deleteLater()
                self.socket = None
            self.listen_button.setText(t("live.start_listening"))
            self.hook_status = t("live.hook_not_connected")
        self._update_status()

    def _read_datagrams(self) -> None:
        socket = self.socket
        while socket is not None and socket.hasPendingDatagrams():
            datagram = socket.receiveDatagram()
            try:
                message = parse_message(bytes(datagram.data()))
            except ProtocolError:
                continue
            self.handle_message(message)

    def handle_message(self, message: object) -> None:
        if isinstance(message, HoveredItem):
            evaluator = self._ensure_evaluator()
            if evaluator is None:
                self._update_status()
                return
            if evaluator.table is None:
                self.write_table()
            evaluation = evaluator.evaluate(message)
            if self.recorder is not None:
                self.recorder.record(evaluation)
            self._add_row(evaluation)
        elif isinstance(message, HookStatus):
            if message.ok:
                self.hook_status = t("live.hook_connected", pid=message.pid)
            else:
                self.hook_status = t("live.hook_not_hooked", pid=message.pid)
        elif isinstance(message, HookError):
            self.hook_status = t("live.hook_error", detail=message.detail)
        elif isinstance(message, TableStatus):
            self.table_status = (
                t("live.table_loaded", table=message.table_id)
                if message.ok
                else t("live.table_rejected", detail=message.detail)
            )
        elif isinstance(message, FilterDecision):
            if message.hidden:
                self.hidden_count += 1
        self._update_status()

    def _record_toggled(self, enabled: bool) -> None:
        self.settings.setValue(RECORD_SETTING, enabled)
        self.recorder = EvaluationRecorder(self._record_path()) if enabled else None

    def _record_path(self) -> Path:
        root = getattr(self.runtime_paths, "application_root", Path.cwd())
        return Path(root) / "live-records" / time.strftime("live-%Y%m%d.jsonl")

    # --- display ------------------------------------------------------------

    def _add_row(self, evaluation: LiveEvaluation) -> None:
        self.evaluations.insert(0, evaluation)
        del self.evaluations[MAX_ROWS:]
        self.table.insertRow(0)
        score = evaluation.relevance.score
        quality = evaluation.quality.value
        if not evaluation.dll_reported:
            dll = t("live.dll_none")
        elif evaluation.mismatches:
            dll = t("live.dll_differs")
        else:
            dll = t("live.dll_agrees")
        values = (
            time.strftime("%H:%M:%S", time.localtime(evaluation.received_at)),
            evaluation.display_name,
            t(f"live.rarity_{evaluation.relevance.rarity_class}"),
            score.grade + (" ▾" if evaluation.hidden_by_filter else ""),
            f"{score.effective_score:.2f}",
            "—" if quality is None else f"{quality:.0%}",
            evaluation.label,
            dll,
        )
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column != 1:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(0, column, item)
        while self.table.rowCount() > MAX_ROWS:
            self.table.removeRow(self.table.rowCount() - 1)
        self.table.setCurrentCell(0, 0)

    def _row_selected(self, row: int, *_args: object) -> None:
        if not 0 <= row < len(self.evaluations):
            return
        self.details.setHtml(self.details_html(self.evaluations[row]))

    @staticmethod
    def details_html(evaluation: LiveEvaluation) -> str:
        score = evaluation.relevance.score
        parts = [
            f"<b>{html.escape(evaluation.display_name)}</b> — seed {evaluation.item.seed}",
            t(
                "live.detail_relevance",
                grade=score.grade,
                score=f"{score.effective_score:.2f}",
                matched=score.matched_count,
                total=score.total_category_count,
            ),
        ]
        if evaluation.quality.value is not None:
            parts.append(t("live.detail_roll", roll=f"{evaluation.quality.value:.0%}"))
            parts.extend(
                f"&nbsp;&nbsp;{stat.percentile:.0%} · {html.escape(strip_color_codes(stat.text))}"
                for stat in evaluation.quality.rolled
            )
        if evaluation.mismatches:
            parts.append(
                "<span style='color:#e0827a'>"
                + html.escape("; ".join(evaluation.mismatches))
                + "</span>"
            )
        if evaluation.quality.unmatched_lines:
            parts.append(
                t("live.detail_unmatched")
                + html.escape(", ".join(evaluation.quality.unmatched_lines))
            )
        parts.append("<hr>")
        parts.extend(
            html.escape(strip_color_codes(line.text)) for line in evaluation.item.lines
        )
        parts.append("<hr>")
        parts.extend(html.escape(record) for record in evaluation.item.records if record)
        return "<br>".join(parts)

    def _update_status(self) -> None:
        pieces = [self.hook_status]
        if self.table_status:
            pieces.append(self.table_status)
        if self.hidden_count:
            pieces.append(t("live.hidden_count", count=self.hidden_count))
        self.status.setText(" · ".join(pieces))
