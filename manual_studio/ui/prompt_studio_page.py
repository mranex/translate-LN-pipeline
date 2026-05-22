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
        title = QLabel("Phòng Prompt AI")
        title.setObjectName("titleLabel")
        title_row.addWidget(title)
        title_row.addStretch(1)
        context_label = QLabel("Phân đoạn đang chọn:")
        context_label.setObjectName("mutedLabel")
        title_row.addWidget(context_label)
        self.context_value = QLabel("không có | Chưa chọn")
        self.context_value.setObjectName("mutedLabel")
        title_row.addWidget(self.context_value)
        layout.addLayout(title_row)

        context_row = QHBoxLayout()
        scope_label = QLabel("Phạm vi:")
        scope_label.setObjectName("mutedLabel")
        context_row.addWidget(scope_label)
        self.scope_value = QLabel("không có")
        self.scope_value.setObjectName("mutedLabel")
        context_row.addWidget(self.scope_value)
        context_row.addSpacing(16)
        selected_id_label = QLabel("Mã đã chọn:")
        selected_id_label.setObjectName("mutedLabel")
        context_row.addWidget(selected_id_label)
        self.selected_id_value = QLabel("Chưa chọn")
        self.selected_id_value.setObjectName("mutedLabel")
        context_row.addWidget(self.selected_id_value)
        context_row.addStretch(1)
        layout.addLayout(context_row)

        header_row = QHBoxLayout()
        selector_panel = QWidget()
        selector_layout = QVBoxLayout(selector_panel)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        selector_label = QLabel("Bước thực hiện khả dụng:")
        selector_label.setObjectName("mutedLabel")
        selector_layout.addWidget(selector_label)
        self.step_selector = StepSelectorWidget()
        self.step_selector.step_changed.connect(self._on_step_changed)
        selector_layout.addWidget(self.step_selector)

        # Khuyến nghị bước tiếp theo
        self.recommendation_label = QLabel("")
        self.recommendation_label.setStyleSheet("color: #06b6d4; font-weight: bold; background-color: #161e2e; border: 1px solid #06b6d4; border-radius: 4px; padding: 6px 10px; margin-top: 4px;")
        self.recommendation_label.setWordWrap(True)
        selector_layout.addWidget(self.recommendation_label)
        self.recommendation_label.hide()

        header_row.addWidget(selector_panel, 1)

        action_column = QVBoxLayout()
        action_column.setContentsMargins(0, 0, 0, 0)
        action_row = QHBoxLayout()
        self.generate_prompt_button = QPushButton("Tạo Prompt AI")
        self.generate_prompt_button.setObjectName("aiButton")
        self.copy_prompt_button = QPushButton("Sao Chép Prompt")
        self.run_local_action_button = QPushButton("Chạy Tiến Trình")
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
        prompt_label = QLabel("Xem Trước Prompt")
        prompt_label.setObjectName("titleLabel")
        prompt_layout.addWidget(prompt_label)
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setStyleSheet("font-family: 'Consolas', monospace; background-color: #0c0d14; border: 1px solid #1f233a;")
        self.prompt_preview.setPlaceholderText("Nội dung prompt được tạo sẽ xuất hiện tại đây.")
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

        self.workflow_status = QLabel("Hãy chọn phân đoạn của dự án và bước dịch để bắt đầu.")
        self.workflow_status.setObjectName("mutedLabel")
        self.workflow_status.setWordWrap(True)
        layout.addWidget(self.workflow_status)

    def _load_steps_for_context(self) -> None:
        self._reset_generated_state(clear_response=False)
        if self.workflow_service is None or self.current_context is None:
            self.step_selector.set_steps([])
            self.workflow_status.setText("Dịch vụ quy trình dịch thuật không khả dụng.")
            self.recommendation_label.hide()
            return
        try:
            steps = self.workflow_service.available_steps(self.current_context.scope)
        except Exception as exc:
            self.step_selector.set_steps([])
            self.recommendation_label.hide()
            self._show_error("Không tải được danh sách các bước.", exc)
            return
        self.step_selector.set_steps(steps)
        if steps:
            first_step = steps[0]
            self.recommendation_label.setText(f"🔥 Khuyến nghị: Bắt đầu bước '{first_step.label}' để tiếp tục tiến trình.")
            self.recommendation_label.show()
            self._update_step_mode()
        else:
            self.recommendation_label.hide()
            self.workflow_status.setText("Không có bước dịch nào khả dụng cho phân đoạn này.")

    def _on_step_changed(self, _step_id: str) -> None:
        self._reset_generated_state(clear_response=False)
        self._update_step_mode()

    def _update_step_mode(self) -> None:
        step = self.step_selector.selected_step()
        if step is None:
            self.generate_prompt_button.setEnabled(False)
            self.copy_prompt_button.setEnabled(False)
            self.run_local_action_button.setEnabled(False)
            self.workflow_status.setText("Chưa chọn bước thực hiện.")
            return

        if step.is_local_action:
            self.generate_prompt_button.setEnabled(False)
            self.copy_prompt_button.setEnabled(False)
            self.run_local_action_button.setEnabled(True)
            self.response_panel.set_validate_enabled(False)
            self.response_panel.set_import_enabled(False)
            if step.writes_artifact:
                self.response_panel.set_status("Đã chọn tiến trình nội bộ. Hãy chạy Tiến Trình để cập nhật dữ liệu.")
                self.workflow_status.setText("Đã chọn tiến trình nội bộ. Hãy chạy Tiến Trình để cập nhật dữ liệu.")
            else:
                self.response_panel.set_status("Đã chọn tiến trình mẫu. Hãy chạy Tiến Trình để xem thông báo mẫu.")
                self.workflow_status.setText("Đã chọn tiến trình mẫu. Hỗ trợ soạn thảo trực tiếp sẽ được cập nhật ở phiên bản sau.")
            return

        self.generate_prompt_button.setEnabled(True)
        self.run_local_action_button.setEnabled(False)
        self.copy_prompt_button.setEnabled(False)
        self.response_panel.set_validate_enabled(False)
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status("Hãy Tạo Prompt cho bước này, sau đó dán kết quả AI và thực hiện Kiểm Tra.")
        self.workflow_status.setText("Đã chọn bước dùng AI Prompt. Hãy Tạo Prompt để tiếp tục.")

    def _generate_prompt(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("Bối cảnh quy trình dịch thuật không khả dụng.")
            return
        step = self.step_selector.selected_step()
        if step is None:
            self._show_message("Vui lòng chọn bước thực hiện trước.")
            return
        if step.is_local_action:
            self._show_message("Đây là tiến trình nội bộ. Vui lòng bấm Chạy Tiến Trình thay vì Tạo Prompt.")
            return
        try:
            result = self.workflow_service.render_prompt(step.id, self.current_context)
        except Exception as exc:
            self._show_error("Tạo prompt thất bại.", exc)
            return

        self.generated_step_id = result.step_id
        self.generated_is_local = result.is_local_action
        self.parsed_response = None
        self.copy_prompt_button.setEnabled(bool((result.prompt_text or result.message).strip()))
        self.prompt_preview.setPlainText(result.prompt_text or result.message or "")

        if result.is_local_action:
            self.response_panel.set_validate_enabled(False)
            self.response_panel.set_import_enabled(False)
            self.response_panel.set_status("Tiến trình nội bộ/thủ công. Tính năng nhập phản hồi bị tắt.")
            self.workflow_status.setText(result.message or "Đã chọn tiến trình nội bộ/thủ công.")
            self.status_message.emit(result.message or "Đã chọn tiến trình nội bộ/thủ công.")
            return

        self.response_panel.set_validate_enabled(True)
        self.response_panel.set_import_enabled(False)
        self.response_panel.set_status("Dán phản hồi của AI và thực hiện Kiểm Tra trước khi nhập.")
        self.workflow_status.setText(f"Prompt đã sẵn sàng cho bước '{result.step_id}'.")
        self.status_message.emit(f"Đã tạo prompt cho {result.step_id}.")

    def _copy_prompt(self) -> None:
        text = self.prompt_preview.toPlainText().strip()
        if not text:
            self._show_message("Không có nội dung prompt nào để sao chép.")
            return
        QApplication.clipboard().setText(text)
        self.workflow_status.setText("Đã sao chép prompt vào bộ nhớ tạm.")
        self.status_message.emit("Đã sao chép prompt vào bộ nhớ tạm.")

    def _validate_response(self) -> None:
        if self.workflow_service is None:
            self._show_message("Dịch vụ quy trình dịch thuật không khả dụng.")
            return
        if not self.generated_step_id or self.generated_is_local:
            self._show_message("Vui lòng tạo Prompt cho bước dùng AI trước khi thực hiện Kiểm Tra.")
            return

        text = self.response_panel.response_text().strip()
        if not text:
            self._show_message("Vui lòng dán phản hồi của AI trước khi kiểm tra.")
            return

        try:
            self.parsed_response = self.workflow_service.validate_response_text(text)
        except Exception as exc:
            self.parsed_response = None
            self.response_panel.set_import_enabled(False)
            self.response_panel.set_status("Phản hồi không phải là JSON hợp lệ cho quy trình này.")
            self._show_error("Kiểm tra phản hồi thất bại.", exc)
            return

        self.response_panel.set_import_enabled(True)
        self.response_panel.set_status("Phản hồi hợp lệ và sẵn sàng nhập vào hệ thống.")
        self.workflow_status.setText("Kiểm tra phản hồi thành công.")
        self.status_message.emit("Kiểm tra phản hồi thành công.")

    def _import_response(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("Bối cảnh quy trình dịch thuật không khả dụng.")
            return
        if not self.generated_step_id or self.generated_is_local:
            self._show_message("Bước đã chọn là tiến trình nội bộ và không thể nhập phản hồi.")
            return
        if self.parsed_response is None:
            self._show_message("Vui lòng kiểm tra phản hồi trước khi nhập bản dịch.")
            return

        try:
            outcome = self.workflow_service.import_response(
                self.generated_step_id,
                self.current_context,
                self.parsed_response,
            )
        except Exception as exc:
            self._show_error("Nhập phản hồi thất bại.", exc)
            return

        self.parsed_response = None
        self.response_panel.set_import_enabled(False)
        # Tự động Việt hóa các thông báo thành công thường gặp từ lõi hệ thống nếu có thể, hoặc hiển thị nguyên bản
        msg = outcome.message
        if "Imported" in msg:
            msg = msg.replace("Imported", "Đã nhập thành công").replace("for scope", "cho phạm vi").replace("step", "bước")
        self.response_panel.set_status(msg)
        self.workflow_status.setText(msg)
        self.status_message.emit(msg)
        self.import_completed.emit()
        self.workflow_changed.emit()

    def _run_local_action(self) -> None:
        if self.workflow_service is None or self.current_context is None:
            self._show_message("Bối cảnh quy trình dịch thuật không khả dụng.")
            return

        step = self.step_selector.selected_step()
        if step is None:
            self._show_message("Vui lòng chọn bước thực hiện trước.")
            return
        if not step.is_local_action:
            self._show_message("Bước đã chọn dùng AI Prompt. Vui lòng bấm Tạo Prompt thay thế.")
            return

        try:
            outcome = self.workflow_service.run_local_action(step.id, self.current_context)
        except Exception as exc:
            self._show_error("Chạy tiến trình nội bộ thất bại.", exc)
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
        self.status_message.emit("Đã xóa nội dung phản hồi.")

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
            self.response_panel.set_status("Tạo Prompt cho một bước dùng AI để kích hoạt tính năng kiểm tra.")

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
