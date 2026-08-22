"""Resolve development and packaged application resource paths."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

APP_ROOT_ENVIRONMENT_VARIABLE = "GRIM_GLEANER_APP_ROOT"
EXPORT_LOCALIZATION_SOURCES = {
    "tags_items.txt": Path("base/text_en/tags_items.txt"),
    "tagsgdx1_items.txt": Path("gdx1/text_en/tagsgdx1_items.txt"),
    "tagsgdx2_items.txt": Path("gdx2/text_en/tagsgdx2_items.txt"),
    "tagsgdx2_endlessdungeon.txt": Path(
        "gdx2/text_en/tagsgdx2_endlessdungeon.txt"
    ),
    "tagsgdx3_items.txt": Path("gdx3/text_en/tagsgdx3_items.txt"),
}
ITEM_TAG_FILENAMES = tuple(EXPORT_LOCALIZATION_SOURCES)

LocalizationSourceFiles = tuple[tuple[Path, Path], ...]


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """All filesystem locations the running application owns or consumes."""

    mode: str
    application_root: Path
    project_root: Path | None
    catalog_root: Path
    tags_root: Path
    staging_output_root: Path
    backups_root: Path
    profiles_root: Path

    def as_dict(self) -> dict[str, str | None]:
        return {
            key: str(value) if value is not None else None
            for key, value in asdict(self).items()
        }


@dataclass(frozen=True, slots=True)
class ExportSourceSelection:
    """Primary and fallback localization roots selected for one export."""

    primary_root: Path
    fallback_root: Path | None
    game_text_root: Path | None
    game_files: tuple[str, ...]
    primary_files: LocalizationSourceFiles | None = None
    fallback_files: LocalizationSourceFiles | None = None

    @property
    def uses_game_files(self) -> bool:
        return bool(self.game_files)


def resolve_export_sources(
    game_folder: Path | None,
    bundled_tags_root: Path,
    *,
    installed_text_root: Path | None = None,
) -> ExportSourceSelection:
    """Prefer installed item tags and use bundled tags for missing files.

    Grim Dawn has no useful fallback once an item-tag localization file is
    installed, so a clean installation uses the complete bundled files. When
    Rainbow or another item localization is already installed, its files take
    precedence individually and the bundled directory fills any missing
    expansion files.
    """

    bundled = Path(bundled_tags_root).expanduser().resolve()
    bundled_files = _development_source_files(bundled)
    game_text_root: Path | None = None
    game_files: tuple[str, ...] = ()
    if installed_text_root is not None:
        game_text_root = Path(installed_text_root).expanduser().resolve()
        game_files = tuple(
            filename
            for filename in ITEM_TAG_FILENAMES
            if (game_text_root / filename).is_file()
        )
    elif game_folder is not None and str(game_folder).strip():
        game_text_root = (
            Path(game_folder).expanduser().resolve() / "settings" / "text_en"
        )
        game_files = tuple(
            filename
            for filename in ITEM_TAG_FILENAMES
            if (game_text_root / filename).is_file()
        )
    if game_text_root is not None and game_text_root.is_dir():
        return ExportSourceSelection(
            primary_root=game_text_root,
            fallback_root=bundled,
            game_text_root=game_text_root,
            game_files=game_files,
            fallback_files=bundled_files,
        )
    return ExportSourceSelection(
        primary_root=bundled,
        fallback_root=None,
        game_text_root=game_text_root,
        game_files=(),
        primary_files=bundled_files,
    )


def _development_source_files(root: Path) -> LocalizationSourceFiles | None:
    """Map the extracted ``game_data`` tree to flat export filenames.

    Packaged releases already have a flat ``tags`` directory and therefore
    return ``None`` so every bundled file remains eligible. Development uses
    the extracted source tree directly, with this allowlist preventing DBRs
    and unrelated localization files from being copied into Grim Dawn.
    """

    expected = tuple(
        (root / relative_path, Path(filename))
        for filename, relative_path in EXPORT_LOCALIZATION_SOURCES.items()
    )
    if not any(source_path.exists() for source_path, _ in expected):
        return None
    missing = tuple(
        str(source_path) for source_path, _ in expected if not source_path.is_file()
    )
    if missing:
        raise ValueError(
            "centralized game-data localization is incomplete: "
            + ", ".join(missing)
        )
    return expected


def resolve_runtime_paths(
    *,
    application_root: Path | None = None,
    project_root: Path | None = None,
    frozen: bool | None = None,
    executable: Path | None = None,
    nuitka_application_root: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> RuntimePaths:
    """Return stable paths without depending on the process working directory.

    An explicit application root or ``GRIM_GLEANER_APP_ROOT`` selects the
    packaged layout. The environment override is useful for testing a staged
    release with the normal Python entry point.
    """

    environment = os.environ if environment is None else environment
    explicit_root = application_root
    if explicit_root is None:
        configured_root = environment.get(APP_ROOT_ENVIRONMENT_VARIABLE, "").strip()
        if configured_root:
            explicit_root = Path(configured_root)

    if explicit_root is None:
        explicit_root = (
            Path(nuitka_application_root)
            if nuitka_application_root is not None
            else _nuitka_application_root()
        )

    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if explicit_root is not None or is_frozen:
        if explicit_root is None:
            executable_path = Path(sys.executable) if executable is None else executable
            explicit_root = executable_path.parent
        root = Path(explicit_root).expanduser().resolve()
        return RuntimePaths(
            mode="release",
            application_root=root,
            project_root=None,
            catalog_root=root / "catalog",
            tags_root=root / "tags",
            staging_output_root=root / "staging" / "text_en",
            backups_root=root / "backups",
            profiles_root=root / "Profiles",
        )

    root = (
        Path(project_root).expanduser().resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[2]
    )
    return RuntimePaths(
        mode="development",
        application_root=root,
        project_root=root,
        catalog_root=root / "artifacts" / "catalog",
        tags_root=root / "game_data",
        staging_output_root=root / "artifacts" / "generated" / "text_en",
        backups_root=root / "artifacts" / "backups",
        profiles_root=root / "artifacts" / "profiles",
    )


def _nuitka_application_root() -> Path | None:
    """Return the directory containing a Nuitka-built application.

    Nuitka deliberately does not set ``sys.frozen``. Its injected
    ``__main__.__compiled__.containing_dir`` value is stable for standalone
    and onefile deployments and points to the directory where user-supplied
    resources should live. The marker belongs to the compiled entry-point
    module; Nuitka does not guarantee that it is injected into imported
    modules such as this one.
    """

    main_module = sys.modules.get("__main__")
    compiled = getattr(main_module, "__compiled__", None)
    containing_dir = getattr(compiled, "containing_dir", None)
    if not containing_dir:
        return None
    return Path(containing_dir).expanduser().resolve()
