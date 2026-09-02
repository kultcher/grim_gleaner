from __future__ import annotations

from pathlib import Path
import json

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile, RUSSIAN_LOCALE
from gd_affix_relevance.grade_export import (
    BACKUP_MANIFEST,
    BACKUP_CONTENTS,
    LOCALIZATION_LOCATION_INSTALLATION,
    LOCALIZATION_LOCATION_USER,
    backup_available,
    detect_grim_dawn_user_settings_root,
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


def test_detects_redirected_documents_user_settings(tmp_path: Path) -> None:
    settings_root = tmp_path / "My Games" / "Grim Dawn" / "Settings"
    settings_root.mkdir(parents=True)

    assert detect_grim_dawn_user_settings_root(tmp_path) == settings_root


def test_text_root_uses_user_localization_only_when_language_folder_has_files(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    user_settings = tmp_path / "Documents" / "My Games" / "Grim Dawn" / "Settings"
    user_settings.mkdir(parents=True)

    assert grim_dawn_text_root(
        game,
        user_settings_root=user_settings,
    ) == game / "settings" / "text_en"

    user_text = user_settings / "text_en"
    user_text.mkdir()
    (user_text / "tags_items.txt").write_text("tag=value\n", encoding="utf-8")

    assert grim_dawn_text_root(
        game,
        user_settings_root=user_settings,
    ) == user_text.resolve()


def test_text_root_requires_choice_when_both_locations_contain_files(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    install_text = game / "settings" / "text_ru"
    install_text.mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    (install_text / "tags_items.txt").write_text("tag=value\n", encoding="utf-8")
    user_settings = tmp_path / "Documents" / "My Games" / "Grim Dawn" / "Settings"
    user_text = user_settings / "text_ru"
    user_text.mkdir(parents=True)
    (user_text / "tags_items.txt").write_text("tag=value\n", encoding="utf-8")

    try:
        grim_dawn_text_root(
            game,
            locale=RUSSIAN_LOCALE,
            user_settings_root=user_settings,
        )
    except ValueError as error:
        assert "both" in str(error).casefold()
        assert "choose" in str(error).casefold()
    else:
        raise AssertionError("ambiguous localization roots were accepted")

    assert grim_dawn_text_root(
        game,
        locale=RUSSIAN_LOCALE,
        user_settings_root=user_settings,
        location_preference=LOCALIZATION_LOCATION_INSTALLATION,
    ) == install_text
    assert grim_dawn_text_root(
        game,
        locale=RUSSIAN_LOCALE,
        user_settings_root=user_settings,
        location_preference=LOCALIZATION_LOCATION_USER,
    ) == user_text.resolve()


def test_export_can_target_active_user_settings_instead_of_install(
    tmp_path: Path,
) -> None:
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    install_text = game / "settings" / "text_ru"
    install_text.mkdir(parents=True)
    (install_text / "tags_items.txt").write_text(
        "tagHealthy=Неверный источник\n",
        encoding="utf-8-sig",
    )
    user_settings = tmp_path / "Documents" / "My Games" / "Grim Dawn" / "Settings"
    active_text = user_settings / "text_ru" / "aom"
    active_text.mkdir(parents=True)
    active_file = active_text / "rainbow-items.txt"
    active_file.write_text(
        "tagHealthy=[ms]{^G}Здоровый\n",
        encoding="utf-8-sig",
    )

    exported = export_grades_to_game(
        game,
        _bundled_tags(tmp_path),
        tmp_path / "staging" / "text_ru",
        tmp_path / "backups",
        _catalog(),
        BuildProfile("Здоровье", {"health": 4}),
        locale=RUSSIAN_LOCALE,
        user_settings_root=user_settings,
        location_preference=LOCALIZATION_LOCATION_USER,
    )

    assert exported.target_root == user_settings / "text_ru"
    assert "[ms]{^C}(C1){^G}Здоровый" in active_file.read_text(
        encoding="utf-8-sig"
    )
    assert "Неверный источник" in (install_text / "tags_items.txt").read_text(
        encoding="utf-8-sig"
    )


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


def test_russian_export_and_restore_are_isolated_from_english(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    russian = game / "settings" / "text_ru"
    english = game / "settings" / "text_en"
    russian.mkdir(parents=True)
    english.mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    original_russian = "\ufefftagHealthy={^G}Здоровый\r\n".encode("utf-8")
    (russian / "tags_items.txt").write_bytes(original_russian)
    (english / "tags_items.txt").write_text(
        "tagHealthy=Healthy\n",
        encoding="utf-8-sig",
    )
    english_before = (english / "tags_items.txt").read_bytes()
    bundled = tmp_path / "app" / "tags" / "ru"
    bundled.mkdir(parents=True)
    (bundled / "tags_items.txt").write_text(
        "tagHealthy=Здоровый\n",
        encoding="utf-8-sig",
    )
    staging = tmp_path / "app" / "staging" / "text_ru"
    backups = tmp_path / "app" / "backups"

    exported = export_grades_to_game(
        game,
        bundled,
        staging,
        backups,
        _catalog(),
        BuildProfile("Здоровье", {"health": 4}),
        locale=RUSSIAN_LOCALE,
    )

    assert exported.target_root == russian.resolve()
    assert "{^C}(C1){^G}Здоровый" in (
        russian / "tags_items.txt"
    ).read_text(encoding="utf-8-sig")
    assert (english / "tags_items.txt").read_bytes() == english_before
    manifest = json.loads(
        (exported.backup_root / BACKUP_MANIFEST).read_text(encoding="utf-8")
    )
    assert manifest["locale"] == "ru"
    assert (exported.backup_root / "text_ru" / "tags_items.txt").read_bytes() == (
        original_russian
    )

    restored = restore_game_backup(
        game,
        backups,
        locale=RUSSIAN_LOCALE,
    )

    assert restored.locale is RUSSIAN_LOCALE
    assert (russian / "tags_items.txt").read_bytes() == original_russian
    assert (english / "tags_items.txt").read_bytes() == english_before


def test_restore_rejects_backup_manifest_for_another_locale(tmp_path: Path) -> None:
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    bundled = _bundled_tags(tmp_path)
    exported = export_grades_to_game(
        game,
        bundled,
        tmp_path / "staging" / "text_en",
        tmp_path / "backups",
        _catalog(),
        BuildProfile(),
    )
    manifest_path = exported.backup_root / BACKUP_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["locale"] = "ru"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        restore_game_backup(game, tmp_path / "backups")
    except ValueError as error:
        assert "locale" in str(error).lower()
    else:
        raise AssertionError("backup for another locale was accepted")
