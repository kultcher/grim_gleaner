import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import SkillCatalog, SkillDefinition
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.skills_editor import SkillsEditor, build_mastery_skills


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _skill(
    skill_id: str,
    name: str,
    mastery_id: str,
    mastery_name: str,
    *,
    category: str = "player",
    is_mastery: bool = False,
    required: int = 1,
    skill_tier: int = 1,
    tree_order: int = 1,
    parent_skill_id: str = "",
    max_level: int = 12,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        source="base",
        category=category,
        name_tag=f"tag{name.replace(' ', '')}",
        display_name=name,
        name_resolution="localized",
        description_tag="",
        mastery_id=mastery_id,
        mastery_name=mastery_name,
        mastery_level_required=required,
        max_level=max_level,
        is_mastery=is_mastery,
        skill_tier=skill_tier,
        tree_order=tree_order,
        parent_skill_id=parent_skill_id,
    )


def _catalog() -> SkillCatalog:
    return SkillCatalog(
        (
            _skill(
                "records/skills/playerclass01/_classtraining_class01.dbr",
                "Soldier",
                "playerclass01",
                "Soldier",
                is_mastery=True,
                required=0,
                skill_tier=0,
                tree_order=0,
            ),
            _skill(
                "records/skills/playerclass01/cadence1.dbr",
                "Cadence",
                "playerclass01",
                "Soldier",
                tree_order=2,
            ),
            _skill(
                "records/skills/playerclass01/pets/internal.dbr",
                "Internal Pet Attack",
                "playerclass01",
                "Soldier",
                category="pet",
                skill_tier=0,
                tree_order=0,
            ),
            _skill(
                "records/skills/playerclass02/_classtraining_class02.dbr",
                "Demolitionist",
                "playerclass02",
                "Demolitionist",
                is_mastery=True,
                required=0,
                skill_tier=0,
                tree_order=0,
            ),
            _skill(
                "records/skills/playerclass02/flamestrike1.dbr",
                "Fire Strike",
                "playerclass02",
                "Demolitionist",
                tree_order=2,
            ),
            _skill(
                "records/skills/playerclass03/_classtraining_class03.dbr",
                "Occultist",
                "playerclass03",
                "Occultist",
                is_mastery=True,
                required=0,
                skill_tier=0,
                tree_order=0,
            ),
            _skill(
                "records/skills/playerclass03/doombolt1.dbr",
                "Doom Bolt",
                "playerclass03",
                "Occultist",
                tree_order=2,
            ),
        )
    )


def test_mastery_groups_exclude_headers_and_internal_pet_skills() -> None:
    masteries = build_mastery_skills(_catalog())

    assert [mastery.display_name for mastery in masteries] == [
        "Soldier",
        "Demolitionist",
        "Occultist",
    ]
    assert [skill.display_name for skill in masteries[0].skills] == ["Cadence"]


def test_mastery_skills_sort_by_tier_with_children_after_their_parent() -> None:
    cadence_id = "records/skills/playerclass01/cadence1.dbr"
    catalog = SkillCatalog(
        _catalog().skills
        + (
            _skill(
                "records/skills/playerclass01/fightingform.dbr",
                "Fighting Form",
                "playerclass01",
                "Soldier",
                skill_tier=4,
                tree_order=4,
                parent_skill_id=cadence_id,
            ),
            _skill(
                "records/skills/playerclass01/forcewave.dbr",
                "Forcewave",
                "playerclass01",
                "Soldier",
                skill_tier=1,
                tree_order=11,
            ),
            _skill(
                "records/skills/playerclass01/militaryconditioning.dbr",
                "Military Conditioning",
                "playerclass01",
                "Soldier",
                skill_tier=2,
                tree_order=6,
            ),
            _skill(
                "records/skills/playerclass01/tremor.dbr",
                "Tremor",
                "playerclass01",
                "Soldier",
                skill_tier=2,
                tree_order=12,
                max_level=1,
            ),
        )
    )

    soldier = build_mastery_skills(catalog)[0]

    assert [skill.display_name for skill in soldier.skills] == [
        "Cadence",
        "Fighting Form",
        "Forcewave",
        "Military Conditioning",
    ]

    _application()
    editor = SkillsEditor(
        BuildProfile(masteries=("playerclass01", "")), catalog
    )
    assert [
        editor.panels[0].available_list.item(index).text()
        for index in range(editor.panels[0].available_list.count())
    ] == ["Cadence", "└ Fighting Form", "Forcewave", "Military Conditioning"]


