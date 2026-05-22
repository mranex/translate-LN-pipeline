from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from manual_studio.core.editor_actions import EditResult, EditorActionService, TranslationBundle
from manual_studio.core.editor_index import ArtifactView, EditorSnapshot, EditorRow
from manual_studio.core.jsonio import pretty, read_json
from manual_studio.core.manual_workflow import SelectionContext
from manual_studio.core.series_canon import SeriesCanonService
from manual_studio.core.workspace import Workspace
from manual_studio.ui.raw_edit_panel import RawEditTarget
from manual_studio.ui.raw_json_viewer import RawJsonViewer


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    label: str
    editable: bool = False
    kind: str = "text"


CANON_FILTER_OPTIONS = ("All", "In Series", "New to Series", "Conflict", "Needs Review")


class CanonStatusLens:
    def __init__(self, workspace: Workspace | None):
        self.workspace = workspace
        self.series_service = SeriesCanonService(workspace if workspace is not None else Workspace("."))

    def set_workspace(self, workspace: Workspace | None) -> None:
        self.workspace = workspace
        self.series_service = SeriesCanonService(workspace if workspace is not None else Workspace("."))

    def glossary_flags(self, volume: int | None, entry: dict[str, Any]) -> list[str]:
        in_series = self.find_glossary_series_index(entry) is not None
        conflict = self._has_glossary_conflict(volume, entry)
        flags: list[str] = []
        if conflict:
            flags.append("Conflict")
        if in_series:
            flags.append("In Series")
        else:
            flags.append("New to Series")
        if bool(entry.get("needs_human_review")):
            flags.append("Needs Review")
        return flags

    def relationship_flags(self, volume: int | None, entry: dict[str, Any]) -> list[str]:
        in_series = self.find_relationship_series_index(entry) is not None
        conflict = self._has_relationship_conflict(volume, entry)
        flags: list[str] = []
        if conflict:
            flags.append("Conflict")
        if in_series:
            flags.append("In Series")
        else:
            flags.append("New to Series")
        if bool(entry.get("needs_human_review")):
            flags.append("Needs Review")
        return flags

    def find_glossary_series_index(self, entry: dict[str, Any]) -> int | None:
        for index, candidate in enumerate(self._series_glossary_entries()):
            if self.series_service.glossary_entries_overlap(entry, candidate):
                return index
        return None

    def find_relationship_series_index(self, entry: dict[str, Any]) -> int | None:
        target_identity = self.series_service.relationship_identity(entry)
        if target_identity is None:
            return None
        for index, candidate in enumerate(self._series_relationship_entries()):
            if self.series_service.relationship_identity(candidate) == target_identity:
                return index
        return None

    def _series_glossary_entries(self) -> list[dict[str, Any]]:
        try:
            loaded = self.series_service.load_series_glossary()
        except Exception:
            return []
        entries = loaded.get("volume_merge_glossary")
        return [entry for entry in entries if isinstance(entries, list) and isinstance(entry, dict)] if isinstance(entries, list) else []

    def _series_relationship_entries(self) -> list[dict[str, Any]]:
        try:
            loaded = self.series_service.load_series_relationships()
        except Exception:
            return []
        entries = loaded.get("relationship_pronoun_canon")
        return [entry for entry in entries if isinstance(entries, list) and isinstance(entry, dict)] if isinstance(entries, list) else []

    def _has_glossary_conflict(self, volume: int | None, entry: dict[str, Any]) -> bool:
        if self.workspace is None or volume is None:
            return False
        report = read_json(self.workspace.series_glossary_sync_report(volume), None)
        if not isinstance(report, dict):
            return False
        for section in ("conflicts", "ambiguous"):
            rows = report.get(section)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                volume_entry = row.get("volume_entry")
                if isinstance(volume_entry, dict) and self.series_service.glossary_entries_overlap(entry, volume_entry):
                    return True
        return False

    def _has_relationship_conflict(self, volume: int | None, entry: dict[str, Any]) -> bool:
        if self.workspace is None or volume is None:
            return False
        report = read_json(self.workspace.series_relationships_sync_report(volume), None)
        if not isinstance(report, dict):
            return False
        target_identity = self.series_service.relationship_identity(entry)
        for section in ("conflicts", "ambiguous"):
            rows = report.get(section)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                volume_entry = row.get("volume_entry")
                if not isinstance(volume_entry, dict):
                    continue
                candidate_identity = self.series_service.relationship_identity(volume_entry)
                if target_identity is None:
                    if volume_entry == entry:
                        return True
                    continue
                if candidate_identity == target_identity:
                    return True
        return False


class ArtifactTableTab(QWidget):
    object_selected = pyqtSignal(object)

    def __init__(self, columns: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.columns = columns
        self.rows: list[EditorRow] = []
        self._build_ui()

    def set_view(self, view: ArtifactView) -> None:
        self.rows = list(view.rows)
        self.message_label.setText(view.error or view.message or "")
        self.table.clearContents()
        self.table.setRowCount(len(self.rows))

        for row_index, row in enumerate(self.rows):
            for column_index, (key, _label) in enumerate(self.columns):
                value = row.values.get(key, "")
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_index, column_index, item)

        if self.rows:
            self.table.resizeRowsToContents()
        self.object_selected.emit(None)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.message_label = QLabel("")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.columns)):
            self.table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._emit_selected_object)
        layout.addWidget(self.table, 1)

    def _emit_selected_object(self) -> None:
        row_index = self.table.currentRow()
        if 0 <= row_index < len(self.rows):
            self.object_selected.emit(self.rows[row_index].raw)
        else:
            self.object_selected.emit(None)


