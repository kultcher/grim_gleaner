import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
    SkillCatalog,
    SkillDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.main_window import MainWindow


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _affix(affix_id: str, name: str, stat_id: str) -> AffixDefinition:
    return AffixDefinition(
        affix_id=affix_id,
        localization_tag=f"tag{name}",
        display_name=name,
        kind="prefix",
        variants=(
            AffixVariantDefinition(
                gear_slot="Ring",
                level_requirements=(5,),
                properties=(AffixProperty(stat_id, stat_id, {}),),
                stat_lines=(f"+[x] {name} stat",),
                representative_source=f"base:{affix_id}.dbr",
                source_record_count=1,
                stat_layout_count=1,
            ),
        ),
    )


def test_top_matches_tracks_active_editor_profile() -> None:
    _application()
    profile = BuildProfile("Testing", {"health": 4})
    catalog = AffixCatalog(
        (
            _affix("prefix:swift", "Swift", "movement_speed"),
            _affix("prefix:tough", "Tough", "health"),
        )
    )
    window = MainWindow(profile, catalog=catalog)
    window.show()

    page = window.top_matches_page
    assert page.table.rowCount() == 2
    assert page.table.item(0, 1).text() == "Tough"
    assert page.table.item(0, 0).text() == "[B1]"
    assert "All affix stats" in page.details.toPlainText()

    window.profile_editor.accordions["core_health"].rows[
        "health"
    ].weight_control.set_value(0)
    window.profile_editor.accordions["core_speed"].rows[
        "movement_speed"
    ].weight_control.set_value(4)

    assert page.table.item(0, 1).text() == "Swift"
    assert "Movement Speed" in page.table.item(0, 4).text()


def test_top_matches_prompts_for_a_weighted_profile() -> None:
    _application()
    window = MainWindow(BuildProfile(), catalog=AffixCatalog(()))

    assert window.top_matches_page.table.rowCount() == 0
    assert "Set at least one" in window.top_matches_page.status.text()


def test_top_matches_uses_selected_skill_weight_and_display_name() -> None:
    _application()
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    profile = BuildProfile(skill_weights={skill_id: 4})
    affix = AffixDefinition(
        affix_id="prefix:cadence",
        localization_tag="tagCadence",
        display_name="Veteran's",
        kind="prefix",
        variants=(
            AffixVariantDefinition(
                gear_slot="Head",
                level_requirements=(20,),
                properties=(
                    AffixProperty(
                        "skill_bonus",
                        "skill_bonus:1",
                        {"skill_reference": skill_id},
                    ),
                ),
                stat_lines=("+[x] to Cadence",),
                representative_source="base:records/items/example.dbr",
                source_record_count=1,
                stat_layout_count=1,
            ),
        ),
    )
    skills = SkillCatalog(
        (
            SkillDefinition(
                skill_id=skill_id,
                source="base",
                category="player",
                name_tag="tagSkillNameCadence",
                display_name="Cadence",
                name_resolution="localized",
                description_tag="",
                mastery_id="playerclass01",
                mastery_name="Soldier",
                mastery_level_required=1,
                max_level=16,
                is_mastery=False,
            ),
        )
    )

    window = MainWindow(profile, catalog=AffixCatalog((affix,)), skills=skills)

    page = window.top_matches_page
    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "[B1]"
    assert page.table.item(0, 4).text() == "+Ranks to Cadence"
    assert "+Ranks to Cadence: weight 4" in page.details.toPlainText()
