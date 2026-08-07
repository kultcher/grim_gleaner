from dataclasses import replace

from gd_affix_relevance.catalog import (
    ItemCatalog,
    ItemDefinition,
    ItemProperty,
    ItemSkillModifier,
    ItemVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.scoring import rank_unique_items_for_slot
from gd_affix_relevance.slots import SLOT_HEAD


def _variant(**changes: object) -> ItemVariantDefinition:
    base = ItemVariantDefinition(
        source="base",
        record_path="records/items/gearhead/b001_head.dbr",
        category="monster_infrequent",
        rarity="Rare",
        item_class="ArmorProtective_Head",
        gear_slot="Head",
        item_level=20,
        level_requirement=15,
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
        acquisition_source="Specific Monster Drop",
    )
    return replace(base, **changes)


def _item(name: str, *variants: ItemVariantDefinition) -> ItemDefinition:
    return ItemDefinition(
        item_id=f"equipment:{name.casefold()}",
        family="equipment",
        localization_tag=f"tag{name}",
        display_name=name,
        name_resolution="localized",
        description_tag="",
        description="",
        variants=variants,
    )


def test_unique_ranking_uses_highest_variant_and_flags_selected_skill_modifier() -> None:
    skill_id = "records/skills/playerclass01/cadence1.dbr"
    low = _variant(
        properties=(ItemProperty("fire_resistance", "fire_resistance", {}),),
        stat_lines=("+[x]% Fire Resistance",),
    )
    high = _variant(
        record_path="records/items/gearhead/b001b_head.dbr",
        item_level=94,
        level_requirement=84,
        skill_modifiers=(
            ItemSkillModifier(skill_id, "Cadence", "modifier.dbr", (), ()),
        ),
    )
    catalog = ItemCatalog((_item("Chosen Helm", low, high),), (), (), (), (), ())
    profile = BuildProfile(
        "Soldier",
        weights={"health": 4},
        skill_weights={skill_id: 0},
    )

    matches = rank_unique_items_for_slot(catalog, profile, slot_id=SLOT_HEAD)

    assert len(matches) == 1
    assert matches[0].variant.level_requirement == 84
    assert matches[0].item_type == "monster_infrequent"
    assert matches[0].variant.acquisition_source == "Specific Monster Drop"
    assert matches[0].has_selected_skill_modifier
    assert matches[0].marker == "[B†1]"


def test_unique_ranking_filters_types_and_excludes_items_below_b_grade() -> None:
    epic = _item(
        "Epic Helm",
        _variant(category="epic", rarity="Epic", acquisition_source="Random Drop"),
    )
    legendary = _item(
        "Legendary Helm",
        _variant(
            category="legendary",
            rarity="Legendary",
            acquisition_source="Crafted",
        ),
    )
    catalog = ItemCatalog((epic, legendary), (), (), (), (), ())

    assert rank_unique_items_for_slot(
        catalog,
        BuildProfile(weights={"health": 4}),
        slot_id=SLOT_HEAD,
        enabled_types=frozenset({"legendary"}),
    )[0].item.display_name == "Legendary Helm"
    assert not rank_unique_items_for_slot(
        catalog,
        BuildProfile(weights={"health": 4}),
        slot_id=SLOT_HEAD,
        enabled_types=frozenset({"legendary"}),
        minimum_grade="A",
    )
    assert not rank_unique_items_for_slot(
        catalog,
        BuildProfile(weights={"health": 3}),
        slot_id=SLOT_HEAD,
    )


def test_selected_mastery_bonus_is_treated_as_core_weight() -> None:
    variant = _variant(
        category="epic",
        rarity="Epic",
        properties=(
            ItemProperty(
                "mastery_bonus",
                "mastery_bonus:1",
                {"mastery_reference": "records/skills/playerclass01/_classtraining.dbr"},
            ),
        ),
    )
    catalog = ItemCatalog((_item("Soldier Helm", variant),), (), (), (), (), ())

    matches = rank_unique_items_for_slot(
        catalog,
        BuildProfile(masteries=("playerclass01", "playerclass02")),
        slot_id=SLOT_HEAD,
    )

    assert matches[0].score.weighted_match == 4
