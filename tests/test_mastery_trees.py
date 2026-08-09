from pathlib import Path

import pytest

from gd_affix_relevance.catalog.mastery_trees import (
    load_mastery_tree_relationships,
)


def test_load_mastery_tree_relationships(tmp_path: Path) -> None:
    (tmp_path / "01soldier.md").write_text(
        "\n".join(
            (
                "# CLASS 01: Soldier",
                "",
                "## PARENT SKILL: Cadence",
                "### CHILD 1: Fighting Form",
                "### CHILD 2: Deadly Momentum",
            )
        ),
        encoding="utf-8",
    )

    relationships = load_mastery_tree_relationships(tmp_path)

    assert [(item.mastery_id, item.parent_name, item.child_name) for item in relationships] == [
        ("playerclass01", "Cadence", "Fighting Form"),
        ("playerclass01", "Cadence", "Deadly Momentum"),
    ]


def test_mastery_tree_rejects_child_before_parent(tmp_path: Path) -> None:
    (tmp_path / "01soldier.md").write_text(
        "# CLASS 01: Soldier\n### CHILD 1: Fighting Form\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="child appears before a parent"):
        load_mastery_tree_relationships(tmp_path)
