"""Staging-folder generation page for Rainbow-derived localization output."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gd_affix_relevance.catalog import AffixCatalog, ItemCatalog
from gd_affix_relevance.domain import BuildProfile
from gd_affix_relevance.output import RainbowGenerationResult, generate_rainbow_output


class GenerateOutputPage(QWidget):
    def __init__(
        self,
        catalog: AffixCatalog | None,
        profile: BuildProfile,
        *,
        items: ItemCatalog | None = None,
        source_root: Path,
        output_root: Path,
        catalog_status: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.items = items or ItemCatalog((), (), (), (), (), ())
        self.profile = profile
        self.catalog_status = catalog_status
        self.last_result: RainbowGenerationResult | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        heading = QLabel("Generate Output", self)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)
        hint = QLabel(
            "Create a complete staging copy of item-localization files with affix "
            "and unique-item markers for the active profile. This does not write "
            "to the game folder.",
            self,
        )
        hint.setObjectName("pageHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        self.source_edit = QLineEdit(str(source_root), self)
        self.source_edit.setObjectName("outputPath")
        form.addRow("Item text_en source", self._path_row(self.source_edit, True))
        self.output_edit = QLineEdit(str(output_root), self)
        self.output_edit.setObjectName("outputPath")
        form.addRow("Staging output folder", self._path_row(self.output_edit, False))
        layout.addLayout(form)

        action_row = QHBoxLayout()
        self.generate_button = QPushButton("Generate Staging Folder", self)
        self.generate_button.setObjectName("primaryAction")
        self.generate_button.setEnabled(catalog is not None)
        self.generate_button.clicked.connect(self.generate)
        action_row.addWidget(self.generate_button)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.status = QLabel(self)
        self.status.setObjectName("pageHint")
        self.status.setWordWrap(True)
        if catalog is None:
            self.status.setText(catalog_status or "No compiled affix catalog is available.")
        else:
            self.status.setText(catalog_status)
        layout.addWidget(self.status)

        self.preview = QPlainTextEdit(self)
        self.preview.setObjectName("outputPreview")
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText(
            "A summary and sample of changed localization lines will appear here."
        )
        layout.addWidget(self.preview, 1)

    def generate(self, _checked: bool = False) -> None:
        if self.catalog is None:
            return
        try:
            result = generate_rainbow_output(
                Path(self.source_edit.text()),
                Path(self.output_edit.text()),
                self.catalog,
                self.profile,
                items=self.items,
            )
        except (OSError, UnicodeError, ValueError) as error:
            QMessageBox.critical(self, "Could Not Generate Output", str(error))
            return
        self.last_result = result
        self.status.setText(
            f"Generated {result.files_written} files in {result.output_root}. "
            f"Annotated {result.annotated_lines} lines for "
            f"{result.affix_tags_found}/{result.affix_tags_scored} affix tags and "
            f"{result.unique_tags_found}/{result.unique_tags_scored} unique tags."
        )
        self.preview.setPlainText(_format_preview(result, self.profile.name))

    def _path_row(self, line_edit: QLineEdit, require_existing: bool) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(line_edit, 1)
        button = QPushButton("Browse...", row)
        button.setObjectName("profileAction")
        button.clicked.connect(
            lambda: self._browse_directory(line_edit, require_existing)
        )
        layout.addWidget(button)
        return row

    def _browse_directory(
        self,
        line_edit: QLineEdit,
        require_existing: bool,
    ) -> None:
        current = Path(line_edit.text())
        starting = current if current.is_dir() else current.parent
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Folder",
            str(starting),
        )
        if selected:
            line_edit.setText(selected)
        elif not require_existing:
            line_edit.setText(line_edit.text())


def _format_preview(result: RainbowGenerationResult, profile_name: str) -> str:
    lines = [
        f"Profile: {profile_name}",
        f"Output: {result.output_root}",
        f"Files copied: {result.files_written}",
        f"Affix tags found: {result.affix_tags_found}/{result.affix_tags_scored}",
        f"Unique tags found: {result.unique_tags_found}/{result.unique_tags_scored}",
        f"Localization lines changed: {result.annotated_lines}",
        "Catalog tags missing from source: "
        f"{len(result.missing_affix_tags) + len(result.missing_unique_tags)}",
    ]
    if result.changes:
        lines.extend(["", "Changed-line sample:"])
        for change in result.changes[:30]:
            lines.append(
                f"{change.relative_path}:{change.line_number}  {change.after}"
            )
    if result.missing_affix_tags:
        lines.extend(["", "Missing affix-tag sample:"])
        lines.extend(f"- {tag}" for tag in result.missing_affix_tags[:20])
    if result.missing_unique_tags:
        lines.extend(["", "Missing unique-tag sample:"])
        lines.extend(f"- {tag}" for tag in result.missing_unique_tags[:20])
    return "\n".join(lines)
