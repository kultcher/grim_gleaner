"""The grade table the in-game hook loads.

A plain-text, tab-separated file written by Grim Gleaner for the active
profile. The DLL polls its modification time and reloads it, so changing the
profile or filter in the app takes effect in game within a couple of seconds.

    GGT1    <table id>
    adjust  <profile adjustment>
    grade   <grade> <minimum effective score>      (highest first)
    filter  <0|1>
    hide    <rarity class>  <minimum grade>        (classes with a threshold)
    stat    <index> <relevance points> <weight>
    rec     <record path>   <rarity class>  <index>[*<multiplier>],...
    line    <tooltip line key>      <index>
    petline <tooltip line key>      <index>
    end

Record paths are lower-case with forward slashes. Multipliers (optional
magnitude) are omitted when 1. Everything here comes from live/scoring.py,
which is the reference for the DLL's arithmetic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.io_utils import atomic_write_text
from gd_affix_relevance.live.scoring import LiveCatalog, LootFilterSettings, _points
from gd_affix_relevance.live.stat_lines import StatLineIndex
from gd_affix_relevance.scoring.catalog_scorer import (
    GRADE_THRESHOLDS,
    profile_score_adjustment,
    profile_weight_for_semantic_id,
)
from gd_affix_relevance.scoring.magnitude import profile_multipliers
from gd_affix_relevance.stats import stat_is_registered

TABLE_VERSION = "GGT1"


def _format_float(value: float) -> str:
    return repr(float(value))


@dataclass(frozen=True, slots=True)
class GradeTable:
    text: str
    table_id: str
    record_count: int
    stat_count: int
    line_count: int


def build_grade_table(
    catalog: LiveCatalog,
    profile: BuildProfile,
    line_index: StatLineIndex,
    filter_settings: LootFilterSettings,
) -> GradeTable:
    stat_ids: list[str] = []
    stat_index: dict[str, int] = {}

    def index_of(stat_id: str) -> int:
        if stat_id not in stat_index:
            stat_index[stat_id] = len(stat_ids)
            stat_ids.append(stat_id)
        return stat_index[stat_id]

    record_lines: list[str] = []
    for path, info in sorted(catalog.records.items()):
        multipliers = profile_multipliers(profile, (path,)) or {}
        cells = []
        for stat_id in info.stat_ids:
            cell = str(index_of(stat_id))
            multiplier = multipliers.get(stat_id, 1.0)
            if multiplier != 1.0:
                cell += "*" + _format_float(multiplier)
            cells.append(cell)
        record_lines.append(f"rec\t{path}\t{info.rarity_class}\t{','.join(cells)}")

    line_lines: list[str] = []
    for key, stat_id in sorted(line_index.stats_by_key.items()):
        line_lines.append(f"line\t{key}\t{index_of(stat_id)}")
        pet_stat = f"pet_{stat_id}"
        if stat_is_registered(pet_stat):
            line_lines.append(f"petline\t{key}\t{index_of(pet_stat)}")

    body = [
        f"adjust\t{_format_float(profile_score_adjustment(profile))}",
        *(f"grade\t{grade}\t{_format_float(threshold)}" for grade, threshold in GRADE_THRESHOLDS.items()),
        f"filter\t{1 if filter_settings.enabled else 0}",
        *(
            f"hide\t{rarity}\t{grade}"
            for rarity, grade in sorted(filter_settings.thresholds.items())
            if grade is not None
        ),
    ]
    for index, stat_id in enumerate(stat_ids):
        weight = profile_weight_for_semantic_id(profile, stat_id)
        body.append(f"stat\t{index}\t{_format_float(_points(weight))}\t{weight}")
    body.extend(record_lines)
    body.extend(line_lines)
    content = "\n".join(body) + "\nend\n"
    table_id = hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]
    text = f"{TABLE_VERSION}\t{table_id}\n{content}"
    return GradeTable(text, table_id, len(record_lines), len(stat_ids), len(line_lines))


def default_table_path() -> Path:
    import os

    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "GrimGleaner" / "live" / "grade_table.txt"


def write_grade_table(table: GradeTable, path: Path | None = None) -> Path:
    destination = Path(path) if path is not None else default_table_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(destination, table.text)
    return destination
