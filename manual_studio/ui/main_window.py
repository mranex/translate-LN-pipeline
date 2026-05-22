from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QSplitter, QTabWidget, QWidget, QVBoxLayout

from manual_studio.core.manual_workflow import ManualWorkflowService, SelectionContext
from manual_studio.core.workspace import Workspace
from manual_studio.ui.editor_page import EditorPage
from manual_studio.ui.navigation_panel import NavigationPanel
from manual_studio.ui.project_progress_page import ProjectProgressPage
from manual_studio.ui.prompt_studio_page import PromptStudioPage
from manual_studio.ui.release_center_page import ReleaseCenterPage
from manual_studio.ui.series_canon_page import SeriesCanonPage


class MainWindow(QMainWindow):
    def __init__(self, workspace: Workspace, repo_root: str | Path, project_name: str, parent=None):
        super().__init__(parent)
        self.workspace = workspace
        self.repo_root = Path(repo_root)
        self.project_name = project_name
        self.workflow_service = ManualWorkflowService(workspace)
        self.current_selection: dict | None = None
        self.current_context: SelectionContext | None = None

        self.setWindowTitle("Manual Studio v3 - Buồng Lái Dịch Thuật")
        
        icon_path = Path(__file__).parent / "app_icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            
        self.resize(1440, 920)
        self._build_ui()
        self._load_workspace()

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        splitter = QSplitter()
        self.navigation_panel = NavigationPanel()
        self.navigation_panel.selection_changed.connect(self._on_selection_changed)
        self.prompt_page = PromptStudioPage(self.workflow_service)
        self.prompt_page.status_message.connect(self.statusBar().showMessage)
        self.prompt_page.import_completed.connect(self._refresh_after_workflow_change)
        self.editor_page = EditorPage(self.workspace)
        self.editor_page.status_message.connect(self.statusBar().showMessage)
        self.editor_page.artifacts_changed.connect(self._refresh_after_workflow_change)
        self.editor_page.open_series_canon_requested.connect(self._open_series_canon_from_editor)
        self.progress_page = ProjectProgressPage(self.workspace)
        self.progress_page.status_message.connect(self.statusBar().showMessage)
        self.series_canon_page = SeriesCanonPage(self.workspace, self.workflow_service)
        self.series_canon_page.status_message.connect(self.statusBar().showMessage)
        self.series_canon_page.workflow_changed.connect(self._refresh_after_workflow_change)
        self.release_page = ReleaseCenterPage(self.workspace)
        self.release_page.status_message.connect(self.statusBar().showMessage)

        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.addTab(self.prompt_page, "Phòng Prompt AI")
        self.workspace_tabs.addTab(self.editor_page, "Trình Soạn Thảo")
        self.workspace_tabs.addTab(self.progress_page, "Tiến Độ Dự Án")
        self.workspace_tabs.addTab(self.series_canon_page, "Thư Viện Canon")
        self.workspace_tabs.addTab(self.release_page, "Trạm Xuất Bản")

        splitter.addWidget(self.navigation_panel)
        splitter.addWidget(self.workspace_tabs)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self.setCentralWidget(central)

        self.project_status = QLabel()
        self.selection_status = QLabel("Chưa chọn phân đoạn")
        self.statusBar().addPermanentWidget(self.project_status)
        self.statusBar().addPermanentWidget(self.selection_status, 1)
        self.project_status.setText(f"Dự án: {self.project_name} ({self.repo_root})")

    def _load_workspace(self) -> None:
        try:
            self.navigation_panel.set_workspace(self.workspace)
        except Exception as exc:
            QMessageBox.critical(self, "Manual Studio v3", f"Tải dự án thất bại:\n{exc}")
            self.prompt_page.set_selection_context(None, "Tải dự án thất bại")
            self.editor_page.set_selection_context(None, "Tải dự án thất bại", prompt_on_dirty=False)
            self.progress_page.set_selection_context(None, "Tải dự án thất bại")
            self.series_canon_page.set_selection_context(None)
            self.release_page.set_selection_context(None)

    def _on_selection_changed(self, selection: dict) -> None:
        try:
            next_context, selected_id = self._selection_context_from_payload(selection)
        except ValueError as exc:
            QMessageBox.critical(self, "Manual Studio v3", str(exc))
            self.prompt_page.set_selection_context(None, "Lựa chọn không hợp lệ")
            self.editor_page.set_selection_context(None, "Lựa chọn không hợp lệ", prompt_on_dirty=False)
            self.progress_page.set_selection_context(None, "Lựa chọn không hợp lệ")
            self.series_canon_page.set_selection_context(None)
            self.release_page.set_selection_context(None)
            self.selection_status.setText("Lựa chọn không hợp lệ")
            return

        if not self.editor_page.set_selection_context(next_context, selected_id, prompt_on_dirty=True):
            if self.current_selection is not None:
                self.navigation_panel.select_payload(self.current_selection)
            return

        self.current_selection = selection
        self.current_context = next_context
        self.prompt_page.set_selection_context(self.current_context, selected_id)
        self.progress_page.set_selection_context(self.current_context, selected_id)
        self.series_canon_page.set_selection_context(self.current_context)
        self.release_page.set_selection_context(self.current_context)
        self._update_selection_status()

    def _refresh_after_workflow_change(self) -> None:
        self.release_page.refresh_project_data()
        self.progress_page.refresh_current_view()
        self.editor_page.refresh_current_view(force=False)
        self.series_canon_page.refresh_project_data()
        self._update_selection_status()

    def _open_series_canon_from_editor(self, canon_kind: str, entry_obj: object, volume: int) -> None:
        if not isinstance(entry_obj, dict):
            self.statusBar().showMessage("Hãy chọn một mục canon trước khi mở trong Thư viện Canon.")
            return

        self.workspace_tabs.setCurrentWidget(self.series_canon_page)
        if canon_kind == "glossary":
            focused = self.series_canon_page.focus_glossary_entry(volume, entry_obj)
        elif canon_kind == "relationships":
            focused = self.series_canon_page.focus_relationship_entry(volume, entry_obj)
        else:
            self.statusBar().showMessage(f"Đối tượng Series Canon không được hỗ trợ: {canon_kind}")
            return

        if not focused:
            self.statusBar().showMessage("Không tìm thấy mục Series Canon tương ứng cho hàng soạn thảo đã chọn.")

    def _update_selection_status(self) -> None:
        if self.current_context is None:
            self.selection_status.setText("Chưa chọn phân đoạn")
            return

        scope = self.current_context.scope
        volume = self.current_context.volume
        if scope == "volume":
            status_text = f"Đang chọn tập {volume:02d}"
        elif scope == "chapter":
            status_text = f"Đang chọn tập {volume:02d}, chương {self.current_selected_id()}"
        elif scope == "segment":
            status_text = f"Đang chọn tập {volume:02d}, phân đoạn {self.current_context.segment}"
        else:
            status_text = "Không hỗ trợ lựa chọn này"
        self.selection_status.setText(status_text)

    def current_selected_id(self) -> str:
        if self.current_selection is None:
            return "Unknown"
        return str(self.current_selection.get("selected_id", "Unknown"))

    def _selection_context_from_payload(self, selection: dict) -> tuple[SelectionContext, str]:
        scope = str(selection.get("scope") or "")
        volume = selection.get("volume")
        if not isinstance(volume, int):
            raise ValueError("The selected item does not include a valid volume.")

        if scope == "volume":
            selected_id = str(selection.get("selected_id") or f"Volume {volume:02d}")
            return SelectionContext(scope="volume", volume=volume), selected_id

        if scope == "chapter":
            chapter_value = selection.get("chapter")
            if chapter_value is None:
                chapter_value = self._parse_chapter_id(selection.get("chapter_id"))
            try:
                chapter_int = int(chapter_value)
            except Exception as exc:
                raise ValueError("The selected chapter could not be converted to a numeric chapter id.") from exc
            selected_id = str(selection.get("selected_id") or selection.get("chapter_id") or chapter_int)
            return SelectionContext(scope="chapter", volume=volume, chapter=chapter_int), selected_id

        if scope == "segment":
            segment_id = str(selection.get("segment_id") or "")
            if not segment_id:
                raise ValueError("The selected segment does not include a valid segment id.")
            return SelectionContext(scope="segment", volume=volume, segment=segment_id), segment_id

        raise ValueError(f"Unsupported selection scope: {scope}")

    def _parse_chapter_id(self, chapter_id) -> int:
        if chapter_id is None:
            raise ValueError("The selected chapter does not include a chapter id.")
        text = str(chapter_id).strip()
        if text.lower().startswith("c"):
            text = text[1:]
        try:
            return int(text)
        except Exception as exc:
            raise ValueError(f"Could not parse chapter id '{chapter_id}'.") from exc
