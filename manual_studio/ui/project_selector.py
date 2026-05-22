from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class ProjectSelectorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Manual Studio Project")
        self.resize(640, 220)
        self._build_ui()
        self.root_edit.setText(str(Path.cwd()))
        self.refresh_projects()

    def selected_repo_root(self) -> str:
        return self.root_edit.text().strip()

    def selected_project_name(self) -> str:
        return self.project_combo.currentText().strip()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Open Existing Manual Project")
        title.setObjectName("titleLabel")
        subtitle = QLabel("Select a repo root and one of the discovered projects under data/.")
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        root_row = QHBoxLayout()
        self.root_edit = QLineEdit()
        self.root_edit.editingFinished.connect(self.refresh_projects)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self.browse_root)
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(browse_button)
        form.addRow("Repo root", root_row)

        self.project_combo = QComboBox()
        self.project_combo.setEditable(False)
        form.addRow("Project", self.project_combo)

        self.info_label = QLabel("")
        self.info_label.setObjectName("mutedLabel")
        self.info_label.setWordWrap(True)
        form.addRow("Status", self.info_label)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select Repo Root", self.selected_repo_root() or str(Path.cwd()))
        if selected:
            self.root_edit.setText(selected)
            self.refresh_projects()

    def refresh_projects(self) -> None:
        root = Path(self.selected_repo_root()).expanduser()
        current = self.selected_project_name()

        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.blockSignals(False)

        if not root.exists() or not root.is_dir():
            self.info_label.setText("Repo root does not exist yet.")
            return

        data_dir = root.joinpath("data")
        if not data_dir.exists() or not data_dir.is_dir():
            self.info_label.setText("No data/ directory found under the selected repo root.")
            return

        projects = sorted(
            directory.name
            for directory in data_dir.iterdir()
            if directory.is_dir() and directory.name not in {"source", "segments"}
        )
        self.project_combo.addItems(projects)

        if current:
            index = self.project_combo.findText(current)
            if index >= 0:
                self.project_combo.setCurrentIndex(index)

        if not projects:
            self.info_label.setText("No projects were found under data/.")
        else:
            self.info_label.setText(f"Found {len(projects)} project(s).")

    def _accept_if_valid(self) -> None:
        if not self.selected_repo_root():
            QMessageBox.warning(self, "Select Project", "Please choose a repo root.")
            return
        if not self.selected_project_name():
            QMessageBox.warning(self, "Select Project", "Please choose a project.")
            return
        self.accept()
