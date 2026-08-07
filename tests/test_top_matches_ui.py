import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
    ItemCatalog,
    ItemDefinition,
    ItemProperty,
    ItemVariantDefinition,
    SkillCatalog,
    SkillDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.slots import (
    SLOT_LABELS,
    SLOT_RING,
    SLOT_WEAPON_1H_CASTER,
    SLOT_WEAPON_1H_MELEE,
    SLOT_WEAPON_1H_RANGED,
    SLOT_WEAPON_2H_MELEE,
    SLOT_WEAPON_2H_RANGED,
)
from gd_affix_relevance.ui.main_window import MainWindow


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _affix(
    affix_id: str,
    name: str,
    stat_id: str,
    *,
    kind: str = "prefix",
    slot_id: str = SLOT_RING,
) -> AffixDefinition:
    return AffixDefinition(
        affix_id=affix_id,
        localization_tag=f"tag{name}",
        display_name=name,
        kind=kind,
        variants=(
            AffixVariantDefinition(
                gear_slot=SLOT_LABELS[slot_id],
                level_requirements=(5,),
                properties=(AffixProperty(stat_id, stat_id, {}),),
                stat_lines=(f"+[x] {name} stat",),
                representative_source=f"base:{affix_id}.dbr",
                source_record_count=1,
                stat_layout_count=1,
                applicable_slots=(slot_id,),
            ),
        ),
    )


def _item(
    name: str,
    *,
    category: str,
    rarity: str,
    source: str,
) -> ItemDefinition:
    return ItemDefinition(
        item_id=f"equipment:{name.casefold()}",
        family="equipment",
        localization_tag=f"tag{name}",
        display_name=name,
        name_resolution="localized",
        description_tag="",
        description="",
        variants=(
            ItemVariantDefinition(
                source="base",
                record_path=f"records/items/gearhead/{name.casefold()}.dbr",
                category=category,
                rarity=rarity,
                item_class="ArmorProtective_Head",
                gear_slot="Head",
                item_level=94,
                level_requirement=84,
                applicable_slots=(),
                set_reference="",
                set_name="",
                granted_skill_reference="",
                granted_skill_name="",
                effect_skill_reference="",
                effect_skill_name="",
                effect_properties=(),
                effect_stat_lines=(),
                completion_bonus_reference="",
                properties=(ItemProperty("health", "health", {}),),
                stat_lines=("+[x] Health",),
                skill_modifiers=(),
                acquisition_source=source,
            ),
        ),
    )


def test_slot_tables_separate_prefixes_and_suffixes_and_track_profile() -> None:
    _application()
    profile = BuildProfile("Testing", {"health": 4})
    catalog = AffixCatalog(
        (
            _affix("prefix:swift", "Swift", "movement_speed"),
            _affix("prefix:tough", "Tough", "health"),
            _affix(
                "suffix:fortitude",
                "of Fortitude",
                "health",
                kind="suffix",
            ),
        )
    )
    window = MainWindow(profile, catalog=catalog)
    window.show()

    page = window.top_matches_page
    prefix_table = page.tables[(SLOT_RING, "prefix")]
    suffix_table = page.tables[(SLOT_RING, "suffix")]
    assert prefix_table.item(0, 1).text() == "Tough"
    assert suffix_table.item(0, 1).text() == "of Fortitude"
    assert prefix_table.item(0, 0).text() == "[B1]"
    assert [
        prefix_table.horizontalHeaderItem(column).text()
        for column in range(prefix_table.columnCount())
    ] == ["Grade", "Affix", "Score", "Coverage"]
    assert "All affix stats" in page.details.toPlainText()

    window.profile_editor.accordions["core_health"].rows[
        "health"
    ].weight_control.set_value(0)
    window.profile_editor.accordions["core_speed"].rows[
        "movement_speed"
    ].weight_control.set_value(4)

    assert prefix_table.item(0, 1).text() == "Swift"
    assert suffix_table.rowCount() == 0
    assert "Movement Speed" in page.details.toPlainText()