def test_skills_editor_adds_weights_and_excludes_duplicate_mastery() -> None:
    _application()
    profile = BuildProfile()
    editor = SkillsEditor(profile, _catalog())
    editor.show()

    editor.all_skills_row.weight_control.set_value(3)
    assert profile.weight_for("all_skills_bonus") == 3

    soldier_index = editor.panels[0].mastery_combo.findData("playerclass01")
    editor.panels[0].mastery_combo.setCurrentIndex(soldier_index)

    assert profile.masteries == ("playerclass01", "")
    assert editor.panels[1].mastery_combo.findData("playerclass01") == -1
    item = editor.panels[0].available_list.item(0)
    assert item.text() == "Cadence"
    editor.panels[0].available_list.setCurrentItem(item)
    editor.panels[0].add_button.click()

    skill_id = "records/skills/playerclass01/cadence1.dbr"
    assert profile.skill_weights == {skill_id: 0}
    assert editor.panels[0].available_list.count() == 1
    disabled_item = editor.panels[0].available_list.item(0)
    assert disabled_item.text() == "Cadence"
    assert not disabled_item.flags() & Qt.ItemFlag.ItemIsEnabled
    assert not disabled_item.flags() & Qt.ItemFlag.ItemIsSelectable
    editor.panels[0].rows[skill_id].weight_control.set_value(4)
    assert profile.skill_weights == {skill_id: 4}


def test_mastery_change_only_clears_skills_from_changed_mastery() -> None:
    _application()
    soldier_skill_id = "records/skills/playerclass01/cadence1.dbr"
    demolitionist_skill_id = "records/skills/playerclass02/flamestrike1.dbr"
    profile = BuildProfile(
        masteries=("playerclass01", "playerclass02"),
        skill_weights={soldier_skill_id: 3, demolitionist_skill_id: 4},
    )
    editor = SkillsEditor(profile, _catalog())
    editor.show()

    editor._confirm_mastery_change = lambda: False
    occultist_index = editor.panels[0].mastery_combo.findData("playerclass03")
    editor.panels[0].mastery_combo.setCurrentIndex(occultist_index)
    assert profile.masteries == ("playerclass01", "playerclass02")
    assert profile.skill_weights == {
        soldier_skill_id: 3,
        demolitionist_skill_id: 4,
    }

    editor._confirm_mastery_change = lambda: True
    occultist_index = editor.panels[0].mastery_combo.findData("playerclass03")
    editor.panels[0].mastery_combo.setCurrentIndex(occultist_index)
    assert profile.masteries == ("playerclass03", "playerclass02")
    assert profile.skill_weights == {demolitionist_skill_id: 4}


def test_changing_mastery_without_its_own_skills_needs_no_confirmation() -> None:
    _application()
    profile = BuildProfile(
        masteries=("playerclass01", "playerclass02"),
        skill_weights={
            "records/skills/playerclass02/flamestrike1.dbr": 4,
        },
    )
    editor = SkillsEditor(profile, _catalog())

    def unexpected_confirmation() -> bool:
        raise AssertionError("confirmation should not be displayed")

    editor._confirm_mastery_change = unexpected_confirmation

    occultist_index = editor.panels[0].mastery_combo.findData("playerclass03")
    editor.panels[0].mastery_combo.setCurrentIndex(occultist_index)

    assert profile.masteries == ("playerclass03", "playerclass02")
    assert profile.skill_weights == {
        "records/skills/playerclass02/flamestrike1.dbr": 4,
    }


def test_double_click_adds_available_skill() -> None:
    _application()
    profile = BuildProfile(masteries=("playerclass02", ""))
    editor = SkillsEditor(profile, _catalog())
    item = editor.panels[0].available_list.item(0)

    editor.panels[0].available_list.itemDoubleClicked.emit(item)

    assert profile.skill_weights == {
        "records/skills/playerclass02/flamestrike1.dbr": 0
    }
