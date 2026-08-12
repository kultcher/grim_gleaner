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
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.runtime_paths import ITEM_TAG_FILENAMES
from gd_affix_relevance.stats import registered_stat_definitions

TAG_SOURCES = dict(zip(("base", "gdx1", "gdx2", "gdx3"), ITEM_TAG_FILENAMES))
OPTIONAL_RELEASE_DOCUMENTS = ("LICENSE.txt", "THIRD_PARTY_NOTICES.txt")
EXAMPLE_PROFILE_DIRECTORY = Path("Profiles/examples")
MANAGED_RELEASE_PATHS = (
    "catalog",
    "tags",
    "README.txt",
    "LICENSE.txt",
    "THIRD_PARTY_NOTICES.txt",
    "release-manifest.json",
    str(EXAMPLE_PROFILE_DIRECTORY),
)


@dataclass(frozen=True, slots=True)
class ReleaseAssemblyResult:
    output_root: Path
    catalog_files: int
    tag_files: int
    tag_entries: int
    example_profiles: int
    optional_documents_missing: tuple[str, ...]
    manifest_path: Path

    def as_dict(self) -> dict[str, object]:
        return {
            "output_root": str(self.output_root),
            "catalog_files": self.catalog_files,
            "tag_files": self.tag_files,
            "tag_entries": self.tag_entries,
            "example_profiles": self.example_profiles,
            "optional_documents_missing": list(self.optional_documents_missing),
            "manifest_path": str(self.manifest_path),
        }


def assemble_release(
    project_root: Path,
    *,
    output_root: Path | None = None,
    catalog_root: Path | None = None,
    data_root: Path | None = None,
    profiles_root: Path | None = None,
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
    profile_source = (
        Path(profiles_root).expanduser().resolve()
        if profiles_root is not None
        else project / "artifacts" / "profiles" / "examples"
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

    example_profile_sources = _validate_example_profiles(
        profile_source, bundle
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
        staged_profiles = managed_stage / EXAMPLE_PROFILE_DIRECTORY
        staged_catalog.mkdir(parents=True)
        staged_tags.mkdir(parents=True)
        staged_profiles.mkdir(parents=True)

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

        profile_hashes: dict[str, str] = {}
        for source in example_profile_sources:
            target = staged_profiles / source.name
            shutil.copy2(source, target)
            profile_hashes[source.name] = _sha256(target)
        profile_readme = profile_source / "README.txt"
        if profile_readme.is_file():
            shutil.copy2(profile_readme, staged_profiles / "README.txt")

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
            "example_profiles": profile_hashes,
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
        example_profiles=len(example_profile_sources),
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
                previous_target = previous / name
                previous_target.parent.mkdir(parents=True, exist_ok=True)
                target.replace(previous_target)
                moved_old.append(name)
        for name in MANAGED_RELEASE_PATHS:
            staged = stage / name
            if staged.exists():
                target = _managed_child(output, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_managed_path(staged, target)
                installed_new.append(name)
    except OSError:
        for name in reversed(installed_new):
            target = _managed_child(output, name)
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        for name in reversed(moved_old):
            target = _managed_child(output, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            (previous / name).replace(target)
        raise


def _copy_managed_path(source: Path, target: Path) -> None:
    """Install a staged path while inheriting the release root's ACL.

    Temporary directories are intentionally private. Moving their children
    into the release would preserve that private ACL on Windows, potentially
    making packaged resources unreadable to the user who runs the application.
    Creating fresh destination entries inherits the output directory's access
    rules instead.
    """

    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)


def _managed_child(output: Path, name: str) -> Path:
    child = (output / name).resolve()
    if output.resolve() not in child.parents:
        raise ValueError(f"managed release path escapes output directory: {name}")
    return child


def _validate_example_profiles(
    root: Path,
    bundle: CatalogBundle,
) -> tuple[Path, ...]:
    if not root.is_dir():
        raise FileNotFoundError(
            f"example-profile directory is missing: {root}"
        )
    sources = tuple(sorted(root.glob("*.json")))
    if not sources:
        raise ValueError(f"example-profile directory contains no JSON files: {root}")

    valid_stats = {
        definition.stat_id for definition in registered_stat_definitions()
    }
    skills = bundle.skills.by_id()
    mastery_ids = {skill.mastery_id for skill in skills.values() if skill.mastery_id}
    for source in sources:
        profile = load_profile(source)
        if not profile.name.strip():
            raise ValueError(f"example profile has a blank name: {source}")
        if any(not mastery for mastery in profile.masteries):
            raise ValueError(
                f"example profile {source.name} must select two masteries"
            )
        unknown_stats = sorted(set(profile.weights) - valid_stats)
        if unknown_stats:
            raise ValueError(
                f"example profile {source.name} has unknown stats: "
                + ", ".join(unknown_stats)
            )
        unknown_masteries = sorted(
            mastery
            for mastery in profile.masteries
            if mastery not in mastery_ids
        )
        if unknown_masteries:
            raise ValueError(
                f"example profile {source.name} has unknown masteries: "
                + ", ".join(unknown_masteries)
            )
        missing_skills = sorted(set(profile.skill_weights) - set(skills))
        if missing_skills:
            raise ValueError(
                f"example profile {source.name} has unknown skills: "
                + ", ".join(missing_skills)
            )
        wrong_mastery_skills = sorted(
            skill_id
            for skill_id in profile.skill_weights
            if skills[skill_id].mastery_id not in profile.masteries
        )
        if wrong_mastery_skills:
            raise ValueError(
                f"example profile {source.name} has skills outside its masteries: "
                + ", ".join(wrong_mastery_skills)
            )
    return sources


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
