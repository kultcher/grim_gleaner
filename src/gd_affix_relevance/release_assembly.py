"""Build the resource portion of a distributable Grim Gleaner directory."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.importers.localization_parser import parse_localization_file
from gd_affix_relevance.runtime_paths import ITEM_TAG_FILENAMES

TAG_SOURCES = dict(zip(("base", "gdx1", "gdx2", "gdx3"), ITEM_TAG_FILENAMES))
OPTIONAL_RELEASE_DOCUMENTS = ("LICENSE.txt", "THIRD_PARTY_NOTICES.txt")
MANAGED_RELEASE_PATHS = (
    "catalog",
    "tags",
    "README.txt",
    "LICENSE.txt",
    "THIRD_PARTY_NOTICES.txt",
    "release-manifest.json",
)


@dataclass(frozen=True, slots=True)
class ReleaseAssemblyResult:
    output_root: Path
    catalog_files: int
    tag_files: int
    tag_entries: int
    optional_documents_missing: tuple[str, ...]
    manifest_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "output_root": str(self.output_root),
            "catalog_files": self.catalog_files,
            "tag_files": self.tag_files,
            "tag_entries": self.tag_entries,
            "optional_documents_missing": list(self.optional_documents_missing),
            "manifest_path": str(self.manifest_path),
        }


def assemble_release(
    project_root: Path,
    *,
    output_root: Path | None = None,
    catalog_root: Path | None = None,
    data_root: Path | None = None,
) -> ReleaseAssemblyResult:
    """Validate and stage packaged catalogs, raw tags, and release metadata.

    Only paths listed in ``MANAGED_RELEASE_PATHS`` are replaced. In particular,
    a previously built executable, dependency directory, staging output, and
    user backups are left untouched.
    """

    project = Path(project_root).expanduser().resolve()
    output = (
        Path(output_root).expanduser().resolve()
        if output_root is not None
        else project / "dist" / "Grim Gleaner"
    )
    catalog_source = (
        Path(catalog_root).expanduser().resolve()
        if catalog_root is not None
        else project / "artifacts" / "catalog"
    )
    data_source = (
        Path(data_root).expanduser().resolve()
        if data_root is not None
        else project / "game_data"
    )
    _validate_output_root(output, project)

    bundle = CatalogBundle.load(catalog_source)
    catalog_files = ("manifest.json", *bundle.manifest.files)
    missing_catalog_files = [
        name for name in catalog_files if not (catalog_source / name).is_file()
    ]
    if missing_catalog_files:
        raise FileNotFoundError(
            "catalog is missing required files: " + ", ".join(missing_catalog_files)
        )

    tag_sources: dict[str, Path] = {}
    tag_entry_counts: dict[str, int] = {}
    for source, filename in TAG_SOURCES.items():
        path = data_source / source / "text_en" / filename
        if not path.is_file():
            raise FileNotFoundError(f"required localization file is missing: {path}")
        entry_count = len(parse_localization_file(path))
        if not entry_count:
            raise ValueError(f"localization file contains no tag definitions: {path}")
        tag_sources[filename] = path
        tag_entry_counts[filename] = entry_count

    readme_source = project / "README.md"
    if not readme_source.is_file():
        raise FileNotFoundError(f"release README source is missing: {readme_source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = Path(
        tempfile.mkdtemp(prefix=".grim-gleaner-release-", dir=output.parent)
    )
    try:
        managed_stage = temporary_root / "managed"
        staged_catalog = managed_stage / "catalog"
        staged_tags = managed_stage / "tags"
        staged_catalog.mkdir(parents=True)
        staged_tags.mkdir(parents=True)

        catalog_hashes: dict[str, str] = {}
        for filename in catalog_files:
            source = catalog_source / filename
            target = staged_catalog / filename
            shutil.copy2(source, target)
            catalog_hashes[filename] = _sha256(target)

        tag_hashes: dict[str, str] = {}
        for filename, source in tag_sources.items():
            target = staged_tags / filename
            shutil.copy2(source, target)
            tag_hashes[filename] = _sha256(target)

        shutil.copy2(readme_source, managed_stage / "README.txt")
        optional_missing: list[str] = []
        for filename in OPTIONAL_RELEASE_DOCUMENTS:
            source = project / filename
            if source.is_file():
                shutil.copy2(source, managed_stage / filename)
            else:
                optional_missing.append(filename)

        manifest_payload = {
            "application": "Grim Gleaner",
            "application_version": _application_version(),
            "catalog": {
                "schema_version": bundle.manifest.schema_version,
                "game_version": bundle.manifest.game_version,
                "locale": bundle.manifest.locale,
                "files": catalog_hashes,
            },
            "tags": {
                filename: {
                    "entries": tag_entry_counts[filename],
                    "sha256": tag_hashes[filename],
                }
                for filename in TAG_SOURCES.values()
            },
        }
        (managed_stage / "release-manifest.json").write_text(
            json.dumps(manifest_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        output.mkdir(parents=True, exist_ok=True)
        _replace_managed_paths(output, managed_stage, temporary_root / "previous")
        (output / "Profiles").mkdir(exist_ok=True)
    finally:
        shutil.rmtree(temporary_root, ignore_errors=True)

    return ReleaseAssemblyResult(
        output_root=output,
        catalog_files=len(catalog_files),
        tag_files=len(tag_sources),
        tag_entries=sum(tag_entry_counts.values()),
        optional_documents_missing=tuple(optional_missing),
        manifest_path=output / "release-manifest.json",
    )


def _replace_managed_paths(output: Path, stage: Path, previous: Path) -> None:
    previous.mkdir(parents=True)
    moved_old: list[str] = []
    installed_new: list[str] = []
    try:
        for name in MANAGED_RELEASE_PATHS:
            target = _managed_child(output, name)
            if target.exists():
                target.replace(previous / name)
                moved_old.append(name)
        for name in MANAGED_RELEASE_PATHS:
            staged = stage / name
            if staged.exists():
                staged.replace(_managed_child(output, name))
                installed_new.append(name)
    except OSError:
        for name in reversed(installed_new):
            target = _managed_child(output, name)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        for name in reversed(moved_old):
            (previous / name).replace(_managed_child(output, name))
        raise


def _managed_child(output: Path, name: str) -> Path:
    child = (output / name).resolve()
    if child.parent != output.resolve():
        raise ValueError(f"managed release path escapes output directory: {name}")
    return child


def _validate_output_root(output: Path, project: Path) -> None:
    if output == output.parent or output == project:
        raise ValueError("release output must be a dedicated subdirectory")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _application_version() -> str:
    try:
        return version("gd-affix-relevance")
    except PackageNotFoundError:
        return "0.1.0"
