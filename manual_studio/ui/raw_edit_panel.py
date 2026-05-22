from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from manual_studio.core.jsonio import pretty


@dataclass(frozen=True)
class RawEditTarget:
    title: str
    obj: dict[str, Any] | list[Any] | None
    selection_key: str = ""
    editable: bool = True
    apply_callback: Callable[[dict[str, Any] | list[Any]], str] | None = None
    message: str = ""


class RawEditPanel(QWidget):
    apply_requested = pyqtSignal(object)
    reset_requested = pyqtSignal()
    dirty_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_target: RawEditTarget | None = None
        self._loaded_text = ""
        self._loading = False
        self._dirty = False
        self._build_ui()
        self.clear("Select an editable object to use Raw Edit.")

    def set_object(self, title: str, obj: dict[str, Any] | list[Any] | None, editable: bool = True) -> None:
        self._load_target(RawEditTarget(title=title, obj=obj, editable=editable), "")

    def set_target(self, target: RawEditTarget | None, message: str = "") -> None:
        self._load_target(target, message)

    def clear(self, message: str = "") -> None:
        self.show_placeholder(message or "Select an editable object to use Raw Edit.")

    def has_unapplied_changes(self) -> bool:
        return self._has_unapplied_text()

    def has_unapplied_text(self) -> bool:
        return self.has_unapplied_changes()

    def reset_from_current(self) -> None:
        self._load_target(self.current_target, self.current_target.message if self.current_target is not None else "")

    def parsed_json_or_error(self) -> tuple[object | None, str | None]:
        text = self.text_edit.toPlainText().strip()
        if not text:
            return None, "Raw edit JSON is empty."
        try:
            payload = json.loads(text)
        except Exception as exc:
            return None, f"Invalid JSON: {exc}"
        expected_is_list = isinstance(self.current_target.obj, list) if self.current_target is not None else False
        if expected_is_list:
            if not isinstance(payload, list):
                return None, "Expected a JSON array for this selection."
        elif not isinstance(payload, dict):
            return None, "Expected a JSON object for this selection."
        return payload, None

    def show_placeholder(self, message: str) -> None:
        self.current_target = None
        self._loading = True
        try:
            self.title_label.setText("Raw Edit")
            self.text_edit.setPlainText("")
            self.text_edit.setReadOnly(True)
        finally:
            self._loading = False
        self._loaded_text = ""
        self._set_dirty(False)
        self.status_label.setText(message)
        self._set_controls_enabled(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.title_label = QLabel("Raw Edit")
        self.title_label.setObjectName("titleLabel")
        layout.addWidget(self.title_label)

        self.info_label = QLabel("Apply raw JSON to the current in-memory selection. Save in the tab to write artifacts.")
        self.info_label.setObjectName("mutedLabel")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.text_edit = QTextEdit()
        self.text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.text_edit, 1)

        self.validate_button = QPushButton("Validate JSON")
        self.apply_button = QPushButton("Apply to Selection")
        self.reset_button = QPushButton("Reset From Selection")
        self.validate_button.clicked.connect(self._validate_json)
        self.apply_button.clicked.connect(self._apply_json)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self.validate_button)
        layout.addWidget(self.apply_button)
        layout.addWidget(self.reset_button)

        self._set_controls_enabled(False)

    def _has_unapplied_text(self) -> bool:
        return self.text_edit.toPlainText() != self._loaded_text

    def _set_controls_enabled(self, enabled: bool) -> None:
        editable = enabled and bool(self.current_target.editable) if self.current_target is not None else False
        self.text_edit.setEnabled(enabled)
        self.text_edit.setReadOnly(not editable)
        self.validate_button.setEnabled(enabled)
        self.apply_button.setEnabled(editable)
        self.reset_button.setEnabled(enabled)

    def _load_target(self, target: RawEditTarget | None, message: str) -> None:
        self.current_target = target
        self._loading = True
        try:
            if target is None:
                self.title_label.setText("Raw Edit")
                self.text_edit.setPlainText("")
                self.text_edit.setReadOnly(True)
                self._loaded_text = ""
                self._set_controls_enabled(False)
            else:
                text = pretty(target.obj) if isinstance(target.obj, (dict, list)) else ""
                self.title_label.setText(target.title)
                self.text_edit.setPlainText(text)
                self._loaded_text = text
                self._set_controls_enabled(isinstance(target.obj, (dict, list)))
        finally:
            self._loading = False

        self._set_dirty(False)
        if target is None:
            self.status_label.setText(message or "Select an editable object to use Raw Edit.")
        else:
            self.status_label.setText(
                message or target.message or "Applied changes stay in memory until you use the tab's Save action."
            )

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        if self.current_target is None:
            return
        if self._has_unapplied_text():
            self.status_label.setText("Raw JSON changed in memory. Apply or Reset before switching away.")
            self._set_dirty(True)
        else:
            self.status_label.setText("Raw JSON matches the current in-memory selection.")
            self._set_dirty(False)

    def _validate_json(self) -> None:
        _payload, error = self.parsed_json_or_error()
        if error is not None:
            self.status_label.setText(error)
            return
        title = self.current_target.title if self.current_target is not None else "selection"
        self.status_label.setText(f"Valid JSON for {title}.")

    def _apply_json(self) -> None:
        payload, error = self.parsed_json_or_error()
        if error is not None:
            self.status_label.setText(error)
            return
        self.apply_requested.emit(payload)

    def _on_reset_clicked(self) -> None:
        self.reset_requested.emit()

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirty_changed.emit(dirty)
