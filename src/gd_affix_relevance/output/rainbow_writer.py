"""Generate a complete Rainbow-derived localization staging folder."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.io_utils import atomic_write_bytes
from gd_affix_relevance.scoring import (
    affix_variants_for_profile,
    canonical_skill_reference,
    item_variant_is_eligible,
    item_semantic_stat_ids,
    score_semantic_stat_ids,
    unique_item_type,
    variant_semantic_stat_ids,
)

UTF8_BOM = b"\xef\xbb\xbf"
COLOR_CODE_PATTERN = re.compile(r"\{\^[^}]+\}")
GENERATED_MARKER_PATTERN = re.compile(
    r"\((?:S\+\+|S\+|S|A|B|C|D|F|-|—)[*!]{0,2}\d*[*!]{0,2}\)"
)
RAINBOW_SET_MARKER_PATTERN = re.compile(
    r"^(?P<leading>\s*)(?:\{\^E\})?\((?:S|\$)\)"
)
MARKER_COLOR = "{^C}"
DEFAULT_COLOR = "{^E}"


@dataclass(frozen=True, slots=True)
class _MarkerInstruction:
    marker: str
    placement: str


@dataclass(frozen=True, slots=True)
class LocalizationChange:
    relative_path: str
    line_number: int
    localization_tag: str
    before: str
    after: str


@dataclass(frozen=True, slots=True)
class RainbowGenerationResult:
    source_root: Path
    output_root: Path
    files_written: int
    affix_tags_scored: int
    affix_tags_found: int
    unique_tags_scored: int
    unique_tags_found: int
    annotated_lines: int
    missing_affix_tags: tuple[str, ...]
    missing_unique_tags: tuple[str, ...]
    changes: tuple[LocalizationChange, ...]
    fallback_source_root: Path | None = None


def build_affix_markers(
    catalog: AffixCatalog,
    profile: BuildProfile,
) -> dict[str, str]:
    """Build one conservative marker for each exact affix localization tag."""

    return {
        tag: instruction.marker
        for tag, instruction in _build_affix_instructions(catalog, profile).items()
    }


def _build_affix_instructions(
    catalog: AffixCatalog,
    profile: BuildProfile,
) -> dict[str, _MarkerInstruction]:
    variants_by_tag: dict[str, list[tuple[str, object]]] = defaultdict(list)
    for affix in catalog.affixes:
        for variant in affix_variants_for_profile(
            affix, profile, include_future_fallback=True
        ):
            variants_by_tag[affix.localization_tag].append((affix.kind, variant))

    instructions: dict[str, _MarkerInstruction] = {}
    for localization_tag, tagged_variants in sorted(variants_by_tag.items()):
        variant_sets = [
            set(variant_semantic_stat_ids(variant, profile))
            for _, variant in tagged_variants
        ]
        common_stat_ids = tuple(sorted(set.intersection(*variant_sets)))
        score = score_semantic_stat_ids(common_stat_ids, profile)
        has_granted_skill = any(
            property_.property_id == "granted_item_skill"
            for _, variant in tagged_variants
            for property_ in variant.properties
        )
        flags = "*" if has_granted_skill else ""
        kinds = {kind for kind, _ in tagged_variants}
        placement = "suffix" if kinds == {"suffix"} else "prefix"
        instructions[localization_tag] = _MarkerInstruction(
            f"({score.marker_body}{flags})", placement
        )
    return instructions


def build_unique_item_markers(
    catalog: ItemCatalog,
    profile: BuildProfile,
) -> dict[str, str]:
    """Build markers for MI, epic, and legendary equipment name tags."""

    return {
        tag: instruction.marker
        for tag, instruction in _build_unique_instructions(catalog, profile).items()
    }


def _build_unique_instructions(
    catalog: ItemCatalog,
    profile: BuildProfile,
) -> dict[str, _MarkerInstruction]:
    selected_skills = {
        canonical_skill_reference(skill_id) for skill_id in profile.skill_weights
    }
    instructions: dict[str, _MarkerInstruction] = {}
    for item in catalog.equipment:
        all_candidates = tuple(
            variant
            for variant in item.variants
            if unique_item_type(variant)
        )
        if not all_candidates:
            continue
        eligible_candidates = tuple(
            variant
            for variant in all_candidates
            if item_variant_is_eligible(variant, profile)
        )
        candidates = eligible_candidates or tuple(
            variant
            for variant in all_candidates
            if variant.level_requirement
            == min(value.level_requirement for value in all_candidates)
        )
        variant = max(
            candidates,
            key=lambda candidate: (
                candidate.level_requirement,
                candidate.item_level,
                score_semantic_stat_ids(
                    item_semantic_stat_ids(candidate, profile), profile
                ).rank_key,
                candidate.record_path,
            ),
        )
        score = score_semantic_stat_ids(
            item_semantic_stat_ids(variant, profile), profile
        )
        flags = ""
        if variant.granted_skill_reference or variant.granted_skill_name:
            flags += "*"
        if any(
            canonical_skill_reference(modifier.modified_skill_reference)
            in selected_skills
            for modifier in variant.skill_modifiers
        ):
            flags += "!"
        instructions[item.localization_tag] = _MarkerInstruction(
            f"({score.marker_body}{flags})", "prefix"
        )
    return instructions


def generate_rainbow_output(
    source_root: Path,
    output_root: Path,
    catalog: AffixCatalog,
    profile: BuildProfile,
    *,
    items: ItemCatalog | None = None,
    fallback_source_root: Path | None = None,
) -> RainbowGenerationResult:
    """Clone merged localization and annotate affix and unique-item tags.

    Files from ``source_root`` take precedence. The optional fallback supplies
    only relative paths absent from the primary source, allowing an installed
    Rainbow setup to override the bundled clean-install item tags per file.
    """

    source = Path(source_root).resolve()
    destination = Path(output_root).resolve()
    if not source.is_dir():
        raise ValueError(f"localization source is not a directory: {source}")
    if _paths_overlap(source, destination):
        raise ValueError("source and output directories must not overlap")

    fallback = (
        Path(fallback_source_root).resolve()
        if fallback_source_root is not None
        else None
    )
    if fallback is not None:
        if not fallback.is_dir():
            raise ValueError(
                f"fallback localization source is not a directory: {fallback}"
            )
        if _paths_overlap(fallback, destination):
            raise ValueError("fallback source and output directories must not overlap")

    source_files = _merged_source_files(source, fallback)
    if not source_files:
        raise ValueError("localization sources contain no files")

    affix_instructions = _build_affix_instructions(catalog, profile)
    unique_instructions = _build_unique_instructions(
        items or ItemCatalog((), (), (), (), (), ()), profile
    )
    instructions = {**affix_instructions, **unique_instructions}
    found_tags: set[str] = set()
    changes: list[LocalizationChange] = []
    for source_path, relative in source_files:
        destination_path = destination / relative
        raw_bytes = source_path.read_bytes()
        if source_path.suffix.casefold() == ".txt":
            output_bytes, file_changes, file_found_tags = _annotate_text_bytes(
                raw_bytes,
                instructions,
                relative.as_posix(),
            )
            changes.extend(file_changes)
            found_tags.update(file_found_tags)
        else:
            output_bytes = raw_bytes
        _write_bytes_atomically(destination_path, output_bytes)

    found_affix_tags = found_tags & set(affix_instructions)
    found_unique_tags = found_tags & set(unique_instructions)
    missing_affixes = tuple(
        sorted(set(affix_instructions) - found_tags, key=str.casefold)
    )
    missing_uniques = tuple(
        sorted(set(unique_instructions) - found_tags, key=str.casefold)
    )
    return RainbowGenerationResult(
        source_root=source,
        output_root=destination,
        files_written=len(source_files),
        affix_tags_scored=len(affix_instructions),
        affix_tags_found=len(found_affix_tags),
        unique_tags_scored=len(unique_instructions),
        unique_tags_found=len(found_unique_tags),
        annotated_lines=len(changes),
        missing_affix_tags=missing_affixes,
        missing_unique_tags=missing_uniques,
        changes=tuple(changes),
        fallback_source_root=fallback,
    )


def _merged_source_files(
    primary: Path,
    fallback: Path | None,
) -> tuple[tuple[Path, Path], ...]:
    selected: dict[str, tuple[Path, Path]] = {}
    for root in (fallback, primary):
        if root is None:
            continue
        for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
            relative = path.relative_to(root)
            selected[relative.as_posix().casefold()] = (path, relative)
    return tuple(selected[key] for key in sorted(selected))


def _annotate_text_bytes(
    raw_bytes: bytes,
    instructions: dict[str, _MarkerInstruction],
    relative_path: str,
) -> tuple[bytes, tuple[LocalizationChange, ...], set[str]]:
    has_bom = raw_bytes.startswith(UTF8_BOM)
    text = raw_bytes.decode("utf-8-sig")
    output_lines: list[str] = []
    changes: list[LocalizationChange] = []
    found_tags: set[str] = set()
    for line_number, line in enumerate(text.splitlines(keepends=True), start=1):
        body, ending = _split_line_ending(line)
        separator = body.find("=")
        if separator < 1:
            output_lines.append(line)
            continue
        tag = body[:separator]
        instruction = instructions.get(tag)
        if instruction is None:
            output_lines.append(line)
            continue

        found_tags.add(tag)
        value = body[separator + 1 :]
        annotated_value = _replace_generated_marker(value, instruction)
        annotated_body = f"{tag}={annotated_value}"
        output_lines.append(annotated_body + ending)
        if annotated_body != body:
            changes.append(
                LocalizationChange(
                    relative_path=relative_path,
                    line_number=line_number,
                    localization_tag=tag,
                    before=body,
                    after=annotated_body,
                )
            )

    output = "".join(output_lines).encode("utf-8")
    if has_bom:
        output = UTF8_BOM + output
    return output, tuple(changes), found_tags


def _replace_generated_marker(
    value: str, instruction: _MarkerInstruction
) -> str:
    clean_value = _normalize_rainbow_set_marker(
        _strip_generated_marker(value)
    )
    has_explicit_color = COLOR_CODE_PATTERN.search(clean_value) is not None
    if instruction.placement == "suffix":
        marker_color = MARKER_COLOR if has_explicit_color else ""
        return f"{clean_value}{marker_color}{instruction.marker}"
    marker_color = MARKER_COLOR if has_explicit_color else ""
    return f"{marker_color}{instruction.marker}{clean_value}"


def _strip_generated_marker(value: str) -> str:
    existing = next(
        (
            match
            for match in GENERATED_MARKER_PATTERN.finditer(value)
            if match.group() != "(S)"
            or value[
                max(0, match.start() - len(MARKER_COLOR)) : match.start()
            ]
            == MARKER_COLOR
        ),
        None,
    )
    if existing is None:
        return value
    start, end = existing.span()
    if value[max(0, start - len(MARKER_COLOR)) : start] == MARKER_COLOR:
        start -= len(MARKER_COLOR)
    if value[end : end + len(DEFAULT_COLOR)] == DEFAULT_COLOR:
        end += len(DEFAULT_COLOR)
    return value[:start] + value[end:]


def _normalize_rainbow_set_marker(value: str) -> str:
    """Disambiguate Rainbow's set marker and restore its default color."""

    return RAINBOW_SET_MARKER_PATTERN.sub(
        lambda match: f"{match.group('leading')}{DEFAULT_COLOR}($)",
        value,
        count=1,
    )


def _split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith(("\r", "\n")):
        return line[:-1], line[-1:]
    return line, ""


def _paths_overlap(first: Path, second: Path) -> bool:
    return (
        first == second
        or first.is_relative_to(second)
        or second.is_relative_to(first)
    )


def _write_bytes_atomically(path: Path, payload: bytes) -> None:
    atomic_write_bytes(path, payload)
