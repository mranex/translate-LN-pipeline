from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from manual_studio.core.manual_workflow import SelectionContext
from manual_studio.core.project_index import ProjectIndex
from manual_studio.core.release_service import (
    ReleaseBuildResult,
    ReleaseDiagnostics,
    ReleaseOptions,
    ReleaseService,
)
from manual_studio.core.workspace import Workspace


class ReleaseCenterPage(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, workspace: Workspace | None = None, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        placeholder_workspace = workspace if workspace is not None else Workspace(".")
        self.release_service = ReleaseService(placeholder_workspace)
        self.project_index = ProjectIndex(workspace) if workspace is not None else None
        self.current_context: SelectionContext | None = None
        self.last_build_result: ReleaseBuildResult | None = None
        self._busy = False
        self._build_ui()
        self.refresh_project_data()

    def set_workspace(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.release_service = ReleaseService(workspace)
        self.project_index = ProjectIndex(workspace)
        self.last_build_result = None
        self.refresh_project_data()

    def set_selection_context(self, context: SelectionContext | None) -> None:
        self.current_context = context
        if context is not None:
            self._set_volume_value(context.volume)

    def refresh_project_data(self) -> None:
        current_volume = self._selected_volume()
        volumes = self.project_index.list_volumes() if self.project_index is not None else []

        self.volume_combo.blockSignals(True)
        try:
            self.volume_combo.clear()
            for volume in volumes:
                self.volume_combo.addItem(f"Volume {volume:02d}", volume)
        finally:
            self.volume_combo.blockSignals(False)

        if volumes:
            target_volume = self.current_context.volume if self.current_context is not None else current_volume
            if target_volume in volumes:
                self._set_volume_value(target_volume)
            else:
                self.volume_combo.setCurrentIndex(0)
            self.preview_button.setEnabled(True)
            self.build_button.setEnabled(True)
            self.volume_status_label.setText(f"Discovered {len(volumes)} volume(s).")
        else:
            self.preview_button.setEnabled(False)
            self.build_button.setEnabled(False)
            self.volume_status_label.setText("No source volumes were found for this project.")

        if self.workspace is not None:
            if not self.output_dir_edit.text().strip():
                self.output_dir_edit.setText(str(self.workspace.root / "release_ui"))
            if not self.novel_title_edit.text().strip():
                self.novel_title_edit.setText(self.workspace.root.name)
        self._sync_option_states()
        self._update_open_button()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Release Center")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "Build release JSON, HTML, and optional EPUB outputs from the current manual workflow artifacts."
        )
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        options_panel = QWidget()
        options_layout = QVBoxLayout(options_panel)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.volume_combo = QComboBox()
        form.addRow("Volume", self.volume_combo)

        self.translation_source_combo = QComboBox()
        self.translation_source_combo.addItems(["fixed_if_available", "fixed_only", "draft_only"])
        form.addRow("Translation source", self.translation_source_combo)

        output_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.textChanged.connect(self._update_open_button)
        self.output_browse_button = QPushButton("Browse...")
        self.output_browse_button.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(self.output_browse_button)
        form.addRow("Output folder", output_row)

        self.novel_title_edit = QLineEdit()
        form.addRow("Novel title", self.novel_title_edit)

        self.author_edit = QLineEdit("Unknown")
        form.addRow("Author", self.author_edit)

        self.copy_css_check = QCheckBox("Copy CSS files into the HTML folder")
        self.copy_css_check.toggled.connect(self._sync_option_states)
        form.addRow("Copy CSS", self.copy_css_check)

        css_row = QHBoxLayout()
        self.css_files_edit = QLineEdit()
        self.css_files_edit.setPlaceholderText("Select one or more CSS files")
        self.css_browse_button = QPushButton("Browse...")
        self.css_browse_button.clicked.connect(self._browse_css_files)
        css_row.addWidget(self.css_files_edit, 1)
        css_row.addWidget(self.css_browse_button)
        form.addRow("CSS files", css_row)

        self.pack_epub_check = QCheckBox("Pack an EPUB after writing HTML")
        self.pack_epub_check.toggled.connect(self._sync_option_states)
        form.addRow("Pack EPUB", self.pack_epub_check)

        cover_row = QHBoxLayout()
        self.cover_path_edit = QLineEdit()
        self.cover_path_edit.setPlaceholderText("Optional cover image path")
        self.cover_browse_button = QPushButton("Browse...")
        self.cover_browse_button.clicked.connect(self._browse_cover)
        cover_row.addWidget(self.cover_path_edit, 1)
        cover_row.addWidget(self.cover_browse_button)
        form.addRow("Cover", cover_row)

        self.add_to_calibre_check = QCheckBox("Add the EPUB to Calibre")
        form.addRow("Add to Calibre", self.add_to_calibre_check)
        options_layout.addLayout(form)

        self.volume_status_label = QLabel("")
        self.volume_status_label.setObjectName("mutedLabel")
        self.volume_status_label.setWordWrap(True)
        options_layout.addWidget(self.volume_status_label)

        button_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview Diagnostics")
        self.preview_button.clicked.connect(self._preview_diagnostics)
        self.build_button = QPushButton("Build Release")
        self.build_button.clicked.connect(self._build_release)
        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.clicked.connect(self._open_output_folder)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_project_data)
        button_row.addWidget(self.preview_button)
        button_row.addWidget(self.build_button)
        button_row.addWidget(self.open_output_button)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch(1)
        options_layout.addLayout(button_row)
        options_layout.addStretch(1)

        results_panel = QWidget()
        results_layout = QVBoxLayout(results_panel)
        self.results_status_label = QLabel("Preview diagnostics or build a release to see output paths and messages.")
        self.results_status_label.setObjectName("mutedLabel")
        self.results_status_label.setWordWrap(True)
        results_layout.addWidget(self.results_status_label)

        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setPlaceholderText("Release diagnostics, messages, and output paths will appear here.")
        results_layout.addWidget(self.results_view, 1)

        splitter.addWidget(options_panel)
        splitter.addWidget(results_panel)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

        self._sync_option_states()
        self._update_open_button()

    def _selected_volume(self) -> int | None:
        value = self.volume_combo.currentData()
        if isinstance(value, int):
            return value
        text = self.volume_combo.currentText().strip()
        if not text:
            return None
        try:
            return int(text.split()[-1])
        except Exception:
            return None

    def _set_volume_value(self, volume: int) -> None:
        index = self.volume_combo.findData(volume)
        if index >= 0:
            self.volume_combo.setCurrentIndex(index)

    def _selected_css_files(self) -> list[Path]:
        text = self.css_files_edit.text().strip()
        if not text:
            return []
        return [Path(part.strip()) for part in text.split(";") if part.strip()]

    def _selected_output_dir(self) -> Path | None:
        text = self.output_dir_edit.text().strip()
        return Path(text) if text else None

    def _browse_output_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.output_dir_edit.text().strip() or str(Path.cwd()),
        )
        if selected:
            self.output_dir_edit.setText(selected)

    def _browse_css_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Select CSS Files",
            str(Path.cwd()),
            "CSS Files (*.css);;All Files (*.*)",
        )
        if selected:
            self.css_files_edit.setText("; ".join(selected))

    def _browse_cover(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            str(Path.cwd()),
            "Images (*.jpg *.jpeg *.png);;All Files (*.*)",
        )
        if selected:
            self.cover_path_edit.setText(selected)

    def _sync_option_states(self) -> None:
        css_enabled = self.copy_css_check.isChecked()
        self.css_files_edit.setEnabled(css_enabled)
        self.css_browse_button.setEnabled(css_enabled)

        epub_enabled = self.pack_epub_check.isChecked()
        self.cover_path_edit.setEnabled(epub_enabled)
        self.cover_browse_button.setEnabled(epub_enabled)
        self.add_to_calibre_check.setEnabled(epub_enabled)
        if not epub_enabled:
            self.add_to_calibre_check.setChecked(False)

    def _update_open_button(self) -> None:
        output_dir = self._selected_output_dir()
        self.open_output_button.setEnabled(not self._busy and output_dir is not None and output_dir.exists())

    def _preview_diagnostics(self) -> None:
        volume = self._require_volume()
        if volume is None:
            return

        try:
            self._set_busy(True)
            _chapters, diagnostics = self.release_service.build_volume_json(
                volume,
                self.translation_source_combo.currentText().strip(),
            )
        except Exception as exc:
            self._show_error("Preview Diagnostics Failed", exc)
            return
        finally:
            self._set_busy(False)

        warning = "No translated segments were found for this volume." if diagnostics.translated_segments == 0 else ""
        self.results_status_label.setText(
            warning or f"Previewed diagnostics for volume {volume:02d} using {diagnostics.source_mode}."
        )
        self.results_view.setPlainText(self._format_diagnostics_text(diagnostics))
        if warning:
            self.status_message.emit(warning)
        else:
            self.status_message.emit(f"Previewed release diagnostics for volume {volume:02d}.")

    def _build_release(self) -> None:
        volume = self._require_volume()
        if volume is None:
            return

        output_dir = self._selected_output_dir()
        if output_dir is None:
            self._show_message("Please choose an output folder before building a release.")
            return

        options = ReleaseOptions(
            volume=volume,
            output_dir=output_dir,
            translation_source=self.translation_source_combo.currentText().strip(),
            novel_title=self.novel_title_edit.text().strip(),
            book_author=self.author_edit.text().strip() or "Unknown",
            copy_css=self.copy_css_check.isChecked(),
            css_files=self._selected_css_files(),
            pack_epub=self.pack_epub_check.isChecked(),
            add_to_calibre=self.add_to_calibre_check.isChecked(),
            cover_path=Path(self.cover_path_edit.text().strip()) if self.cover_path_edit.text().strip() else None,
        )

        try:
            self._set_busy(True)
            result = self.release_service.build_release(options)
        except Exception as exc:
            self._show_error("Build Release Failed", exc)
            return
        finally:
            self._set_busy(False)

        self.last_build_result = result
        self.results_status_label.setText(f"Built release outputs for volume {result.volume:02d}.")
        self.results_view.setPlainText(self._format_build_result_text(result))
        self._update_open_button()
        self.status_message.emit(f"Built release outputs for volume {result.volume:02d}.")

    def _open_output_folder(self) -> None:
        path = None
        if self.last_build_result is not None and self.last_build_result.output_dir.exists():
            path = self.last_build_result.output_dir
        else:
            output_dir = self._selected_output_dir()
            if output_dir is not None and output_dir.exists():
                path = output_dir
        if path is None:
            self._show_message("The selected output folder does not exist yet.")
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        if not opened:
            self._show_message(f"Could not open output folder: {path}")
            return
        self.status_message.emit(f"Opened output folder: {path}")

    def _require_volume(self) -> int | None:
        volume = self._selected_volume()
        if volume is None:
            self._show_message("Please select a volume first.")
            return None
        return volume

    def _format_diagnostics_text(self, diagnostics: ReleaseDiagnostics) -> str:
        lines = [
            f"Source mode: {diagnostics.source_mode}",
            f"Total chapters: {diagnostics.total_chapters}",
            f"Total segments: {diagnostics.total_segments}",
            f"Translated segments: {diagnostics.translated_segments}",
            f"Missing segments: {diagnostics.missing_count}",
        ]
        if diagnostics.missing_segments:
            preview = ", ".join(diagnostics.missing_segments[:25])
            if diagnostics.missing_count > len(diagnostics.missing_segments):
                preview += " ..."
            lines.append(f"Missing segment ids: {preview}")
        return "\n".join(lines)

    def _format_build_result_text(self, result: ReleaseBuildResult) -> str:
        lines = [
            f"Volume: {result.volume:02d}",
            "",
            "Output paths:",
            f"- JSON: {result.volume_json_path}" if result.volume_json_path is not None else "- JSON: none",
            f"- HTML dir: {result.html_dir}" if result.html_dir is not None else "- HTML dir: none",
            f"- TOC: {result.toc_path}" if result.toc_path is not None else "- TOC: none",
            f"- EPUB: {result.epub_path}" if result.epub_path is not None else "- EPUB: none",
            f"- Manifest: {result.manifest_path}" if result.manifest_path is not None else "- Manifest: none",
            "",
            "Diagnostics:",
            self._format_diagnostics_text(result.diagnostics),
            "",
            "Messages:",
        ]
        lines.extend(f"- {message}" for message in result.messages)
        return "\n".join(lines)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        elif QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        has_volume = self.volume_combo.count() > 0
        self.preview_button.setEnabled(not busy and has_volume)
        self.build_button.setEnabled(not busy and has_volume)
        self.refresh_button.setEnabled(not busy)
        self.volume_combo.setEnabled(not busy)
        self.translation_source_combo.setEnabled(not busy)
        self.output_dir_edit.setEnabled(not busy)
        self.output_browse_button.setEnabled(not busy)
        self.novel_title_edit.setEnabled(not busy)
        self.author_edit.setEnabled(not busy)
        self.copy_css_check.setEnabled(not busy)
        self.pack_epub_check.setEnabled(not busy)
        self.css_files_edit.setEnabled(not busy and self.copy_css_check.isChecked())
        self.css_browse_button.setEnabled(not busy and self.copy_css_check.isChecked())
        self.cover_path_edit.setEnabled(not busy and self.pack_epub_check.isChecked())
        self.cover_browse_button.setEnabled(not busy and self.pack_epub_check.isChecked())
        self.add_to_calibre_check.setEnabled(not busy and self.pack_epub_check.isChecked())
        self._update_open_button()

    def _show_message(self, message: str) -> None:
        self.results_status_label.setText(message)
        self.status_message.emit(message)

    def _show_error(self, title: str, exc: Exception) -> None:
        message = str(exc)
        self.results_status_label.setText(message)
        self.status_message.emit(message)
        QMessageBox.critical(self, title, message)
