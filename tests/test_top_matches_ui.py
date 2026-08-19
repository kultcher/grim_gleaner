import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QFrame

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
    ItemCatalog,
    ItemContainerSource,
    ItemDefinition,
    ItemMonsterSource,
    ItemProperty,
    ItemSkillModifier,
    ItemVendorSource,
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
from gd_affix_relevance.ui.top_matches import (
    DETAIL_TITLE_COLORS,
    SKILL_MODIFIER_HIGHLIGHT,
    SKILL_RANK_HIGHLIGHT,
    SKILL_MODIFIER_STAT_COLOR,
    SKILL_RANK_STAT_COLOR,
    STAT_CATEGORY_COLORS,
    _item_source_label,
    _semantic_stat_color,
)


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _affix(
    affix_id: str,
    name: str,
    stat_id: str,
    *,
    kind: str = "prefix",
    slot_id: str = SLOT_RING,
    rarity: str = "Rare",
) -> AffixDefinition:
    return AffixDefinition(
        affix_id=affix_id,
        localization_tag=f"tag{name}",
        display_name=name,
        kind=kind,
        rarity=rarity,
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
    emphasized: bool = True,
    monster_sources: tuple[ItemMonsterSource, ...] = (),
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
                properties=(
                    ItemProperty("health", "health", {}),
                    ItemProperty("offensive_ability", "offensive_ability", {}),
                    *(
                        (ItemProperty("defensive_ability", "defensive_ability", {}),)
                        if emphasized
                        else ()
                    ),
                ),
                stat_lines=(
                    "+[x] Health",
                    "+[x] Offensive Ability",
                    *(("+[x] Defensive Ability",) if emphasized else ()),
                ),
                skill_modifiers=(),
                acquisition_source=source,
                monster_sources=monster_sources,
            ),
        ),
    )


def _addon(
    name: str,
    *,
    family: str,
    acquisition_source: str,
    faction_name: str = "",
    recipe_factions: tuple[ItemVendorSource, ...] = (),
) -> ItemDefinition:
    base = _item(
        name,
        category="component" if family == "components" else "augment",
        rarity="Rare",
        source=acquisition_source,
    )
    variant = replace(
        base.variants[0],
        item_class=("ItemRelic" if family == "components" else "ItemEnchantment"),
        applicable_slots=("Head",),
        faction_source="User7" if faction_name else "",
        faction_name=faction_name,
        vendor_sources=recipe_factions,
    )
    return replace(base, family=family, variants=(variant,))


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
    assert prefix_table.item(0, 0).text() == "[C1]"
    assert [
        prefix_table.horizontalHeaderItem(column).text()
        for column in range(prefix_table.columnCount())
    ] == ["Grade", "Affix", "Score", "Coverage"]
    assert "Matched stats" in page.details.toPlainText()
    assert "Remaining unmatched stats" in page.details.toPlainText()

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


def test_affix_detail_title_uses_compiled_rarity_and_color() -> None:
    app = _application()
    for rarity, color_key in (
        ("Rare", "affix_rare"),
        ("Magical", "affix_magical"),
    ):
        window = MainWindow(
            BuildProfile(weights={"health": 4}),
            catalog=AffixCatalog(
                (_affix("prefix:tough", "Tough", "health", rarity=rarity),)
            ),
        )
        table = window.top_matches_page.tables[(SLOT_RING, "prefix")]
        table.selectRow(0)
        app.processEvents()

        title = window.top_matches_page.affix_detail_pane.title
        assert title.text().endswith(f"Tough · Ring · {rarity} Prefix")
        assert DETAIL_TITLE_COLORS[color_key] in title.styleSheet()


def test_affix_detail_displays_granted_skill_as_unevaluated() -> None:
    app = _application()
    affix = _affix("prefix:storm", "Stormcharged", "lightning_damage_percent")
    variant = replace(
        affix.variants[0],
        properties=(
            *affix.variants[0].properties,
            AffixProperty(
                "granted_item_skill",
                "granted_item_skill",
                {
                    "display_name": "Lightning Bolt",
                    "skill_reference": (
                        "records/skills/itemskills/item_lightningbolt_01.dbr"
                    ),
                },
            ),
        ),
    )
    affix = replace(affix, variants=(variant,))
    window = MainWindow(
        BuildProfile(weights={"lightning_damage_percent": 4}),
        catalog=AffixCatalog((affix,)),
    )
    table = window.top_matches_page.tables[(SLOT_RING, "prefix")]
    table.selectRow(0)
    app.processEvents()

    details = window.top_matches_page.details.toPlainText()
    assert table.item(0, 0).text().endswith("*]")
    assert "Granted skill (not evaluated):\n- Lightning Bolt" in details
    unmatched = details.split("Remaining unmatched stats:\n", 1)[1].split(
        "\n\n", 1
    )[0]
    assert "Lightning Bolt" not in unmatched


