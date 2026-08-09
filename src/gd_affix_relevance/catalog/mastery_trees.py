"""Parse the curated mastery parent/child relationship files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


CLASS_PATTERN = re.compile(r"^# CLASS (\d{2}):\s*(.+?)\s*$")
PARENT_PATTERN = re.compile(r"^## PARENT SKILL:\s*(.+?)\s*$")
CHILD_PATTERN = re.compile(r"^### CHILD \d+:\s*(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class MasteryTreeRelationship:
    mastery_id: str
    parent_name: str
    child_name: str
    source: str


def load_mastery_tree_relationships(
    root: Path | None,
) -> tuple[MasteryTreeRelationship, ...]:
    """Load strict, display-name-based relationships from Markdown files."""

    if root is None:
        return ()
    tree_root = Path(root)
    if not tree_root.exists():
        raise ValueError(f"mastery-tree root does not exist: {tree_root}")

    relationships: list[MasteryTreeRelationship] = []
    seen_children: dict[tuple[str, str], str] = {}
    for path in sorted(tree_root.glob("*.md")):
        mastery_id = ""
        current_parent = ""
        for line_number, raw_line in enumerate(
            path.read_text(encoding="utf-8-sig").splitlines(), start=1
        ):
            line = raw_line.strip()
            if match := CLASS_PATTERN.fullmatch(line):
                mastery_id = f"playerclass{match.group(1)}"
                current_parent = ""
                continue
            if match := PARENT_PATTERN.fullmatch(line):
                if not mastery_id:
                    raise ValueError(
                        f"{path}:{line_number}: parent appears before class header"
                    )
                current_parent = match.group(1).strip()
                continue
            if match := CHILD_PATTERN.fullmatch(line):
                child_name = match.group(1).strip()
                if not mastery_id or not current_parent:
                    raise ValueError(
                        f"{path}:{line_number}: child appears before a parent"
                    )
                key = (mastery_id, child_name.casefold())
                previous = seen_children.get(key)
                if previous is not None and previous.casefold() != current_parent.casefold():
                    raise ValueError(
                        f"{path}:{line_number}: {child_name!r} has multiple parents"
                    )
                seen_children[key] = current_parent
                relationships.append(
                    MasteryTreeRelationship(
                        mastery_id=mastery_id,
                        parent_name=current_parent,
                        child_name=child_name,
                        source=f"{path.name}:{line_number}",
                    )
                )

    return tuple(relationships)
