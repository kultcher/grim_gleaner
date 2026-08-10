"""Install generated grade tags into Grim Dawn with recoverable backups."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.output import RainbowGenerationResult, generate_rainbow_output
from gd_affix_relevance.runtime_paths import resolve_export_sources

BACKUP_SCHEMA_VERSION = 1
BACKUP_MANIFEST = "backup-manifest.json"
BACKUP_CONTENTS = "text_en"


@dataclass(frozen=True, slots=True)
class GradeExportResult:
    target_root: Path
    backup_root: Path
    backup_created: bool
    generation: RainbowGenerationResult


@dataclass(frozen=True, slots=True)
class GradeRestoreResult:
    target_root: Path
    original_existed: bool
    restored_files: int


def grim_dawn_text_root(game_folder: Path) -> Path:
    game = Path(game_folder).expanduser().resolve()
    if not game.is_dir():
        raise ValueError(f"Grim Dawn folder does not exist: {game}")
    return game / "settings" / "text_en"


def export_grades_to_game(
    game_folder: Path,
    bundled_tags_root: Path,
    staging_root: Path,
    backups_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    items: ItemCatalog | None = None,
) -> GradeExportResult:
    """Generate, back up the original once, and install graded localization."""

    target = grim_dawn_text_root(game_folder)
    selection = resolve_export_sources(game_folder, bundled_tags_root)
    stage = Path(staging_root).expanduser().resolve()
    if target.resolve() == stage or target.resolve().is_relative_to(stage):
        raise ValueError("staging and Grim Dawn text_en paths must not overlap")

    stage.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".grade-export-", dir=stage.parent))
    try:
        generated = temporary / "text_en"
        generation = generate_rainbow_output(
            selection.primary_root,
            generated,
            catalog,
            profile,
            items=items,
            fallback_source_root=selection.fallback_root,
        )
        _replace_directory(stage, generated)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    backup, backup_created = _ensure_original_backup(target, backups_root)
    _install_directory(stage, target)
    return GradeExportResult(
        target_root=target,
        backup_root=backup,
        backup_created=backup_created,
        generation=replace(generation, output_root=stage),
    )


def restore_game_backup(
    game_folder: Path,
    backups_root: Path,
) -> GradeRestoreResult:
    """Restore and consume the original snapshot for the configured game."""

    target = grim_dawn_text_root(game_folder)
    backup = backup_path_for(target, backups_root)
    manifest = _load_backup_manifest(backup, target)
    original_existed = bool(manifest["original_existed"])
    contents = backup / BACKUP_CONTENTS
    restored_files = 0
    if original_existed:
        if not contents.is_dir():
            raise ValueError(f"backup contents are missing: {contents}")
        restored_files = sum(1 for path in contents.rglob("*") if path.is_file())
        _install_directory(contents, target)
    else:
        _remove_directory_recoverably(target)
    shutil.rmtree(backup)
    return GradeRestoreResult(target, original_existed, restored_files)


def backup_path_for(target_root: Path, backups_root: Path) -> Path:
    target = Path(target_root).expanduser().resolve()
    identity = hashlib.sha256(str(target).casefold().encode("utf-8")).hexdigest()[:12]
    return Path(backups_root).expanduser().resolve() / f"{identity}-text_en"


def backup_available(game_folder: Path, backups_root: Path) -> bool:
    try:
        target = grim_dawn_text_root(game_folder)
    except ValueError:
        return False
    return (backup_path_for(target, backups_root) / BACKUP_MANIFEST).is_file()


def _ensure_original_backup(target: Path, backups_root: Path) -> tuple[Path, bool]:
    backup = backup_path_for(target, backups_root)
    if backup.exists():
        _load_backup_manifest(backup, target)
        return backup, False

    backup.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=backup.parent))
    try:
        original_existed = target.is_dir()
        if original_existed:
            shutil.copytree(target, temporary / BACKUP_CONTENTS)
        (temporary / BACKUP_MANIFEST).write_text(
            json.dumps(
                {
                    "schema_version": BACKUP_SCHEMA_VERSION,
                    "target_root": str(target.resolve()),
                    "original_existed": original_existed,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(backup)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return backup, True


def _load_backup_manifest(backup: Path, target: Path) -> dict[str, object]:
    manifest_path = backup / BACKUP_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"no original-state backup exists for {target}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read backup manifest: {error}") from error
    if payload.get("schema_version") != BACKUP_SCHEMA_VERSION:
        raise ValueError("unsupported backup manifest version")
    if Path(str(payload.get("target_root", ""))).resolve() != target.resolve():
        raise ValueError("backup does not belong to the configured Grim Dawn folder")
    return payload


def _install_directory(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".grim-gleaner-install-", dir=target.parent))
    try:
        incoming = temporary / "text_en"
        shutil.copytree(source, incoming)
        _replace_directory(target, incoming)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _replace_directory(target: Path, incoming: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
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


def _remove_directory_recoverably(target: Path) -> None:
    if not target.exists():
        return
    temporary = target.parent / f".{target.name}-grim-gleaner-restore"
    if temporary.exists():
        raise ValueError(f"unfinished prior restore exists: {temporary}")
    target.replace(temporary)
    shutil.rmtree(temporary)
