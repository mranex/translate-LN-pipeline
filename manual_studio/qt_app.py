from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from manual_studio.core.workspace import Workspace
from manual_studio.ui.main_window import MainWindow
from manual_studio.ui.project_selector import ProjectSelectorDialog
from manual_studio.ui.theme import apply_app_theme


APP_TITLE = "Manual Studio v3"


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    app.setApplicationName(APP_TITLE)
    apply_app_theme(app)

    while True:
        dialog = ProjectSelectorDialog()
        if dialog.exec() != ProjectSelectorDialog.DialogCode.Accepted:
            return 0

        try:
            repo_root, project_name = _validate_selection(
                dialog.selected_repo_root(),
                dialog.selected_project_name(),
            )
        except ValueError as exc:
            QMessageBox.critical(None, APP_TITLE, str(exc))
            continue

        workspace = Workspace.from_legacy(repo_root, project_name)
        window = MainWindow(workspace=workspace, repo_root=repo_root, project_name=project_name)
        window.show()
        return app.exec()


def _validate_selection(repo_root: str, project_name: str) -> tuple[Path, str]:
    root = Path(repo_root).expanduser()
    if not repo_root or not root.exists() or not root.is_dir():
        raise ValueError("The selected repo root does not exist or is not a directory.")

    if not project_name:
        raise ValueError("Please select a project name.")

    project_root = root.joinpath("data", project_name)
    if not project_root.exists() or not project_root.is_dir():
        raise ValueError(f"Project not found: {project_root}")

    return root, project_name

if __name__ == "__main__":
    raise SystemExit(main())
