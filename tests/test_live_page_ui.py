import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import CatalogBundle
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.live.protocol import FilterDecision, HoveredItem, TableStatus
from gd_affix_relevance.runtime_paths import resolve_runtime_paths
from gd_affix_relevance.ui import live_page as live_page_module
from gd_affix_relevance.ui.live_page import LivePage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).parent / "fixtures" / "live" / "tags_ui_sample.txt"


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_live_page_without_catalog_reports_status() -> None:
    _application()
    page = LivePage(None, BuildProfile(), None, resolve_runtime_paths())
    page.handle_message(HoveredItem(calls=1, seed=1, base_record="records/x.dbr"))
    assert page.table.rowCount() == 0
    assert "Catalog not loaded" in page.status.text()


def test_live_page_grades_items_and_writes_table(tmp_path: Path, monkeypatch) -> None:
    _application()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(live_page_module, "find_ui_templates", lambda *a, **k: TEMPLATES)
    bundle = CatalogBundle.load(PROJECT_ROOT / "artifacts" / "catalog")
    profile = BuildProfile(weights={"bleeding_damage_percent": 4, "health": 2})
    page = LivePage(bundle, profile, None, resolve_runtime_paths())

    page.filter_checkbox.setChecked(True)
    page.filter_combos["magic"].setCurrentIndex(page.filter_combos["magic"].findData("S++"))
    page.write_table()
    table_path = tmp_path / "GrimGleaner" / "live" / "grade_table.txt"
    assert table_path.read_text(encoding="utf-8").startswith("GGT1\t")
    assert "hide\tmagic\tS++" in table_path.read_text(encoding="utf-8")

    page.handle_message(
        HoveredItem(
            calls=1,
            seed=7,
            base_record="records/items/gearlegs/a02_legs01.dbr",
            suffix_record="records/items/lootaffixes/suffix/a035e_off_dmg%bleed_06_ar.dbr",
        )
    )
    assert page.table.rowCount() == 1
    assert page.table.item(0, 2).text() == "Magic"
    assert page.table.item(0, 3).text().endswith("▾")  # filter would hide it
    assert "seed 7" in page.details.toHtml()

    page.handle_message(TableStatus("abc123", True, "filter=1"))
    page.handle_message(FilterDecision(7, "records/x.dbr", "", "", "D", "magic", True, "abc123"))
    assert "abc123" in page.status.text()
    assert "1 items hidden" in page.status.text()
