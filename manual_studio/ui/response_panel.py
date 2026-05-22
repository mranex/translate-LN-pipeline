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
        self.status_label.setText("Response cleared.")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Response")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.status_label = QLabel("Generate a prompt for a prompt-backed step to enable validation.")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.validate_button = QPushButton("Validate Response")
        self.import_button = QPushButton("Import Response")
        self.clear_button = QPushButton("Clear Response")
        actions.addWidget(self.validate_button)
        actions.addWidget(self.import_button)
        actions.addWidget(self.clear_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.response_edit = QTextEdit()
        self.response_edit.setPlaceholderText("Paste model JSON response here.")
        layout.addWidget(self.response_edit, 1)

        self.set_validate_enabled(False)
        self.set_import_enabled(False)
