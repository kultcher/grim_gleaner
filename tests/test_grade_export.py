from __future__ import annotations

from pathlib import Path

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.grade_export import (
    BACKUP_CONTENTS,
    backup_available,
    export_grades_to_game,
    grim_dawn_text_root,
    restore_game_backup,
)


def _catalog() -> AffixCatalog:
    variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
        representative_source="base:healthy.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    return AffixCatalog(
        (
            AffixDefinition(
                affix_id="prefix:healthy",
                localization_tag="tagHealthy",
                display_name="Healthy",
                kind="prefix",
                variants=(variant,),
            ),
        )
    )


def _bundled_tags(tmp_path: Path) -> Path:
    bundled = tmp_path / "app" / "tags"
    bundled.mkdir(parents=True)
    (bundled / "tags_items.txt").write_text(
        "tagHealthy=Bundled Healthy\n",
        encoding="utf-8",
    )
    (bundled / "tagsgdx3_items.txt").write_text(
        "tagExpansion=Expansion Item\n",
        encoding="utf-8",
    )
    return bundled


def test_game_folder_requires_grim_dawn_executable(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    game.mkdir()

    try:
        grim_dawn_text_root(game)
    except ValueError as error:
        assert "does not contain Grim Dawn.exe" in str(error)
    else:
        raise AssertionError("folder without Grim Dawn.exe was accepted")

    (game / "Grim Dawn.exe").touch()

    assert grim_dawn_text_root(game) == game / "settings" / "text_en"


def test_export_preserves_first_original_backup_across_reexports_and_restores(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    target = game / "settings" / "text_en"
    target.mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    original = b"tagHealthy={^G}Rainbow Healthy\r\ntagOther=Keep Me\r\n"
    (target / "tags_items.txt").write_bytes(original)
    (target / "rainbow-extra.txt").write_text("tagExtra=Extra\n", encoding="utf-8")
    bundled = _bundled_tags(tmp_path)
    staging = tmp_path / "app" / "staging" / "text_en"
    backups = tmp_path / "app" / "backups"

    first = export_grades_to_game(
        game,
        bundled,
        staging,
        backups,
        _catalog(),
        BuildProfile("Health", {"health": 4}),
    )

    assert first.backup_created
    assert (first.backup_root / BACKUP_CONTENTS / "tags_items.txt").read_bytes() == original
    assert "{^G}Rainbow Healthy" in (target / "tags_items.txt").read_text(
        encoding="utf-8-sig"
    )
    assert (target / "tagsgdx3_items.txt").is_file()
    assert (target / "rainbow-extra.txt").is_file()
    assert backup_available(game, backups)

    second = export_grades_to_game(
        game,
        bundled,
        staging,
        backups,
        _catalog(),
        BuildProfile("Ignored", {}),
    )

    assert not second.backup_created
    assert (first.backup_root / BACKUP_CONTENTS / "tags_items.txt").read_bytes() == original

    restored = restore_game_backup(game, backups)

    assert restored.original_existed
    assert (target / "tags_items.txt").read_bytes() == original
    assert (target / "rainbow-extra.txt").is_file()
    assert not (target / "tagsgdx3_items.txt").exists()
    assert not backup_available(game, backups)


def test_restore_removes_generated_text_folder_for_clean_install(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    bundled = _bundled_tags(tmp_path)
    staging = tmp_path / "app" / "staging" / "text_en"
    backups = tmp_path / "app" / "backups"

    exported = export_grades_to_game(
        game,
        bundled,
        staging,
        backups,
        _catalog(),
        BuildProfile("Health", {"health": 4}),
    )

    assert exported.backup_created
    assert exported.target_root.is_dir()

    restored = restore_game_backup(game, backups)

    assert not restored.original_existed
    assert not exported.target_root.exists()
