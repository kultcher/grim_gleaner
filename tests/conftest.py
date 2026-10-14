from __future__ import annotations

from pathlib import Path

import pytest

from gd_affix_relevance.domain import ENGLISH_LOCALE
from gd_affix_relevance.ui import i18n

PROJECT_ROOT = Path(__file__).resolve().parents[1]
I18N_RESOURCES_ROOT = PROJECT_ROOT / "resources" / "i18n"


@pytest.fixture(autouse=True)
def _default_ui_locale():
    """Mirror the application's startup behavior: English until configured.

    ``ui.i18n`` holds process-global state because locale changes require a
    restart. Resetting it before and after every test keeps tests that
    exercise the Russian UI from leaking that choice into unrelated tests.
    """

    i18n.configure(I18N_RESOURCES_ROOT, ENGLISH_LOCALE)
    yield
    i18n.configure(I18N_RESOURCES_ROOT, ENGLISH_LOCALE)


@pytest.fixture
def localization_archive_tool(monkeypatch):
    """Exercise real extraction/export with a simulated installed ArchiveTool."""
    from subprocess import CompletedProcess
    from gd_affix_relevance import game_localization

    original_prepare = game_localization.prepare_game_item_tags
    calls = []
    seed: dict[str, str] = {}

    def prepare(game_folder, destination_root, *, locale):
        game = Path(game_folder)
        game_localization.validate_grim_dawn_folder(game)
        (game / "ArchiveTool.exe").touch()
        for directory in ("resources", "gdx1/resources", "gdx2/resources", "gdx3/resources"):
            root = game / directory
            root.mkdir(parents=True, exist_ok=True)
            (root / locale.game_archive_filename).touch()
        # Tests can supply clean localized values; extraction still refreshes all files.
        seed.clear()
        for path in Path(destination_root).rglob("*.txt"):
            seed[path.name] = path.read_text(encoding="utf-8-sig")
        seed.setdefault("tags_items.txt", "tagHealthy=Здоровый\n" if locale.code == "ru" else "tagHealthy=Bundled Healthy\n")
        calls.append((game_folder, destination_root, locale.code))
        return original_prepare(game_folder, destination_root, locale=locale)

    def extract(command, **kwargs):
        target = Path(command[-2]) / command[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(seed.get(target.name, "tagNative=Native\n"), encoding="utf-8-sig")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(game_localization, "prepare_game_item_tags", prepare)
    monkeypatch.setattr(game_localization.subprocess, "run", extract)
    return calls
