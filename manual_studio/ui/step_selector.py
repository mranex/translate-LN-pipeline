from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from manual_studio.core.step_registry import Step


class StepSelectorWidget(QWidget):
    step_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def set_steps(self, steps: list[Step]) -> None:
        self.combo.blockSignals(True)
        self.combo.clear()
        for step in steps:
            mode = "Local Action" if step.is_local_action else "Prompt Step"
            label = f"{step.label} [{mode}]"
            self.combo.addItem(label, step)
        self.combo.blockSignals(False)
        self._update_metadata()
        if self.combo.count():
            self.combo.setCurrentIndex(0)
            self.step_changed.emit(self.selected_step_id() or "")

    def selected_step(self) -> Step | None:
        data = self.combo.currentData()
        return data if isinstance(data, Step) else None

    def selected_step_id(self) -> str | None:
        step = self.selected_step()
        return step.id if step is not None else None

    def set_current_step_id(self, step_id: str) -> bool:
        for index in range(self.combo.count()):
            step = self.combo.itemData(index)
            if isinstance(step, Step) and step.id == step_id:
                self.combo.setCurrentIndex(index)
                return True
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_selection_changed)
        layout.addWidget(self.combo)

        self.meta_label = QLabel("No step selected.")
        self.meta_label.setObjectName("mutedLabel")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

    def _on_selection_changed(self) -> None:
        self._update_metadata()
        self.step_changed.emit(self.selected_step_id() or "")

    def _update_metadata(self) -> None:
        step = self.selected_step()
        if step is None:
            self.meta_label.setText("No step selected.")
            return
        mode = "Local Action" if step.is_local_action else "Prompt Step"
        artifact_mode = "writes artifact" if step.writes_artifact else "no artifact write"
        self.meta_label.setText(f"ID: {step.id} | Scope: {step.scope} | Type: {mode} | {artifact_mode}")
