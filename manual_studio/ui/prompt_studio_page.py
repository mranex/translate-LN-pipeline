from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from manual_studio.core.manual_workflow import LocalActionResult, ManualWorkflowService, SelectionContext
from manual_studio.core.step_registry import Step
from manual_studio.ui.response_panel import ResponsePanel
from manual_studio.ui.step_selector import StepSelectorWidget


class PromptStudioPage(QWidget):
    status_message = pyqtSignal(str)
    import_completed = pyqtSignal()
    workflow_changed = pyqtSignal()

    def __init__(self, workflow_service: ManualWorkflowService | None = None, parent=None):
        super().__init__(parent)
        self.workflow_service = workflow_service
        self.current_context: SelectionContext | None = None
        self.current_selected_id = "No selection"
        self.generated_step_id: str | None = None
        self.generated_is_local = False
        self.parsed_response: dict | None = None
        self._build_ui()

    def set_workflow_service(self, workflow_service: ManualWorkflowService) -> None:
        self.workflow_service = workflow_service
        if self.current_context is not None:
            self._load_steps_for_context()

    def set_selection_context(self, context: SelectionContext | None, selected_id: str) -> None:
        self.current_context = context
        self.current_selected_id = selected_id
        if context is None:
            self.set_selection_summary("none", selected_id)
            self.step_selector.set_steps([])
            self._reset_generated_state(clear_response=False)
            self.workflow_status.setText("No selection context available.")
            return

        self.set_selection_summary(context.scope, selected_id)
        self._load_steps_for_context()

    def set_selection_summary(self, scope_type: str, selected_id: str) -> None:
        self.scope_value.setText(scope_type)
        self.selected_id_value.setText(selected_id)
        self.context_value.setText(f"{scope_type} | {selected_id}")

    def set_progress(self, rows: list[object]) -> None:
        _ = rows

    def set_review_flags(self, flags: list[object], message: str = "") -> None:
        _ = flags
        _ = message

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title_row = QHBoxLayout()
        title = QLabel("Prompt Studio")
        title.setObjectName("titleLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        context_label = QLabel("Selected context")
        context_label.setObjectName("mutedLabel")
        title_row.addWidget(context_label)
        self.context_value = QLabel("none | No selection")
        self.context_value.setObjectName("mutedLabel")
        title_row.addWidget(self.context_value)
        layout.addLayout(title_row)

        context_row = QHBoxLayout()
        scope_label = QLabel("Scope")
        scope_label.setObjectName("mutedLabel")
        context_row.addWidget(scope_label)
        self.scope_value = QLabel("none")
        self.scope_value.setObjectName("mutedLabel")
        context_row.addWidget(self.scope_value)
        context_row.addSpacing(16)
        selected_id_label = QLabel("Selected ID")
        selected_id_label.setObjectName("mutedLabel")
        context_row.addWidget(selected_id_label)
        self.selected_id_value = QLabel("No selection")
        self.selected_id_value.setObjectName("mutedLabel")
        context_row.addWidget(self.selected_id_value)
        context_row.addStretch(1)
        layout.addLayout(context_row)

        header_row = QHBoxLayout()
        selector_panel = QWidget()
        selector_layout = QVBoxLayout(selector_panel)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_label = QLabel("Available step")
        selector_label.setObjectName("mutedLabel")
        selector_layout.addWidget(selector_label)
        self.step_selector = StepSelectorWidget()
        self.step_selector.step_changed.connect(self._on_step_changed)
        selector_layout.addWidget(self.step_selector)
        header_row.addWidget(selector_panel, 1)

        action_column = QVBoxLayout()
        action_column.setContentsMargins(0, 0, 0, 0)
        action_row = QHBoxLayout()
        self.generate_prompt_button = QPushButton("Generate Prompt")
        self.copy_prompt_button = QPushButton("Copy Prompt")
        self.run_local_action_button = QPushButton("Run Local Action")
        self.copy_prompt_button.setEnabled(False)
        self.run_local_action_button.setEnabled(False)
        self.generate_prompt_button.clicked.connect(self._generate_prompt)
        self.copy_prompt_button.clicked.connect(self._copy_prompt)
        self.run_local_action_button.clicked.connect(self._run_local_action)
        action_row.addWidget(self.generate_prompt_button)
        action_row.addWidget(self.copy_prompt_button)
        action_row.addWidget(self.run_local_action_button)
        action_column.addLayout(action_row)
        header_row.addLayout(action_column)
        layout.addLayout(header_row)

        self.prompt_response_splitter = QSplitter(Qt.Orientation.Horizontal)

        prompt_panel = QWidget()
        prompt_layout = QVBoxLayout(prompt_panel)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_label = QLabel("Prompt Preview")
        prompt_label.setObjectName("titleLabel")
        prompt_layout.addWidget(prompt_label)
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setPlaceholderText("Generated prompt text will appear here.")
        prompt_layout.addWidget(self.prompt_preview, 1)

        self.response_panel = ResponsePanel()
        self.response_panel.validate_button.clicked.connect(self._validate_response)
        self.response_panel.import_button.clicked.connect(self._import_response)
        self.response_panel.clear_button.clicked.connect(self._clear_response)

        self.prompt_response_splitter.addWidget(prompt_panel)
        self.prompt_response_splitter.addWidget(self.response_panel)
        self.prompt_response_splitter.setStretchFactor(0, 3)
        self.prompt_response_splitter.setStretchFactor(1, 2)
        layout.addWidget(self.prompt_response_splitter, 1)

        self.workflow_status = QLabel("Select a project item and step to begin.")
        self.workflow_status.setObjectName("mutedLabel")
        self.workflow_status.setWordWrap(True)
        layout.addWidget(self.workflow_status)

    def _load_steps_for_context(self) -> None:
        self._reset_generated_state(clear_response=False)
        if self.workflow_service is None or self.current_context is None:
            self.step_selector.set_steps([])
            self.workflow_status.setText("Workflow service is not available.")
            return
        try:
            steps = self.workflow_service.available_steps(self.current_context.scope)
        except Exception as exc:
            self.step_selector.set_steps([])
            self._show_error("Failed to load available steps.", exc)
            return
        self.step_selector.set_steps(steps)
        if steps:
            self._update_step_mode()
        else:
            self.workflow_status.setText("No steps are available for this scope.")

    def _on_step_changed(self, _step_id: str) -> None:
        self._reset_generated_state(clear_response=False)
        self._update_step_mode()

    def _update_step_mode(self) -> None:
        step = self.step_selector.selected_step()
        if step is None:
            self.generate_prompt_button.setEnabled(False)
            self.copy_prompt_button.setEnabled(False)
            self.run_local_action_button.setEnabled(False)
            self.workflow_status.setText("No step selected.")
            return

        if step.is_local_action:
            self.generate_prompt_button.setEnabled(False)
            self.copy_prompt_button.setEnabled(False)
            self.run_local_action_button.setEnabled(True)
            self.response_panel.set_validate_enabled(False)
            self.response_panel.set_import_enabled(False)
            if step.writes_artifact:
                self.response_panel.set_status("Local action selected. Use Run Local Action to update the artifact.")
                self.workflow_status.setText("Local action selected. Run it to update the current artifact.")
            else:
                self.response_panel.set_status("Local placeholder selected. Run Local Action to see the placeholder message.")
                self.workflow_status.setText("Local placeholder selected. Editor-backed handling will arrive in a later phase.")
            return

        self.generate_prompt_button.setEnabled(True)
        self.run_local_action_button.setEnabled(False)
        self.copy_prompt_button.setEnabled(False)
        self.response_panel.set_validate_enabled(False)
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status("Generate a prompt for this step, then paste and validate a response.")
        self.workflow_status.setText("Prompt-backed step selected. Generate prompt to continue.")

    def _generate_prompt(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("No workflow context is available.")
            return
        step = self.step_selector.selected_step()
        if step is None:
            self._show_message("Please select a step first.")
            return
        if step.is_local_action:
            self._show_message("This is a local action. Use Run Local Action instead of Generate Prompt.")
            return
        try:
            result = self.workflow_service.render_prompt(step.id, self.current_context)
        except Exception as exc:
            self._show_error("Failed to generate prompt.", exc)
            return

        self.generated_step_id = result.step_id
        self.generated_is_local = result.is_local_action
        self.parsed_response = None
        self.copy_prompt_button.setEnabled(bool((result.prompt_text or result.message).strip()))
        self.prompt_preview.setPlainText(result.prompt_text or result.message or "")

        if result.is_local_action:
            self.response_panel.set_validate_enabled(False)
            self.response_panel.set_import_enabled(False)
            self.response_panel.set_status("Local/manual step. Response import is disabled.")
            self.workflow_status.setText(result.message or "Local/manual step selected.")
            self.status_message.emit(result.message or "Local/manual step selected.")
            return

        self.response_panel.set_validate_enabled(True)
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status("Paste a response and validate it before import.")
        self.workflow_status.setText(f"Prompt ready for step '{result.step_id}'.")
        self.status_message.emit(f"Generated prompt for {result.step_id}.")

    def _copy_prompt(self) -> None:
        text = self.prompt_preview.toPlainText().strip()
        if not text:
            self._show_message("No prompt text is available to copy.")
            return
        QApplication.clipboard().setText(text)
        self.workflow_status.setText("Prompt copied to clipboard.")
        self.status_message.emit("Prompt copied to clipboard.")

    def _validate_response(self) -> None:
        if self.workflow_service is None:
            self._show_message("Workflow service is not available.")
            return
        if not self.generated_step_id or self.generated_is_local:
            self._show_message("Generate a prompt for a prompt-backed step before validating a response.")
            return

        text = self.response_panel.response_text().strip()
        if not text:
            self._show_message("Please paste a response before validating.")
            return

        try:
            self.parsed_response = self.workflow_service.validate_response_text(text)
        except Exception as exc:
            self.parsed_response = None
            self.response_panel.set_import_enabled(False)
            self.response_panel.set_status("Response is not valid JSON for this workflow.")
            self._show_error("Response validation failed.", exc)
            return

        self.response_panel.set_import_enabled(True)
        self.response_panel.set_status("Response is valid and ready to import.")
        self.workflow_status.setText("Response validated successfully.")
        self.status_message.emit("Response validated successfully.")

    def _import_response(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("Workflow context is not available.")
            return
        if not self.generated_step_id or self.generated_is_local:
            self._show_message("The selected step is local/manual and cannot import a response.")
            return
        if self.parsed_response is None:
            self._show_message("Validate the response before importing it.")
            return

        try:
            outcome = self.workflow_service.import_response(
                self.generated_step_id,
                self.current_context,
                self.parsed_response,
            )
        except Exception as exc:
            self._show_error("Failed to import response.", exc)
            return

        self.parsed_response = None
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status(outcome.message)
        self.workflow_status.setText(outcome.message)
        self.status_message.emit(outcome.message)
        self.import_completed.emit()
        self.workflow_changed.emit()

    def _run_local_action(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("Workflow context is not available.")
            return

        step = self.step_selector.selected_step()
        if step is None:
            self._show_message("Please select a step first.")
            return
        if not step.is_local_action:
            self._show_message("The selected step is prompt-backed. Use Generate Prompt instead.")
            return

        try:
            outcome = self.workflow_service.run_local_action(step.id, self.current_context)
        except Exception as exc:
            self._show_error("Failed to run local action.", exc)
            return

        self._apply_local_action_result(step, outcome)
        self.import_completed.emit()
        self.workflow_changed.emit()

    def _clear_response(self) -> None:
        self.parsed_response = None
        self.response_panel.clear_response()
        self.response_panel.set_import_enabled(False)
        if self.generated_step_id and not self.generated_is_local:
            self.response_panel.set_validate_enabled(True)
        self.status_message.emit("Response cleared.")

    def _reset_generated_state(self, clear_response: bool) -> None:
        self.generated_step_id = None
        self.generated_is_local = False
        self.parsed_response = None
        self.copy_prompt_button.setEnabled(False)
        self.prompt_preview.clear()
        self.response_panel.set_validate_enabled(False)
        self.response_panel.set_import_enabled(False)
        self.run_local_action_button.setEnabled(False)
        if clear_response:
            self.response_panel.clear_response()
        else:
            self.response_panel.set_status("Generate a prompt for a prompt-backed step to enable validation.")

    def _apply_local_action_result(self, step: Step, outcome: LocalActionResult) -> None:
        self.generated_step_id = None
        self.generated_is_local = True
        self.parsed_response = None
        self.prompt_preview.setPlainText(outcome.message)
        self.copy_prompt_button.setEnabled(False)
        self.response_panel.set_validate_enabled(False)
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status(outcome.message)
        self.workflow_status.setText(outcome.message)
        self.status_message.emit(outcome.message)

    def _show_message(self, message: str) -> None:
        self.workflow_status.setText(message)
        self.status_message.emit(message)

    def _show_error(self, title: str, exc: Exception) -> None:
        message = str(exc)
        self.workflow_status.setText(message)
        self.status_message.emit(message)
        QMessageBox.critical(self, title, message)
