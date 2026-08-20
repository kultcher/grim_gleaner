"""Top-level Grim Gleaner application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QCloseEvent, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import (
    AffixCatalog,
    CatalogBundle,
    ItemCatalog,
    SkillCatalog,
    load_catalog_locale_overlay,
    localize_catalog_bundle,
)
from gd_affix_relevance.domain import BuildProfile, locale_for_code
from gd_affix_relevance.profile_store import load_profile
from gd_affix_relevance.runtime_paths import RuntimePaths, resolve_runtime_paths
from gd_affix_relevance.ui.generate_output import GenerateOutputPage
from gd_affix_relevance.ui.guide import GuidePage
from gd_affix_relevance.ui.i18n import active_locale, t
from gd_affix_relevance.ui.profile_editor import ProfileEditor
from gd_affix_relevance.ui.settings import GAME_LOCALE_SETTING, SettingsPage
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
        user_settings_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grim Gleaner")
        self.resize(1120, 780)
        self.setMinimumSize(880, 620)
        self.settings = settings
        self.runtime_paths = runtime_paths or resolve_runtime_paths()
        if self.settings is not None:
            locale_code = self.settings.value(
                GAME_LOCALE_SETTING,
                self.runtime_paths.locale.code,
                type=str,
            )
            try:
                self.runtime_paths = self.runtime_paths.for_locale(
                    locale_for_code(locale_code)
                )
            except ValueError:
                self.settings.remove(GAME_LOCALE_SETTING)
        self._game_folder_prompted = False
        self._catalog_error_shown = False
        self.catalog_load_error = ""

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
                    startup_notice = t("main_window.profile_not_found_notice")
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

        self.profile_summary = QFrame(sidebar)
        self.profile_summary.setObjectName("sidebarProfileSummary")
        profile_summary_layout = QVBoxLayout(self.profile_summary)
        profile_summary_layout.setContentsMargins(10, 8, 10, 8)
        profile_summary_layout.setSpacing(3)
        profile_title = QLabel(t("main_window.current_profile"), self.profile_summary)
        profile_title.setObjectName("sidebarInfoTitle")
        profile_summary_layout.addWidget(profile_title)
        self.sidebar_profile_name = QLabel(
            t("main_window.new_build_profile"), self.profile_summary
        )
        self.sidebar_profile_name.setObjectName("sidebarProfileName")
        self.sidebar_profile_name.setWordWrap(True)
        profile_summary_layout.addWidget(self.sidebar_profile_name)
        self.sidebar_profile_level = QLabel(
            t("main_window.profile_level", level="90+"), self.profile_summary
        )
        self.sidebar_profile_level.setObjectName("sidebarProfileLevel")
        profile_summary_layout.addWidget(self.sidebar_profile_level)
        sidebar_layout.addWidget(self.profile_summary)

        self.game_location_warning = QLabel(
            t("main_window.game_location_warning"), sidebar
        )
        self.game_location_warning.setObjectName("gameLocationWarning")
        self.game_location_warning.setWordWrap(True)
        sidebar_layout.addWidget(self.game_location_warning)

        self.catalog_warning = QLabel(
            t("main_window.catalog_warning"),
            sidebar,
        )
        self.catalog_warning.setObjectName("catalogLoadWarning")
        self.catalog_warning.setWordWrap(True)
        sidebar_layout.addWidget(self.catalog_warning)
        layout.addWidget(sidebar)

        self.pages = QStackedWidget(central)
        layout.addWidget(self.pages, 1)

        catalog_status = ""
        catalog_for_export = catalog
        if catalog is None and skills is None and items is None:
            bundle, catalog_status = _load_runtime_catalog(self.runtime_paths)
            if bundle is not None:
                catalog = bundle.affixes
                skills = bundle.skills
                items = bundle.items
                catalog_for_export = catalog
            elif self.runtime_paths.mode == "release":
                self.catalog_load_error = catalog_status
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
            t("nav.build_profile"),
            t("nav.build_profile_tooltip"),
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
            t("nav.gear_grades"),
            t("nav.gear_grades_tooltip"),
            self.gear_grades_page_index,
        )
        self.gear_subnavigation_rows: dict[int, int] = {}
        gear_tab_keys = ("tabs.affixes", "tabs.uniques", "tabs.addons")
        for tab_index, key in enumerate(gear_tab_keys):
            title = t(key)
            self.gear_subnavigation_rows[tab_index] = self._add_navigation_item(
                title,
                t("nav.gear_grades_subtab_tooltip", title=title),
                self.gear_grades_page_index,
                tab_index=tab_index,
                child=True,
            )

        self.generate_output_page = GenerateOutputPage(
            catalog_for_export,
            self.profile_editor.profile,
            items=items,
            source_root=self.runtime_paths.tags_root,
            output_root=self.runtime_paths.staging_output_root,
            backups_root=self.runtime_paths.backups_root,
            user_settings_root=user_settings_root,
            locale=self.runtime_paths.locale,
            catalog_status=catalog_status,
            settings=self.settings,
            parent=self.pages,
        )
        self.export_grades_page_index = self.pages.addWidget(
            self.generate_output_page
        )
        self.export_grades_navigation_row = self._add_navigation_item(
            t("nav.export_grades"),
            t("nav.export_grades_tooltip"),
            self.export_grades_page_index,
        )

        self.settings_page = SettingsPage(
            self.settings,
            self.pages,
            runtime_paths=self.runtime_paths,
        )
        self.settings_page.game_folder_changed.connect(self._game_folder_changed)
        self.settings_page.game_locale_changed.connect(self._game_locale_changed)
        self.settings_page_index = self.pages.addWidget(self.settings_page)
        self.settings_navigation_row = self._add_navigation_item(
            t("nav.settings"),
            t("nav.settings_tooltip"),
            self.settings_page_index,
        )

        self.guide_page = GuidePage(self.pages)
        self.guide_page_index = self.pages.addWidget(self.guide_page)
        self.guide_navigation_row = self._add_navigation_item(
            t("nav.guide"),
            t("nav.guide_tooltip"),
            self.guide_page_index,
        )

        self.profile_editor.profile_changed.connect(self.top_matches_page.refresh)
        self.profile_editor.profile_metadata_changed.connect(
            self._update_profile_summary
        )
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
        self._update_profile_summary()
        self._update_game_location_state()
        self.catalog_warning.setVisible(bool(self.catalog_load_error))

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

    def _update_profile_summary(self) -> None:
        profile = self.profile_editor.profile
        self.sidebar_profile_name.setText(
            profile.name.strip() or t("main_window.unnamed_profile")
        )
        self.sidebar_profile_level.setText(
            t("main_window.profile_level", level=profile.level_band)
        )

    def prompt_for_game_folder_if_needed(self) -> None:
        """Prompt once at startup when no confirmed installation is stored."""

        if self._game_folder_prompted or self.settings_page.has_valid_game_folder():
            return
        self._game_folder_prompted = True
        self.navigation.setCurrentRow(self.settings_navigation_row)
        self.settings_page.prompt_for_game_folder()
        self._update_game_location_state()

    def show_startup_prompts(self) -> None:
        """Show release-critical errors before ordinary first-run setup."""

        if self.catalog_load_error and not self._catalog_error_shown:
            self._catalog_error_shown = True
            QMessageBox.critical(
                self,
                t("main_window.catalog_unavailable_title"),
                t(
                    "main_window.catalog_unavailable_body",
                    error=self.catalog_load_error,
                ),
            )
        self.prompt_for_game_folder_if_needed()

    def _game_folder_changed(self, game_folder: str = "") -> None:
        self.generate_output_page.refresh_game_location(game_folder)
        self._update_game_location_state()

    def _game_locale_changed(self, locale_code: str) -> None:
        locale = locale_for_code(locale_code)
        self.runtime_paths = self.runtime_paths.for_locale(locale)
        self.generate_output_page.set_locale(
            locale,
            source_root=self.runtime_paths.tags_root,
            output_root=self.runtime_paths.staging_output_root,
        )

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
            return None, t("main_window.catalog_missing_release", root=root)
        return None, t("main_window.catalog_missing_development")
    try:
        bundle = CatalogBundle.load(root)
        bundle = _localize_catalog_for_ui(bundle, runtime_paths)
    except (OSError, ValueError, KeyError, TypeError) as error:
        return None, t("main_window.catalog_load_error", root=root, error=error)
    return bundle, t("main_window.catalog_status", root=root)


def _localize_catalog_for_ui(
    bundle: CatalogBundle,
    runtime_paths: RuntimePaths,
) -> CatalogBundle:
    """Overlay display names for the configured UI locale, English untouched.

    The catalog display language follows ``ui_locale`` (see ``ui.i18n``),
    not the ``game_locale`` export target: a Russian interface should show
    Russian item names even if grades are still exported to ``text_en``.
    """

    catalog_locale = active_locale()
    if catalog_locale.code == bundle.manifest.locale:
        return bundle
    overlay_paths = runtime_paths.for_locale(catalog_locale)
    overlay = load_catalog_locale_overlay(
        overlay_paths.tags_root, locale=catalog_locale
    )
    return localize_catalog_bundle(bundle, overlay)
