from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from manual_studio.core.manual_workflow import SelectionContext
from manual_studio.core.progress import ProgressService, StepProgress
from manual_studio.core.project_index import ProjectIndex
from manual_studio.core.workspace import Workspace
from manual_studio.ui.progress_widgets import ProgressTableWidget


class ProjectProgressPage(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, workspace: Workspace | None = None, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        placeholder_workspace = workspace if workspace is not None else Workspace(".")
        self.progress_service = ProgressService(placeholder_workspace)
        self.project_index = ProjectIndex(workspace) if workspace is not None else None
        self.current_context: SelectionContext | None = None
        self.current_selected_id = "No selection"
        self._build_ui()
        self.refresh_project_data()

    def set_workspace(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.progress_service = ProgressService(workspace)
        self.project_index = ProjectIndex(workspace)
        self.refresh_project_data()

    def set_selection_context(self, context: SelectionContext | None, selected_id: str = "No selection") -> None:
        self.current_context = context
        self.current_selected_id = selected_id
        if context is not None:
            self._set_volume_value(context.volume)
        self.refresh_current_view()

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
            self.status_label.setText(f"Loaded {len(volumes)} volume(s) for progress tracking.")
        else:
            self.status_label.setText("No source volumes were found for this project.")

        self.refresh_current_view()

    def refresh_current_view(self) -> None:
        context = self._effective_context()
        if context is None:
            self.context_value.setText("No selection")
            self.summary_scope_value.setText("none")
            self.progress_table.set_progress([])
            self._set_summary([])
            return

        rows = self._progress_rows_for_context(context)
        selected_id = self.current_selected_id if self.current_context is not None else f"Volume {context.volume:02d}"
        self.context_value.setText(selected_id)
        self.summary_scope_value.setText(context.scope)
        self.progress_table.set_progress(rows)
        self._set_summary(rows)
        self.status_message.emit(f"Loaded progress for {context.scope} in volume {context.volume:02d}.")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Project Progress")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Volume"))
        self.volume_combo = QComboBox()
        self.volume_combo.currentIndexChanged.connect(self._on_volume_changed)
        controls.addWidget(self.volume_combo)
        controls.addSpacing(12)
        scope_label = QLabel("Current filter")
        scope_label.setObjectName("mutedLabel")
        controls.addWidget(scope_label)
        self.summary_scope_value = QLabel("none")
        self.summary_scope_value.setObjectName("mutedLabel")
        controls.addWidget(self.summary_scope_value)
        controls.addSpacing(12)
        selected_label = QLabel("Selected ID")
        selected_label.setObjectName("mutedLabel")
        controls.addWidget(selected_label)
        self.context_value = QLabel("No selection")
        self.context_value.setObjectName("mutedLabel")
        controls.addWidget(self.context_value, 1)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_project_data)
        controls.addWidget(self.refresh_button)
        layout.addLayout(controls)

        summary_row = QHBoxLayout()
        self.total_steps_label = QLabel("Total steps: 0")
        self.done_steps_label = QLabel("Done: 0")
        self.partial_steps_label = QLabel("Partial: 0")
        self.not_started_steps_label = QLabel("Not started: 0")
        self.missing_source_label = QLabel("Missing source: 0")
        for label in (
            self.total_steps_label,
            self.done_steps_label,
            self.partial_steps_label,
            self.not_started_steps_label,
            self.missing_source_label,
        ):
            label.setObjectName("mutedLabel")
            summary_row.addWidget(label)
        summary_row.addStretch(1)
        layout.addLayout(summary_row)

        self.status_label = QLabel("Select a project item to inspect progress.")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress_table = ProgressTableWidget()
        layout.addWidget(self.progress_table, 1)

    def _selected_volume(self) -> int | None:
        value = self.volume_combo.currentData()
        return value if isinstance(value, int) else None

    def _set_volume_value(self, volume: int) -> None:
        index = self.volume_combo.findData(volume)
        if index >= 0:
            self.volume_combo.blockSignals(True)
            try:
                self.volume_combo.setCurrentIndex(index)
            finally:
                self.volume_combo.blockSignals(False)

    def _effective_context(self) -> SelectionContext | None:
        if self.current_context is not None:
            return self.current_context
        volume = self._selected_volume()
        if volume is None:
            return None
        return SelectionContext(scope="volume", volume=volume)

    def _progress_rows_for_context(self, context: SelectionContext) -> list[StepProgress]:
        if context.scope == "volume":
            return self.progress_service.volume_progress(context.volume)
        if context.scope == "chapter" and context.chapter is not None:
            return self.progress_service.chapter_progress(context.volume, str(context.chapter))
        if context.scope == "segment" and context.segment is not None:
            return self.progress_service.segment_progress(context.volume, context.segment)
        return []

    def _set_summary(self, rows: list[StepProgress]) -> None:
        total_steps = len(rows)
        done_steps = sum(1 for row in rows if row.status == "done")
        partial_steps = sum(1 for row in rows if row.status == "partial")
        not_started_steps = sum(1 for row in rows if row.status == "not_started")
        missing_source = sum(1 for row in rows if row.status == "missing_source")

        self.total_steps_label.setText(f"Total steps: {total_steps}")
        self.done_steps_label.setText(f"Done: {done_steps}")
        self.partial_steps_label.setText(f"Partial: {partial_steps}")
        self.not_started_steps_label.setText(f"Not started: {not_started_steps}")
        self.missing_source_label.setText(f"Missing source: {missing_source}")

    def _on_volume_changed(self) -> None:
        volume = self._selected_volume()
        if volume is None:
            return
        self.current_context = SelectionContext(scope="volume", volume=volume)
        self.current_selected_id = f"Volume {volume:02d}"
        self.refresh_current_view()
