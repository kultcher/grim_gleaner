"""Install generated grade tags into Grim Dawn with recoverable backups."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import ENGLISH_LOCALE, BuildProfile, LocaleSpec
from gd_affix_relevance.output import RainbowGenerationResult, generate_rainbow_output
from gd_affix_relevance.runtime_paths import resolve_export_sources

BACKUP_SCHEMA_VERSION = 2
LEGACY_BACKUP_SCHEMA_VERSION = 1
BACKUP_MANIFEST = "backup-manifest.json"
BACKUP_CONTENTS = ENGLISH_LOCALE.game_text_directory
GRIM_DAWN_EXECUTABLE = "Grim Dawn.exe"
LOCALIZATION_LOCATION_AUTO = "auto"
LOCALIZATION_LOCATION_INSTALLATION = "installation"
LOCALIZATION_LOCATION_USER = "user"
LOCALIZATION_LOCATION_CHOICES = (
    LOCALIZATION_LOCATION_AUTO,
    LOCALIZATION_LOCATION_INSTALLATION,
    LOCALIZATION_LOCATION_USER,
)


@dataclass(frozen=True, slots=True)
class GradeExportResult:
    target_root: Path
    backup_root: Path
    backup_created: bool
    generation: RainbowGenerationResult
    locale: LocaleSpec


@dataclass(frozen=True, slots=True)
class GradeRestoreResult:
    target_root: Path
    original_existed: bool
    restored_files: int
    locale: LocaleSpec


def validate_grim_dawn_folder(game_folder: Path) -> Path:
    """Return a confirmed Grim Dawn install root.

    A directory alone is not sufficient: users commonly select the Steam
    library or ``steamapps/common`` parent instead of the actual game folder.
    The executable is the stable, inexpensive confirmation available at
    runtime.
    """

    game = Path(game_folder).expanduser().resolve()
    if not game.is_dir():
        raise ValueError(f"Grim Dawn folder does not exist: {game}")
    executable = game / GRIM_DAWN_EXECUTABLE
    if not executable.is_file():
        raise ValueError(
            f"Selected folder does not contain {GRIM_DAWN_EXECUTABLE}: {game}"
        )
    return game


def grim_dawn_text_root(
    game_folder: Path,
    *,
    locale: LocaleSpec = ENGLISH_LOCALE,
    user_settings_root: Path | None = None,
    location_preference: str = LOCALIZATION_LOCATION_AUTO,
) -> Path:
    """Resolve one locale's active item-localization directory.

    Automatic selection follows existing localization files rather than the
    mere presence of a Settings directory. When both supported locations have
    files, the caller must use the persisted user preference explicitly.
    """

    game = validate_grim_dawn_folder(game_folder)
    installation_text_root = game / "settings" / locale.game_text_directory
    preference = str(location_preference).strip().casefold()
    if preference not in LOCALIZATION_LOCATION_CHOICES:
        raise ValueError(
            "Unsupported localization folder preference: "
            f"{location_preference!r}"
        )
    if preference == LOCALIZATION_LOCATION_INSTALLATION:
        return installation_text_root

    user_text_root = None
    if user_settings_root is not None:
        user_text_root = (
            Path(user_settings_root).expanduser().resolve()
            / locale.game_text_directory
        )
    if preference == LOCALIZATION_LOCATION_USER:
        if user_text_root is None:
            raise ValueError(
                "The Documents/My Games Grim Dawn Settings folder could not "
                "be located. Choose the game installation folder instead."
            )
        return user_text_root

    installation_has_files = _contains_localization_files(
        installation_text_root
    )
    user_has_files = (
        user_text_root is not None
        and _contains_localization_files(user_text_root)
    )
    if installation_has_files and user_has_files:
        raise ValueError(
            "Localization files exist in both the Grim Dawn installation and "
            "Documents/My Games. Choose a localization folder on the Settings "
            "page before exporting or restoring."
        )
    if user_has_files:
        return user_text_root
    return installation_text_root


def _contains_localization_files(root: Path) -> bool:
    return root.is_dir() and any(path.is_file() for path in root.rglob("*.txt"))


def detect_grim_dawn_user_settings_root(
    documents_root: Path | None = None,
) -> Path | None:
    """Find the active per-user Grim Dawn Settings directory when present."""

    documents = Path(documents_root).expanduser() if documents_root else None
    if documents is None and os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            ) as key:
                raw_documents = winreg.QueryValueEx(key, "Personal")[0]
            documents = Path(os.path.expandvars(raw_documents))
        except (OSError, TypeError, ValueError):
            documents = None
    if documents is None:
        documents = Path.home() / "Documents"
    candidate = (documents / "My Games" / "Grim Dawn" / "Settings").resolve()
    return candidate if candidate.is_dir() else None


def export_grades_to_game(
    game_folder: Path,
    bundled_tags_root: Path,
    staging_root: Path,
    backups_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    items: ItemCatalog | None = None,
    locale: LocaleSpec = ENGLISH_LOCALE,
    user_settings_root: Path | None = None,
    location_preference: str = LOCALIZATION_LOCATION_AUTO,
) -> GradeExportResult:
    """Generate, back up the original once, and install graded localization."""

    target = grim_dawn_text_root(
        game_folder,
        locale=locale,
        user_settings_root=user_settings_root,
        location_preference=location_preference,
    )
    selection = resolve_export_sources(
        game_folder,
        bundled_tags_root,
        locale=locale,
        installed_text_root=target,
    )
    stage = Path(staging_root).expanduser().resolve()
    if target.resolve() == stage or target.resolve().is_relative_to(stage):
        raise ValueError(
            "staging and Grim Dawn localization paths must not overlap"
        )

    stage.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".grade-export-", dir=stage.parent))
    try:
        generated = temporary / locale.game_text_directory
        generation = generate_rainbow_output(
            selection.primary_root,
            generated,
            catalog,
            profile,
            items=items,
            fallback_source_root=selection.fallback_root,
            source_files=selection.primary_files,
            fallback_source_files=selection.fallback_files,
            locale=locale,
        )
        _replace_directory(stage, generated)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

    backup, backup_created = _ensure_original_backup(
        target,
        backups_root,
        locale,
    )
    _install_directory(stage, target, locale)
    return GradeExportResult(
        target_root=target,
        backup_root=backup,
        backup_created=backup_created,
        generation=replace(generation, output_root=stage),
        locale=locale,
    )


def restore_game_backup(
    game_folder: Path,
    backups_root: Path,
    *,
    locale: LocaleSpec = ENGLISH_LOCALE,
    user_settings_root: Path | None = None,
    location_preference: str = LOCALIZATION_LOCATION_AUTO,
) -> GradeRestoreResult:
    """Restore and consume the original snapshot for the configured game."""

    target = grim_dawn_text_root(
        game_folder,
        locale=locale,
        user_settings_root=user_settings_root,
        location_preference=location_preference,
    )
    backup = backup_path_for(target, backups_root, locale=locale)
    manifest = _load_backup_manifest(backup, target, locale)
    original_existed = bool(manifest["original_existed"])
    contents = backup / locale.game_text_directory
    restored_files = 0
    if original_existed:
        if not contents.is_dir():
            raise ValueError(f"backup contents are missing: {contents}")
        restored_files = sum(1 for path in contents.rglob("*") if path.is_file())
        _install_directory(contents, target, locale)
    else:
        _remove_directory_recoverably(target)
    shutil.rmtree(backup)
    return GradeRestoreResult(target, original_existed, restored_files, locale)


def backup_path_for(
    target_root: Path,
    backups_root: Path,
    *,
    locale: LocaleSpec = ENGLISH_LOCALE,
) -> Path:
    target = Path(target_root).expanduser().resolve()
    identity = hashlib.sha256(str(target).casefold().encode("utf-8")).hexdigest()[:12]
    return (
        Path(backups_root).expanduser().resolve()
        / f"{identity}-{locale.game_text_directory}"
    )


def backup_available(
    game_folder: Path,
    backups_root: Path,
    *,
    locale: LocaleSpec = ENGLISH_LOCALE,
    user_settings_root: Path | None = None,
    location_preference: str = LOCALIZATION_LOCATION_AUTO,
) -> bool:
    try:
        target = grim_dawn_text_root(
            game_folder,
            locale=locale,
            user_settings_root=user_settings_root,
            location_preference=location_preference,
        )
    except ValueError:
        return False
    return (
        backup_path_for(target, backups_root, locale=locale) / BACKUP_MANIFEST
    ).is_file()


def _ensure_original_backup(
    target: Path,
    backups_root: Path,
    locale: LocaleSpec,
) -> tuple[Path, bool]:
    backup = backup_path_for(target, backups_root, locale=locale)
    if backup.exists():
        _load_backup_manifest(backup, target, locale)
        return backup, False

    backup.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=backup.parent))
    try:
        original_existed = target.is_dir()
        if original_existed:
            shutil.copytree(target, temporary / locale.game_text_directory)
        (temporary / BACKUP_MANIFEST).write_text(
            json.dumps(
                {
                    "schema_version": BACKUP_SCHEMA_VERSION,
                    "target_root": str(target.resolve()),
                    "original_existed": original_existed,
                    "locale": locale.code,
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


def _load_backup_manifest(
    backup: Path,
    target: Path,
    locale: LocaleSpec,
) -> dict[str, object]:
    manifest_path = backup / BACKUP_MANIFEST
    if not manifest_path.is_file():
        raise ValueError(f"no original-state backup exists for {target}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"could not read backup manifest: {error}") from error
    schema_version = payload.get("schema_version")
    if schema_version not in (LEGACY_BACKUP_SCHEMA_VERSION, BACKUP_SCHEMA_VERSION):
        raise ValueError("unsupported backup manifest version")
    manifest_locale = payload.get("locale")
    if schema_version == LEGACY_BACKUP_SCHEMA_VERSION:
        manifest_locale = ENGLISH_LOCALE.code
    if manifest_locale != locale.code:
        raise ValueError(
            "backup locale does not match the selected localization: "
            f"{manifest_locale!r} != {locale.code!r}"
        )
    if Path(str(payload.get("target_root", ""))).resolve() != target.resolve():
        raise ValueError("backup does not belong to the configured Grim Dawn folder")
    return payload


def _install_directory(
    source: Path,
    target: Path,
    locale: LocaleSpec,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".grim-gleaner-install-", dir=target.parent))
    try:
        incoming = temporary / locale.game_text_directory
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
