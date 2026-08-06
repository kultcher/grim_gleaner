import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gd_affix_relevance.catalog import (
    AffixCatalog,
    AffixDefinition,
    AffixProperty,
    AffixVariantDefinition,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.main_window import MainWindow


def _application() -> QApplication:
    return QApplication.instance() or QApplication([])


def _affix(affix_id: str, name: str, stat_id: str) -> AffixDefinition:
    return AffixDefinition(
        affix_id=affix_id,
        localization_tag=f"tag{name}",
        display_name=name,
        kind="prefix",
        variants=(
            AffixVariantDefinition(
                gear_slot="Ring",
                level_requirements=(5,),
                properties=(AffixProperty(stat_id, stat_id, {}),),
                stat_lines=(f"+[x] {name} stat",),
                representative_source=f"base:{affix_id}.dbr",
                source_record_count=1,
                stat_layout_count=1,
            ),
        ),
    )


def test_top_matches_tracks_active_editor_profile() -> None:
    _application()
    profile = BuildProfile("Testing", {"health": 4})
    catalog = AffixCatalog(
        (
            _affix("prefix:swift", "Swift", "movement_speed"),
            _affix("prefix:tough", "Tough", "health"),
        )
    )
    window = MainWindow(profile, catalog=catalog)
    window.show()

    page = window.top_matches_page
    assert page.table.rowCount() == 2
    assert page.table.item(0, 1).text() == "Tough"
    assert page.table.item(0, 0).text() == "[B1]"
    assert "All affix stats" in page.details.toPlainText()

    window.profile_editor.accordions["core_health"].rows[
        "health"
    ].weight_control.set_value(0)
    window.profile_editor.accordions["core_speed"].rows[
        "movement_speed"
    ].weight_control.set_value(4)

    assert page.table.item(0, 1).text() == "Swift"
    assert "Movement Speed" in page.table.item(0, 4).text()


def test_top_matches_prompts_for_a_weighted_profile() -> None:
    _application()
    window = MainWindow(BuildProfile(), catalog=AffixCatalog(()))

    assert window.top_matches_page.table.rowCount() == 0
    assert "Set at least one" in window.top_matches_page.status.text()
