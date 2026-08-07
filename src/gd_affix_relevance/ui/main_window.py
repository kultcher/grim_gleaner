"""Top-level Grim Gleaner application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from gd_affix_relevance.catalog import (
    AffixCatalog,
    CatalogBundle,
    ItemCatalog,
    SkillCatalog,
)
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.ui.generate_output import GenerateOutputPage
from gd_affix_relevance.ui.profile_editor import ProfileEditor
from gd_affix_relevance.ui.top_matches import TopMatchesPage


class MainWindow(QMainWindow):
    def __init__(
        self,
        profile: BuildProfile | None = None,
        parent: QWidget | None = None,
        *,
        catalog: AffixCatalog | None = None,
        skills: SkillCatalog | None = None,
        items: ItemCatalog | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grim Gleaner")
        self.resize(1120, 780)
        self.setMinimumSize(880, 620)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.navigation = QListWidget(central)
        self.navigation.setObjectName("mainNavigation")
        self.navigation.setFixedWidth(190)
        self.navigation.setSpacing(2)
        self.navigation.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        layout.addWidget(self.navigation)

        self.pages = QStackedWidget(central)
        layout.addWidget(self.pages, 1)

        catalog_status = ""
        if catalog is None and skills is None and items is None:
            bundle, catalog_status = _load_development_catalog()
            if bundle is not None:
                catalog = bundle.affixes
                skills = bundle.skills
                items = bundle.items
        catalog = catalog or AffixCatalog(())
        skills = skills or SkillCatalog(())
        items = items or ItemCatalog((), (), (), (), (), ())

        self.profile_editor = ProfileEditor(
            profile, self.pages, skills=skills
        )
        self.pages.addWidget(self.profile_editor)
        self._add_navigation_item("Build Profile", "Set the stats this build values")

        self.top_matches_page = TopMatchesPage(
            catalog,
            self.profile_editor.profile,
            catalog_status=catalog_status,
            skills=skills,
            items=items,
            parent=self.pages,
        )
        self.pages.addWidget(self.top_matches_page)
        self._add_navigation_item("Top Matches", "Rank affixes and gear against this profile")

        source_root, output_root = _development_output_paths()
        self.generate_output_page = GenerateOutputPage(
            catalog,
            self.profile_editor.profile,
            source_root=source_root,
            output_root=output_root,
            catalog_status=catalog_status,
            parent=self.pages,
        )
        self.pages.addWidget(self.generate_output_page)
        self._add_navigation_item(
            "Generate Output",
            "Create a graded Rainbow text_en staging folder",
        )

        self.profile_editor.profile_changed.connect(self.top_matches_page.refresh)
        self.navigation.currentRowChanged.connect(self._navigation_changed)
        self.navigation.setCurrentRow(0)
        self.setCentralWidget(central)

    def _add_navigation_item(self, title: str, tooltip: str) -> None:
        item = QListWidgetItem(title)
        item.setToolTip(tooltip)
        self.navigation.addItem(item)

    def _navigation_changed(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        if index == 1:
            self.top_matches_page.refresh()


def _load_development_catalog() -> tuple[CatalogBundle | None, str]:
    roots = (
        Path.cwd() / "artifacts" / "catalog",
        Path(__file__).resolve().parents[3] / "artifacts" / "catalog",
    )
    failures: list[str] = []
    for root in dict.fromkeys(roots):
        if not (root / "manifest.json").is_file():
            continue
        try:
            bundle = CatalogBundle.load(root)
        except (OSError, ValueError, KeyError, TypeError) as error:
            failures.append(f"{root}: {error}")
            continue
        return bundle, f"Catalog: {root}"
    if failures:
        return None, "Could not load the compiled catalog: " + "; ".join(failures)
    return None, "Compile a development catalog under artifacts/catalog to rank gear."


def _development_output_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[3]
    source_candidates = (
        Path.cwd() / "artifacts" / "text_en",
        project_root / "artifacts" / "text_en",
    )
    source = next((path for path in source_candidates if path.is_dir()), source_candidates[0])
    output = project_root / "artifacts" / "generated" / "text_en"
    return source, output
