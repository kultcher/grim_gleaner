import json
from pathlib import Path

from gd_affix_relevance.catalog import CatalogBundle, compile_catalog_bundle
from gd_affix_relevance.catalog.item_compiler import (
    _acquisition_source,
    _discover_component_blueprint_distribution,
)
from gd_affix_relevance.importers.localization_parser import parse_localization_text
from gd_affix_relevance.records import RecordRepository
from gd_affix_relevance.slots import SLOT_RING


def _write_dbr(path: Path, fields: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key},{value},\n" for key, value in fields),
        encoding="utf-8",
    )


def test_component_recipe_sources_follow_blueprint_distribution(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "game_data"
    blueprint_root = (
        data_root / "base/records/items/crafting/blueprints/component"
    )
    for recipe in ("default", "random", "vendor"):
        _write_dbr(
            blueprint_root / f"craft_{recipe}.dbr",
            [("artifactName", f"records/items/materia/comp_{recipe}.dbr")],
        )
    table_root = data_root / "base/records/items/loottables/blueprints"
    _write_dbr(
        table_root / "tdyn_random.dbr",
        [
            (
                "lootName1",
                "records/items/crafting/blueprints/component/craft_random.dbr",
            )
        ],
    )
    _write_dbr(
        table_root / "tdyn_specialvendor.dbr",
        [
            (
                "lootName1",
                "records/items/crafting/blueprints/component/craft_vendor.dbr",
            )
        ],
    )

    random_paths, vendor_paths = _discover_component_blueprint_distribution(
        RecordRepository(data_root, ("base",))
    )

    assert random_paths == frozenset(
        {"records/items/materia/comp_random.dbr"}
    )
    assert vendor_paths == frozenset(
        {"records/items/materia/comp_vendor.dbr"}
    )
    crafted = frozenset(
        {
            "records/items/materia/comp_default.dbr",
            "records/items/materia/comp_random.dbr",
            "records/items/materia/comp_vendor.dbr",
        }
    )
    assert _acquisition_source(
        "records/items/materia/comp_default.dbr", "component", crafted
    ) == "Default Recipe"
    assert _acquisition_source(
        "records/items/materia/comp_random.dbr",
        "component",
        crafted,
        random_component_blueprint=True,
    ) == "Random Blueprint"
    assert _acquisition_source(
        "records/items/materia/comp_vendor.dbr",
        "component",
        crafted,
        special_vendor_component_blueprint=True,
    ) == "Special Vendor Blueprint"


def test_compiler_overlays_skills_and_includes_unreferenced_named_skills(
    tmp_path: Path,
) -> None:
    base = tmp_path / "game_data" / "base"
    expansion = tmp_path / "game_data" / "gdx1"
    skill_path = Path("records/skills/playerclass01/testskill.dbr")
    _write_dbr(
        base / "records/skills/playerclass01/_classtraining_class01.dbr",
        [("skillDisplayName", "tagSoldier")],
    )
    _write_dbr(
        base / skill_path,
        [("skillDisplayName", "tagBaseSkillName")],
    )
    _write_dbr(
        expansion / skill_path,
        [
            ("skillDisplayName", "TagExpansionSkillName"),
            ("skillBaseDescription", "tagExpansionSkillDescription"),
            ("skillTier", "5"),
        ],
    )
    _write_dbr(
        base / "records/skills/playerclass01/_classtree_class01.dbr",
        [
            (
                "skillName1",
                "records/skills/playerclass01/_classtraining_class01.dbr",
            ),
            ("skillName2", skill_path.as_posix()),
        ],
    )
    _write_dbr(
        base / "records/skills/itemskills/unreferenced_skill.dbr",
        [("skillDisplayName", "tagUnreferencedSkillName")],
    )
    _write_dbr(
        base / "records/skills/itemskills/unnamed_controller.dbr",
        [("Class", "Skill_SecondarySkill")],
    )
    _write_dbr(
        base / "records/skills/nonplayerskills/named_monster_skill.dbr",
        [("skillDisplayName", "tagMonsterSkillName")],
    )
    _write_dbr(
        base / "records/skills/devotion/named_devotion_skill.dbr",
        [("skillDisplayName", "tagDevotionSkillName")],
    )
    _write_dbr(
        base / "records/skills/base_template skills/named_template.dbr",
        [("skillDisplayName", "tagTemplateSkillName")],
    )
    _write_dbr(
        base / "records/skills/playerclass06/squall2.dbr",
        [
            (
                "buffSkillName",
                "records/skills/playerclass06/pets/raging_tempest.dbr",
            )
        ],
    )
    _write_dbr(
        base / "records/skills/playerclass06/pets/raging_tempest.dbr",
        [("skillDisplayName", "tagRagingTempest")],
    )
    pet_bonus_path = "records/skills/itemskills/pets/test_pet_bonus.dbr"
    _write_dbr(
        base / pet_bonus_path,
        [
            ("offensiveTotalDamageModifier", "15"),
            ("characterLifeModifier", "10"),
            ("characterOffensiveAbilityModifier", "8"),
        ],
    )

    affix_root = base / "records/items/lootaffixes/prefix"
    affix_path = affix_root / "test_acid.dbr"
    table_path = affix_root / "prefixtables/prefix_ring.dbr"
    loot_path = base / "records/items/loottables/gearaccessories/lt_ring.dbr"
    _write_dbr(
        affix_path,
        [
            ("Class", "LootRandomizer"),
            ("itemClassification", "Magical"),
            ("lootRandomizerName", "tagTestAcid"),
            ("levelRequirement", "5"),
            ("offensivePoisonModifier", "25.000000"),
            ("offensiveFireMin", "3.000000"),
            ("offensiveFireMax", "5.000000"),
            ("offensiveFireChance", "10.000000"),
            ("petBonusName", pet_bonus_path),
            ("augmentSkillLevel1", "2"),
            ("augmentSkillName1", "records/skills/playerclass06/squall2.dbr"),
        ],
    )
    _write_dbr(
        table_path,
        [("randomizerName1", "records/items/lootaffixes/prefix/test_acid.dbr")],
    )
    _write_dbr(
        loot_path,
        [
            (
                "prefixTableName1",
                "records/items/lootaffixes/prefix/prefixtables/prefix_ring.dbr",
            )
        ],
    )
    localization = parse_localization_text(
        "\n".join(
            (
                "tagexpansionskillname=Expansion Skill",
                "tagSoldier=Soldier",
                "tagUnreferencedSkillName=Unreferenced Skill",
                "tagTestAcid=Corrosive",
                "tagRagingTempest=Raging Tempest",
                "tagMonsterSkillName=Monster Skill",
                "tagDevotionSkillName=Devotion Skill",
                "tagTemplateSkillName=Template Skill",
            )
        )
    )
    output = tmp_path / "catalog"

    result = compile_catalog_bundle(
        tmp_path / "game_data",
        localization,
        output,
        game_version="test-version",
        source_names=("base", "gdx1"),
    )
    bundle = CatalogBundle.load(output)

    assert result.skill_count == 4
    assert result.unresolved_skill_name_count == 0
    assert result.affix_count == 1
    assert bundle.manifest.game_version == "test-version"
    assert bundle.manifest.affix_scope == "structurally_reachable_magic_and_rare"
    assert bundle.manifest.skill_scope == (
        "named_player_pet_and_item_granted_with_mastery_tree_metadata"
    )
    assert bundle.manifest.item_scope == (
        "named_equipment_components_augments_relics_runes_and_consumables"
    )
    skills = bundle.skills.by_id()
    overlaid = skills[skill_path.as_posix()]
    assert overlaid.source == "gdx1"
    assert overlaid.display_name == "Expansion Skill"
    assert overlaid.name_resolution == "localized"
    assert overlaid.category == "player"
    assert overlaid.mastery_id == "playerclass01"
    assert overlaid.mastery_name == "Soldier"
    assert overlaid.skill_tier == 5
    assert overlaid.tree_order == 2
    training = skills["records/skills/playerclass01/_classtraining_class01.dbr"]
    assert training.is_mastery
    assert "records/skills/itemskills/unreferenced_skill.dbr" in skills
    assert skills[
        "records/skills/itemskills/unreferenced_skill.dbr"
    ].category == "item_granted"
    assert "records/skills/itemskills/unnamed_controller.dbr" not in skills
    assert skills[
        "records/skills/playerclass06/pets/raging_tempest.dbr"
    ].category == "pet"
    assert "records/skills/nonplayerskills/named_monster_skill.dbr" not in skills
    assert "records/skills/devotion/named_devotion_skill.dbr" not in skills
    assert "records/skills/base_template skills/named_template.dbr" not in skills
    assert bundle.affixes.affixes[0].display_name == "Corrosive"
    assert bundle.affixes.affixes[0].rarity == "Magical"
    assert bundle.affixes.affixes[0].variants[0].gear_slot == "Ring"
    assert bundle.affixes.affixes[0].variants[0].applicable_slots == (SLOT_RING,)
    skill_properties = [
        property_
        for property_ in bundle.affixes.affixes[0].variants[0].properties
        if property_.property_id == "skill_bonus"
    ]
    assert skill_properties[0].attributes["display_name"] == "Raging Tempest"
    assert skill_properties[0].attributes["skill_level"] == "2"
    assert "+2 to Raging Tempest" in bundle.affixes.affixes[0].variants[0].stat_lines
    assert (
        "[x]% Chance of [y]-[z] Fire Damage"
        in bundle.affixes.affixes[0].variants[0].stat_lines
    )
    property_ids = {
        property_.property_id
        for property_ in bundle.affixes.affixes[0].variants[0].properties
    }
    assert "pet_bonus" not in property_ids
    assert "chance_flat_fire_damage" in property_ids
    assert {
        "pet_total_damage_percent",
        "pet_health_percent",
        "pet_offensive_ability_percent",
    } <= property_ids


def test_compiler_applies_curated_mastery_relationships(
    tmp_path: Path,
) -> None:
    base = tmp_path / "game_data/base"
    parent_path = "records/skills/playerclass01/parent.dbr"
    child_path = "records/skills/playerclass01/child.dbr"
    child_proxy_path = "records/skills/playerclass01/child_proxy.dbr"
    alternate_path = "records/skills/playerclass01/alternate.dbr"
    _write_dbr(
        base / "records/skills/playerclass01/_classtraining_class01.dbr",
        [("skillDisplayName", "tagSoldier")],
    )
    _write_dbr(
        base / parent_path,
        [("skillDisplayName", "tagParent"), ("skillTier", "1")],
    )
    _write_dbr(
        base / child_path,
        [("skillDisplayName", "tagChild"), ("skillTier", "3")],
    )
    _write_dbr(
        base / alternate_path,
        [("skillDisplayName", "tagAlternate"), ("skillTier", "3")],
    )
    _write_dbr(
        base / child_proxy_path,
        [
            ("petSkillName", child_path),
            ("alternatePetModifierSkillName", alternate_path),
        ],
    )
    _write_dbr(
        base / "records/skills/playerclass01/_classtree_class01.dbr",
        [
            (
                "skillName1",
                "records/skills/playerclass01/_classtraining_class01.dbr",
            ),
            ("skillName2", parent_path),
            ("skillName3", child_proxy_path),
        ],
    )
    tree_root = tmp_path / "mastery-trees"
    tree_root.mkdir()
    (tree_root / "01soldier.md").write_text(
        "# CLASS 01: Soldier\n"
        "## PARENT SKILL: Parent Skill\n"
        "### CHILD 1: Child Skill\n",
        encoding="utf-8",
    )

    output = tmp_path / "catalog"
    compile_catalog_bundle(
        tmp_path / "game_data",
        parse_localization_text(
            "tagSoldier=Soldier\ntagParent=Parent Skill\n"
            "tagChild=Child Skill\ntagAlternate=Alternate Skill\n"
        ),
        output,
        source_names=("base",),
        mastery_tree_root=tree_root,
    )

    skills = CatalogBundle.load(output).skills.by_id()
    assert skills[parent_path].tree_order == 2
    assert skills[parent_path].parent_skill_id == ""
    assert skills[child_path].tree_order == 3
    assert skills[child_path].skill_tier == 3
    assert skills[child_path].parent_skill_id == parent_path
    assert skills[alternate_path].tree_order == 0


def test_compiler_preserves_max_skill_rank_for_collapsed_affix_layout(
    tmp_path: Path,
) -> None:
    base = tmp_path / "game_data/base"
    affix_root = base / "records/items/lootaffixes/prefix"
    for suffix, level, ranks in (("a", 10, 1), ("b", 50, 3)):
        _write_dbr(
            affix_root / f"test_skill_{suffix}.dbr",
            [
                ("Class", "LootRandomizer"),
                ("itemClassification", "Rare"),
                ("lootRandomizerName", "tagTestSkill"),
                ("levelRequirement", str(level)),
                ("augmentSkillLevel1", str(ranks)),
                (
                    "augmentSkillName1",
                    "records/skills/playerclass01/testskill.dbr",
                ),
            ],
        )
    _write_dbr(
        affix_root / "prefixtables/prefix_ring.dbr",
        [
            (
                "randomizerName1",
                "records/items/lootaffixes/prefix/test_skill_a.dbr",
            ),
            (
                "randomizerName2",
                "records/items/lootaffixes/prefix/test_skill_b.dbr",
            ),
        ],
    )
    _write_dbr(
        base / "records/items/loottables/gearaccessories/lt_ring.dbr",
        [
            (
                "prefixTableName1",
                "records/items/lootaffixes/prefix/prefixtables/prefix_ring.dbr",
            )
        ],
    )
    _write_dbr(
        base / "records/skills/playerclass01/testskill.dbr",
        [("skillDisplayName", "tagTestSkillName")],
    )

    output = tmp_path / "catalog"
    compile_catalog_bundle(
        tmp_path / "game_data",
        parse_localization_text(
            "tagTestSkill=Skilled\ntagTestSkillName=Test Skill\n"
        ),
        output,
        source_names=("base",),
    )

    affix = CatalogBundle.load(output).affixes.affixes[0]
    assert affix.rarity == "Rare"
    assert len(affix.variants) == 1
    skill_bonus = next(
        property_
        for property_ in affix.variants[0].properties
        if property_.property_id == "skill_bonus"
    )
    assert skill_bonus.attributes["skill_level"] == "3"
    assert skill_bonus.attributes["skill_level_min"] == "1"
    assert skill_bonus.attributes["skill_level_max"] == "3"
    assert affix.variants[0].stat_lines == ("+3 to Test Skill",)


def test_catalog_output_is_deterministic(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    _write_dbr(
        data_root / "base/records/skills/devotion/example.dbr",
        [("skillDisplayName", "tagExample")],
    )
    localization = parse_localization_text("tagExample=Example\n")
    first = tmp_path / "first"
    second = tmp_path / "second"

    compile_catalog_bundle(
        data_root, localization, first, source_names=("base",)
    )
    compile_catalog_bundle(
        data_root, localization, second, source_names=("base",)
    )

    for filename in (
        "manifest.json",
        "strings.en.json",
        "skills.json",
        "affixes.json",
        "equipment.json",
        "components.json",
        "augments.json",
        "relics.json",
        "runes.json",
        "consumables.json",
    ):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_loader_rejects_manifest_count_mismatch(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    localization = parse_localization_text("")
    output = tmp_path / "catalog"
    compile_catalog_bundle(
        data_root, localization, output, source_names=("base",)
    )
    manifest_path = output / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"]["skills"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        CatalogBundle.load(output)
    except ValueError as error:
        assert "skill count" in str(error)
    else:
        raise AssertionError("expected CatalogBundle.load to reject bad counts")


def test_compiler_splits_item_families_and_groups_leveled_variants(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "game_data"
    base_items = data_root / "base/records/items"
    _write_dbr(
        base_items / "gearhead/b001a_head.dbr",
        [
            ("Class", "ArmorProtective_Head"),
            ("FileDescription", "Test MI low"),
            ("itemClassification", "Rare"),
            ("itemNameTag", "tagTestHelm"),
            ("itemLevel", "20"),
            ("levelRequirement", "15"),
            ("characterLife", "100"),
            ("augmentSkillLevel1", "1"),
            ("augmentSkillName1", "records/skills/playerclass01/testskill.dbr"),
        ],
    )
    _write_dbr(
        base_items / "gearhead/b001b_head.dbr",
        [
            ("Class", "ArmorProtective_Head"),
            ("FileDescription", "Test MI high"),
            ("itemClassification", "Rare"),
            ("itemNameTag", "tagTestHelm"),
            ("itemLevel", "50"),
            ("levelRequirement", "45"),
            ("characterLife", "200"),
            ("offensivePierceMin", "10"),
            ("offensivePierceChance", "30"),
            ("augmentSkillLevel1", "2"),
            ("augmentSkillName1", "records/skills/playerclass01/testskill.dbr"),
            ("itemSetName", "records/items/lootsets/test_set.dbr"),
        ],
    )
    _write_dbr(
        base_items / "lootsets/test_set.dbr",
        [("setName", "tagTestSet")],
    )
    _write_dbr(
        base_items / "crafting/blueprints/test_helm_blueprint.dbr",
        [("artifactName", "records/items/gearhead/b001b_head.dbr")],
    )
    _write_dbr(
        base_items / "gearhead/c000_head.dbr",
        [
            ("Class", "ArmorProtective_Head"),
            ("FileDescription", "BASE BLANK EPIC HEAD"),
            ("itemClassification", "Epic"),
            ("itemNameTag", "tagMissingPlaceholder"),
        ],
    )
    _write_dbr(
        base_items / "materia/comp_test.dbr",
        [
            ("Class", "ItemRelic"),
            ("description", "tagTestComponent"),
            ("itemText", "tagTestComponentDesc"),
            ("itemClassification", "Common"),
            ("head", "1"),
            ("defensiveFire", "10"),
        ],
    )
    _write_dbr(
        base_items / "crafting/blueprints/component/craft_comp_test.dbr",
        [("artifactName", "records/items/materia/comp_test.dbr")],
    )
    _write_dbr(
        data_root / "base/records/controllers/factions/faction_test.dbr",
        [("myFaction", "User7")],
    )
    _write_dbr(
        data_root / "base/records/creatures/npcs/merchants/merchant_test.dbr",
        [
            (
                "marketFileName",
                "records/creatures/npcs/merchants/factiontables/"
                "_merchanttbl_test.dbr",
            ),
            ("factions", "records/controllers/factions/faction_test.dbr"),
        ],
    )
    _write_dbr(
        data_root
        / "base/records/creatures/npcs/merchants/factiontables/"
        "_merchanttbl_test.dbr",
        [
            (
                "respectedNormalTable",
                "records/creatures/npcs/merchants/factiontables/"
                "test_respected.dbr",
            )
        ],
    )
    _write_dbr(
        data_root
        / "base/records/creatures/npcs/merchants/factiontables/"
        "test_respected.dbr",
        [
            (
                "marketStaticItems",
                "records/items/crafting/blueprints/component/"
                "craft_comp_test.dbr",
            )
        ],
    )
    _write_dbr(
        base_items / "gearrelic/relic_test.dbr",
        [
            ("Class", "ItemArtifact"),
            ("description", "tagTestRelic"),
            ("itemClassification", "Epic"),
        ],
    )
    _write_dbr(
        base_items / "enchants/augment_test.dbr",
        [
            ("Class", "ItemEnchantment"),
            ("description", "tagTestAugment"),
            ("itemClassification", "Rare"),
            ("amulet", "1"),
            ("factionSource", "User7"),
        ],
    )
    _write_dbr(
        data_root / "gdx2/records/items/enchants/runes/rune_test.dbr",
        [
            ("Class", "ItemEnchantment"),
            ("description", "tagTestRune"),
            ("itemClassification", "Magical"),
            ("itemSkillName", "records/skills/itemskills/test_rune_skill.dbr"),
        ],
    )
    _write_dbr(
        base_items / "crafting/consumables/potion_test.dbr",
        [
            ("Class", "OneShot_Scroll"),
            ("description", "tagTestConsumable"),
            ("itemClassification", "Magical"),
            ("skillName", "records/skills/itemskills/test_consumable_skill.dbr"),
        ],
    )
    _write_dbr(
        data_root / "base/records/skills/itemskills/test_rune_skill.dbr",
        [("skillDisplayName", "tagTestRuneSkill")],
    )
    _write_dbr(
        data_root / "base/records/skills/playerclass01/testskill.dbr",
        [("skillDisplayName", "tagTestSkillName")],
    )
    _write_dbr(
        data_root / "base/records/skills/itemskills/test_consumable_skill.dbr",
        [
            ("skillDisplayName", "tagTestConsumableSkill"),
            ("defensiveFire", "15"),
        ],
    )
    localization = parse_localization_text(
        "\n".join(
            (
                "tagTestHelm=Test Helm",
                "tagTestSet=Test Set",
                "tagTestComponent=Test Component",
                "tagTestComponentDesc=Component description",
                "tagTestRelic=Test Relic",
                "tagTestAugment=Test Augment",
                "tagFactionUser7=The Black Legion",
                "tagTestRune=Test Rune",
                "tagTestRuneSkill=Rune Dash",
                "tagTestSkillName=Test Skill",
                "tagTestConsumable=Test Consumable",
                "tagTestConsumableSkill=Consumable Ward",
            )
        )
    )

    result = compile_catalog_bundle(
        data_root,
        localization,
        tmp_path / "catalog",
        source_names=("base", "gdx2"),
    )
    bundle = CatalogBundle.load(tmp_path / "catalog")

    assert result.item_counts == {
        "equipment": 1,
        "components": 1,
        "augments": 1,
        "relics": 1,
        "runes": 1,
        "consumables": 1,
    }
    assert result.item_variant_count == 7
    assert result.unresolved_item_record_count == 1
    helm = bundle.items.equipment[0]
    assert helm.display_name == "Test Helm"
    assert len(helm.variants) == 2
    assert helm.variants[0].category == "monster_infrequent"
    assert helm.variants[0].gear_slot == "Head"
    assert helm.variants[0].acquisition_source == "Specific Monster Drop"
    assert helm.variants[0].properties[0].property_id == "health"
    assert helm.variants[1].set_name == "Test Set"
    assert helm.variants[1].acquisition_source == "Crafted"
    assert "+2 to Test Skill" in helm.variants[1].stat_lines
    assert "[x]% Chance of [y] Pierce Damage" in helm.variants[1].stat_lines
    assert "chance_flat_pierce_damage" in {
        property_.property_id for property_ in helm.variants[1].properties
    }
    component = bundle.items.components[0]
    assert component.description == "Component description"
    assert component.variants[0].applicable_slots == ("Head",)
    assert component.variants[0].properties[0].property_id == "fire_resistance"
    assert component.variants[0].acquisition_source == "Faction Vendor Blueprint"
    assert len(component.variants[0].vendor_sources) == 1
    assert component.variants[0].vendor_sources[0].faction_name == (
        "The Black Legion"
    )
    assert component.variants[0].vendor_sources[0].reputation == "Respected"
    augment = bundle.items.augments[0].variants[0]
    assert augment.acquisition_source == "Purchased"
    assert augment.faction_source == "User7"
    assert augment.faction_name == "The Black Legion"
    assert bundle.items.runes[0].variants[0].granted_skill_name == "Rune Dash"
    consumable = bundle.items.consumables[0].variants[0]
    assert consumable.effect_skill_name == "Consumable Ward"
    assert consumable.effect_properties[0].property_id == "fire_resistance"
