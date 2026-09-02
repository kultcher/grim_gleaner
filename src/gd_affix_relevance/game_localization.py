"""Prepare item-tag localization from a user's installed Grim Dawn copy."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.domain import LocaleSpec
from gd_affix_relevance.grade_export import validate_grim_dawn_folder
from gd_affix_relevance.runtime_paths import ITEM_TAG_FILENAMES

ARCHIVE_TOOL_FILENAME = "ArchiveTool.exe"


@dataclass(frozen=True, slots=True)
class ItemTagSource:
    """Where one item-tag file lives for a locale: its archive and the path
    passed to ``ArchiveTool -extract`` to pull it out of that archive."""

    archive_directory: str
    path_in_archive: str


# Real Grim Dawn installs do not keep every item-tag file in one place per
# locale. Russian ships a single combined archive with DLC content nested
# inside it under aom/fg/foa. English ships the base game and each DLC
# (gdx1/gdx2/gdx3) as separate archives, each with its item-tag file at the
# archive root. Keyed by locale code so no "en"/"ru" string literals leak
# into the extraction logic below.
ITEM_TAG_SOURCES: dict[str, dict[str, ItemTagSource]] = {
    "ru": {
        "tags_items.txt": ItemTagSource("resources", "tags_items.txt"),
        "tagsgdx1_items.txt": ItemTagSource("resources", "aom/tagsgdx1_items.txt"),
        "tagsgdx2_items.txt": ItemTagSource("resources", "fg/tagsgdx2_items.txt"),
        "tagsgdx2_endlessdungeon.txt": ItemTagSource(
            "resources", "fg/tagsgdx2_endlessdungeon.txt"
        ),
        "tagsgdx3_items.txt": ItemTagSource("resources", "foa/tagsgdx3_items.txt"),
    },
    "en": {
        "tags_items.txt": ItemTagSource("resources", "tags_items.txt"),
        "tagsgdx1_items.txt": ItemTagSource("gdx1/resources", "tagsgdx1_items.txt"),
        "tagsgdx2_items.txt": ItemTagSource("gdx2/resources", "tagsgdx2_items.txt"),
        "tagsgdx2_endlessdungeon.txt": ItemTagSource(
            "gdx2/resources", "tagsgdx2_endlessdungeon.txt"
        ),
        "tagsgdx3_items.txt": ItemTagSource("gdx3/resources", "tagsgdx3_items.txt"),
    },
}


@dataclass(frozen=True, slots=True)
class PreparedGameLocalization:
    locale: LocaleSpec
    archive_paths: tuple[Path, ...]
    output_root: Path
    files_written: tuple[str, ...]


def prepare_game_item_tags(
    game_folder: Path,
    destination_root: Path,
    *,
    locale: LocaleSpec,
) -> PreparedGameLocalization:
    """Extract and atomically install only the item-tag files for *locale*."""

    game = validate_grim_dawn_folder(game_folder)
    archive_tool = game / ARCHIVE_TOOL_FILENAME
    if not archive_tool.is_file():
        raise ValueError(f"Grim Dawn archive tool is missing: {archive_tool}")

    try:
        layout = ITEM_TAG_SOURCES[locale.code]
    except KeyError as error:
        raise ValueError(
            f"No item-tag archive layout is known for locale: {locale.code}"
        ) from error

    archives: dict[str, Path] = {
        filename: game / source.archive_directory / locale.game_archive_filename
        for filename, source in layout.items()
    }
    missing_archives = sorted(
        {str(path) for path in archives.values() if not path.is_file()}
    )
    if missing_archives:
        raise ValueError(
            f"Grim Dawn {locale.display_name} text archive is missing: "
            + ", ".join(missing_archives)
        )

    destination = Path(destination_root).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # ArchiveTool is an old Win32 utility and can fail with INVALID_HANDLE_VALUE
    # when extraction paths become long. Keep its scratch directory short and
    # move only the five validated outputs to the requested destination.
    temporary = Path(tempfile.mkdtemp(prefix="gg-localization-"))
    try:
        staged_archives: dict[Path, Path] = {}
        for index, archive in enumerate(dict.fromkeys(archives.values())):
            archive_stage = temporary / "archives" / str(index)
            archive_stage.mkdir(parents=True)
            staged_archive = archive_stage / archive.name
            shutil.copy2(archive, staged_archive)
            staged_archives[archive] = staged_archive

        extracted = temporary / "extracted"
        extracted.mkdir()
        diagnostics: list[str] = []
        failed = False
        for filename, source in layout.items():
            try:
                completed = subprocess.run(
                    [
                        str(archive_tool),
                        str(staged_archives[archives[filename]]),
                        "-extract",
                        str(extracted),
                        source.path_in_archive,
                    ],
                    cwd=game,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=30,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except subprocess.TimeoutExpired as error:
                raise ValueError(
                    "Grim Dawn ArchiveTool timed out. Close any ArchiveTool "
                    "error dialog and try again."
                ) from error
            failed = failed or completed.returncode != 0
            diagnostics.extend(
                part.strip()
                for part in (completed.stdout, completed.stderr)
                if part.strip()
            )
        extracted_files, missing = _find_item_tag_files(extracted)
        if failed or missing:
            detail = "\n".join(diagnostics)
            missing_text = ", ".join(missing) if missing else "none"
            raise ValueError(
                "Could not extract the required Grim Dawn localization files. "
                f"Missing: {missing_text}. Close Grim Dawn and try again."
                + (f"\nArchiveTool: {detail}" if detail else "")
            )

        prepared = temporary / "prepared"
        prepared.mkdir()
        for filename, source_path in extracted_files.items():
            shutil.copy2(source_path, prepared / filename)
        _replace_directory(destination, prepared)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    return PreparedGameLocalization(
        locale=locale,
        archive_paths=tuple(dict.fromkeys(archives.values())),
        output_root=destination,
        files_written=ITEM_TAG_FILENAMES,
    )


def _find_item_tag_files(
    extracted_root: Path,
) -> tuple[dict[str, Path], tuple[str, ...]]:
    sources: dict[str, Path] = {}
    for filename in ITEM_TAG_FILENAMES:
        candidates = sorted(
            extracted_root.rglob(filename),
            key=lambda path: (len(path.parts), str(path).casefold()),
        )
        if candidates:
            sources[filename] = candidates[0]
    missing = tuple(
        filename for filename in ITEM_TAG_FILENAMES if filename not in sources
    )
    return sources, missing


def _replace_directory(target: Path, incoming: Path) -> None:
    previous = target.parent / f".{target.name}-grim-gleaner-previous"
    if previous.exists():
        raise ValueError(f"unfinished prior replacement exists: {previous}")
    moved_previous = False
    try:
        if target.exists():
            target.replace(previous)
            moved_previous = True
        incoming.replace(target)
    except Exception:
        if moved_previous and not target.exists():
            previous.replace(target)
        raise
    else:
        if moved_previous:
            shutil.rmtree(previous)