def test_slot_tables_prompt_for_a_weighted_profile() -> None:
    _application()
    window = MainWindow(BuildProfile(), catalog=AffixCatalog(()))

    assert all(table.rowCount() == 0 for table in window.top_matches_page.tables.values())
    assert "Set at least one" in window.top_matches_page.status.text()


def test_slot_tables_use_selected_skill_weight_and_display_name() -> None:
    _application()
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    profile = BuildProfile(skill_weights={skill_id: 4})
    property_ = AffixProperty(
        "skill_bonus",
        "skill_bonus:1",
        {"skill_reference": skill_id},
    )
    affix = AffixDefinition(
        affix_id="prefix:cadence",
        localization_tag="tagCadence",
        display_name="Veteran's",
        kind="prefix",
        variants=(
            AffixVariantDefinition(
                gear_slot="Ring",
                level_requirements=(20,),
                properties=(property_,),
                stat_lines=("+[x] to Cadence",),
                representative_source="base:records/items/example.dbr",
                source_record_count=1,
                stat_layout_count=1,
                applicable_slots=(SLOT_RING,),
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

    table = window.top_matches_page.tables[(SLOT_RING, "prefix")]
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "[B1]"
    assert "+Ranks to Cadence: weight 4" in (
        window.top_matches_page.details.toPlainText()
    )


def test_weapon_filters_compose_handedness_and_weapon_style() -> None:
    _application()
    window = MainWindow(
        BuildProfile(weights={"health": 4}),
        catalog=AffixCatalog(()),
    )
    window.show()
    page = window.top_matches_page

    page.slot_filters["one_handed"].setChecked(False)
    assert page.slot_rows[SLOT_WEAPON_1H_MELEE].isHidden()
    assert page.slot_rows[SLOT_WEAPON_1H_CASTER].isHidden()
    assert page.slot_rows[SLOT_WEAPON_1H_RANGED].isHidden()
    assert page.unique_slot_rows[SLOT_WEAPON_1H_MELEE].isHidden()
    assert page.unique_slot_rows[SLOT_WEAPON_1H_CASTER].isHidden()
    assert page.unique_slot_rows[SLOT_WEAPON_1H_RANGED].isHidden()
    assert not page.slot_rows[SLOT_WEAPON_2H_MELEE].isHidden()
    assert not page.slot_rows[SLOT_WEAPON_2H_RANGED].isHidden()

    page.slot_filters["melee"].setChecked(False)
    assert page.slot_rows[SLOT_WEAPON_2H_MELEE].isHidden()
    assert not page.slot_rows[SLOT_WEAPON_2H_RANGED].isHidden()


def test_unique_tables_show_b_or_better_items_and_filter_types() -> None:
    _application()
    items = ItemCatalog(
        (
            _item(
                "Chosen Visage",
                category="monster_infrequent",
                rarity="Rare",
                source="Specific Monster Drop",
            ),
            _item(
                "Crafted Crown",
                category="legendary",
                rarity="Legendary",
                source="Crafted",
            ),
            _item(
                "Epic Crown",
                category="epic",
                rarity="Epic",
                source="Random Drop",
            ),
        ),
        (),
        (),
        (),
        (),
        (),
    )
    window = MainWindow(
        BuildProfile(weights={"health": 4}),
        catalog=AffixCatalog(()),
        items=items,
    )
    page = window.top_matches_page
    table = page.unique_tables["head"]

    assert table.rowCount() == 3
    assert [
        table.horizontalHeaderItem(column).text()
        for column in range(table.columnCount())
    ] == ["Grade", "Item", "Type", "Source", "Score", "Coverage"]
    assert {table.item(row, 2).text() for row in range(3)} == {
        "Monster Infrequent",
        "Epic",
        "Legendary",
    }
    assert "Grades assume the highest-level" in page.status.text()

    page.type_filters["epic"].setChecked(False)

    assert table.rowCount() == 2
    assert "Epic" not in {table.item(row, 2).text() for row in range(2)}
