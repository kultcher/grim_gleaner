"""Locate the stat-line templates (tags_ui.txt) for the live reader."""

from __future__ import annotations

from pathlib import Path

from gd_affix_relevance.domain import ENGLISH_LOCALE, LocaleSpec
from gd_affix_relevance.game_localization import (
    UI_TEMPLATE_FILENAME,
    prepare_ui_templates,
)
from gd_affix_relevance.runtime_paths import RuntimePaths


def ui_template_candidates(paths: RuntimePaths, locale: LocaleSpec) -> list[Path]:
    candidates: list[Path] = []
    if paths.project_root is not None and locale.code == ENGLISH_LOCALE.code:
        candidates.append(
            paths.project_root / "game_data" / "base" / locale.game_text_directory
            / UI_TEMPLATE_FILENAME
        )
    candidates.append(prepared_ui_templates_root(paths, locale) / UI_TEMPLATE_FILENAME)
    return candidates


def prepared_ui_templates_root(paths: RuntimePaths, locale: LocaleSpec) -> Path:
    return paths.application_root / "prepared-ui" / locale.code


def find_ui_templates(
    paths: RuntimePaths,
    locale: LocaleSpec,
    *,
    game_folder: Path | None = None,
) -> Path | None:
    """Return tags_ui.txt, extracting it from the game once if needed."""

    for candidate in ui_template_candidates(paths, locale):
        if candidate.is_file():
            return candidate
    if game_folder is None:
        return None
    prepared = prepare_ui_templates(
        game_folder, prepared_ui_templates_root(paths, locale), locale=locale
    )
    path = prepared.output_root / UI_TEMPLATE_FILENAME
    return path if path.is_file() else None
