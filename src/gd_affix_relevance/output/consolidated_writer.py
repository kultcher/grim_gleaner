"""Build one game-recognized override file without importing legacy filters."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import ENGLISH_LOCALE, BuildProfile, LocaleSpec
from gd_affix_relevance.importers.localization_parser import (
    parse_localization_file,
    parse_localization_text,
)
from gd_affix_relevance.io_utils import atomic_replace_directory
from gd_affix_relevance.output.rainbow_writer import (
    RainbowGenerationResult,
    _annotate_text_bytes,
    _build_affix_instructions,
    _build_unique_instructions,
    _paths_overlap,
    _strip_generated_marker,
    _write_bytes_atomically,
)

PREPARED_MANIFEST = "localization-manifest.json"
BEGIN_BLOCK = "# BEGIN GRIM GLEANER GENERATED TAGS"
END_BLOCK = "# END GRIM GLEANER GENERATED TAGS"
GRADE_HISTORY = "# Grim Gleaner graded tags: "


def prepared_host_path(
    source_root: Path, *, locale: LocaleSpec = ENGLISH_LOCALE,
) -> Path:
    """Read the host selected and validated against the installed archives."""
    root = Path(source_root)
    manifest = json.loads((root / PREPARED_MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("locale") != locale.code:
        raise ValueError(
            "prepared localization language does not match the export language"
        )
    host = manifest.get("host_relative_path")
    if not isinstance(host, str) or not host:
        raise ValueError("prepared localization manifest has no host path")
    relative = Path(host)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("invalid consolidated localization host path")
    if not (root / relative).is_file():
        raise ValueError(f"prepared localization host is missing: {relative}")
    return relative


def _existing_customizations(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_bytes().decode("utf-8-sig")
    retained: list[str] = []
    previous_grades: set[str] = set()
    in_block = False
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        if body == BEGIN_BLOCK:
            if in_block:
                raise ValueError("nested Grim Gleaner generated section")
            in_block = True
            continue
        if body == END_BLOCK:
            if not in_block:
                raise ValueError("unmatched Grim Gleaner generated section")
            in_block = False
            continue
        if body.startswith(GRADE_HISTORY):
            tags = json.loads(body[len(GRADE_HISTORY):])
            if not isinstance(tags, list) or not all(
                isinstance(tag, str) for tag in tags
            ):
                raise ValueError("invalid Grim Gleaner grade history")
            previous_grades.update(tags)
            continue
        if not in_block:
            retained.append(line)
    if in_block:
        raise ValueError("unfinished Grim Gleaner generated section")
    # Only remove grades we previously owned; unrelated Raynbow text is intact.
    result: list[str] = []
    for line in retained:
        body = line.rstrip("\r\n")
        tag, separator, value = body.partition("=")
        if separator and tag in previous_grades:
            ending = line[len(body):]
            line = f"{tag}={_strip_generated_marker(value)}{ending}"
        result.append(line)
    return "".join(result)


def generate_consolidated_output(
    clean_source_root: Path,
    output_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    existing_root: Path | None = None,
    host_relative_path: Path | None = None,
    items: ItemCatalog | None = None,
    locale: LocaleSpec = ENGLISH_LOCALE,
) -> RainbowGenerationResult:
    """Preserve a modern master, fill required keys, and refresh owned entries.

    Only host-native keys and graded keys are added from clean game text.
    Missing catalog tags are reported (e.g. equipment from uninstalled DLC).
    Blank customized values are deliberately left ungraded and untouched.
    """
    source = Path(clean_source_root).resolve()
    destination = Path(output_root).resolve()
    existing = Path(existing_root).resolve() if existing_root is not None else None
    for root in (source, existing):
        if root is not None and _paths_overlap(root, destination):
            raise ValueError("source and output directories must not overlap")
    host = host_relative_path or prepared_host_path(source, locale=locale)
    if host.is_absolute() or ".." in host.parts:
        raise ValueError("invalid consolidated localization host path")
    host_source = source / host
    native = parse_localization_file(host_source, encoding=locale.encoding)
    if not native:
        raise ValueError(
            f"localization host contains no tag definitions: {host_source}"
        )
    clean: dict[str, str] = {}
    # Prepared item files are flat; newest-expansion names override older ones.
    for path in sorted(source.rglob("*.txt")):
        for entry in parse_localization_file(path, encoding=locale.encoding):
            clean[entry.tag] = entry.value
    for entry in native:
        clean[entry.tag] = entry.value
    custom = (
        _existing_customizations(existing / host) if existing is not None else ""
    )
    custom_values = {
        entry.tag: entry.value for entry in parse_localization_text(custom)
    }
    affixes = _build_affix_instructions(catalog, profile)
    uniques = _build_unique_instructions(
        items or ItemCatalog((), (), (), (), (), ()), profile
    )
    instructions = {**affixes, **uniques}
    required = {entry.tag for entry in native} | set(instructions)
    additions = {
        tag: clean[tag]
        for tag in sorted(required)
        if tag not in custom_values and tag in clean
    }
    # Intentional empty strings may hide pickup labels or other Raynbow text.
    active = {
        tag: instruction
        for tag, instruction in instructions.items()
        if tag not in custom_values or custom_values[tag].strip()
    }
    newline = "\r\n" if "\r\n" in custom else "\n"
    body = custom
    if body and not body.endswith(("\n", "\r")):
        body += newline
    body += BEGIN_BLOCK + newline
    for tag, value in additions.items():
        body += f"{tag}={value}{newline}"
    present = set(custom_values) | set(additions)
    body += (
        GRADE_HISTORY
        + json.dumps(sorted(set(active) & present), ensure_ascii=False)
        + newline
    )
    body += END_BLOCK + newline
    output, changes, _ = _annotate_text_bytes(
        body.encode(locale.encoding), active, host.as_posix(), locale,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".gleaner-output-", dir=destination.parent))
    try:
        generated = temporary / "generated"
        _write_bytes_atomically(generated / host, output)
        atomic_replace_directory(destination, generated)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return RainbowGenerationResult(
        source_root=source,
        output_root=destination,
        files_written=1,
        affix_tags_scored=len(affixes),
        affix_tags_found=len(set(affixes) & present),
        unique_tags_scored=len(uniques),
        unique_tags_found=len(set(uniques) & present),
        annotated_lines=len(changes),
        missing_affix_tags=tuple(sorted(set(affixes) - present)),
        missing_unique_tags=tuple(sorted(set(uniques) - present)),
        changes=changes,
        master_relative_path=host,
    )
