from pathlib import Path

from gd_affix_relevance.importers.localization_parser import parse_localization_text
from gd_affix_relevance.normalization.item_audit import (
    build_item_audit,
    format_item_audit_report,
)


def _write_dbr(path: Path, fields: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{key},{value},\n" for key, value in fields),
        encoding="utf-8",
    )


def test_item_audit_separates_mi_modifier_records_from_item_metadata(
    tmp_path: Path,
) -> None:
    source = tmp_path / "base"
    item = source / "records/items/gearhead/b001_head.dbr"
    player_skill = source / "records/skills/playerclass01/test_skill.dbr"
    modifier = source / "records/skills/itemskills/skillmodifiers/test_modifier.dbr"
    _write_dbr(
        item,
        [
            ("FileDescription", "Monster Helm"),
            ("itemClassification", "Rare"),
            ("itemNameTag", "tagTestHelm"),
            ("dropSoundWater", "records/sounds/water.dbr"),
            ("offensivePoisonModifier", "25"),
            ("modifiedSkillName1", "records/skills/playerclass01/test_skill.dbr"),
            (
                "modifierSkillName1",
                "records/skills/itemskills/skillmodifiers/test_modifier.dbr",
            ),
        ],
    )
    _write_dbr(player_skill, [("skillDisplayName", "tagTestSkill")])
    _write_dbr(
        modifier,
        [
            ("Class", "Skill_Modifier"),
            ("conversionInType", "Fire"),
            ("conversionOutType", "Lightning"),
            ("conversionPercentage", "100"),
            ("skillCooldownTime", "-1"),
        ],
    )
    localization = parse_localization_text(
        "tagTestHelm=Monster Crown\ntagTestSkill=Test Strike\n"
    )

    result = build_item_audit(
        tmp_path,
        localization,
        source_names=("base",),
        affix_property_ids={"acid_damage_percent", "damage_conversion"},
    )

    assert len(result.records) == 1
    audited = result.records[0]
    assert audited.group == "monster_infrequent"
    assert audited.display_name == "Monster Crown"
    assert "acid_damage_percent" in audited.mapped_property_ids
    assert "damage_conversion" in audited.mapped_property_ids
    assert "skill_modifier" in audited.new_property_ids
    assert "skill_modifier_cooldown" in audited.new_property_ids
    assert audited.unresolved_gameplay_fields == ()
    assert any(
        line.startswith("Skill Modifier for Test Strike:")
        for line in audited.stat_lines
    )


def test_item_audit_reports_mastery_and_deflection_as_new_item_properties(
    tmp_path: Path,
) -> None:
    item = tmp_path / "base/records/items/gearhead/c001_head.dbr"
    _write_dbr(
        item,
        [
            ("FileDescription", "Epic Helm"),
            ("itemClassification", "Epic"),
            ("itemNameTag", "tagEpicHelm"),
            ("augmentMasteryLevel1", "1"),
            (
                "augmentMasteryName1",
                "records/skills/playerclass01/_classtraining_class01.dbr",
            ),
            ("characterDeflectProjectile", "5"),
            ("characterLife", "100"),
        ],
    )

    result = build_item_audit(tmp_path, source_names=("base",))
    audited = result.records[0]

    assert audited.group == "epic"
    assert audited.new_property_ids == ("mastery_bonus", "projectile_deflection")
    assert "health" in audited.mapped_property_ids
    report = format_item_audit_report(result)
    assert "| Epic | 1 | 1 | 1 | 1 | 0 |" in report
    assert "`mastery_bonus` (1)" in report
    assert "`projectile_deflection` (1)" in report
