"""Evaluate hovered items in the app and compare with the DLL's verdict."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.live.grade_table import GradeTable, build_grade_table
from gd_affix_relevance.live.protocol import HoveredItem
from gd_affix_relevance.live.scoring import (
    LiveCatalog,
    LiveRelevance,
    LootFilterSettings,
    RollQuality,
    roll_quality,
    score_live_item,
    tooltip_label,
)
from gd_affix_relevance.live.stat_lines import StatLineIndex

SCORE_TOLERANCE = 1e-3


@dataclass(frozen=True, slots=True)
class LiveEvaluation:
    item: HoveredItem
    received_at: float
    display_name: str
    relevance: LiveRelevance
    quality: RollQuality
    label: str
    hidden_by_filter: bool
    # Empty when the DLL agrees with the app (or sent no verdict).
    mismatches: tuple[str, ...]

    @property
    def dll_reported(self) -> bool:
        return "grade" in self.item.attributes

    def to_record(self) -> dict[str, object]:
        """One JSON line for the testing log."""

        return {
            "time": self.received_at,
            "seed": self.item.seed,
            "records": list(self.item.records),
            "name": self.display_name,
            "app": {
                "grade": self.relevance.score.grade,
                "score": round(self.relevance.score.effective_score, 4),
                "matched": self.relevance.score.matched_count,
                "total": self.relevance.score.total_category_count,
                "rarity": self.relevance.rarity_class,
                "rq": None if self.quality.value is None else round(self.quality.value, 4),
                "label": self.label,
                "hide": self.hidden_by_filter,
                "unknown_records": list(self.relevance.unknown_records),
            },
            "dll": dict(self.item.attributes),
            "mismatches": list(self.mismatches),
            "rolled": [
                {"text": stat.text, "stat": stat.stat_id, "p": round(stat.percentile, 4)}
                for stat in self.quality.rolled
            ],
            "unmatched_lines": list(self.quality.unmatched_lines),
            "lines": [[line.text_class, line.text] for line in self.item.lines],
        }


class LiveEvaluator:
    def __init__(
        self,
        bundle: object,
        profile: BuildProfile,
        line_index: StatLineIndex,
        filter_settings: LootFilterSettings | None = None,
    ) -> None:
        self.bundle = bundle
        self.profile = profile
        self.line_index = line_index
        self.filter_settings = filter_settings or LootFilterSettings()
        self.catalog = LiveCatalog.build(bundle, profile)
        self.table: GradeTable | None = None

    def refresh(self) -> GradeTable:
        """Rebuild for the current profile/filter and return the new table."""

        self.catalog = LiveCatalog.build(self.bundle, self.profile)
        self.table = build_grade_table(
            self.catalog, self.profile, self.line_index, self.filter_settings
        )
        return self.table

    def display_name(self, item: HoveredItem) -> str:
        base = self.catalog.get(item.base_record)
        names = [
            info.display_name
            for info in (self.catalog.get(item.prefix_record), base, self.catalog.get(item.suffix_record))
            if info is not None
        ]
        return " ".join(names) if names else item.base_record

    def evaluate(self, item: HoveredItem) -> LiveEvaluation:
        relevance = score_live_item(self.catalog, self.profile, *item.records)
        lines = [(line.text_class, line.text) for line in item.lines]
        quality = roll_quality(self.line_index, self.profile, lines)
        grade = relevance.score.grade
        return LiveEvaluation(
            item=item,
            received_at=time.time(),
            display_name=self.display_name(item),
            relevance=relevance,
            quality=quality,
            label=tooltip_label(grade, quality.value),
            hidden_by_filter=self.filter_settings.should_hide(grade, relevance.rarity_class),
            mismatches=self._compare(item, relevance, quality),
        )

    def _compare(
        self, item: HoveredItem, relevance: LiveRelevance, quality: RollQuality
    ) -> tuple[str, ...]:
        dll = item.attributes
        if "grade" not in dll:
            return ()
        problems: list[str] = []
        if self.table is not None and dll.get("table") not in (None, self.table.table_id):
            problems.append(f"table {dll.get('table')} != {self.table.table_id} (stale)")
        if dll.get("grade") != relevance.score.grade:
            problems.append(f"grade {dll.get('grade')} != {relevance.score.grade}")
        try:
            if abs(float(dll.get("score", "nan")) - relevance.score.effective_score) > SCORE_TOLERANCE:
                problems.append(
                    f"score {dll.get('score')} != {relevance.score.effective_score:.4f}"
                )
        except ValueError:
            problems.append(f"score {dll.get('score')!r} unreadable")
        if dll.get("matched") != str(relevance.score.matched_count) or dll.get(
            "total"
        ) != str(relevance.score.total_category_count):
            problems.append(
                f"coverage {dll.get('matched')}/{dll.get('total')} != "
                f"{relevance.score.matched_count}/{relevance.score.total_category_count}"
            )
        if dll.get("rarity") not in (None, relevance.rarity_class):
            problems.append(f"rarity {dll.get('rarity')} != {relevance.rarity_class}")
        dll_rq = dll.get("rq", "-")
        if (dll_rq == "-") != (quality.value is None) or (
            quality.value is not None
            and dll_rq != "-"
            and abs(float(dll_rq) - quality.value) > SCORE_TOLERANCE
        ):
            problems.append(f"roll quality {dll_rq} != {quality.value}")
        return tuple(problems)


class EvaluationRecorder:
    """Append evaluations to a JSON-lines file for later comparison."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, evaluation: LiveEvaluation) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(evaluation.to_record(), ensure_ascii=False) + "\n")
