"""Resolve development and packaged application resource paths."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

APP_ROOT_ENVIRONMENT_VARIABLE = "GRIM_GLEANER_APP_ROOT"
ITEM_TAG_FILENAMES = (
    "tags_items.txt",
    "tagsgdx1_items.txt",
    "tagsgdx2_items.txt",
    "tagsgdx3_items.txt",
)


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

    @property
    def uses_game_files(self) -> bool:
        return bool(self.game_files)


def resolve_export_sources(
    game_folder: Path | None,
    bundled_tags_root: Path,
) -> ExportSourceSelection:
    """Prefer installed item tags and use bundled tags for missing files.

    Grim Dawn has no useful fallback once an item-tag localization file is
    installed, so a clean installation uses the complete bundled files. When
    Rainbow or another item localization is already installed, its files take
    precedence individually and the bundled directory fills any missing
    expansion files.
    """

    bundled = Path(bundled_tags_root).expanduser().resolve()
    game_text_root: Path | None = None
    game_files: tuple[str, ...] = ()
    if game_folder is not None and str(game_folder).strip():
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
        )
    return ExportSourceSelection(
        primary_root=bundled,
        fallback_root=None,
        game_text_root=game_text_root,
        game_files=(),
    )


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
        tags_root=root / "artifacts" / "text_en",
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
