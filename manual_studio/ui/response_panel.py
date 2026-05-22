from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ResponsePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def response_text(self) -> str:
        return self.response_edit.toPlainText()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_validate_enabled(self, enabled: bool) -> None:
        self.validate_button.setEnabled(enabled)

    def set_import_enabled(self, enabled: bool) -> None:
        self.import_button.setEnabled(enabled)

    def clear_response(self) -> None:
        self.response_edit.clear()
        self.status_label.setText("Đã xóa nội dung phản hồi.")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Kết Quả AI Phản Hồi")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.status_label = QLabel("Hãy tạo Prompt trước để kích hoạt tính năng kiểm tra kết quả.")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.validate_button = QPushButton("Kiểm Tra Cú Pháp")
        self.import_button = QPushButton("Nhập Bản Dịch")
        self.import_button.setObjectName("aiButton")
        self.clear_button = QPushButton("Xóa Trắng Khung")
        self.clear_button.setObjectName("dangerButton")
        actions.addWidget(self.validate_button)
        actions.addWidget(self.import_button)
        actions.addWidget(self.clear_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.response_edit = QTextEdit()
        self.response_edit.setPlaceholderText("Dán kết quả phản hồi JSON của AI tại đây.")
        layout.addWidget(self.response_edit, 1)

        self.set_validate_enabled(False)
        self.set_import_enabled(False)