def test_slot_tables_use_selected_skill_weight_and_display_name() -> None:
    _application()
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    profile = BuildProfile(skill_weights={skill_id: 4})
    property_ = AffixProperty(
        "skill_bonus",
        "skill_bonus:1",
        {"skill_reference": skill_id, "skill_level": "2"},
    )
    affix = AffixDefinition(
        affix_id="prefix:cadence",
        localization_tag="tagCadence",
        display_name="Veteran's",
        kind="prefix",
        rarity="Rare",
        variants=(
            AffixVariantDefinition(
                gear_slot="Ring",
                level_requirements=(20,),
                properties=(property_,),
                stat_lines=("+2 to Cadence",),
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
    assert table.item(0, 0).text() == "[C1]"
    assert "+2 to Cadence: weight 4" in (
        window.top_matches_page.details.toPlainText()
    )
    assert window.top_matches_page._label_for(
        "mastery_bonus:playerclass01"
    ) == "+Ranks to all skills in Soldier"


def test_detail_labels_use_resolved_property_names_for_skill_wrappers() -> None:
    _application()
    squall_reference = "records/skills/playerclass06/squall2.dbr"
    granted_reference = (
        "records/skills/itemskills/item_lightningorbnova.dbr"
    )
    properties = (
        AffixProperty(
            "skill_bonus",
            "skill_bonus:1",
            {
                "display_name": "Raging Tempest",
                "skill_level": "2",
                "skill_reference": squall_reference,
            },
        ),
        AffixProperty(
            "granted_item_skill",
            "granted_item_skill",
            {
                "display_name": "Lightning Barrage",
                "skill_reference": granted_reference,
            },
        ),
    )
    page = MainWindow(
        BuildProfile(), catalog=AffixCatalog(()), skills=SkillCatalog(())
    ).top_matches_page

    assert page._label_for(
        f"skill_bonus:{squall_reference}", properties
    ) == "+2 to Raging Tempest"
    assert page._label_for(
        f"granted_item_skill:{granted_reference}", properties
    ) == "Granted Skill: Lightning Barrage"
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

    page.slot_filters["two_handed"].setChecked(False)
    assert all(not warning.isHidden() for warning in page.weapon_filter_warnings)
    assert all(
        not heading.isHidden()
        for heading, slots in (
            page.category_widgets[0],
            page.unique_category_widgets[0],
        )
        if slots
    )
    assert page.weapon_filter_warnings[0].text() == (
        "1H or 2H, and at least one weapon type must be selected to view weapons."
    )
    assert page.slot_filter_divider.frameShape() == QFrame.Shape.VLine

    page.slot_filters["one_handed"].setChecked(True)
    page.slot_filters["caster"].setChecked(False)
    page.slot_filters["ranged"].setChecked(False)
    assert all(not warning.isHidden() for warning in page.weapon_filter_warnings)

    page.slot_filters["melee"].setChecked(True)
    assert all(warning.isHidden() for warning in page.weapon_filter_warnings)


def test_unique_tables_show_b_or_better_items_and_filter_types() -> None:
    app = _application()
    items = ItemCatalog(
        (
            _item(
                "Chosen Visage",
                category="monster_infrequent",
                rarity="Rare",
                source="Specific Monster Drop",
                monster_sources=(
                    ItemMonsterSource(
                        "Fleshwarped Commander",
                        "tagFleshwarpedCommander",
                        "Champion",
                    ),
                    ItemMonsterSource(
                        "Fleshwarped Overseer",
                        "tagFleshwarpedOverseer",
                        "Hero",
                    ),
                ),
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
            _item(
                "Useful Crown",
                category="epic",
                rarity="Epic",
                source="Random Drop",
                emphasized=False,
            ),
        ),
        (),
        (),
        (),
        (),
        (),
    )
    window = MainWindow(
        BuildProfile(
            weights={
                "health": 4,
                "offensive_ability": 4,
                "defensive_ability": 4,
            }
        ),
        catalog=AffixCatalog(()),
        items=items,
    )
    page = window.top_matches_page
    table = page.unique_tables["head"]

    assert page.minimum_grade.currentText() == "A"
    assert [
        page.minimum_grade.itemText(index)
        for index in range(page.minimum_grade.count())
    ] == ["S++", "S+", "S", "A", "B"]
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
    chosen_row = next(
        row
        for row in range(table.rowCount())
        if table.item(row, 1).text() == "Chosen Visage"
    )
    assert table.item(chosen_row, 3).text() == (
        "Fleshwarped Commander +1 other"
    )
    assert _item_source_label(table.matches[chosen_row].variant) == (
        "Fleshwarped Commander +1 other"
    )
    assert _item_source_label(
        replace(
            table.matches[chosen_row].variant,
            acquisition_source="Purchased",
        )
    ) == "Purchased"
    assert _item_source_label(
        replace(
            table.matches[chosen_row].variant,
            acquisition_source="Lootable Container",
            monster_sources=(),
            container_sources=(
                ItemContainerSource("Rotting Corpse", "tagChestCorpseA01"),
            ),
        )
    ) == "Lootable Container: Rotting Corpse"
    table.selectRow(chosen_row)
    app.processEvents()
    unique_details = page.unique_details.toPlainText()
    assert "Source: Fleshwarped Commander +1 other" in unique_details
    assert "Drops from 2 enemies:" in unique_details
    assert "- Fleshwarped Commander" in unique_details
    assert "- Fleshwarped Overseer" in unique_details
    for row, match in enumerate(table.matches):
        table.selectRow(row)
        app.processEvents()
        assert DETAIL_TITLE_COLORS[match.item_type] in (
            page.unique_detail_pane.title.styleSheet()
        )
    assert "highest variant eligible for level band 90+" in page.status.text()

    page.minimum_grade.setCurrentText("B")
    assert table.rowCount() == 4

    page.type_filters["epic"].setChecked(False)

    assert table.rowCount() == 2
    assert "Epic" not in {table.item(row, 2).text() for row in range(2)}


def test_addon_tables_rank_components_and_augments_per_slot() -> None:
    app = _application()
    component = _addon(
        "Living Armor",
        family="components",
        acquisition_source="Faction Vendor Blueprint",
        recipe_factions=(
            ItemVendorSource("User2", "Homestead", "Respected"),
        ),
    )
    augment = _addon(
        "Mankind's Vigil",
        family="augments",
        acquisition_source="Purchased",
        faction_name="The Black Legion",
    )
    items = ItemCatalog((), (component,), (augment,), (), (), ())
    window = MainWindow(
        BuildProfile(weights={"health": 4, "offensive_ability": 4}),
        catalog=AffixCatalog(()),
        items=items,
    )
    window.show()
    page = window.top_matches_page

    assert page.tabs.count() == 3
    assert page.tabs.tabText(2) == "Add-ons"
    component_table = page.addon_tables[("head", "component")]
    augment_table = page.addon_tables[("head", "augment")]
    assert component_table.item(0, 1).text() == "Living Armor"
    assert component_table.item(0, 2).text() == "Homestead"
    assert augment_table.item(0, 1).text() == "Mankind's Vigil"
    assert augment_table.item(0, 2).text() == "The Black Legion"
    assert [
        component_table.horizontalHeaderItem(column).text()
        for column in range(component_table.columnCount())
    ] == ["Grade", "Component", "Faction / Source", "Score", "Coverage"]
    assert [
        augment_table.horizontalHeaderItem(column).text()
        for column in range(augment_table.columnCount())
    ] == ["Grade", "Augment", "Faction", "Score", "Coverage"]

    augment_table.selectRow(0)
    app.processEvents()
    assert "Faction: The Black Legion" in page.addon_details.toPlainText()
    assert "Source: Purchased" in page.addon_details.toPlainText()
    assert "Matched stats" in page.addon_details.toPlainText()

    component_table.selectRow(0)
    app.processEvents()
    assert "Recipe sold by: Homestead (Respected)" in (
        page.addon_details.toPlainText()
    )


def test_resistance_cap_mode_overrides_only_addon_resistance_weights() -> None:
    app = _application()
    component_base = _addon(
        "Fire Ward",
        family="components",
        acquisition_source="Crafted",
    )
    component = replace(
        component_base,
        variants=(
            replace(
                component_base.variants[0],
                properties=(
                    ItemProperty(
                        "fire_resistance", "fire_resistance", {}
                    ),
                ),
                stat_lines=("+[x]% Fire Resistance",),
            ),
        ),
    )
    affix = _affix(
        "prefix:fireward",
        "Fireward",
        "fire_resistance",
        slot_id=SLOT_RING,
    )
    unique_base = _item(
        "Fire Crown",
        category="epic",
        rarity="Epic",
        source="Random Drop",
        emphasized=False,
    )
    unique = replace(
        unique_base,
        variants=(
            replace(
                unique_base.variants[0],
                properties=(
                    ItemProperty(
                        "fire_resistance", "fire_resistance", {}
                    ),
                    ItemProperty("health", "health", {}),
                ),
                stat_lines=("+[x]% Fire Resistance", "+[x] Health"),
            ),
        ),
    )
    profile = BuildProfile(weights={"fire_resistance": 4, "health": 4})
    window = MainWindow(
        profile,
        catalog=AffixCatalog((affix,)),
        items=ItemCatalog((unique,), (component,), (), (), (), ()),
    )
    window.show()
    page = window.top_matches_page
    component_table = page.addon_tables[("head", "component")]
    affix_table = page.tables[(SLOT_RING, "prefix")]
    page.minimum_grade.setCurrentText("B")
    unique_table = page.unique_tables["head"]

    assert page.resistance_cap_body.isHidden()
    assert not page.resistance_cap_toggle.isChecked()
    assert not page.resistance_cap_rows_widget.isEnabled()
    assert (
        page.resistance_cap_rows["fire_resistance"].weight_control.value
        == 4
    )
    assert component_table.rowCount() == 1
    assert affix_table.rowCount() == 1
    assert unique_table.rowCount() == 1

    page.resistance_cap_button.click()
    assert not page.resistance_cap_body.isHidden()
    page.resistance_cap_toggle.setChecked(True)
    assert page.resistance_cap_button.property("active") is True
    assert page.resistance_cap_button.text().endswith("(On)")
    assert page.resistance_cap_rows_widget.isEnabled()
    assert component_table.rowCount() == 1
    assert component_table.matches[0].score.effective_score == 15.2
    assert affix_table.rowCount() == 1
    assert unique_table.rowCount() == 1
    assert profile.weight_for("fire_resistance") == 4
    assert profile.resistance_cap_enabled
    assert profile.resistance_cap_weights == {}
    assert window.profile_editor.is_dirty

    fire_control = page.resistance_cap_rows[
        "fire_resistance"
    ].weight_control
    fire_control.set_value(2)
    assert profile.resistance_cap_weights == {"fire_resistance": 2}
    assert component_table.rowCount() == 1
    assert component_table.matches[0].score.effective_score == 3.8
    assert affix_table.matches[0].score.effective_score == 3.8
    assert unique_table.matches[0].score.effective_score == 7.6

    fire_control.set_value(4)
    component_table.selectRow(0)
    app.processEvents()
    assert component_table.matches[0].score.effective_score == 15.2
    assert component_table.item(0, 0).text().startswith("[S")
    assert "cap weight 4 (amplified to 8)" in (
        page.addon_details.toPlainText()
    )
    assert "Resistance Cap Mode is enabled" in page.status.text()

    page.tabs.setCurrentIndex(2)
    app.processEvents()
    scrollbar = page.addon_scroll.verticalScrollBar()
    scrollbar.setValue(0)
    wheel = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(page.resistance_cap_hint, wheel)
    assert scrollbar.value() > 0

    page.resistance_cap_toggle.setChecked(False)
    assert page.resistance_cap_button.property("active") is False
    assert not profile.resistance_cap_enabled
    assert component_table.matches[0].score.effective_score == 3.8
    assert affix_table.matches[0].score.effective_score == 3.8
    assert unique_table.matches[0].score.effective_score == 7.6


def test_skill_rank_and_modifier_rows_use_distinct_precedence_highlights() -> None:
    app = _application()
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    selected_skill_id = "records/skills/playerclass01/cadence1_buff.dbr"
    skill_property = AffixProperty(
        "skill_bonus",
        "skill_bonus:1",
        {"skill_reference": skill_id},
    )
    affix = AffixDefinition(
        affix_id="prefix:cadence-health",
        localization_tag="tagCadenceHealth",
        display_name="Veteran's",
        kind="prefix",
        rarity="Rare",
        variants=(
            AffixVariantDefinition(
                gear_slot="Ring",
                level_requirements=(84,),
                properties=(
                    AffixProperty("health", "health", {}),
                    skill_property,
                    AffixProperty("movement_speed", "movement_speed", {}),
                ),
                stat_lines=(),
                representative_source="base:test.dbr",
                source_record_count=1,
                stat_layout_count=1,
                applicable_slots=(SLOT_RING,),
            ),
        ),
    )

    rank_base = _item(
        "Rank Crown",
        category="epic",
        rarity="Epic",
        source="Random Drop",
    )
    rank_variant = replace(
        rank_base.variants[0],
        properties=(
            ItemProperty("health", "health", {}),
            ItemProperty(
                "skill_bonus",
                "skill_bonus:1",
                {"skill_reference": skill_id},
            ),
            ItemProperty("fire_resistance", "fire_resistance", {}),
        ),
    )
    rank_item = replace(rank_base, variants=(rank_variant,))
    modifier_base = _item(
        "Modifier Crown",
        category="legendary",
        rarity="Legendary",
        source="Random Drop",
    )
    modifier_variant = replace(
        modifier_base.variants[0],
        properties=rank_variant.properties,
        skill_modifiers=(
            ItemSkillModifier(
                skill_id,
                "Cadence",
                "records/skills/modifiers/cadence.dbr",
                (),
                ("+[x]% Weapon Damage",),
            ),
        ),
    )
    modifier_item = replace(modifier_base, variants=(modifier_variant,))
    profile = BuildProfile(
        weights={"health": 4},
        skill_weights={selected_skill_id: 4},
    )
    window = MainWindow(
        profile,
        catalog=AffixCatalog((affix,)),
        items=ItemCatalog((rank_item, modifier_item), (), (), (), (), ()),
    )
    window.show()
    window.top_matches_page.minimum_grade.setCurrentText("B")

    affix_table = window.top_matches_page.tables[(SLOT_RING, "prefix")]
    assert affix_table.item(0, 0).background().color().name() == (
        SKILL_RANK_HIGHLIGHT.name()
    )
    affix_table.selectRow(0)
    app.processEvents()
    affix_details = window.top_matches_page.details.toPlainText()
    affix_match = affix_table.matches[0]
    assert window.top_matches_page.affix_detail_pane.title.text() == (
        f"{affix_match.marker}Veteran's · Ring · Rare Prefix"
    )
    assert DETAIL_TITLE_COLORS["affix_rare"] in (
        window.top_matches_page.affix_detail_pane.title.styleSheet()
    )
    assert "Veteran's" not in affix_details
    assert "Remaining unmatched stats:\n- Movement Speed" in affix_details
    unmatched_section = affix_details.split("Remaining unmatched stats:\n", 1)[
        1
    ].split("\n\n", 1)[0]
    assert "Health" not in unmatched_section

    unique_table = window.top_matches_page.unique_tables["head"]
    rows = {
        unique_table.item(row, 1).text(): row
        for row in range(unique_table.rowCount())
    }
    assert unique_table.item(
        rows["Rank Crown"], 0
    ).background().color().name() == SKILL_RANK_HIGHLIGHT.name()
    assert unique_table.item(
        rows["Modifier Crown"], 0
    ).background().color().name() == SKILL_MODIFIER_HIGHLIGHT.name()

    unique_table.selectRow(rows["Modifier Crown"])
    app.processEvents()
    details = window.top_matches_page.unique_details.toPlainText()
    modifier_match = unique_table.matches[rows["Modifier Crown"]]
    assert window.top_matches_page.unique_detail_pane.title.text() == (
        f"{modifier_match.marker}Modifier Crown · Helm · Legendary"
    )
    assert DETAIL_TITLE_COLORS["legendary"] in (
        window.top_matches_page.unique_detail_pane.title.styleSheet()
    )
    assert details.startswith("Effective score:")
    assert "Matched stats:" in details
    assert "Remaining unmatched stats:" in details
    assert "Fire Resistance" in details
    assert "Skill modifiers:" in details
    assert "+[x]% Weapon Damage" in details
    detail_html = window.top_matches_page.unique_details.toHtml().lower()
    assert SKILL_RANK_STAT_COLOR in detail_html
    assert SKILL_MODIFIER_STAT_COLOR in detail_html


def test_detail_stat_colors_follow_semantic_families() -> None:
    expectations = {
        "elemental_resistance": "elemental",
        "flat_burn_damage": "fire",
        "poison_acid_resistance": "acid",
        "aether_damage_percent": "aether",
        "flat_bleeding_damage": "bleeding",
        "pierce_resistance": "pierce",
        "base_weapon_damage_as_chaos": "chaos",
        "frostburn_damage_percent": "cold",
        "flat_electrocute_damage": "lightning",
        "internal_trauma_damage_percent": "physical",
        "vitality_decay_damage_percent": "vitality",
        "physique_percent": "attribute",
        "offensive_ability": "ability",
        "health_regeneration": "health",
        "energy_regeneration_percent": "energy",
    }
    for stat_id, family in expectations.items():
        assert _semantic_stat_color(stat_id, matched=False) == (
            STAT_CATEGORY_COLORS[family]
        )

    assert _semantic_stat_color(
        "skill_bonus:records/skills/example.dbr", matched=False
    ) == SKILL_RANK_STAT_COLOR
