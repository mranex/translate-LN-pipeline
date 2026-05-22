from __future__ import annotations

import json

from PyQt6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from manual_studio.core.jsonio import pretty


class RawJsonViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.clear_placeholder()

    def set_object(self, obj) -> None:
        if obj is None:
            self.clear_placeholder()
            return
        self.status_label.setText("Showing raw JSON for the selected object.")
        try:
            if isinstance(obj, (dict, list)):
                text = pretty(obj)
            else:
                text = json.dumps(obj, ensure_ascii=False, indent=2)
        except Exception:
            text = str(obj)
        self.text_edit.setPlainText(text)

    def clear_placeholder(self, message: str = "Select a row in any Editor tab to inspect its raw JSON.") -> None:
        self.status_label.setText(message)
        self.text_edit.setPlainText("")

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit, 1)