class EditableVolumeTableTab(QWidget):
    object_selected = pyqtSignal(object)
    dirty_changed = pyqtSignal(bool)
    status_message = pyqtSignal(str)
    artifact_written = pyqtSignal()
    reload_requested = pyqtSignal()
    open_series_canon_requested = pyqtSignal(str, object, int)

    def __init__(
        self,
        *,
        artifact_label: str,
        list_key: str,
        canon_kind: str,
        canon_lens: CanonStatusLens,
        columns: list[ColumnSpec],
        raw_edit_title: str,
        default_row_factory: Callable[[], dict[str, Any]],
        save_callback: Callable[[int, dict[str, Any]], EditResult],
        approve_callback: Callable[[int], EditResult],
        approve_button_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.artifact_label = artifact_label
        self.list_key = list_key
        self.canon_kind = canon_kind
        self.canon_lens = canon_lens
        self.columns = columns
        self.raw_edit_title = raw_edit_title
        self.default_row_factory = default_row_factory
        self.save_callback = save_callback
        self.approve_callback = approve_callback
        self.approve_button_text = approve_button_text
        self.current_volume: int | None = None
        self.artifact: dict[str, Any] | None = None
        self._canon_flags_by_row: list[list[str]] = []
        self._dirty = False
        self._loading_table = False
        self._build_ui()

    def set_view(self, volume: int | None, view: ArtifactView) -> None:
        self.current_volume = volume
        self.message_label.setText(view.error or view.message or "")

        if view.error or not isinstance(view.raw_object, dict):
            self.artifact = None
            self._rebuild_table([])
            self._canon_flags_by_row = []
            self._set_controls_enabled(False)
            self._set_dirty(False)
            self.object_selected.emit(None)
            return

        self.artifact = copy.deepcopy(view.raw_object)
        row_list = self._row_list()
        if row_list is None:
            self.artifact = None
            self._rebuild_table([])
            self._canon_flags_by_row = []
            self._set_controls_enabled(False)
            self._set_dirty(False)
            self.message_label.setText(
                f"The loaded {self.artifact_label.lower()} is missing a valid '{self.list_key}' list."
            )
            self.object_selected.emit(None)
            return

        self._rebuild_table(row_list)
        self._refresh_canon_overlay()
        self._set_controls_enabled(volume is not None)
        self._set_dirty(False)
        self.table.clearSelection()
        self.object_selected.emit(None)

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def resolve_unsaved_changes(self, parent: QWidget, reason: str) -> bool:
        if not self._dirty:
            return True

        choice = self._unsaved_choice(parent, reason)
        if choice == QMessageBox.StandardButton.Save:
            return self._save_draft(show_success=True, emit_change=False)
        if choice == QMessageBox.StandardButton.Discard:
            self._set_dirty(False)
            return True
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        button_row = QHBoxLayout()
        self.add_row_button = QPushButton("Add Row")
        self.duplicate_row_button = QPushButton("Duplicate Row")
        self.delete_row_button = QPushButton("Delete Row")
        self.save_button = QPushButton("Save Draft")
        self.reload_button = QPushButton("Reload/Revert")
        self.approve_button = QPushButton(self.approve_button_text)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(CANON_FILTER_OPTIONS))
        self.open_in_series_button = QPushButton("Open in Series Canon")
        self.add_row_button.clicked.connect(self._add_row)
        self.duplicate_row_button.clicked.connect(self._duplicate_row)
        self.delete_row_button.clicked.connect(self._delete_row)
        self.save_button.clicked.connect(lambda: self._save_draft(show_success=True, emit_change=True))
        self.reload_button.clicked.connect(self._reload)
        self.approve_button.clicked.connect(self._approve)
        self.filter_combo.currentTextChanged.connect(lambda _text: self._apply_filter())
        self.open_in_series_button.clicked.connect(self._open_in_series_canon)
        for button in (
            self.add_row_button,
            self.duplicate_row_button,
            self.delete_row_button,
            self.save_button,
            self.reload_button,
            self.approve_button,
        ):
            button_row.addWidget(button)
        button_row.addWidget(QLabel("Filter"))
        button_row.addWidget(self.filter_combo)
        button_row.addWidget(self.open_in_series_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.message_label = QLabel("")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.table = QTableWidget(0, len(self.columns))
        self._configure_table(self.table, editable=True)
        self.table.itemSelectionChanged.connect(self._emit_selected_object)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in (
            self.add_row_button,
            self.duplicate_row_button,
            self.delete_row_button,
            self.save_button,
            self.reload_button,
            self.approve_button,
        ):
            button.setEnabled(enabled)
        self.table.setEnabled(enabled)
        self.filter_combo.setEnabled(enabled)
        self.open_in_series_button.setEnabled(enabled)

    def _row_list(self) -> list[dict[str, Any]] | None:
        if self.artifact is None:
            return None
        row_list = self.artifact.get(self.list_key)
        return row_list if isinstance(row_list, list) else None

    def _rebuild_table(self, rows: list[dict[str, Any]]) -> None:
        self._loading_table = True
        self.table.blockSignals(True)
        try:
            self.table.clearContents()
            self.table.setRowCount(len(rows))
            for row_index, row in enumerate(rows):
                self._populate_detail_row(self.table, row_index, row, self.columns)
            if rows:
                self.table.resizeRowsToContents()
        finally:
            self.table.blockSignals(False)
            self._loading_table = False

    def _refresh_canon_overlay(self) -> None:
        rows = self._row_list() or []
        if self.canon_kind == "glossary":
            self._canon_flags_by_row = [
                self.canon_lens.glossary_flags(self.current_volume, row if isinstance(row, dict) else {})
                for row in rows
            ]
        else:
            self._canon_flags_by_row = [
                self.canon_lens.relationship_flags(self.current_volume, row if isinstance(row, dict) else {})
                for row in rows
            ]
        self._update_canon_status_cells(self.table, self._canon_flags_by_row)
        self._apply_filter()

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_table:
            return
        rows = self._row_list()
        if rows is None:
            return
        row_index = item.row()
        column_index = item.column()
        if not (0 <= row_index < len(rows) and 0 <= column_index < len(self.columns)):
            return
        column = self.columns[column_index]
        if not column.editable:
            return
        self._apply_item_value(rows[row_index], column, item)
        self._refresh_canon_overlay()
        self._set_dirty(True)
        if row_index == self.table.currentRow():
            self.object_selected.emit(rows[row_index])

    def _emit_selected_object(self) -> None:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if rows is not None and 0 <= row_index < len(rows):
            self.object_selected.emit(rows[row_index])
        else:
            self.object_selected.emit(None)

    def raw_edit_descriptor(self) -> tuple[RawEditTarget | None, str]:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if rows is None or not (0 <= row_index < len(rows)) or not isinstance(rows[row_index], dict):
            return None, f"Select a {self.raw_edit_title.lower()} row to edit it as raw JSON."
        return (
            RawEditTarget(
                title=self.raw_edit_title,
                obj=copy.deepcopy(rows[row_index]),
                selection_key=f"{self.artifact_label}:{row_index}",
                apply_callback=lambda obj, target_index=row_index: self._apply_raw_edit_at_index(target_index, obj),
                message="Applied changes stay in memory until you save this tab.",
            ),
            "",
        )

    def apply_raw_edit_object(self, obj: dict[str, Any]) -> str:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if rows is None or not (0 <= row_index < len(rows)):
            raise ValueError(f"Select a {self.raw_edit_title.lower()} row before applying raw JSON.")
        return self._apply_raw_edit_at_index(row_index, obj)

    def _apply_raw_edit_at_index(self, row_index: int, obj: dict[str, Any] | list[Any]) -> str:
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object for this selection.")
        rows = self._row_list()
        if rows is None or not (0 <= row_index < len(rows)):
            raise ValueError(f"Select a {self.raw_edit_title.lower()} row before applying raw JSON.")
        rows[row_index] = copy.deepcopy(obj)
        self._rebuild_table(rows)
        self._refresh_canon_overlay()
        self.table.selectRow(row_index)
        self._set_dirty(True)
        self.object_selected.emit(rows[row_index])
        return f"Applied in memory. Click Save Draft to write the {self.artifact_label.lower()} artifact."

    def _add_row(self) -> None:
        rows = self._row_list()
        if rows is None:
            return
        rows.append(self.default_row_factory())
        self._rebuild_table(rows)
        self._refresh_canon_overlay()
        self.table.selectRow(len(rows) - 1)
        self._set_dirty(True)
        self.status_message.emit(f"Added a new row to {self.artifact_label.lower()}.")

    def _duplicate_row(self) -> None:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if rows is None or not (0 <= row_index < len(rows)):
            self.status_message.emit("Select a row to duplicate.")
            return
        rows.insert(row_index + 1, copy.deepcopy(rows[row_index]))
        self._rebuild_table(rows)
        self._refresh_canon_overlay()
        self.table.selectRow(row_index + 1)
        self._set_dirty(True)
        self.status_message.emit(f"Duplicated a row in {self.artifact_label.lower()}.")

    def _delete_row(self) -> None:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if rows is None or not (0 <= row_index < len(rows)):
            self.status_message.emit("Select a row to delete.")
            return
        rows.pop(row_index)
        self._rebuild_table(rows)
        self._refresh_canon_overlay()
        if rows:
            self.table.selectRow(min(row_index, len(rows) - 1))
        self._set_dirty(True)
        self.status_message.emit(f"Deleted a row from {self.artifact_label.lower()}.")

    def _reload(self) -> None:
        if not self.resolve_unsaved_changes(self, "reloading this tab"):
            return
        self.reload_requested.emit()

    def _save_draft(self, show_success: bool, emit_change: bool) -> bool:
        if self.current_volume is None or self.artifact is None:
            self.status_message.emit(f"{self.artifact_label} is not available for saving.")
            return False
        try:
            result = self.save_callback(self.current_volume, copy.deepcopy(self.artifact))
        except Exception as exc:
            QMessageBox.critical(self, "Save Draft Failed", str(exc))
            self.status_message.emit(str(exc))
            return False

        self._set_dirty(False)
        if show_success:
            self.status_message.emit(result.message)
        if emit_change:
            self.artifact_written.emit()
        return True

    def _approve(self) -> None:
        if self.current_volume is None:
            self.status_message.emit(f"{self.artifact_label} is not available for approval.")
            return
        if self._dirty:
            choice = self._save_before_continue_choice(self, "Save the current draft before approving?")
            if choice != QMessageBox.StandardButton.Save:
                return
            if not self._save_draft(show_success=False, emit_change=False):
                return

        confirm = QMessageBox.question(
            self,
            self.approve_button_text,
            f"Approve the current {self.artifact_label.lower()} draft into the finalized artifact?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.approve_callback(self.current_volume)
        except Exception as exc:
            QMessageBox.critical(self, "Approve Failed", str(exc))
            self.status_message.emit(str(exc))
            return

        self.status_message.emit(result.message)
        self.artifact_written.emit()

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def _configure_table(self, table: QTableWidget, editable: bool) -> None:
        table.setHorizontalHeaderLabels([column.label for column in self.columns])
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.columns)):
            table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        if not editable:
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def _populate_detail_row(
        self,
        table: QTableWidget,
        row_index: int,
        row: dict[str, Any],
        columns: list[ColumnSpec],
    ) -> None:
        for column_index, column in enumerate(columns):
            table.setItem(row_index, column_index, self._build_detail_item(row, column))

    def _build_detail_item(self, row: dict[str, Any], column: ColumnSpec) -> QTableWidgetItem:
        if column.kind == "bool":
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if column.editable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if bool(row.get(column.key)) else Qt.CheckState.Unchecked)
            return item

        if column.kind == "count":
            value = len(row.get(column.key) or [])
        else:
            value = row.get(column.key, "")

        item = QTableWidgetItem("" if value is None else str(value))
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if column.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        return item

    def _apply_item_value(self, row: dict[str, Any], column: ColumnSpec, item: QTableWidgetItem) -> None:
        if column.kind == "bool":
            row[column.key] = item.checkState() == Qt.CheckState.Checked
        else:
            row[column.key] = item.text()

    def _canon_status_column_index(self) -> int:
        for index, column in enumerate(self.columns):
            if column.key == "canon_status":
                return index
        return -1

    def _update_canon_status_cells(self, table: QTableWidget, flags_by_row: list[list[str]]) -> None:
        column_index = self._canon_status_column_index()
        if column_index < 0:
            return
        for row_index, flags in enumerate(flags_by_row):
            item = table.item(row_index, column_index)
            if item is None:
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row_index, column_index, item)
            item.setText(", ".join(flags))

    def _apply_filter(self) -> None:
        selected_filter = self.filter_combo.currentText().strip() or "All"
        for row_index, flags in enumerate(self._canon_flags_by_row):
            visible = selected_filter == "All" or selected_filter in flags
            self.table.setRowHidden(row_index, not visible)
        current_row = self.table.currentRow()
        if 0 <= current_row < len(self._canon_flags_by_row) and not self.table.isRowHidden(current_row):
            return
        for row_index in range(self.table.rowCount()):
            if not self.table.isRowHidden(row_index):
                self.table.selectRow(row_index)
                return
        self.table.clearSelection()

    def _open_in_series_canon(self) -> None:
        rows = self._row_list()
        row_index = self.table.currentRow()
        if self.current_volume is None or rows is None or not (0 <= row_index < len(rows)):
            self.status_message.emit("Select a canon row before opening it in Series Canon.")
            return
        self.open_series_canon_requested.emit(self.canon_kind, copy.deepcopy(rows[row_index]), self.current_volume)

    def _unsaved_choice(self, parent: QWidget, reason: str) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText(f"{self.artifact_label} has unsaved changes.")
        box.setInformativeText(f"What would you like to do before {reason}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def _save_before_continue_choice(self, parent: QWidget, message: str) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText(f"{self.artifact_label} has unsaved changes.")
        box.setInformativeText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())


