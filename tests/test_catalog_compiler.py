import json
from pathlib import Path

from gd_affix_relevance.catalog import CatalogBundle, compile_catalog_bundle
from gd_affix_relevance.importers.localization_parser import parse_localization_text


def _write_dbr(path: Path, fields: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key},{value},\n" for key, value in fields),
        encoding="utf-8",
    )


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
    assert bundle.manifest.skill_scope == "named_player_pet_and_item_granted"
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
    assert bundle.affixes.affixes[0].variants[0].gear_slot == "Ring"
    skill_properties = [
        property_
        for property_ in bundle.affixes.affixes[0].variants[0].properties
        if property_.property_id == "skill_bonus"
    ]
    assert skill_properties[0].attributes["display_name"] == "Raging Tempest"
    property_ids = {
        property_.property_id
        for property_ in bundle.affixes.affixes[0].variants[0].properties
    }
    assert "pet_bonus" not in property_ids
    assert {
        "pet_total_damage_percent",
        "pet_health_percent",
        "pet_offensive_ability_percent",
    } <= property_ids


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
            ("itemSetName", "records/items/lootsets/test_set.dbr"),
        ],
    )
    _write_dbr(
        base_items / "lootsets/test_set.dbr",
        [("setName", "tagTestSet")],
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
                "tagTestRune=Test Rune",
                "tagTestRuneSkill=Rune Dash",
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
    assert helm.variants[0].properties[0].property_id == "health"
    assert helm.variants[1].set_name == "Test Set"
    component = bundle.items.components[0]
    assert component.description == "Component description"
    assert component.variants[0].applicable_slots == ("Head",)
    assert component.variants[0].properties[0].property_id == "fire_resistance"
    assert bundle.items.runes[0].variants[0].granted_skill_name == "Rune Dash"
    consumable = bundle.items.consumables[0].variants[0]
    assert consumable.effect_skill_name == "Consumable Ward"
    assert consumable.effect_properties[0].property_id == "fire_resistance"
