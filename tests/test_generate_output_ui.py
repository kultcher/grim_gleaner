import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.generate_output import GenerateOutputPage


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_generate_page_writes_staging_folder_and_shows_preview(
    tmp_path: Path,
) -> None:
    _application()
    source = tmp_path / "source"
    source.mkdir()
    (source / "tags_items.txt").write_text(
        "tagHealthy={^G}Healthy\ntagBase={^B}Base Item\n",
        encoding="utf-8",
    )
    variant = AffixVariantDefinition(
        gear_slot="Ring",
        level_requirements=(5,),
        properties=(AffixProperty("health", "health", {}),),
        stat_lines=("+[x] Health",),
        representative_source="base:healthy.dbr",
        source_record_count=1,
        stat_layout_count=1,
    )
    catalog = AffixCatalog(
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
    output = tmp_path / "generated" / "text_en"
    page = GenerateOutputPage(
        catalog,
        BuildProfile("Health", {"health": 4}),
        source_root=source,
        output_root=output,
    )

    page.generate()

    assert page.last_result is not None
    assert "tagHealthy=(B1){^G}Healthy" in (
        output / "tags_items.txt"
    ).read_text(encoding="utf-8")
    assert "tagBase={^B}Base Item" in (
        output / "tags_items.txt"
    ).read_text(encoding="utf-8")
    assert "Localization lines changed: 1" in page.preview.toPlainText()
