import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile, RUSSIAN_LOCALE
from gd_affix_relevance.ui.generate_output import GenerateOutputPage


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


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


def _page(tmp_path: Path, game: Path, bundled: Path) -> GenerateOutputPage:
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    settings.setValue("paths/grim_dawn_folder", str(game))
    return GenerateOutputPage(
        _catalog(),
        BuildProfile("Health", {"health": 4}),
        source_root=bundled,
        output_root=tmp_path / "staging" / "text_en",
        backups_root=tmp_path / "backups",
        settings=settings,
    )


def test_export_page_installs_grades_and_restores_original(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _application()
    bundled = tmp_path / "app" / "tags"
    bundled.mkdir(parents=True)
    (bundled / "tags_items.txt").write_text(
        "tagHealthy=Bundled Healthy\n",
        encoding="utf-8",
    )
    game = tmp_path / "Grim Dawn"
    installed = game / "settings" / "text_en"
    installed.mkdir(parents=True)
    (game / "Grim Dawn.exe").touch()
    original = "tagHealthy={^G}Rainbow Healthy\ntagOther=Keep Me\n"
    (installed / "tags_items.txt").write_text(original, encoding="utf-8")
    page = _page(tmp_path, game, bundled)
    assert page.last_exported_profile.text() == "None"
    questions: list[str] = []

    def confirm(_parent, _title, message, *_args):
        questions.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)

    page.generate()

    assert page.last_result is not None
    assert "About to apply grade tags to 1 affix and 0 unique item entries" in questions[0]
    assert "tagHealthy={^C}(C1){^G}Rainbow Healthy" in (
        installed / "tags_items.txt"
    ).read_text(encoding="utf-8")
    assert page.restore_button.isEnabled()
    assert "Created the original-state backup" in page.status.text()
    assert page.last_exported_profile.text() == "Health"
    assert page.settings.value("export/last_profile_name") == "Health"

    page.restore_backup()

    assert questions[1].startswith(
        "Restoring Grim Dawn/settings/text_en folder to original state."
    )
    assert (installed / "tags_items.txt").read_text(encoding="utf-8") == original
    assert not page.restore_button.isEnabled()


def test_export_page_uses_bundled_tags_for_clean_install(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _application()
    bundled = tmp_path / "app" / "tags"
    bundled.mkdir(parents=True)
    (bundled / "tags_items.txt").write_text(
        "tagHealthy=Bundled Healthy\n",
        encoding="utf-8",
    )
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    page = _page(tmp_path, game, bundled)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    page.generate()

    installed = game / "settings" / "text_en"
    assert "tagHealthy=(C1)Bundled Healthy" in (
        installed / "tags_items.txt"
    ).read_text(encoding="utf-8")

    page.restore_backup()

    assert not installed.exists()
    assert "clean-install state" in page.status.text()


def test_export_page_requires_configured_game_folder(tmp_path: Path) -> None:
    _application()
    settings = QSettings(
        str(tmp_path / "settings.ini"), QSettings.Format.IniFormat
    )
    page = GenerateOutputPage(
        _catalog(),
        BuildProfile(),
        source_root=tmp_path / "tags",
        output_root=tmp_path / "staging" / "text_en",
        backups_root=tmp_path / "backups",
        settings=settings,
    )

    assert not page.generate_button.isEnabled()
    assert not page.restore_button.isEnabled()
    assert "Set a valid Grim Dawn folder" in page.target_label.text()


def test_export_page_rejects_existing_folder_without_executable(
    tmp_path: Path,
) -> None:
    _application()
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    bundled = tmp_path / "tags"
    bundled.mkdir()
    page = _page(tmp_path, game, bundled)

    assert not page.generate_button.isEnabled()
    assert not page.restore_button.isEnabled()
    assert "Set a valid Grim Dawn folder" in page.target_label.text()

    (game / "Grim Dawn.exe").touch()
    page.refresh_game_location()

    assert page.generate_button.isEnabled()
    assert str(game / "settings" / "text_en") in page.target_label.text()


def test_export_page_can_target_russian_localization(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _application()
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    bundled = tmp_path / "tags" / "ru"
    bundled.mkdir(parents=True)
    (bundled / "tags_items.txt").write_text(
        "tagHealthy=Здоровый\n",
        encoding="utf-8-sig",
    )
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    settings.setValue("paths/grim_dawn_folder", str(game))
    page = GenerateOutputPage(
        _catalog(),
        BuildProfile("Здоровье", {"health": 4}),
        source_root=bundled,
        output_root=tmp_path / "staging" / "text_ru",
        backups_root=tmp_path / "backups",
        locale=RUSSIAN_LOCALE,
        settings=settings,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    page.generate()

    target = game / "settings" / "text_ru"
    assert target.is_dir()
    assert "text_ru" in page.target_label.text()
    assert not (game / "settings" / "text_en").exists()


def test_export_page_prepares_missing_selected_language_automatically(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _application()
    game = tmp_path / "Grim Dawn"
    game.mkdir()
    (game / "Grim Dawn.exe").touch()
    bundled = tmp_path / "tags" / "ru"
    settings = QSettings(
        str(tmp_path / "settings.ini"),
        QSettings.Format.IniFormat,
    )
    settings.setValue("paths/grim_dawn_folder", str(game))
    page = GenerateOutputPage(
        _catalog(),
        BuildProfile("Здоровье", {"health": 4}),
        source_root=bundled,
        output_root=tmp_path / "staging" / "text_ru",
        backups_root=tmp_path / "backups",
        locale=RUSSIAN_LOCALE,
        settings=settings,
    )
    prepared: list[tuple[Path, Path, str]] = []

    def prepare(game_folder, destination_root, *, locale):
        prepared.append((game_folder, destination_root, locale.code))
        destination_root.mkdir(parents=True)
        for filename in (
            "tags_items.txt",
            "tagsgdx1_items.txt",
            "tagsgdx2_items.txt",
            "tagsgdx3_items.txt",
        ):
            (destination_root / filename).write_text(
                "tagHealthy=Здоровый\n",
                encoding="utf-8-sig",
            )

    monkeypatch.setattr(
        "gd_affix_relevance.ui.generate_output.prepare_game_item_tags",
        prepare,
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    page.generate()

    assert prepared == [(game, bundled, "ru")]
    assert page.last_result is not None
    assert "(C1)Здоровый" in (
        game / "settings" / "text_ru" / "tags_items.txt"
    ).read_text(encoding="utf-8-sig")