class EditableSegmentJsonlTab(QWidget):
    object_selected = pyqtSignal(object)
    dirty_changed = pyqtSignal(bool)
    status_message = pyqtSignal(str)
    artifact_written = pyqtSignal()
    reload_requested = pyqtSignal()
    open_series_canon_requested = pyqtSignal(str, object, int)

    def __init__(
        self,
        *,
        artifact_label: str,
        canon_kind: str,
        canon_lens: CanonStatusLens,
        summary_columns: list[tuple[str, str]],
        detail_columns: list[ColumnSpec],
        raw_edit_title: str,
        load_callback: Callable[[int, str], Any],
        save_callback: Callable[[int, str, dict[str, Any]], EditResult],
        list_getter: Callable[[dict[str, Any]], tuple[str, list[Any]]],
        default_entry_factory: Callable[[], dict[str, Any]],
        add_button_text: str,
        duplicate_button_text: str,
        delete_button_text: str,
        save_button_text: str,
        parent=None,
    ):
        super().__init__(parent)
        self.artifact_label = artifact_label
        self.canon_kind = canon_kind
        self.canon_lens = canon_lens
        self.summary_columns = summary_columns
        self.detail_columns = detail_columns
        self.raw_edit_title = raw_edit_title
        self.load_callback = load_callback
        self.save_callback = save_callback
        self.list_getter = list_getter
        self.default_entry_factory = default_entry_factory
        self.add_button_text = add_button_text
        self.duplicate_button_text = duplicate_button_text
        self.delete_button_text = delete_button_text
        self.save_button_text = save_button_text
        self.current_context: SelectionContext | None = None
        self.current_volume: int | None = None
        self.summary_rows: list[EditorRow] = []
        self.current_segment_id: str | None = None
        self.current_row_wrapper: dict[str, Any] | None = None
        self.current_result: dict[str, Any] | None = None
        self.current_list_key: str | None = None
        self._canon_flags_by_row: list[list[str]] = []
        self._dirty = False
        self._loading_summary = False
        self._loading_detail = False
        self._build_ui()

    def set_view(self, context: SelectionContext | None, view: ArtifactView) -> None:
        self.current_context = context
        self.current_volume = context.volume if context is not None else None
        self.summary_rows = list(view.rows)
        self.message_label.setText(view.error or view.message or "")
        self._rebuild_summary_table()

        preferred_segment_id: str | None = None
        if context is not None and context.scope == "segment" and context.segment is not None:
            preferred_segment_id = str(context.segment)
        elif self.current_segment_id and self._summary_row_index_for_segment(self.current_segment_id) >= 0:
            preferred_segment_id = self.current_segment_id
        elif self.summary_rows:
            preferred_segment_id = self._segment_id_for_summary_row(0)

        self._set_dirty(False)
        if preferred_segment_id:
            self._select_summary_row(preferred_segment_id)
            self._load_segment(preferred_segment_id, quiet=True)
        else:
            self._canon_flags_by_row = []
            self._clear_detail("Select a segment summary row to edit its artifact details.")

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def resolve_unsaved_changes(self, parent: QWidget, reason: str) -> bool:
        if not self._dirty:
            return True
        choice = self._unsaved_choice(parent, reason)
        if choice == QMessageBox.StandardButton.Save:
            return self._save_current(show_success=True, emit_change=False)
        if choice == QMessageBox.StandardButton.Discard:
            self._set_dirty(False)
            return True
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.message_label = QLabel("")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        layout.addWidget(QLabel("Summary"))
        self.summary_table = QTableWidget(0, len(self.summary_columns))
        self.summary_table.setHorizontalHeaderLabels([label for _key, label in self.summary_columns])
        self.summary_table.setAlternatingRowColors(False)
        self.summary_table.setShowGrid(False)
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.summary_columns)):
            self.summary_table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.summary_table.itemSelectionChanged.connect(self._on_summary_selection_changed)
        layout.addWidget(self.summary_table, 1)

        detail_header = QHBoxLayout()
        detail_header.addWidget(QLabel("Editing Segment"))
        self.segment_label = QLabel("No segment selected")
        self.segment_label.setObjectName("mutedLabel")
        detail_header.addWidget(self.segment_label)
        detail_header.addStretch(1)
        layout.addLayout(detail_header)

        self.detail_status_label = QLabel("Select a segment summary row to edit its artifact details.")
        self.detail_status_label.setObjectName("mutedLabel")
        self.detail_status_label.setWordWrap(True)
        layout.addWidget(self.detail_status_label)

        button_row = QHBoxLayout()
        self.add_button = QPushButton(self.add_button_text)
        self.duplicate_button = QPushButton(self.duplicate_button_text)
        self.delete_button = QPushButton(self.delete_button_text)
        self.save_button = QPushButton(self.save_button_text)
        self.reload_button = QPushButton("Reload/Revert")
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(list(CANON_FILTER_OPTIONS))
        self.open_in_series_button = QPushButton("Open in Series Canon")
        self.add_button.clicked.connect(self._add_entry)
        self.duplicate_button.clicked.connect(self._duplicate_entry)
        self.delete_button.clicked.connect(self._delete_entry)
        self.save_button.clicked.connect(lambda: self._save_current(show_success=True, emit_change=True))
        self.reload_button.clicked.connect(self._reload)
        self.filter_combo.currentTextChanged.connect(lambda _text: self._apply_filter())
        self.open_in_series_button.clicked.connect(self._open_in_series_canon)
        for button in (self.add_button, self.duplicate_button, self.delete_button, self.save_button, self.reload_button):
            button_row.addWidget(button)
        button_row.addWidget(QLabel("Filter"))
        button_row.addWidget(self.filter_combo)
        button_row.addWidget(self.open_in_series_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.detail_table = QTableWidget(0, len(self.detail_columns))
        self.detail_table.setHorizontalHeaderLabels([column.label for column in self.detail_columns])
        self.detail_table.setAlternatingRowColors(False)
        self.detail_table.setShowGrid(False)
        self.detail_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.detail_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.detail_table.verticalHeader().setVisible(False)
        self.detail_table.horizontalHeader().setStretchLastSection(True)
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.detail_columns)):
            self.detail_table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.detail_table.itemSelectionChanged.connect(self._emit_detail_object)
        self.detail_table.itemChanged.connect(self._on_detail_item_changed)
        layout.addWidget(self.detail_table, 2)

        self._set_detail_controls_enabled(False)

    def _rebuild_summary_table(self) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            self.summary_table.clearContents()
            self.summary_table.setRowCount(len(self.summary_rows))
            for row_index, row in enumerate(self.summary_rows):
                for column_index, (key, _label) in enumerate(self.summary_columns):
                    value = row.values.get(key, "")
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.summary_table.setItem(row_index, column_index, item)
            if self.summary_rows:
                self.summary_table.resizeRowsToContents()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _summary_row_index_for_segment(self, segment_id: str | None) -> int:
        if not segment_id:
            return -1
        for index, row in enumerate(self.summary_rows):
            if str(row.values.get("item_id") or "") == str(segment_id):
                return index
        return -1

    def _segment_id_for_summary_row(self, row_index: int) -> str | None:
        if 0 <= row_index < len(self.summary_rows):
            value = self.summary_rows[row_index].values.get("item_id")
            return str(value) if value else None
        return None

    def _select_summary_row(self, segment_id: str | None) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            row_index = self._summary_row_index_for_segment(segment_id)
            if row_index >= 0:
                self.summary_table.selectRow(row_index)
            else:
                self.summary_table.clearSelection()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _on_summary_selection_changed(self) -> None:
        if self._loading_summary:
            return
        row_index = self.summary_table.currentRow()
        segment_id = self._segment_id_for_summary_row(row_index)
        if not segment_id:
            return
        if segment_id == self.current_segment_id:
            self._emit_detail_object()
            return
        previous_segment_id = self.current_segment_id
        if self._dirty and not self.resolve_unsaved_changes(self, f"loading segment {segment_id}"):
            self._select_summary_row(previous_segment_id)
            return
        self._load_segment(segment_id, quiet=False)

    def _load_segment(self, segment_id: str, quiet: bool) -> None:
        if self.current_volume is None:
            self._clear_detail("A volume must be selected before segment editing is available.")
            return
        try:
            loaded = self.load_callback(self.current_volume, segment_id)
        except Exception as exc:
            self._clear_detail(str(exc))
            self.status_message.emit(str(exc))
            if not quiet:
                QMessageBox.critical(self, f"{self.artifact_label} Load Failed", str(exc))
            return

        self.current_segment_id = loaded.item_id
        self.current_row_wrapper = copy.deepcopy(loaded.row)
        self.current_result = copy.deepcopy(loaded.result)
        self.current_list_key, entries = self.list_getter(self.current_result)
        self.segment_label.setText(loaded.item_id)
        if loaded.exists:
            self.detail_status_label.setText(loaded.message or "Editing the saved artifact row for this segment.")
        else:
            self.detail_status_label.setText(loaded.message or "Editing an in-memory result until save.")
        self._rebuild_detail_table(entries)
        self._refresh_canon_overlay()
        self._set_detail_controls_enabled(True)
        self._set_dirty(False)
        self.object_selected.emit(self.current_row_wrapper)

    def _clear_detail(self, message: str) -> None:
        self.current_segment_id = None
        self.current_row_wrapper = None
        self.current_result = None
        self.current_list_key = None
        self._canon_flags_by_row = []
        self.segment_label.setText("No segment selected")
        self.detail_status_label.setText(message)
        self._rebuild_detail_table([])
        self._set_detail_controls_enabled(False)
        self._set_dirty(False)
        self.object_selected.emit(None)

    def _entries(self) -> list[dict[str, Any]] | None:
        if self.current_result is None or self.current_list_key is None:
            return None
        entries = self.current_result.get(self.current_list_key)
        return entries if isinstance(entries, list) else None

    def _rebuild_detail_table(self, entries: list[Any]) -> None:
        self._loading_detail = True
        self.detail_table.blockSignals(True)
        try:
            self.detail_table.clearContents()
            self.detail_table.setRowCount(len(entries))
            for row_index, entry in enumerate(entries):
                row = entry if isinstance(entry, dict) else {}
                for column_index, column in enumerate(self.detail_columns):
                    self.detail_table.setItem(row_index, column_index, self._build_detail_item(row, column))
            if entries:
                self.detail_table.resizeRowsToContents()
        finally:
            self.detail_table.blockSignals(False)
            self._loading_detail = False

    def _refresh_canon_overlay(self) -> None:
        entries = self._entries() or []
        if self.canon_kind == "glossary":
            self._canon_flags_by_row = [
                self.canon_lens.glossary_flags(self.current_volume, entry if isinstance(entry, dict) else {})
                for entry in entries
            ]
        else:
            self._canon_flags_by_row = [
                self.canon_lens.relationship_flags(self.current_volume, entry if isinstance(entry, dict) else {})
                for entry in entries
            ]
        self._update_canon_status_cells(self.detail_table, self._canon_flags_by_row)
        self._apply_filter()

    def _build_detail_item(self, row: dict[str, Any], column: ColumnSpec) -> QTableWidgetItem:
        if column.kind == "bool":
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if column.editable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if bool(row.get(column.key)) else Qt.CheckState.Unchecked)
            return item

        if column.kind == "count":
            value = len(row.get(column.key) or [])
        else:
            value = row.get(column.key, "")

        item = QTableWidgetItem("" if value is None else str(value))
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if column.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        return item

    def _on_detail_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_detail:
            return
        entries = self._entries()
        if entries is None:
            return
        row_index = item.row()
        column_index = item.column()
        if not (0 <= row_index < len(entries) and 0 <= column_index < len(self.detail_columns)):
            return
        entry = entries[row_index]
        if not isinstance(entry, dict):
            entry = {}
            entries[row_index] = entry
        column = self.detail_columns[column_index]
        if not column.editable:
            return
        if column.kind == "bool":
            entry[column.key] = item.checkState() == Qt.CheckState.Checked
        else:
            entry[column.key] = item.text()
        self._refresh_canon_overlay()
        self._set_dirty(True)
        if row_index == self.detail_table.currentRow():
            self.object_selected.emit(entry)

    def _emit_detail_object(self) -> None:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if entries is not None and 0 <= row_index < len(entries) and isinstance(entries[row_index], dict):
            self.object_selected.emit(entries[row_index])
        elif self.current_row_wrapper is not None:
            self.object_selected.emit(self.current_row_wrapper)
        else:
            self.object_selected.emit(None)

    def raw_edit_descriptor(self) -> tuple[RawEditTarget | None, str]:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if entries is None or not (0 <= row_index < len(entries)) or not isinstance(entries[row_index], dict):
            return None, f"Select a detail row to edit a {self.raw_edit_title.lower()} as raw JSON."
        return (
            RawEditTarget(
                title=self.raw_edit_title,
                obj=copy.deepcopy(entries[row_index]),
                selection_key=f"{self.artifact_label}:{self.current_segment_id}:{row_index}",
                apply_callback=lambda obj, target_segment_id=self.current_segment_id, target_index=row_index: self._apply_raw_edit_at_index(
                    target_segment_id,
                    target_index,
                    obj,
                ),
                message="Applied changes stay in memory until you use this tab's Save button.",
            ),
            "",
        )

    def apply_raw_edit_object(self, obj: dict[str, Any]) -> str:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if entries is None or not (0 <= row_index < len(entries)):
            raise ValueError(f"Select a detail row before applying raw JSON to this {self.raw_edit_title.lower()}.")
        return self._apply_raw_edit_at_index(self.current_segment_id, row_index, obj)

    def _apply_raw_edit_at_index(
        self,
        expected_segment_id: str | None,
        row_index: int,
        obj: dict[str, Any] | list[Any],
    ) -> str:
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object for this selection.")
        if expected_segment_id is not None and self.current_segment_id != expected_segment_id:
            raise ValueError("The selected segment changed before this raw edit could be applied. Re-select the original row or reset the panel.")
        entries = self._entries()
        if entries is None or not (0 <= row_index < len(entries)):
            raise ValueError(f"Select a detail row before applying raw JSON to this {self.raw_edit_title.lower()}.")
        entries[row_index] = copy.deepcopy(obj)
        self._rebuild_detail_table(entries)
        self._refresh_canon_overlay()
        self.detail_table.selectRow(row_index)
        self._set_dirty(True)
        self.object_selected.emit(entries[row_index])
        return f"Applied in memory. Click Save to write the {self.artifact_label.lower()} artifact."

    def _add_entry(self) -> None:
        entries = self._entries()
        if entries is None:
            self.status_message.emit("Select a segment before adding entries.")
            return
        entries.append(self.default_entry_factory())
        self._rebuild_detail_table(entries)
        self._refresh_canon_overlay()
        self.detail_table.selectRow(len(entries) - 1)
        self._set_dirty(True)
        self.status_message.emit(f"Added a new item to {self.artifact_label.lower()}.")

    def _duplicate_entry(self) -> None:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if entries is None or not (0 <= row_index < len(entries)):
            self.status_message.emit("Select a row to duplicate.")
            return
        entries.insert(row_index + 1, copy.deepcopy(entries[row_index]))
        self._rebuild_detail_table(entries)
        self._refresh_canon_overlay()
        self.detail_table.selectRow(row_index + 1)
        self._set_dirty(True)
        self.status_message.emit(f"Duplicated a row in {self.artifact_label.lower()}.")

    def _delete_entry(self) -> None:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if entries is None or not (0 <= row_index < len(entries)):
            self.status_message.emit("Select a row to delete.")
            return
        entries.pop(row_index)
        self._rebuild_detail_table(entries)
        self._refresh_canon_overlay()
        if entries:
            self.detail_table.selectRow(min(row_index, len(entries) - 1))
        self._set_dirty(True)
        self.status_message.emit(f"Deleted a row from {self.artifact_label.lower()}.")

    def _reload(self) -> None:
        if not self.resolve_unsaved_changes(self, "reloading this tab"):
            return
        self.reload_requested.emit()

    def _save_current(self, show_success: bool, emit_change: bool) -> bool:
        if self.current_volume is None or self.current_segment_id is None or self.current_result is None:
            self.status_message.emit(f"{self.artifact_label} is not available for saving.")
            return False
        try:
            result = self.save_callback(self.current_volume, self.current_segment_id, copy.deepcopy(self.current_result))
        except Exception as exc:
            QMessageBox.critical(self, f"{self.artifact_label} Save Failed", str(exc))
            self.status_message.emit(str(exc))
            return False

        self._set_dirty(False)
        if show_success:
            self.status_message.emit(result.message)
        if emit_change:
            self.artifact_written.emit()
        return True

    def _set_detail_controls_enabled(self, enabled: bool) -> None:
        for button in (self.add_button, self.duplicate_button, self.delete_button, self.save_button, self.reload_button):
            button.setEnabled(enabled)
        self.detail_table.setEnabled(enabled)
        self.filter_combo.setEnabled(enabled)
        self.open_in_series_button.setEnabled(enabled)

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def _unsaved_choice(self, parent: QWidget, reason: str) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText(f"{self.artifact_label} has unsaved changes.")
        box.setInformativeText(f"What would you like to do before {reason}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())

    def _canon_status_column_index(self) -> int:
        for index, column in enumerate(self.detail_columns):
            if column.key == "canon_status":
                return index
        return -1

    def _update_canon_status_cells(self, table: QTableWidget, flags_by_row: list[list[str]]) -> None:
        column_index = self._canon_status_column_index()
        if column_index < 0:
            return
        for row_index, flags in enumerate(flags_by_row):
            item = table.item(row_index, column_index)
            if item is None:
                item = QTableWidgetItem("")
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                table.setItem(row_index, column_index, item)
            item.setText(", ".join(flags))

    def _apply_filter(self) -> None:
        selected_filter = self.filter_combo.currentText().strip() or "All"
        for row_index, flags in enumerate(self._canon_flags_by_row):
            visible = selected_filter == "All" or selected_filter in flags
            self.detail_table.setRowHidden(row_index, not visible)
        current_row = self.detail_table.currentRow()
        if 0 <= current_row < len(self._canon_flags_by_row) and not self.detail_table.isRowHidden(current_row):
            return
        for row_index in range(self.detail_table.rowCount()):
            if not self.detail_table.isRowHidden(row_index):
                self.detail_table.selectRow(row_index)
                return
        self.detail_table.clearSelection()

    def _open_in_series_canon(self) -> None:
        entries = self._entries()
        row_index = self.detail_table.currentRow()
        if self.current_volume is None or entries is None or not (0 <= row_index < len(entries)):
            self.status_message.emit("Select a canon row before opening it in Series Canon.")
            return
        entry = entries[row_index]
        if not isinstance(entry, dict):
            self.status_message.emit("Select a canon row before opening it in Series Canon.")
            return
        self.open_series_canon_requested.emit(self.canon_kind, copy.deepcopy(entry), self.current_volume)


class EditableDialogueLabelsTab(QWidget):
    object_selected = pyqtSignal(object)
    dirty_changed = pyqtSignal(bool)
    status_message = pyqtSignal(str)
    artifact_written = pyqtSignal()
    reload_requested = pyqtSignal()

    def __init__(self, editor_actions: EditorActionService, parent=None):
        super().__init__(parent)
        self.editor_actions = editor_actions
        self.summary_columns = [
            ("item_id", "Item ID"),
            ("status", "Status"),
            ("segment", "Segment"),
            ("units_count", "Units"),
            ("review_count", "Review"),
            ("low_confidence_count", "Low Confidence"),
            ("labeled_source_preview", "Preview"),
        ]
        self.unit_columns = [
            ColumnSpec("unit_id", "Unit ID"),
            ColumnSpec("index", "Index"),
            ColumnSpec("line_index", "Line Index"),
            ColumnSpec("speaker", "Speaker", True),
            ColumnSpec("listener", "Listener", True),
            ColumnSpec("source_text", "Source Text", True),
            ColumnSpec("confidence", "Confidence", True),
            ColumnSpec("review_required", "Review", True, "bool"),
            ColumnSpec("reason", "Reason", True),
            ColumnSpec("notes", "Notes", True),
        ]
        self.current_context: SelectionContext | None = None
        self.current_volume: int | None = None
        self.summary_rows: list[EditorRow] = []
        self.current_segment_id: str | None = None
        self.current_row_wrapper: dict[str, Any] | None = None
        self.current_result: dict[str, Any] | None = None
        self.current_units_key: str | None = None
        self.current_source_text = ""
        self._dirty = False
        self._loading_summary = False
        self._loading_units = False
        self._loading_source = False
        self._build_ui()

    def set_view(self, context: SelectionContext | None, view: ArtifactView) -> None:
        self.current_context = context
        self.current_volume = context.volume if context is not None else None
        self.summary_rows = list(view.rows)
        self.message_label.setText(view.error or view.message or "")
        self._rebuild_summary_table()

        preferred_segment_id: str | None = None
        if context is not None and context.scope == "segment" and context.segment is not None:
            preferred_segment_id = str(context.segment)
        elif self.current_segment_id and self._summary_row_index_for_segment(self.current_segment_id) >= 0:
            preferred_segment_id = self.current_segment_id
        elif self.summary_rows:
            preferred_segment_id = self._segment_id_for_summary_row(0)

        self._set_dirty(False)
        if preferred_segment_id:
            self._select_summary_row(preferred_segment_id)
            self._load_segment(preferred_segment_id, quiet=True)
        else:
            self._clear_detail("Select a dialogue label row to edit, or choose a segment to create one.")

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def resolve_unsaved_changes(self, parent: QWidget, reason: str) -> bool:
        if not self._dirty:
            return True
        choice = self._unsaved_choice(parent, reason)
        if choice == QMessageBox.StandardButton.Save:
            return self._save_current(show_success=True, emit_change=False)
        if choice == QMessageBox.StandardButton.Discard:
            self._set_dirty(False)
            return True
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.message_label = QLabel("")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        layout.addWidget(QLabel("Summary"))
        self.summary_table = QTableWidget(0, len(self.summary_columns))
        self.summary_table.setHorizontalHeaderLabels([label for _key, label in self.summary_columns])
        self.summary_table.setAlternatingRowColors(False)
        self.summary_table.setShowGrid(False)
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.summary_columns)):
            self.summary_table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.summary_table.itemSelectionChanged.connect(self._on_summary_selection_changed)
        layout.addWidget(self.summary_table, 1)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Editing Segment"))
        self.segment_label = QLabel("No segment selected")
        self.segment_label.setObjectName("mutedLabel")
        header_row.addWidget(self.segment_label)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self.detail_status_label = QLabel("Select a segment summary row to edit dialogue labels.")
        self.detail_status_label.setObjectName("mutedLabel")
        self.detail_status_label.setWordWrap(True)
        layout.addWidget(self.detail_status_label)

        action_row = QHBoxLayout()
        self.save_button = QPushButton("Save Dialogue Labels")
        self.reload_button = QPushButton("Reload/Revert")
        self.copy_button = QPushButton("Copy Labeled Source")
        self.reset_button = QPushButton("Reset From Original Source")
        self.save_button.clicked.connect(lambda: self._save_current(show_success=True, emit_change=True))
        self.reload_button.clicked.connect(self._reload)
        self.copy_button.clicked.connect(self._copy_labeled_source)
        self.reset_button.clicked.connect(self._reset_from_original_source)
        for button in (self.save_button, self.reload_button, self.copy_button, self.reset_button):
            action_row.addWidget(button)
        action_row.addStretch(1)
        layout.addLayout(action_row)

        editors_row = QHBoxLayout()
        labeled_panel = QVBoxLayout()
        labeled_panel.addWidget(QLabel("Labeled Source"))
        self.labeled_source_edit = QTextEdit()
        self.labeled_source_edit.textChanged.connect(self._on_labeled_source_changed)
        labeled_panel.addWidget(self.labeled_source_edit, 1)
        editors_row.addLayout(labeled_panel, 1)

        source_panel = QVBoxLayout()
        source_panel.addWidget(QLabel("Original Source"))
        self.source_preview = QTextEdit()
        self.source_preview.setReadOnly(True)
        source_panel.addWidget(self.source_preview, 1)
        editors_row.addLayout(source_panel, 1)
        layout.addLayout(editors_row, 2)

        self.warnings_label = QLabel("No dialogue label warnings.")
        self.warnings_label.setObjectName("mutedLabel")
        self.warnings_label.setWordWrap(True)
        layout.addWidget(self.warnings_label)

        unit_button_row = QHBoxLayout()
        self.add_unit_button = QPushButton("Add Unit")
        self.duplicate_unit_button = QPushButton("Duplicate Unit")
        self.delete_unit_button = QPushButton("Delete Unit")
        self.add_unit_button.clicked.connect(self._add_unit)
        self.duplicate_unit_button.clicked.connect(self._duplicate_unit)
        self.delete_unit_button.clicked.connect(self._delete_unit)
        for button in (self.add_unit_button, self.duplicate_unit_button, self.delete_unit_button):
            unit_button_row.addWidget(button)
        unit_button_row.addStretch(1)
        layout.addLayout(unit_button_row)

        self.units_table = QTableWidget(0, len(self.unit_columns))
        self.units_table.setHorizontalHeaderLabels([column.label for column in self.unit_columns])
        self.units_table.setAlternatingRowColors(False)
        self.units_table.setShowGrid(False)
        self.units_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.units_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.units_table.verticalHeader().setVisible(False)
        self.units_table.horizontalHeader().setStretchLastSection(True)
        self.units_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.unit_columns)):
            self.units_table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.units_table.itemSelectionChanged.connect(self._emit_units_object)
        self.units_table.itemChanged.connect(self._on_unit_item_changed)
        layout.addWidget(self.units_table, 2)

        self._set_controls_enabled(False)

    def _rebuild_summary_table(self) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            self.summary_table.clearContents()
            self.summary_table.setRowCount(len(self.summary_rows))
            for row_index, row in enumerate(self.summary_rows):
                for column_index, (key, _label) in enumerate(self.summary_columns):
                    item = QTableWidgetItem(str(row.values.get(key, "")))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.summary_table.setItem(row_index, column_index, item)
            if self.summary_rows:
                self.summary_table.resizeRowsToContents()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _summary_row_index_for_segment(self, segment_id: str | None) -> int:
        if not segment_id:
            return -1
        for index, row in enumerate(self.summary_rows):
            if str(row.values.get("item_id") or "") == str(segment_id):
                return index
        return -1

    def _segment_id_for_summary_row(self, row_index: int) -> str | None:
        if 0 <= row_index < len(self.summary_rows):
            value = self.summary_rows[row_index].values.get("item_id")
            return str(value) if value else None
        return None

    def _select_summary_row(self, segment_id: str | None) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            row_index = self._summary_row_index_for_segment(segment_id)
            if row_index >= 0:
                self.summary_table.selectRow(row_index)
            else:
                self.summary_table.clearSelection()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _on_summary_selection_changed(self) -> None:
        if self._loading_summary:
            return
        row_index = self.summary_table.currentRow()
        segment_id = self._segment_id_for_summary_row(row_index)
        if not segment_id or segment_id == self.current_segment_id:
            return
        previous_segment_id = self.current_segment_id
        if self._dirty and not self.resolve_unsaved_changes(self, f"loading segment {segment_id}"):
            self._select_summary_row(previous_segment_id)
            return
        self._load_segment(segment_id, quiet=False)

    def _load_segment(self, segment_id: str, quiet: bool) -> None:
        if self.current_volume is None:
            self._clear_detail("A volume must be selected before dialogue label editing is available.")
            return
        try:
            loaded = self.editor_actions.load_dialogue_labels(self.current_volume, segment_id)
            original_source = self.editor_actions.get_segment_source(self.current_volume, segment_id)
        except Exception as exc:
            self._clear_detail(str(exc))
            self.status_message.emit(str(exc))
            if not quiet:
                QMessageBox.critical(self, "Dialogue Labels Load Failed", str(exc))
            return

        self.current_segment_id = loaded.item_id
        self.current_row_wrapper = copy.deepcopy(loaded.row)
        self.current_result = copy.deepcopy(loaded.result)
        self.current_units_key, units = self.editor_actions.get_dialogue_units(self.current_result)
        self.current_source_text = original_source
        self.segment_label.setText(loaded.item_id)
        self.detail_status_label.setText(
            loaded.message or (
                "Editing the saved dialogue label row for this segment."
                if loaded.exists
                else "Editing an in-memory dialogue label draft until save."
            )
        )

        self._loading_source = True
        labeled_source = self.current_result.get("labeled_source")
        self.labeled_source_edit.setPlainText(labeled_source if isinstance(labeled_source, str) else "")
        self.source_preview.setPlainText(original_source)
        self._loading_source = False

        self._rebuild_units_table(units)
        self._set_controls_enabled(True)
        self._set_dirty(False)
        self._refresh_warnings()
        self.object_selected.emit(self.current_row_wrapper)

    def _clear_detail(self, message: str) -> None:
        self.current_segment_id = None
        self.current_row_wrapper = None
        self.current_result = None
        self.current_units_key = None
        self.current_source_text = ""
        self.segment_label.setText("No segment selected")
        self.detail_status_label.setText(message)
        self._loading_source = True
        self.labeled_source_edit.setPlainText("")
        self.source_preview.setPlainText("")
        self._loading_source = False
        self._rebuild_units_table([])
        self._set_controls_enabled(False)
        self._set_dirty(False)
        self.warnings_label.setText("No dialogue label warnings.")
        self.object_selected.emit(None)

    def _units(self) -> list[dict[str, Any]] | None:
        if self.current_result is None or self.current_units_key is None:
            return None
        units = self.current_result.get(self.current_units_key)
        return units if isinstance(units, list) else None

    def _rebuild_units_table(self, units: list[Any]) -> None:
        self._loading_units = True
        self.units_table.blockSignals(True)
        try:
            self.units_table.clearContents()
            self.units_table.setRowCount(len(units))
            for row_index, unit in enumerate(units):
                row = unit if isinstance(unit, dict) else {}
                for column_index, column in enumerate(self.unit_columns):
                    self.units_table.setItem(row_index, column_index, self._build_unit_item(row, column))
            if units:
                self.units_table.resizeRowsToContents()
        finally:
            self.units_table.blockSignals(False)
            self._loading_units = False

    def _build_unit_item(self, unit: dict[str, Any], column: ColumnSpec) -> QTableWidgetItem:
        if column.kind == "bool":
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            if column.editable:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if bool(unit.get(column.key)) else Qt.CheckState.Unchecked)
            return item

        value = unit.get(column.key, "")
        if value is None:
            display = ""
        else:
            display = str(value)
        item = QTableWidgetItem(display)
        flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
        if column.editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        return item

    def _on_labeled_source_changed(self) -> None:
        if self._loading_source or self.current_result is None:
            return
        self.current_result["labeled_source"] = self.labeled_source_edit.toPlainText()
        self._set_dirty(True)
        self._refresh_warnings()
        self.object_selected.emit(self.current_result)

    def _on_unit_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading_units:
            return
        units = self._units()
        if units is None:
            return
        row_index = item.row()
        column_index = item.column()
        if not (0 <= row_index < len(units) and 0 <= column_index < len(self.unit_columns)):
            return
        unit = units[row_index]
        if not isinstance(unit, dict):
            unit = {}
            units[row_index] = unit
        column = self.unit_columns[column_index]
        if not column.editable:
            return
        if column.kind == "bool":
            unit[column.key] = item.checkState() == Qt.CheckState.Checked
        elif column.key == "confidence":
            text = item.text().strip()
            if not text:
                unit[column.key] = None
            else:
                try:
                    unit[column.key] = float(text)
                except Exception:
                    unit[column.key] = text
        else:
            unit[column.key] = item.text()
        self._set_dirty(True)
        self._refresh_warnings()
        if row_index == self.units_table.currentRow():
            self.object_selected.emit(unit)

    def _emit_units_object(self) -> None:
        units = self._units()
        row_index = self.units_table.currentRow()
        if units is not None and 0 <= row_index < len(units) and isinstance(units[row_index], dict):
            self.object_selected.emit(units[row_index])
        elif self.current_row_wrapper is not None:
            self.object_selected.emit(self.current_row_wrapper)
        elif self.current_result is not None:
            self.object_selected.emit(self.current_result)
        else:
            self.object_selected.emit(None)

    def raw_edit_descriptor(self) -> tuple[RawEditTarget | None, str]:
        units = self._units()
        row_index = self.units_table.currentRow()
        if units is not None and 0 <= row_index < len(units) and isinstance(units[row_index], dict):
            return (
                RawEditTarget(
                    title="Dialogue Unit",
                    obj=copy.deepcopy(units[row_index]),
                    selection_key=f"dialogue-unit:{self.current_segment_id}:{row_index}",
                    apply_callback=lambda obj, target_segment_id=self.current_segment_id, target_index=row_index: self._apply_raw_unit_at_index(
                        target_segment_id,
                        target_index,
                        obj,
                    ),
                    message="Applied changes stay in memory until you save Dialogue Labels.",
                ),
                "",
            )
        if isinstance(self.current_result, dict):
            return (
                RawEditTarget(
                    title="Dialogue Labels Result",
                    obj=copy.deepcopy(self.current_result),
                    selection_key=f"dialogue-result:{self.current_segment_id}",
                    apply_callback=lambda obj, target_segment_id=self.current_segment_id: self._apply_raw_result_object(
                        target_segment_id,
                        obj,
                    ),
                    message="Applied changes stay in memory until you save Dialogue Labels.",
                ),
                "",
            )
        return None, "Select a dialogue label row or unit to edit it as raw JSON."

    def apply_raw_edit_object(self, obj: dict[str, Any]) -> str:
        units = self._units()
        row_index = self.units_table.currentRow()
        if units is not None and 0 <= row_index < len(units):
            return self._apply_raw_unit_at_index(self.current_segment_id, row_index, obj)

        if self.current_result is None:
            raise ValueError("Select a dialogue label result before applying raw JSON.")
        return self._apply_raw_result_object(self.current_segment_id, obj)

    def _apply_raw_unit_at_index(
        self,
        expected_segment_id: str | None,
        row_index: int,
        obj: dict[str, Any] | list[Any],
    ) -> str:
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object for this selection.")
        if expected_segment_id is not None and self.current_segment_id != expected_segment_id:
            raise ValueError("The selected segment changed before this raw edit could be applied. Re-select the original unit or reset the panel.")
        units = self._units()
        if units is None or not (0 <= row_index < len(units)):
            raise ValueError("Select a dialogue unit before applying raw JSON.")
        units[row_index] = copy.deepcopy(obj)
        self._rebuild_units_table(units)
        self.units_table.selectRow(row_index)
        self._set_dirty(True)
        self._refresh_warnings()
        self.object_selected.emit(units[row_index])
        return "Applied in memory. Click Save Dialogue Labels to write the artifact."

    def _apply_raw_result_object(
        self,
        expected_segment_id: str | None,
        obj: dict[str, Any] | list[Any],
    ) -> str:
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object for this selection.")
        if expected_segment_id is not None and self.current_segment_id != expected_segment_id:
            raise ValueError("The selected segment changed before this raw edit could be applied. Re-select the original result or reset the panel.")
        if self.current_result is None:
            raise ValueError("Select a dialogue label result before applying raw JSON.")
        self.current_result = copy.deepcopy(obj)
        self.current_units_key, units = self.editor_actions.get_dialogue_units(self.current_result)
        self._loading_source = True
        self.labeled_source_edit.setPlainText(str(self.current_result.get("labeled_source") or ""))
        self._loading_source = False
        self._rebuild_units_table(units)
        self._set_dirty(True)
        self._refresh_warnings()
        self.object_selected.emit(self.current_result)
        return "Applied in memory. Click Save Dialogue Labels to write the artifact."

    def _add_unit(self) -> None:
        units = self._units()
        if units is None:
            self.status_message.emit("Select a segment before adding units.")
            return
        units.append(self.editor_actions.default_dialogue_unit())
        self._rebuild_units_table(units)
        self.units_table.selectRow(len(units) - 1)
        self._set_dirty(True)
        self._refresh_warnings()
        self.status_message.emit("Added a new dialogue unit.")

    def _duplicate_unit(self) -> None:
        units = self._units()
        row_index = self.units_table.currentRow()
        if units is None or not (0 <= row_index < len(units)):
            self.status_message.emit("Select a unit to duplicate.")
            return
        units.insert(row_index + 1, copy.deepcopy(units[row_index]))
        self._rebuild_units_table(units)
        self.units_table.selectRow(row_index + 1)
        self._set_dirty(True)
        self._refresh_warnings()
        self.status_message.emit("Duplicated a dialogue unit.")

    def _delete_unit(self) -> None:
        units = self._units()
        row_index = self.units_table.currentRow()
        if units is None or not (0 <= row_index < len(units)):
            self.status_message.emit("Select a unit to delete.")
            return
        units.pop(row_index)
        self._rebuild_units_table(units)
        if units:
            self.units_table.selectRow(min(row_index, len(units) - 1))
        self._set_dirty(True)
        self._refresh_warnings()
        self.status_message.emit("Deleted a dialogue unit.")

    def _copy_labeled_source(self) -> None:
        text = self.labeled_source_edit.toPlainText()
        if not text:
            self.status_message.emit("No labeled source text is available to copy.")
            return
        QApplication.clipboard().setText(text)
        self.status_message.emit("Labeled source copied to clipboard.")

    def _reset_from_original_source(self) -> None:
        if self.current_result is None or self.current_segment_id is None:
            self.status_message.emit("Select a segment before resetting labeled source.")
            return
        confirm = QMessageBox.question(
            self,
            "Reset From Original Source",
            "Replace labeled_source with the original segment content? Units will be kept unchanged.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._loading_source = True
        self.labeled_source_edit.setPlainText(self.current_source_text)
        self._loading_source = False
        self.current_result["labeled_source"] = self.current_source_text
        self._set_dirty(True)
        self._refresh_warnings()
        self.status_message.emit("Reset labeled source from the original segment content.")

    def _reload(self) -> None:
        if not self.resolve_unsaved_changes(self, "reloading this tab"):
            return
        self.reload_requested.emit()

    def _save_current(self, show_success: bool, emit_change: bool) -> bool:
        if self.current_volume is None or self.current_segment_id is None or self.current_result is None:
            self.status_message.emit("Dialogue labels are not available for saving.")
            return False
        self.current_result["labeled_source"] = self.labeled_source_edit.toPlainText()
        try:
            result = self.editor_actions.save_dialogue_labels(
                self.current_volume,
                self.current_segment_id,
                copy.deepcopy(self.current_result),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Dialogue Labels Save Failed", str(exc))
            self.status_message.emit(str(exc))
            return False

        self._set_dirty(False)
        self._refresh_warnings()
        if show_success:
            self.status_message.emit(result.message)
        if emit_change:
            self.artifact_written.emit()
        return True

    def _set_controls_enabled(self, enabled: bool) -> None:
        for button in (
            self.save_button,
            self.reload_button,
            self.copy_button,
            self.reset_button,
            self.add_unit_button,
            self.duplicate_unit_button,
            self.delete_unit_button,
        ):
            button.setEnabled(enabled)
        self.labeled_source_edit.setEnabled(enabled)
        self.units_table.setEnabled(enabled)

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def _refresh_warnings(self) -> None:
        warnings = []
        labeled_source = ""
        if self.current_result is not None:
            value = self.current_result.get("labeled_source")
            labeled_source = value if isinstance(value, str) else ""
        if not labeled_source:
            warnings.append("labeled_source is empty.")
        if "[NARRATION]" in labeled_source:
            warnings.append("labeled_source contains [NARRATION], which should not be introduced.")
        if "[" not in labeled_source:
            warnings.append("labeled_source does not contain any bracketed label markers.")
        units = self._units() or []
        bad_confidence_indexes = []
        for index, unit in enumerate(units):
            if not isinstance(unit, dict):
                continue
            confidence = unit.get("confidence")
            if confidence is not None and not isinstance(confidence, (int, float)):
                bad_confidence_indexes.append(index + 1)
        if bad_confidence_indexes:
            warnings.append(
                "Units contain non-numeric confidence values at rows: "
                + ", ".join(str(index) for index in bad_confidence_indexes)
                + "."
            )
        self.warnings_label.setText(
            "\n".join(warnings) if warnings else "No dialogue label warnings."
        )

    def _unsaved_choice(self, parent: QWidget, reason: str) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText("Dialogue Labels has unsaved changes.")
        box.setInformativeText(f"What would you like to do before {reason}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())


class EditableTranslationsTab(QWidget):
    object_selected = pyqtSignal(object)
    dirty_changed = pyqtSignal(bool)
    status_message = pyqtSignal(str)
    artifact_written = pyqtSignal()
    reload_requested = pyqtSignal()

    def __init__(self, editor_actions: EditorActionService, parent=None):
        super().__init__(parent)
        self.editor_actions = editor_actions
        self.summary_columns = [
            ("item_id", "Item ID"),
            ("draft_exists", "Draft"),
            ("fixed_exists", "Fixed"),
            ("qa_exists", "QA"),
            ("translation_preview", "Preview"),
        ]
        self.current_context: SelectionContext | None = None
        self.current_volume: int | None = None
        self.summary_rows: list[EditorRow] = []
        self.current_segment_id: str | None = None
        self.current_bundle: TranslationBundle | None = None
        self.current_draft_result: dict[str, Any] | None = None
        self.current_fixed_result: dict[str, Any] | None = None
        self.loaded_draft_result: dict[str, Any] | None = None
        self.loaded_fixed_result: dict[str, Any] | None = None
        self._dirty = False
        self._loading_summary = False
        self._loading_mode = False
        self._loading_translation = False
        self._active_mode = "draft"
        self._build_ui()

    def set_view(self, context: SelectionContext | None, view: ArtifactView) -> None:
        self.current_context = context
        self.current_volume = context.volume if context is not None else None
        self.summary_rows = list(view.rows)
        self.message_label.setText(view.error or view.message or "")
        self._rebuild_summary_table()

        preferred_segment_id: str | None = None
        if context is not None and context.scope == "segment" and context.segment is not None:
            preferred_segment_id = str(context.segment)
        elif self.current_segment_id and self._summary_row_index_for_segment(self.current_segment_id) >= 0:
            preferred_segment_id = self.current_segment_id
        elif self.summary_rows:
            preferred_segment_id = self._segment_id_for_summary_row(0)

        self._set_dirty(False)
        if preferred_segment_id:
            self._select_summary_row(preferred_segment_id)
            self._load_segment(preferred_segment_id, quiet=True)
        else:
            self._clear_detail("Select a translation summary row to edit a segment translation.")

    def has_unsaved_changes(self) -> bool:
        return self._dirty

    def resolve_unsaved_changes(self, parent: QWidget, reason: str) -> bool:
        if not self._dirty:
            return True
        choice = self._unsaved_choice(parent, reason)
        if choice == QMessageBox.StandardButton.Save:
            return self._save_mode(self._active_mode, show_success=True, emit_change=False)
        if choice == QMessageBox.StandardButton.Discard:
            self._set_dirty(False)
            return True
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.message_label = QLabel("")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        layout.addWidget(QLabel("Summary"))
        self.summary_table = QTableWidget(0, len(self.summary_columns))
        self.summary_table.setHorizontalHeaderLabels([label for _key, label in self.summary_columns])
        self.summary_table.setAlternatingRowColors(False)
        self.summary_table.setShowGrid(False)
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for column_index in range(1, len(self.summary_columns)):
            self.summary_table.horizontalHeader().setSectionResizeMode(column_index, QHeaderView.ResizeMode.Stretch)
        self.summary_table.itemSelectionChanged.connect(self._on_summary_selection_changed)
        layout.addWidget(self.summary_table, 1)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Editing Segment"))
        self.segment_label = QLabel("No segment selected")
        self.segment_label.setObjectName("mutedLabel")
        header_row.addWidget(self.segment_label)
        header_row.addStretch(1)
        header_row.addWidget(QLabel("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Draft Translation", "draft")
        self.mode_combo.addItem("Fixed Translation", "fixed")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        header_row.addWidget(self.mode_combo)
        layout.addLayout(header_row)

        self.detail_status_label = QLabel("Select a translation summary row to edit a segment translation.")
        self.detail_status_label.setObjectName("mutedLabel")
        self.detail_status_label.setWordWrap(True)
        layout.addWidget(self.detail_status_label)

        button_row = QHBoxLayout()
        self.save_draft_button = QPushButton("Save Draft Translation")
        self.save_fixed_button = QPushButton("Save Fixed Translation")
        self.copy_button = QPushButton("Copy Translation")
        self.reload_button = QPushButton("Reload/Revert")
        self.save_draft_button.clicked.connect(lambda: self._save_mode("draft", show_success=True, emit_change=True))
        self.save_fixed_button.clicked.connect(lambda: self._save_mode("fixed", show_success=True, emit_change=True))
        self.copy_button.clicked.connect(self._copy_translation)
        self.reload_button.clicked.connect(self._reload)
        for button in (self.save_draft_button, self.save_fixed_button, self.copy_button, self.reload_button):
            button_row.addWidget(button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        content_row = QHBoxLayout()
        self.reference_tabs = QTabWidget()

        self.original_source_edit = QTextEdit()
        self.original_source_edit.setReadOnly(True)
        self.reference_tabs.addTab(self.original_source_edit, "Original Source")

        self.labeled_source_edit = QTextEdit()
        self.labeled_source_edit.setReadOnly(True)
        self.reference_tabs.addTab(self.labeled_source_edit, "Labeled Source")

        self.glossary_table = QTableWidget(0, 2)
        self.glossary_table.setHorizontalHeaderLabels(["Source", "Vietnamese"])
        self._configure_reference_table(self.glossary_table)
        self.reference_tabs.addTab(self.glossary_table, "Segment Glossary")

        self.pronouns_table = QTableWidget(0, 4)
        self.pronouns_table.setHorizontalHeaderLabels(["Speaker", "Listener", "Self", "Other"])
        self._configure_reference_table(self.pronouns_table)
        self.reference_tabs.addTab(self.pronouns_table, "Segment Pronouns")

        self.context_preview = QTextEdit()
        self.context_preview.setReadOnly(True)
        self.reference_tabs.addTab(self.context_preview, "Segment Context")

        self.qa_preview = QTextEdit()
        self.qa_preview.setReadOnly(True)
        self.reference_tabs.addTab(self.qa_preview, "QA Report")

        content_row.addWidget(self.reference_tabs, 1)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.addWidget(QLabel("Translation"))
        self.translation_status_label = QLabel("Translation editing is available when a segment is selected.")
        self.translation_status_label.setObjectName("mutedLabel")
        self.translation_status_label.setWordWrap(True)
        editor_layout.addWidget(self.translation_status_label)
        self.translation_edit = QTextEdit()
        self.translation_edit.textChanged.connect(self._on_translation_changed)
        editor_layout.addWidget(self.translation_edit, 1)
        content_row.addWidget(editor_panel, 1)

        layout.addLayout(content_row, 2)
        self._set_detail_controls_enabled(False)

    def _configure_reference_table(self, table: QTableWidget) -> None:
        table.setAlternatingRowColors(False)
        table.setShowGrid(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _rebuild_summary_table(self) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            self.summary_table.clearContents()
            self.summary_table.setRowCount(len(self.summary_rows))
            for row_index, row in enumerate(self.summary_rows):
                for column_index, (key, _label) in enumerate(self.summary_columns):
                    value = row.values.get(key, "")
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.summary_table.setItem(row_index, column_index, item)
            if self.summary_rows:
                self.summary_table.resizeRowsToContents()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _summary_row_index_for_segment(self, segment_id: str | None) -> int:
        if not segment_id:
            return -1
        for index, row in enumerate(self.summary_rows):
            if str(row.values.get("item_id") or "") == str(segment_id):
                return index
        return -1

    def _segment_id_for_summary_row(self, row_index: int) -> str | None:
        if 0 <= row_index < len(self.summary_rows):
            value = self.summary_rows[row_index].values.get("item_id")
            return str(value) if value else None
        return None

    def _select_summary_row(self, segment_id: str | None) -> None:
        self._loading_summary = True
        self.summary_table.blockSignals(True)
        try:
            row_index = self._summary_row_index_for_segment(segment_id)
            if row_index >= 0:
                self.summary_table.selectRow(row_index)
            else:
                self.summary_table.clearSelection()
        finally:
            self.summary_table.blockSignals(False)
            self._loading_summary = False

    def _on_summary_selection_changed(self) -> None:
        if self._loading_summary:
            return
        row_index = self.summary_table.currentRow()
        segment_id = self._segment_id_for_summary_row(row_index)
        if not segment_id or segment_id == self.current_segment_id:
            return
        previous_segment_id = self.current_segment_id
        if self._dirty and not self.resolve_unsaved_changes(self, f"loading segment {segment_id}"):
            self._select_summary_row(previous_segment_id)
            return
        self._load_segment(segment_id, quiet=False)

    def _load_segment(self, segment_id: str, quiet: bool) -> None:
        if self.current_volume is None:
            self._clear_detail("A volume must be selected before translation editing is available.")
            return
        try:
            bundle = self.editor_actions.load_translation_bundle(self.current_volume, segment_id)
        except Exception as exc:
            self._clear_detail(str(exc))
            self.status_message.emit(str(exc))
            if not quiet:
                QMessageBox.critical(self, "Translations Load Failed", str(exc))
            return

        self.current_segment_id = bundle.segment_id
        self.current_bundle = bundle
        self.loaded_draft_result = copy.deepcopy(bundle.draft_result) if isinstance(bundle.draft_result, dict) else None
        self.loaded_fixed_result = copy.deepcopy(bundle.fixed_result) if isinstance(bundle.fixed_result, dict) else None
        self.current_draft_result = copy.deepcopy(self.loaded_draft_result)
        self.current_fixed_result = copy.deepcopy(self.loaded_fixed_result)
        self.segment_label.setText(bundle.segment_id)
        self.detail_status_label.setText("Editing saved and in-memory translation artifacts for this segment.")
        self._populate_reference_panels(bundle)
        self._refresh_translation_editor()
        self._set_detail_controls_enabled(True)
        self._set_dirty(False)
        self.object_selected.emit(self._bundle_raw(bundle))

    def _populate_reference_panels(self, bundle: TranslationBundle) -> None:
        source_record = bundle.source_record or {}
        self.original_source_edit.setPlainText(str(source_record.get("content") or "No source record found for this segment."))

        dialogue_labels = bundle.dialogue_labels or {}
        labeled_source = dialogue_labels.get("labeled_source")
        self.labeled_source_edit.setPlainText(
            labeled_source if isinstance(labeled_source, str) and labeled_source else "No dialogue labels found for this segment."
        )

        glossary_rows: list[dict[str, Any]] = []
        if isinstance(bundle.segment_glossary, dict):
            _field_name, glossary_entries = self.editor_actions.get_segment_glossary_entries(bundle.segment_glossary)
            glossary_rows = [entry for entry in glossary_entries if isinstance(entry, dict)]
        self._populate_reference_table(
            self.glossary_table,
            glossary_rows,
            ("source", "vi"),
            empty_message="No segment glossary entries found.",
        )

        pronoun_rows: list[dict[str, Any]] = []
        if isinstance(bundle.segment_pronouns, dict):
            _field_name, pronoun_rules = self.editor_actions.get_segment_pronoun_rules(bundle.segment_pronouns)
            pronoun_rows = [rule for rule in pronoun_rules if isinstance(rule, dict)]
        self._populate_reference_table(
            self.pronouns_table,
            pronoun_rows,
            ("speaker", "listener", "self", "other"),
            empty_message="No segment pronoun rules found.",
        )

        self.context_preview.setPlainText(
            pretty(bundle.segment_context)
            if isinstance(bundle.segment_context, dict)
            else "No segment context found."
        )
        self.qa_preview.setPlainText(
            pretty(bundle.qa_result)
            if isinstance(bundle.qa_result, dict)
            else "No QA report found."
        )

    def _populate_reference_table(
        self,
        table: QTableWidget,
        rows: list[dict[str, Any]],
        keys: tuple[str, ...],
        empty_message: str,
    ) -> None:
        display_rows = rows if rows else [{keys[0]: empty_message}]
        table.clearContents()
        table.setRowCount(len(display_rows))
        for row_index, row in enumerate(display_rows):
            for column_index, key in enumerate(keys):
                value = row.get(key, "") if isinstance(row, dict) else ""
                item = QTableWidgetItem("" if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(row_index, column_index, item)
        table.resizeRowsToContents()

    def _refresh_translation_editor(self) -> None:
        current_result = self._current_result()
        translation_ref = self.editor_actions.get_translation_text(current_result)
        self._loading_translation = True
        try:
            self.translation_edit.setPlainText(translation_ref.text)
        finally:
            self._loading_translation = False
        row_state = []
        if self.current_bundle is not None:
            row_state.append("draft row exists" if self.current_bundle.draft_row else "draft row missing")
            row_state.append("fixed row exists" if self.current_bundle.fixed_row else "fixed row missing")
        self.translation_status_label.setText(
            f"Editing field '{translation_ref.field_name}' in {self.mode_combo.currentText().lower()}. "
            + (", ".join(row_state) if row_state else "")
        )
        self._update_mode_button_states()

    def _current_result(self) -> dict[str, Any] | None:
        return self.current_draft_result if self._active_mode == "draft" else self.current_fixed_result

    def _set_current_result(self, value: dict[str, Any] | None) -> None:
        if self._active_mode == "draft":
            self.current_draft_result = value
        else:
            self.current_fixed_result = value

    def _preferred_field_for_mode(self, mode: str) -> str:
        return "translation" if mode == "draft" else "fixed_translation"

    def _on_translation_changed(self) -> None:
        if self._loading_translation:
            return
        current_result = self._current_result()
        if current_result is None:
            return
        updated = self.editor_actions.set_translation_text(
            current_result,
            self.translation_edit.toPlainText(),
            preferred_field=self._preferred_field_for_mode(self._active_mode),
        )
        self._set_current_result(updated)
        self._set_dirty(True)
        translation_ref = self.editor_actions.get_translation_text(updated)
        self.translation_status_label.setText(
            f"Editing field '{translation_ref.field_name}' in {self.mode_combo.currentText().lower()}."
        )
        self.object_selected.emit(updated)

    def _on_mode_changed(self, _index: int) -> None:
        if self._loading_mode:
            return
        target_mode = str(self.mode_combo.currentData() or "draft")
        if target_mode == self._active_mode:
            return

        saved_during_switch = False
        if self._dirty:
            choice = self._unsaved_choice(self, f"switching to {self.mode_combo.currentText().lower()}")
            if choice == QMessageBox.StandardButton.Save:
                if not self._save_mode(self._active_mode, show_success=False, emit_change=False):
                    self._set_mode_combo(self._active_mode)
                    return
                saved_during_switch = True
            elif choice == QMessageBox.StandardButton.Discard:
                self._restore_loaded_results()
            else:
                self._set_mode_combo(self._active_mode)
                return

        self._active_mode = target_mode
        self._refresh_translation_editor()
        self._set_dirty(False)
        current_result = self._current_result()
        if current_result is not None:
            self.object_selected.emit(current_result)
        if saved_during_switch:
            self.artifact_written.emit()

    def _save_mode(self, mode: str, show_success: bool, emit_change: bool) -> bool:
        if self.current_volume is None or self.current_segment_id is None:
            self.status_message.emit("Translations are not available for saving.")
            return False

        result_obj = self.current_draft_result if mode == "draft" else self.current_fixed_result
        if result_obj is None:
            self.status_message.emit("No translation data is loaded for the selected segment.")
            return False

        try:
            if mode == "draft":
                result = self.editor_actions.save_draft_translation(
                    self.current_volume,
                    self.current_segment_id,
                    copy.deepcopy(result_obj),
                )
                self.loaded_draft_result = copy.deepcopy(result_obj)
            else:
                result = self.editor_actions.save_fixed_translation(
                    self.current_volume,
                    self.current_segment_id,
                    copy.deepcopy(result_obj),
                )
                self.loaded_fixed_result = copy.deepcopy(result_obj)
        except Exception as exc:
            QMessageBox.critical(self, "Translation Save Failed", str(exc))
            self.status_message.emit(str(exc))
            return False

        self._set_dirty(False)
        if show_success:
            self.status_message.emit(result.message)
        if emit_change:
            self.artifact_written.emit()
        return True

    def _copy_translation(self) -> None:
        text = self.translation_edit.toPlainText()
        if not text:
            self.status_message.emit("No translation text is available to copy.")
            return
        QApplication.clipboard().setText(text)
        self.status_message.emit("Copied translation text to the clipboard.")

    def _reload(self) -> None:
        if not self.resolve_unsaved_changes(self, "reloading this tab"):
            return
        self.reload_requested.emit()

    def _restore_loaded_results(self) -> None:
        self.current_draft_result = copy.deepcopy(self.loaded_draft_result)
        self.current_fixed_result = copy.deepcopy(self.loaded_fixed_result)

    def _clear_detail(self, message: str) -> None:
        self.current_segment_id = None
        self.current_bundle = None
        self.current_draft_result = None
        self.current_fixed_result = None
        self.loaded_draft_result = None
        self.loaded_fixed_result = None
        self.segment_label.setText("No segment selected")
        self.detail_status_label.setText(message)
        self.original_source_edit.setPlainText("")
        self.labeled_source_edit.setPlainText("")
        self.context_preview.setPlainText("")
        self.qa_preview.setPlainText("")
        self.translation_edit.setPlainText("")
        self.translation_status_label.setText("Translation editing is available when a segment is selected.")
        self._populate_reference_table(self.glossary_table, [], ("source", "vi"), "No segment glossary entries found.")
        self._populate_reference_table(
            self.pronouns_table,
            [],
            ("speaker", "listener", "self", "other"),
            "No segment pronoun rules found.",
        )
        self._set_detail_controls_enabled(False)
        self._set_dirty(False)
        self.object_selected.emit(None)

    def _set_detail_controls_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.reload_button.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.translation_edit.setEnabled(enabled)
        if enabled:
            self._update_mode_button_states()
        else:
            self.save_draft_button.setEnabled(False)
            self.save_fixed_button.setEnabled(False)

    def _update_mode_button_states(self) -> None:
        detail_enabled = self.current_segment_id is not None
        self.save_draft_button.setEnabled(detail_enabled and self._active_mode == "draft")
        self.save_fixed_button.setEnabled(detail_enabled and self._active_mode == "fixed")

    def _set_mode_combo(self, mode: str) -> None:
        self._loading_mode = True
        try:
            index = self.mode_combo.findData(mode)
            if index >= 0:
                self.mode_combo.setCurrentIndex(index)
        finally:
            self._loading_mode = False

    def _bundle_raw(self, bundle: TranslationBundle) -> dict[str, Any]:
        return {
            "item_id": bundle.item_id,
            "volume": bundle.volume,
            "segment_id": bundle.segment_id,
            "source_record": bundle.source_record,
            "dialogue_labels": bundle.dialogue_labels,
            "segment_glossary": bundle.segment_glossary,
            "segment_pronouns": bundle.segment_pronouns,
            "segment_context": bundle.segment_context,
            "draft_row": bundle.draft_row,
            "draft_result": bundle.draft_result,
            "fixed_row": bundle.fixed_row,
            "fixed_result": bundle.fixed_result,
            "qa_row": bundle.qa_row,
            "qa_result": bundle.qa_result,
        }

    def raw_edit_descriptor(self) -> tuple[RawEditTarget | None, str]:
        current_result = self._current_result()
        if not isinstance(current_result, dict):
            return None, "Select a translation row before editing its raw JSON."
        title = "Draft Translation Result" if self._active_mode == "draft" else "Fixed Translation Result"
        return (
            RawEditTarget(
                title=title,
                obj=copy.deepcopy(current_result),
                selection_key=f"translation:{self.current_segment_id}:{self._active_mode}",
                apply_callback=lambda obj, target_segment_id=self.current_segment_id, mode=self._active_mode: self._apply_raw_mode_result(
                    target_segment_id,
                    mode,
                    obj,
                ),
                message="Applied changes stay in memory until you save the current translation mode.",
            ),
            "",
        )

    def apply_raw_edit_object(self, obj: dict[str, Any]) -> str:
        return self._apply_raw_mode_result(self.current_segment_id, self._active_mode, obj)

    def _apply_raw_mode_result(
        self,
        expected_segment_id: str | None,
        mode: str,
        obj: dict[str, Any] | list[Any],
    ) -> str:
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object for this selection.")
        if expected_segment_id is not None and self.current_segment_id != expected_segment_id:
            raise ValueError("The selected segment changed before this raw edit could be applied. Re-select the original translation result or reset the panel.")
        if mode == "draft":
            self.current_draft_result = copy.deepcopy(obj)
        else:
            self.current_fixed_result = copy.deepcopy(obj)
        if self._active_mode == mode:
            self._refresh_translation_editor()
            current_result = self._current_result()
            if current_result is not None:
                self.object_selected.emit(current_result)
        self._set_dirty(True)
        action = "Save Draft Translation" if mode == "draft" else "Save Fixed Translation"
        return f"Applied in memory. Click {action} to write the artifact."

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)

    def _unsaved_choice(self, parent: QWidget, reason: str) -> QMessageBox.StandardButton:
        box = QMessageBox(parent)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved Changes")
        box.setText("Translations has unsaved changes.")
        box.setInformativeText(f"What would you like to do before {reason}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        return QMessageBox.StandardButton(box.exec())


class EditorArtifactTabs(QWidget):
    status_message = pyqtSignal(str)
    artifacts_changed = pyqtSignal()
    reload_requested = pyqtSignal()
    raw_edit_target_changed = pyqtSignal(object, str)
    open_series_canon_requested = pyqtSignal(str, object, int)

    def __init__(self, editor_actions: EditorActionService, workspace: Workspace | None = None, parent=None):
        super().__init__(parent)
        self.editor_actions = editor_actions
        self.workspace = workspace
        self.canon_lens = CanonStatusLens(workspace)
        self._build_ui()

    def set_snapshot(self, snapshot: EditorSnapshot, context: SelectionContext | None) -> None:
        volume = context.volume if context is not None else None
        self.raw_json_viewer.clear_placeholder()
        self.volume_glossary_tab.set_view(volume, snapshot.volume_glossary)
        self.volume_relationships_tab.set_view(volume, snapshot.volume_relationships)
        self.segment_glossaries_tab.set_view(context, snapshot.segment_glossaries)
        self.segment_pronouns_tab.set_view(context, snapshot.segment_pronouns)
        self.segment_contexts_tab.set_view(snapshot.segment_contexts)
        self.dialogue_labels_tab.set_view(context, snapshot.dialogue_labels)
        self.translations_tab.set_view(context, snapshot.translations)
        for label, tab in self._editable_tabs():
            self._update_dirty_label(label, tab.has_unsaved_changes())
        self._emit_raw_edit_target()

    def has_unsaved_changes(self) -> bool:
        return any(tab.has_unsaved_changes() for _label, tab in self._editable_tabs())

    def resolve_unsaved_changes(self, parent: QWidget, reason: str) -> bool:
        for _label, tab in self._editable_tabs():
            if not tab.resolve_unsaved_changes(parent, reason):
                return False
        return True

    def current_raw_edit_target(self) -> tuple[RawEditTarget | None, str]:
        widget = self.tabs.currentWidget()
        if widget is None:
            return None, "Raw edit is waiting for an editable selection."
        descriptor = getattr(widget, "raw_edit_descriptor", None)
        if callable(descriptor):
            return descriptor()
        return None, "Raw edit is only available for supported editable tabs."

    def apply_raw_edit_object(self, obj: dict[str, Any]) -> str:
        widget = self.tabs.currentWidget()
        if widget is None:
            raise ValueError("No Editor tab is active for raw editing.")
        apply_raw = getattr(widget, "apply_raw_edit_object", None)
        if not callable(apply_raw):
            raise ValueError("Raw edit is not available for the current tab.")
        message = apply_raw(obj)
        self._emit_raw_edit_target()
        return message

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.volume_glossary_tab = EditableVolumeTableTab(
            artifact_label="Volume Glossary",
            list_key="volume_merge_glossary",
            canon_kind="glossary",
            canon_lens=self.canon_lens,
            columns=[
                ColumnSpec("id", "ID"),
                ColumnSpec("source", "Source", True),
                ColumnSpec("vi", "Vietnamese", True),
                ColumnSpec("type", "Type", True),
                ColumnSpec("status", "Status", True),
                ColumnSpec("notes", "Notes", True),
                ColumnSpec("needs_human_review", "Needs Review", True, "bool"),
                ColumnSpec("variants", "Variants", False, "count"),
                ColumnSpec("aliases", "Aliases", False, "count"),
                ColumnSpec("forbidden_translations", "Forbidden", False, "count"),
                ColumnSpec("appears_in", "Appears In", False, "count"),
                ColumnSpec("canon_status", "Canon Status"),
            ],
            raw_edit_title="Glossary Entry",
            default_row_factory=self.editor_actions.default_volume_glossary_row,
            save_callback=self.editor_actions.save_volume_glossary_draft,
            approve_callback=self.editor_actions.approve_volume_glossary,
            approve_button_text="Approve Glossary",
        )
        self.volume_relationships_tab = EditableVolumeTableTab(
            artifact_label="Volume Relationships",
            list_key="relationship_pronoun_canon",
            canon_kind="relationships",
            canon_lens=self.canon_lens,
            columns=[
                ColumnSpec("id", "ID"),
                ColumnSpec("speaker", "Speaker", True),
                ColumnSpec("listener", "Listener", True),
                ColumnSpec("relationship", "Relationship", True),
                ColumnSpec("self", "Self", True),
                ColumnSpec("other", "Other", True),
                ColumnSpec("scope", "Scope", True),
                ColumnSpec("status", "Status", True),
                ColumnSpec("notes", "Notes", True),
                ColumnSpec("needs_human_review", "Needs Review", True, "bool"),
                ColumnSpec("variants", "Variants", False, "count"),
                ColumnSpec("canon_status", "Canon Status"),
            ],
            raw_edit_title="Relationship Rule",
            default_row_factory=self.editor_actions.default_volume_relationship_row,
            save_callback=self.editor_actions.save_volume_relationships_draft,
            approve_callback=self.editor_actions.approve_volume_relationships,
            approve_button_text="Approve Relationships",
        )
        self.segment_glossaries_tab = EditableSegmentJsonlTab(
            artifact_label="Segment Glossaries",
            canon_kind="glossary",
            canon_lens=self.canon_lens,
            summary_columns=[
                ("item_id", "Item ID"),
                ("status", "Status"),
                ("segment", "Segment"),
                ("terms_count", "Terms"),
                ("missing_count", "Missing"),
            ],
            detail_columns=[
                ColumnSpec("id", "ID"),
                ColumnSpec("source", "Source", True),
                ColumnSpec("vi", "Vietnamese", True),
                ColumnSpec("type", "Type", True),
                ColumnSpec("status", "Status", True),
                ColumnSpec("notes", "Notes", True),
                ColumnSpec("needs_human_review", "Needs Review", True, "bool"),
                ColumnSpec("aliases", "Aliases", False, "count"),
                ColumnSpec("variants", "Variants", False, "count"),
                ColumnSpec("forbidden_translations", "Forbidden", False, "count"),
                ColumnSpec("appears_in", "Appears In", False, "count"),
                ColumnSpec("canon_status", "Canon Status"),
            ],
            raw_edit_title="Segment Glossary Entry",
            load_callback=self.editor_actions.load_segment_glossary,
            save_callback=self.editor_actions.save_segment_glossary,
            list_getter=self.editor_actions.get_segment_glossary_entries,
            default_entry_factory=self.editor_actions.default_segment_glossary_entry,
            add_button_text="Add Entry",
            duplicate_button_text="Duplicate Entry",
            delete_button_text="Delete Entry",
            save_button_text="Save Segment Glossary",
        )
        self.segment_pronouns_tab = EditableSegmentJsonlTab(
            artifact_label="Segment Pronouns",
            canon_kind="relationships",
            canon_lens=self.canon_lens,
            summary_columns=[
                ("item_id", "Item ID"),
                ("status", "Status"),
                ("segment", "Segment"),
                ("rules_count", "Rules"),
                ("overrides_count", "Overrides"),
                ("missing_count", "Missing"),
            ],
            detail_columns=[
                ColumnSpec("id", "ID"),
                ColumnSpec("speaker", "Speaker", True),
                ColumnSpec("listener", "Listener", True),
                ColumnSpec("relationship", "Relationship", True),
                ColumnSpec("self", "Self", True),
                ColumnSpec("other", "Other", True),
                ColumnSpec("scope", "Scope", True),
                ColumnSpec("status", "Status", True),
                ColumnSpec("notes", "Notes", True),
                ColumnSpec("needs_human_review", "Needs Review", True, "bool"),
                ColumnSpec("source", "Source"),
                ColumnSpec("confidence", "Confidence"),
                ColumnSpec("canon_status", "Canon Status"),
            ],
            raw_edit_title="Segment Pronoun Rule",
            load_callback=self.editor_actions.load_segment_pronouns,
            save_callback=self.editor_actions.save_segment_pronouns,
            list_getter=self.editor_actions.get_segment_pronoun_rules,
            default_entry_factory=self.editor_actions.default_segment_pronoun_rule,
            add_button_text="Add Rule",
            duplicate_button_text="Duplicate Rule",
            delete_button_text="Delete Rule",
            save_button_text="Save Segment Pronouns",
        )
        self.segment_contexts_tab = ArtifactTableTab(
            [
                ("item_id", "Item ID"),
                ("status", "Status"),
                ("segment", "Segment"),
                ("scene_type", "Scene Type"),
                ("tone", "Tone"),
                ("characters_count", "Characters"),
            ]
        )
        self.dialogue_labels_tab = EditableDialogueLabelsTab(self.editor_actions)
        self.translations_tab = EditableTranslationsTab(self.editor_actions)
        self.raw_json_viewer = RawJsonViewer()

        self.tabs.addTab(self.volume_glossary_tab, "Volume Glossary")
        self.tabs.addTab(self.volume_relationships_tab, "Volume Relationships")
        self.tabs.addTab(self.segment_glossaries_tab, "Segment Glossaries")
        self.tabs.addTab(self.segment_pronouns_tab, "Segment Pronouns")
        self.tabs.addTab(self.segment_contexts_tab, "Segment Contexts")
        self.tabs.addTab(self.dialogue_labels_tab, "Dialogue Labels")
        self.tabs.addTab(self.translations_tab, "Translations")
        self.tabs.addTab(self.raw_json_viewer, "Raw JSON")

        for tab in (
            self.volume_glossary_tab,
            self.volume_relationships_tab,
            self.segment_glossaries_tab,
            self.segment_pronouns_tab,
            self.segment_contexts_tab,
            self.dialogue_labels_tab,
            self.translations_tab,
        ):
            tab.object_selected.connect(self.raw_json_viewer.set_object)
            tab.object_selected.connect(lambda _obj: self._emit_raw_edit_target())

        for label, tab in self._editable_tabs():
            tab.dirty_changed.connect(lambda dirty, base_label=label: self._update_dirty_label(base_label, dirty))
            tab.status_message.connect(self.status_message.emit)
            tab.artifact_written.connect(self.artifacts_changed.emit)
            tab.reload_requested.connect(self.reload_requested.emit)
            tab.dirty_changed.connect(lambda _dirty: self._emit_raw_edit_target())

        for tab in (
            self.volume_glossary_tab,
            self.volume_relationships_tab,
            self.segment_glossaries_tab,
            self.segment_pronouns_tab,
        ):
            tab.open_series_canon_requested.connect(self.open_series_canon_requested.emit)

        self.tabs.currentChanged.connect(lambda _index: self._emit_raw_edit_target())

        layout.addWidget(self.tabs)

    def _editable_tabs(self) -> list[tuple[str, Any]]:
        return [
            ("Volume Glossary", self.volume_glossary_tab),
            ("Volume Relationships", self.volume_relationships_tab),
            ("Segment Glossaries", self.segment_glossaries_tab),
            ("Segment Pronouns", self.segment_pronouns_tab),
            ("Dialogue Labels", self.dialogue_labels_tab),
            ("Translations", self.translations_tab),
        ]

    def _update_dirty_label(self, base_label: str, dirty: bool) -> None:
        target = f"{base_label} *" if dirty else base_label
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index).replace(" *", "") == base_label:
                self.tabs.setTabText(index, target)
                break

    def _emit_raw_edit_target(self) -> None:
        target, message = self.current_raw_edit_target()
        self.raw_edit_target_changed.emit(target, message)
