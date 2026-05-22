from __future__ import annotations

import copy

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget

from manual_studio.core.editor_actions import EditorActionService
from manual_studio.core.editor_index import EditorIndex, EditorSnapshot
from manual_studio.core.manual_workflow import SelectionContext
from manual_studio.core.workspace import Workspace
from manual_studio.ui.editor_artifact_tabs import EditorArtifactTabs
from manual_studio.ui.raw_edit_panel import RawEditPanel


class EditorPage(QWidget):
    status_message = pyqtSignal(str)
    artifacts_changed = pyqtSignal()
    open_series_canon_requested = pyqtSignal(str, object, int)

    def __init__(self, workspace: Workspace | None = None, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        placeholder_workspace = workspace if workspace is not None else Workspace(".")
        self.editor_actions = EditorActionService(placeholder_workspace)
        self.editor_index = EditorIndex(workspace) if workspace is not None else None
        self.current_context: SelectionContext | None = None
        self.current_selected_id = "No selection"
        self._build_ui()

    def set_workspace(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.editor_actions = EditorActionService(workspace)
        self.editor_index = EditorIndex(workspace)
        old_tabs = self.artifact_tabs
        self.artifact_tabs = self._make_artifact_tabs()
        self.editor_splitter.replaceWidget(0, self.artifact_tabs)
        old_tabs.deleteLater()
        self._on_raw_edit_target_changed(*self.artifact_tabs.current_raw_edit_target())
        if self.current_context is not None:
            self.refresh_current_view(force=True)

    def has_unsaved_changes(self) -> bool:
        return self.artifact_tabs.has_unsaved_changes()

    def set_selection_context(self, context: SelectionContext | None, selected_id: str, prompt_on_dirty: bool = True) -> bool:
        if prompt_on_dirty and not self._resolve_raw_edit_changes(f"switching to {selected_id}"):
            self.status_message.emit("Selection change canceled.")
            return False
        if prompt_on_dirty and self.current_context is not None and self.artifact_tabs.has_unsaved_changes():
            if not self.artifact_tabs.resolve_unsaved_changes(self, f"switching to {selected_id}"):
                self.status_message.emit("Selection change canceled.")
                return False

        self.current_context = context
        self.current_selected_id = selected_id
        self.scope_value.setText(context.scope if context is not None else "none")
        self.selected_id_value.setText(selected_id)
        self.refresh_current_view(force=True)
        return True

    def refresh_current_view(self, force: bool = False) -> bool:
        if not force and self.artifact_tabs.has_unsaved_changes():
            self.status_label.setText("Editor has unsaved changes. Background refresh was skipped.")
            self.status_message.emit("Editor refresh skipped because there are unsaved changes.")
            return False

        if self.editor_index is None or self.current_context is None:
            self.artifact_tabs.set_snapshot(EditorSnapshot.empty(), None)
            self.status_label.setText("No Editor selection is available.")
            self.status_message.emit("Editor is waiting for a selection.")
            return True

        try:
            snapshot = self.editor_index.load_snapshot(self.current_context)
        except Exception as exc:
            self.artifact_tabs.set_snapshot(EditorSnapshot.empty(), None)
            self.status_label.setText(str(exc))
            self.status_message.emit(str(exc))
            QMessageBox.critical(self, "Editor Refresh Failed", str(exc))
            return False

        self.artifact_tabs.set_snapshot(snapshot, self.current_context)
        self.status_label.setText("Editor refreshed for the current selection.")
        self.status_message.emit("Editor refreshed.")
        return True

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title_row = QHBoxLayout()
        title = QLabel("Editor")
        title.setObjectName("titleLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.raw_edit_toggle = QPushButton("Raw Edit")
        self.raw_edit_toggle.setCheckable(True)
        self.raw_edit_toggle.toggled.connect(self._on_raw_edit_toggled)
        title_row.addWidget(self.raw_edit_toggle)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        title_row.addWidget(self.refresh_button)
        layout.addLayout(title_row)

        self.scope_value = QLabel("none")
        self.scope_value.setObjectName("mutedLabel")
        self.selected_id_value = QLabel("No selection")
        self.selected_id_value.setObjectName("mutedLabel")
        layout.addWidget(QLabel("Selected scope"))
        layout.addWidget(self.scope_value)
        layout.addWidget(QLabel("Selected ID"))
        layout.addWidget(self.selected_id_value)

        self.status_label = QLabel(
            "Volume canon, Segment Glossaries, Segment Pronouns, Dialogue Labels, and Translations support editing. Segment Contexts, QA previews, and Raw JSON remain read-only."
        )
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.artifact_tabs = self._make_artifact_tabs()
        self.raw_edit_panel = RawEditPanel()
        self.raw_edit_panel.apply_requested.connect(self._on_raw_edit_apply_requested)
        self.raw_edit_panel.reset_requested.connect(self._on_raw_edit_reset_requested)
        self.raw_edit_panel.hide()

        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor_splitter.addWidget(self.artifact_tabs)
        self.editor_splitter.addWidget(self.raw_edit_panel)
        self.editor_splitter.setStretchFactor(0, 4)
        self.editor_splitter.setStretchFactor(1, 2)
        layout.addWidget(self.editor_splitter, 1)

    def _on_refresh_clicked(self) -> None:
        if not self._resolve_raw_edit_changes("reloading the current editor view"):
            return
        if self.artifact_tabs.has_unsaved_changes():
            if not self.artifact_tabs.resolve_unsaved_changes(self, "reloading the current editor view"):
                return
        self.refresh_current_view(force=True)

    def _on_artifacts_changed(self) -> None:
        self.refresh_current_view(force=True)
        self.artifacts_changed.emit()

    def _on_raw_edit_toggled(self, checked: bool) -> None:
        if not checked and not self._resolve_raw_edit_changes("hiding the raw edit panel"):
            self.raw_edit_toggle.blockSignals(True)
            self.raw_edit_toggle.setChecked(True)
            self.raw_edit_toggle.blockSignals(False)
            self.raw_edit_panel.setVisible(True)
            return
        self.raw_edit_panel.setVisible(checked)
        if checked:
            self.editor_splitter.setSizes([900, 420])
            self._on_raw_edit_target_changed(*self.artifact_tabs.current_raw_edit_target())
            self.status_message.emit("Raw edit panel opened.")
        else:
            self.editor_splitter.setSizes([1, 0])
            self.status_message.emit("Raw edit panel hidden.")

    def _on_raw_edit_target_changed(self, target, message: str) -> None:
        current_key = self.raw_edit_panel.current_target.selection_key if self.raw_edit_panel.current_target is not None else None
        next_key = target.selection_key if target is not None else None
        if self.raw_edit_toggle.isChecked() and self.raw_edit_panel.has_unapplied_changes() and current_key != next_key:
            self.raw_edit_panel.status_label.setText(
                "Raw edit has unapplied changes. Apply or Reset before following the new selection."
            )
            return
        self.raw_edit_panel.set_target(target, message)

    def _on_raw_edit_apply_requested(self, obj: dict) -> None:
        self._apply_raw_edit_payload(obj)

    def _on_raw_edit_reset_requested(self) -> None:
        self.raw_edit_panel.reset_from_current()
        target, message = self.artifact_tabs.current_raw_edit_target()
        self.raw_edit_panel.set_target(target, message or "Reset from the current in-memory selection.")
        self.status_message.emit("Raw edit reset from the current selection.")

    def _make_artifact_tabs(self) -> EditorArtifactTabs:
        tabs = EditorArtifactTabs(self.editor_actions, self.workspace)
        tabs.status_message.connect(self.status_message.emit)
        tabs.artifacts_changed.connect(self._on_artifacts_changed)
        tabs.reload_requested.connect(lambda: self.refresh_current_view(force=True))
        tabs.raw_edit_target_changed.connect(self._on_raw_edit_target_changed)
        tabs.open_series_canon_requested.connect(self.open_series_canon_requested.emit)
        return tabs

    def _resolve_raw_edit_changes(self, reason: str) -> bool:
        if not self.raw_edit_panel.has_unapplied_changes():
            return True

        choice = self._raw_edit_choice(reason)
        if choice == QMessageBox.StandardButton.Apply:
            payload, error = self.raw_edit_panel.parsed_json_or_error()
            if error is not None:
                self.raw_edit_panel.status_label.setText(error)
                self.status_message.emit(error)
                return False
            return self._apply_raw_edit_payload(payload)
        if choice == QMessageBox.StandardButton.Discard:
            self.raw_edit_panel.reset_from_current()
            return True
        return False

    def _apply_raw_edit_payload(self, payload) -> bool:
        target = self.raw_edit_panel.current_target
        if target is None or target.apply_callback is None:
            message = "Select an editable object before applying raw JSON."
            self.raw_edit_panel.status_label.setText(message)
            self.status_message.emit(message)
            return False
        try:
            message = target.apply_callback(copy.deepcopy(payload))
        except Exception as exc:
            QMessageBox.critical(self, "Raw Edit Apply Failed", str(exc))
            self.status_message.emit(str(exc))
            self.raw_edit_panel.status_label.setText(str(exc))
            return False

        status_message = message or "Applied in memory. Click Save to write artifact."
        if "Applied raw JSON" not in status_message:
            status_message = f"Applied raw JSON in memory. {status_message}"
        next_target, next_message = self.artifact_tabs.current_raw_edit_target()
        self.raw_edit_panel.set_target(
            next_target,
            status_message or next_message or "Applied raw JSON in memory. Click Save to write artifact.",
        )
        self.status_message.emit(status_message)
        return True

    def _raw_edit_choice(self, reason: str) -> QMessageBox.StandardButton:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Raw Edit Changes")
        box.setText("Raw Edit has unapplied changes.")
        box.setInformativeText(f"What would you like to do before {reason}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Apply
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Apply)
        return QMessageBox.StandardButton(box.exec())
