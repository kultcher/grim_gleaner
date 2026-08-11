"""Top-level Grim Gleaner application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import (
    AffixCatalog,
    CatalogBundle,
    ItemCatalog,
    SkillCatalog,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.runtime_paths import RuntimePaths, resolve_runtime_paths
from gd_affix_relevance.ui.generate_output import GenerateOutputPage
from gd_affix_relevance.ui.guide import GuidePage
from gd_affix_relevance.ui.profile_editor import ProfileEditor
from gd_affix_relevance.ui.settings import SettingsPage
from gd_affix_relevance.ui.top_matches import TopMatchesPage

NAV_PAGE_ROLE = Qt.ItemDataRole.UserRole
NAV_TAB_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class MainWindow(QMainWindow):
    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
        *,
        catalog: AffixCatalog | None = None,
        skills: SkillCatalog | None = None,
        items: ItemCatalog | None = None,
        settings: QSettings | None = None,
        runtime_paths: RuntimePaths | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grim Gleaner")
        self.resize(1120, 780)
        self.setMinimumSize(880, 620)
        self.settings = settings
        self.runtime_paths = runtime_paths or resolve_runtime_paths()
        self._game_folder_prompted = False

        profile_path: Path | None = None
        startup_notice = ""
        if profile is None and self.settings is not None:
            raw_path = self.settings.value("profiles/active_path", "", type=str)
            if raw_path:
                candidate = Path(raw_path)
                try:
                    profile = load_profile(candidate)
                except (OSError, ValueError, TypeError):
                    self.settings.remove("profiles/active_path")
                    self.settings.sync()
                    startup_notice = (
                        "The last active profile could not be found or read; "
                        "started a new profile."
                    )
                else:
                    profile_path = candidate

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget(central)
        sidebar.setObjectName("mainSidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 10)
        sidebar_layout.setSpacing(0)

        self.navigation = QListWidget(sidebar)
        self.navigation.setObjectName("mainNavigation")
        self.navigation.setSpacing(2)
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        sidebar_layout.addWidget(self.navigation, 1)

        self.game_location_warning = QLabel(
            "Grim Dawn folder not confirmed.\nExports are disabled.", sidebar
        )
        self.game_location_warning.setObjectName("gameLocationWarning")
        self.game_location_warning.setWordWrap(True)
        sidebar_layout.addWidget(self.game_location_warning)
        layout.addWidget(sidebar)

        self.pages = QStackedWidget(central)
        layout.addWidget(self.pages, 1)

        catalog_status = ""
        if catalog is None and skills is None and items is None:
            bundle, catalog_status = _load_runtime_catalog(self.runtime_paths)
            if bundle is not None:
                catalog = bundle.affixes
                skills = bundle.skills
                items = bundle.items
        catalog = catalog or AffixCatalog(())
        skills = skills or SkillCatalog(())
        items = items or ItemCatalog((), (), (), (), (), ())

        self.profile_editor = ProfileEditor(
            profile,
            self.pages,
            skills=skills,
            profile_path=profile_path,
            profiles_root=self.runtime_paths.profiles_root,
            startup_notice=startup_notice,
        )
        self.profile_page_index = self.pages.addWidget(self.profile_editor)
        self.profile_navigation_row = self._add_navigation_item(
            "Build Profile",
            "Set the stats this build values",
            self.profile_page_index,
        )

        self.top_matches_page = TopMatchesPage(
            catalog,
            self.profile_editor.profile,
            catalog_status=catalog_status,
            skills=skills,
            items=items,
            parent=self.pages,
        )
        self.gear_grades_page_index = self.pages.addWidget(
            self.top_matches_page
        )
        self.gear_grades_navigation_row = self._add_navigation_item(
            "Gear Grades",
            "Rank affixes and gear against this profile",
            self.gear_grades_page_index,
        )
        self.gear_subnavigation_rows: dict[int, int] = {}
        for tab_index, title in enumerate(("Affixes", "Uniques", "Add-ons")):
            self.gear_subnavigation_rows[tab_index] = self._add_navigation_item(
                title,
                f"Open the {title} Gear Grades tab",
                self.gear_grades_page_index,
                tab_index=tab_index,
                child=True,
            )

        self.generate_output_page = GenerateOutputPage(
            catalog,
            self.profile_editor.profile,
            items=items,
            source_root=self.runtime_paths.tags_root,
            output_root=self.runtime_paths.staging_output_root,
            backups_root=self.runtime_paths.backups_root,
            catalog_status=catalog_status,
            settings=self.settings,
            parent=self.pages,
        )
        self.export_grades_page_index = self.pages.addWidget(
            self.generate_output_page
        )
        self.export_grades_navigation_row = self._add_navigation_item(
            "Export Grades",
            "Apply grades to Grim Dawn or restore the original item names",
            self.export_grades_page_index,
        )

        self.settings_page = SettingsPage(self.settings, self.pages)
        self.settings_page.game_folder_changed.connect(self._game_folder_changed)
        self.settings_page_index = self.pages.addWidget(self.settings_page)
        self.settings_navigation_row = self._add_navigation_item(
            "Settings",
            "Configure Grim Dawn paths and application preferences",
            self.settings_page_index,
        )

        self.guide_page = GuidePage(self.pages)
        self.guide_page_index = self.pages.addWidget(self.guide_page)
        self.guide_navigation_row = self._add_navigation_item(
            "Guide",
            "How to use Grim Gleaner and understand its limitations",
            self.guide_page_index,
        )

        self.profile_editor.profile_changed.connect(self.top_matches_page.refresh)
        self.top_matches_page.profile_state_changed.connect(
            self.profile_editor.mark_external_change
        )
        self.profile_editor.profile_path_changed.connect(
            self._remember_profile_path
        )
        self.profile_editor.view_matches_requested.connect(
            lambda: self.navigation.setCurrentRow(
                self.gear_grades_navigation_row
            )
        )
        self.top_matches_page.tabs.currentChanged.connect(
            self._gear_tab_changed
        )
        self.navigation.currentRowChanged.connect(self._navigation_changed)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)
        self._update_game_location_state()

    def _add_navigation_item(
        self,
        title: str,
        tooltip: str,
        page_index: int,
        *,
        tab_index: int = -1,
        child: bool = False,
    ) -> int:
        item = QListWidgetItem(f"    {title}" if child else title)
        item.setToolTip(tooltip)
        item.setData(NAV_PAGE_ROLE, page_index)
        item.setData(NAV_TAB_ROLE, tab_index)
        if child:
            font = QFont(self.navigation.font())
            point_size = font.pointSizeF()
            font.setPointSizeF(max(8.0, point_size - 1.0))
            item.setFont(font)
        self.navigation.addItem(item)
        return self.navigation.row(item)

    def _navigation_changed(self, row: int) -> None:
        item = self.navigation.item(row)
        if item is None:
            return
        page_index = item.data(NAV_PAGE_ROLE)
        tab_index = item.data(NAV_TAB_ROLE)
        if not isinstance(page_index, int):
            return
        self.pages.setCurrentIndex(page_index)
        if page_index == self.gear_grades_page_index:
            if isinstance(tab_index, int) and tab_index >= 0:
                self.top_matches_page.tabs.setCurrentIndex(tab_index)
            self.top_matches_page.refresh()

    def _gear_tab_changed(self, tab_index: int) -> None:
        if self.pages.currentIndex() != self.gear_grades_page_index:
            return
        row = self.gear_subnavigation_rows.get(tab_index)
        if row is not None and self.navigation.currentRow() != row:
            self.navigation.setCurrentRow(row)

    def _remember_profile_path(self, path: object) -> None:
        if self.settings is None:
            return
        if path is None:
            self.settings.remove("profiles/active_path")
        else:
            self.settings.setValue(
                "profiles/active_path", str(Path(path).resolve())
            )
        self.settings.sync()

    def prompt_for_game_folder_if_needed(self) -> None:
        """Prompt once at startup when no confirmed installation is stored."""

        if self._game_folder_prompted or self.settings_page.has_valid_game_folder():
            return
        self._game_folder_prompted = True
        self.navigation.setCurrentRow(self.settings_navigation_row)
        self.settings_page.prompt_for_game_folder()
        self._update_game_location_state()

    def _game_folder_changed(self, game_folder: str = "") -> None:
        self.generate_output_page.refresh_game_location(game_folder)
        self._update_game_location_state()

    def _update_game_location_state(self) -> None:
        self.game_location_warning.setVisible(
            not self.settings_page.has_valid_game_folder()
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.profile_editor.confirm_close():
            event.accept()
        else:
            event.ignore()


def _load_runtime_catalog(
    runtime_paths: RuntimePaths,
) -> tuple[CatalogBundle | None, str]:
    root = runtime_paths.catalog_root
    if not (root / "manifest.json").is_file():
        if runtime_paths.mode == "release":
            return None, f"The packaged catalog is missing from {root}."
        return None, "Compile a development catalog under artifacts/catalog to rank gear."
    try:
        bundle = CatalogBundle.load(root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return None, f"Could not load the compiled catalog at {root}: {error}"
    return bundle, f"Catalog: {root}"
