from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

import pytest

from gd_affix_relevance.domain import ENGLISH_LOCALE, RUSSIAN_LOCALE
from gd_affix_relevance.game_localization import prepare_game_item_tags
from gd_affix_relevance.runtime_paths import ITEM_TAG_FILENAMES


def _game(tmp_path: Path) -> Path:
    """A Russian-layout install: one combined archive, DLC nested inside it."""

    game = tmp_path / "Grim Dawn"
    (game / "resources").mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    (game / "ArchiveTool.exe").touch()
    (game / "resources" / "Text_RU.arc").touch()
    return game


def _game_en(tmp_path: Path) -> Path:
    """An English-layout install: base game and each DLC ship their own
    archive, at their own resources/ path, with item tags at the archive
    root (no aom/fg/foa nesting)."""

    game = tmp_path / "Grim Dawn"
    (game / "resources").mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    (game / "ArchiveTool.exe").touch()
    (game / "resources" / "Text_EN.arc").touch()
    for dlc in ("gdx1", "gdx2", "gdx3"):
        (game / dlc / "resources").mkdir(parents=True)
        (game / dlc / "resources" / "Text_EN.arc").touch()
    return game


def test_prepare_game_item_tags_copies_only_required_files_atomically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    game = _game(tmp_path)
    destination = tmp_path / "artifacts" / "text_ru"
    destination.mkdir(parents=True)
    (destination / "old.txt").write_text("old", encoding="utf-8")
    extracted_archive_paths: list[str] = []

    def extract(command, **kwargs):
        extracted = Path(command[-2])
        archive_path = Path(command[-1])
        extracted_archive_paths.append(command[-1])
        target = extracted / archive_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"tagExample={{^G}}Пример из {target.name}\n",
            encoding="utf-8-sig",
        )
        (extracted / "tags_ui.txt").write_text("not copied", encoding="utf-8")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("gd_affix_relevance.game_localization.subprocess.run", extract)

    result = prepare_game_item_tags(
        game,
        destination,
        locale=RUSSIAN_LOCALE,
    )

    assert result.files_written == ITEM_TAG_FILENAMES
    assert extracted_archive_paths == [
        "tags_items.txt",
        "aom/tagsgdx1_items.txt",
        "fg/tagsgdx2_items.txt",
        "fg/tagsgdx2_endlessdungeon.txt",
        "foa/tagsgdx3_items.txt",
    ]
    # Russian ships one combined archive: every item-tag file resolves to it.
    assert result.archive_paths == (game / "resources" / "Text_RU.arc",)
    assert set(path.name for path in destination.iterdir()) == set(
        ITEM_TAG_FILENAMES
    )
    assert "Пример" in (destination / "tags_items.txt").read_text(
        encoding="utf-8-sig"
    )


def test_prepare_game_item_tags_extracts_english_dlc_from_separate_archives(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Real Steam English installs split each DLC into its own archive, at
    its own resources/ path, with item tags at the archive root (no
    aom/fg/foa nesting) — unlike the Russian combined-archive layout."""

    game = _game_en(tmp_path)
    destination = tmp_path / "artifacts" / "text_en"
    extracted_commands: list[tuple[str, str]] = []

    def extract(command, **kwargs):
        extracted = Path(command[-2])
        archive = command[-4]
        path_in_archive = command[-1]
        extracted_commands.append((archive, path_in_archive))
        target = extracted / path_in_archive
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"tagExample={{^G}}Example from {target.name}\n", encoding="utf-8-sig")
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("gd_affix_relevance.game_localization.subprocess.run", extract)

    result = prepare_game_item_tags(
        game,
        destination,
        locale=ENGLISH_LOCALE,
    )

    assert result.files_written == ITEM_TAG_FILENAMES
    assert extracted_commands == [
        (str(game / "resources" / "Text_EN.arc"), "tags_items.txt"),
        (str(game / "gdx1" / "resources" / "Text_EN.arc"), "tagsgdx1_items.txt"),
        (str(game / "gdx2" / "resources" / "Text_EN.arc"), "tagsgdx2_items.txt"),
        (
            str(game / "gdx2" / "resources" / "Text_EN.arc"),
            "tagsgdx2_endlessdungeon.txt",
        ),
        (str(game / "gdx3" / "resources" / "Text_EN.arc"), "tagsgdx3_items.txt"),
    ]
    assert result.archive_paths == (
        game / "resources" / "Text_EN.arc",
        game / "gdx1" / "resources" / "Text_EN.arc",
        game / "gdx2" / "resources" / "Text_EN.arc",
        game / "gdx3" / "resources" / "Text_EN.arc",
    )
    assert set(path.name for path in destination.iterdir()) == set(
        ITEM_TAG_FILENAMES
    )


def test_prepare_game_item_tags_reports_missing_english_dlc_archive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """A player missing an English DLC install (no gdx2/resources/Text_EN.arc)
    should get a clear error naming that archive, not an ArchiveTool failure
    for a path that was never going to exist in the base archive."""

    game = _game_en(tmp_path)
    (game / "gdx2" / "resources" / "Text_EN.arc").unlink()

    def unexpected_extract(command, **kwargs):
        raise AssertionError("ArchiveTool should not run before archives are validated")

    monkeypatch.setattr(
        "gd_affix_relevance.game_localization.subprocess.run",
        unexpected_extract,
    )

    with pytest.raises(ValueError, match=r"gdx2[\\/]resources[\\/]Text_EN\.arc"):
        prepare_game_item_tags(
            game,
            tmp_path / "text_en",
            locale=ENGLISH_LOCALE,
        )


def test_prepare_game_item_tags_rejects_incomplete_extraction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    game = _game(tmp_path)

    def incomplete(command, **kwargs):
        extracted = Path(command[-2])
        if command[-1] == "tags_items.txt":
            (extracted / "tags_items.txt").write_text(
                "tag=value",
                encoding="utf-8",
            )
        return CompletedProcess(command, 0, stdout="", stderr="locked")

    monkeypatch.setattr(
        "gd_affix_relevance.game_localization.subprocess.run",
        incomplete,
    )

    with pytest.raises(ValueError, match="Close Grim Dawn"):
        prepare_game_item_tags(
            game,
            tmp_path / "text_ru",
            locale=RUSSIAN_LOCALE,
        )

    assert not (tmp_path / "text_ru").exists()
