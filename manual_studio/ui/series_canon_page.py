from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manual_studio.core.jsonio import read_json
from manual_studio.core.manual_workflow import ManualWorkflowService, SelectionContext
from manual_studio.core.project_index import ProjectIndex
from manual_studio.core.series_canon import SeriesCanonService
from manual_studio.core.workspace import Workspace
from manual_studio.ui.raw_json_viewer import RawJsonViewer


class CanonListTab(QWidget):
    object_selected = pyqtSignal(object)

    def __init__(self, columns: list[tuple[str, str]], empty_message: str, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.empty_message = empty_message
        self.entries: list[dict[str, Any]] = []
        self.title_message = ""
        self._build_ui()

    def set_entries(self, entries: list[dict[str, Any]], title_message: str = "") -> None:
        self.entries = [entry for entry in entries if isinstance(entry, dict)]
        self.title_message = title_message or self.empty_message
        self.count_label.setText(f"Số mục: {len(self.entries)}")
        self.status_label.setText(self.title_message if self.entries else self.empty_message)
        self.table.clearContents()
        self.table.setRowCount(len(self.entries))

        for row_index, entry in enumerate(self.entries):
            for column_index, (key, _label) in enumerate(self.columns):
                value = entry.get(key, "")
                if isinstance(value, list):
                    text = str(len(value))
                elif value is None:
                    text = ""
                else:
                    text = str(value)
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(row_index, column_index, item)

        if self.entries:
            self.table.resizeRowsToContents()
        self.object_selected.emit(None)

    def clear(self, message: str) -> None:
        self.entries = []
        self.count_label.setText("Số mục: 0")
        self.status_label.setText(message)
        self.table.clearContents()
        self.table.setRowCount(0)
        self.object_selected.emit(None)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.count_label = QLabel("Số mục: 0")
        self.count_label.setObjectName("mutedLabel")
        self.status_label = QLabel(self.empty_message)
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        header.addWidget(self.count_label)
        header.addSpacing(12)
        header.addWidget(self.status_label, 1)
        layout.addLayout(header)

        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels([label for _key, label in self.columns])
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._emit_selected_object)
        layout.addWidget(self.table, 1)

    def _emit_selected_object(self) -> None:
        row_index = self.table.currentRow()
        if 0 <= row_index < len(self.entries):
            self.object_selected.emit(self.entries[row_index])
        else:
            self.object_selected.emit(None)


class SyncReportTab(QWidget):
    object_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.glossary_report: dict[str, Any] | None = None
        self.relationships_report: dict[str, Any] | None = None
        self._build_ui()

    def set_reports(
        self,
        glossary_report: dict[str, Any] | None,
        relationships_report: dict[str, Any] | None,
    ) -> None:
        self.glossary_report = glossary_report if isinstance(glossary_report, dict) else None
        self.relationships_report = relationships_report if isinstance(relationships_report, dict) else None
        self.glossary_report_tab.set_entries(
            self._flatten_report_rows(self.glossary_report),
            self._report_summary(self.glossary_report, "Không tìm thấy báo cáo đồng bộ thuật ngữ cho tập này."),
        )
        self.relationships_report_tab.set_entries(
            self._flatten_report_rows(self.relationships_report),
            self._report_summary(self.relationships_report, "Không tìm thấy báo cáo đồng bộ đại từ nhân xưng cho tập này."),
        )
        self._emit_report_object()

    def clear(self, message: str) -> None:
        self.glossary_report = None
        self.relationships_report = None
        self.glossary_report_tab.clear(message)
        self.relationships_report_tab.clear(message)
        self.object_selected.emit(None)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.report_tabs = QTabWidget()
        report_columns = [
            ("section", "Phân Nhóm"),
            ("summary", "Tóm Tắt"),
            ("reason", "Lý Do"),
        ]
        self.glossary_report_tab = CanonListTab(report_columns, "Không tìm thấy báo cáo đồng bộ thuật ngữ cho tập này.")
        self.relationships_report_tab = CanonListTab(
            report_columns,
            "Không tìm thấy báo cáo đồng bộ đại từ nhân xưng cho tập này.",
        )
        self.report_tabs.addTab(self.glossary_report_tab, "Báo Cáo Thuật Ngữ")
        self.report_tabs.addTab(self.relationships_report_tab, "Báo Cáo Nhân Xưng")
        self.report_tabs.currentChanged.connect(lambda _index: self._emit_report_object())
        self.glossary_report_tab.object_selected.connect(self._forward_selected_object)
        self.relationships_report_tab.object_selected.connect(self._forward_selected_object)
        layout.addWidget(self.report_tabs)

    def _flatten_report_rows(self, report_obj: dict[str, Any] | None) -> list[dict[str, Any]]:
        if not isinstance(report_obj, dict):
            return []

        rows: list[dict[str, Any]] = []
        for section in ("added", "skipped", "conflicts", "ambiguous"):
            section_vi = "Thêm mới" if section == "added" else ("Bỏ qua" if section == "skipped" else ("Xung đột" if section == "conflicts" else "Mơ hồ"))
            value = report_obj.get(section)
            if not isinstance(value, list):
                continue
            for entry in value:
                if not isinstance(entry, dict):
                    continue
                row = dict(entry)
                row["section"] = section_vi
                row["reason"] = str(entry.get("reason", ""))
                row["summary"] = self._summary_for_report_entry(entry)
                rows.append(row)
        return rows

    def _summary_for_report_entry(self, entry: dict[str, Any]) -> str:
        for key in ("volume_entry", "series_entry"):
            value = entry.get(key)
            if not isinstance(value, dict):
                continue
            source = value.get("source")
            if isinstance(source, str) and source.strip():
                return source.strip()
            speaker = value.get("speaker")
            listener = value.get("listener")
            if isinstance(speaker, str) and isinstance(listener, str):
                return f"{speaker} -> {listener}"
        identity = entry.get("identity")
        if isinstance(identity, list) and len(identity) == 2:
            return f"{identity[0]} -> {identity[1]}"
        return "Mục báo cáo"

    def _report_summary(self, report_obj: dict[str, Any] | None, empty_message: str) -> str:
        if not isinstance(report_obj, dict):
            return empty_message
        counts = []
        for section in ("added", "skipped", "conflicts", "ambiguous"):
            section_vi = "thêm mới" if section == "added" else ("bỏ qua" if section == "skipped" else ("xung đột" if section == "conflicts" else "mơ hồ"))
            value = report_obj.get(section)
            if isinstance(value, list):
                counts.append(f"{section_vi}={len(value)}")
        if not counts:
            return empty_message
        return ", ".join(counts)

    def _forward_selected_object(self, obj: object) -> None:
        if obj is not None:
            self.object_selected.emit(obj)
            return
        self._emit_report_object()

    def _emit_report_object(self) -> None:
        if self.report_tabs.currentWidget() is self.glossary_report_tab:
            self.object_selected.emit(self.glossary_report)
        else:
            self.object_selected.emit(self.relationships_report)


class SeriesCanonPage(QWidget):
    status_message = pyqtSignal(str)
    workflow_changed = pyqtSignal()

    def __init__(
        self,
        workspace: Workspace | None = None,
        workflow_service: ManualWorkflowService | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.workspace = workspace
        self.workflow_service = workflow_service
        self.project_index = ProjectIndex(workspace) if workspace is not None else None
        self.series_service = SeriesCanonService(workspace if workspace is not None else Workspace("."))
        self.current_context: SelectionContext | None = None
        self._busy = False
        self._build_ui()
        self.refresh_project_data()

    def set_workspace(self, workspace: Workspace, workflow_service: ManualWorkflowService | None = None) -> None:
        self.workspace = workspace
        self.workflow_service = workflow_service or self.workflow_service
        self.project_index = ProjectIndex(workspace)
        self.series_service = SeriesCanonService(workspace)
        self.refresh_project_data()

    def set_selection_context(self, context: SelectionContext | None) -> None:
        self.current_context = context
        if context is not None:
            self._set_volume_value(context.volume)
        self.refresh_current_view()

    def refresh_project_data(self) -> None:
        current_volume = self._selected_volume()
        volumes = self.project_index.list_volumes() if self.project_index is not None else []

        self.volume_combo.blockSignals(True)
        try:
            self.volume_combo.clear()
            for volume in volumes:
                self.volume_combo.addItem(f"Tập {volume:02d}", volume)
        finally:
            self.volume_combo.blockSignals(False)

        if volumes:
            target_volume = self.current_context.volume if self.current_context is not None else current_volume
            if target_volume in volumes:
                self._set_volume_value(target_volume)
            else:
                self.volume_combo.setCurrentIndex(0)
            self.status_label.setText(f"Đã tải {len(volumes)} tập để rà soát Canon hệ truyện.")
        else:
            self.status_label.setText("Không tìm thấy tập dữ liệu gốc nào trong dự án này.")
        self._sync_button_state()
        self.refresh_current_view()

    def refresh_current_view(self) -> None:
        volume = self._selected_volume()
        if self.workspace is None or volume is None:
            message = "Chọn một tập truyện để kiểm tra các dữ liệu Canon hệ truyện."
            self.series_glossary_tab.clear(message)
            self.series_relationships_tab.clear(message)
            self.active_glossary_tab.clear(message)
            self.active_relationships_tab.clear(message)
            self.sync_report_tab.clear(message)
            self.raw_json_viewer.clear_placeholder(message)
            self.summary_label.setText("Chưa chọn tập truyện.")
            return

        try:
            series_glossary = self.series_service.load_series_glossary()
            series_relationships = self.series_service.load_series_relationships()
            active_glossary = self.series_service.build_active_volume_glossary(volume, write=False).payload
            active_relationships = self.series_service.build_active_volume_relationships(volume, write=False).payload
        except Exception as exc:
            message = str(exc)
            self.series_glossary_tab.clear(message)
            self.series_relationships_tab.clear(message)
            self.active_glossary_tab.clear(message)
            self.active_relationships_tab.clear(message)
            self.sync_report_tab.clear(message)
            self.raw_json_viewer.clear_placeholder(message)
            self.summary_label.setText(message)
            self.status_message.emit(message)
            return

        self.series_glossary_tab.set_entries(
            series_glossary.get("volume_merge_glossary", []),
            "Đã tải Thuật ngữ Canon hệ truyện.",
        )
        self.series_relationships_tab.set_entries(
            series_relationships.get("relationship_pronoun_canon", []),
            "Đã tải Nhân xưng Canon hệ truyện.",
        )
        self.active_glossary_tab.set_entries(
            active_glossary.get("volume_merge_glossary", []),
            f"Xem trước Thuật ngữ khả dụng cho Tập {volume:02d}.",
        )
        self.active_relationships_tab.set_entries(
            active_relationships.get("relationship_pronoun_canon", []),
            f"Xem trước Nhân xưng khả dụng cho Tập {volume:02d}.",
        )
        glossary_report = read_json(self.workspace.series_glossary_sync_report(volume), None)
        relationships_report = read_json(self.workspace.series_relationships_sync_report(volume), None)
        self.sync_report_tab.set_reports(glossary_report, relationships_report)
        self.summary_label.setText(
            f"Tập {volume:02d}: Thuật ngữ hệ truyện {len(series_glossary.get('volume_merge_glossary', []))} mục, "
            f"Nhân xưng hệ truyện {len(series_relationships.get('relationship_pronoun_canon', []))} quy tắc."
        )

    def focus_glossary_entry(self, volume: int, entry: dict[str, Any]) -> bool:
        self._set_volume_value(volume)
        self.current_context = SelectionContext(scope="volume", volume=volume)
        self.refresh_current_view()
        self.data_tabs.setCurrentWidget(self.series_glossary_tab)

        for index, candidate in enumerate(self.series_glossary_tab.entries):
            if self.series_service.glossary_entries_overlap(entry, candidate):
                self.series_glossary_tab.table.selectRow(index)
                self.raw_json_viewer.set_object(candidate)
                self._show_message(f"Đã tập trung vào mục Thuật ngữ tương thích hệ truyện cho Tập {volume:02d}.")
                return True

        self.series_glossary_tab.table.clearSelection()
        self.raw_json_viewer.clear_placeholder("Không tìm thấy mục Thuật ngữ hệ truyện tương thích.")
        self._show_message(f"Không tìm thấy mục Thuật ngữ hệ truyện tương thích cho Tập {volume:02d}.")
        return False

    def focus_relationship_entry(self, volume: int, entry: dict[str, Any]) -> bool:
        self._set_volume_value(volume)
        self.current_context = SelectionContext(scope="volume", volume=volume)
        self.refresh_current_view()
        self.data_tabs.setCurrentWidget(self.series_relationships_tab)

        target_identity = self.series_service.relationship_identity(entry)
        if target_identity is None:
            self.series_relationships_tab.table.clearSelection()
            self.raw_json_viewer.clear_placeholder("Mối quan hệ được chọn không có nhận diện hướng hợp lệ.")
            self._show_message("Mối quan hệ được chọn không có nhận diện hướng hợp lệ.")
            return False

        for index, candidate in enumerate(self.series_relationships_tab.entries):
            if self.series_service.relationship_identity(candidate) == target_identity:
                self.series_relationships_tab.table.selectRow(index)
                self.raw_json_viewer.set_object(candidate)
                self._show_message(f"Đã tập trung vào mục Nhân xưng tương thích hệ truyện cho Tập {volume:02d}.")
                return True

        self.series_relationships_tab.table.clearSelection()
        self.raw_json_viewer.clear_placeholder("Không tìm thấy quy tắc Nhân xưng hệ truyện tương thích.")
        self._show_message(f"Không tìm thấy quy tắc Nhân xưng hệ truyện tương thích cho Tập {volume:02d}.")
        return False

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Bộ Não Canon Hệ Truyện")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        subtitle = QLabel(
            "Rà soát thuật ngữ và đại từ nhân xưng ở cấp độ toàn bộ hệ truyện (Series-level), xem trước Canon khả dụng cho từng tập, và thực hiện các thao tác đồng bộ hóa."
        )
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.addWidget(QLabel("Tập truyện"))
        self.volume_combo = QComboBox()
        self.volume_combo.currentIndexChanged.connect(self._on_volume_changed)
        controls_layout.addWidget(self.volume_combo)

        self.refresh_button = QPushButton("Làm Mới")
        self.refresh_button.setObjectName("aiButton")
        self.refresh_button.clicked.connect(self.refresh_project_data)
        controls_layout.addWidget(self.refresh_button)

        self.initialize_series_button = QPushButton("Khởi Tạo Hệ Truyện Từ Tập")
        self.initialize_series_button.clicked.connect(
            lambda: self._run_action_batch(
                [
                    "initialize_series_glossary_from_volume",
                    "initialize_series_relationships_from_volume",
                ]
            )
        )
        controls_layout.addWidget(self.initialize_series_button)

        self.build_active_glossary_button = QPushButton("Xây Dựng Thuật Ngữ Khả Dụng")
        self.build_active_glossary_button.clicked.connect(
            lambda: self._run_action_batch(["build_active_volume_glossary"])
        )
        controls_layout.addWidget(self.build_active_glossary_button)

        self.build_active_relationships_button = QPushButton("Xây Dựng Đại Từ Nhân Xưng Khả Dụng")
        self.build_active_relationships_button.clicked.connect(
            lambda: self._run_action_batch(["build_active_volume_relationships"])
        )
        controls_layout.addWidget(self.build_active_relationships_button)

        self.sync_glossary_button = QPushButton("Đồng Bộ Thuật Ngữ Lên Hệ Truyện")
        self.sync_glossary_button.clicked.connect(
            lambda: self._run_action_batch(["sync_volume_glossary_to_series"])
        )
        controls_layout.addWidget(self.sync_glossary_button)

        self.sync_relationships_button = QPushButton("Đồng Bộ Nhân Xưng Lên Hệ Truyện")
        self.sync_relationships_button.clicked.connect(
            lambda: self._run_action_batch(["sync_volume_relationships_to_series"])
        )
        controls_layout.addWidget(self.sync_relationships_button)

        controls_layout.addStretch(1)
        self.summary_label = QLabel("Chưa chọn tập truyện.")
        self.summary_label.setObjectName("mutedLabel")
        self.summary_label.setWordWrap(True)
        controls_layout.addWidget(self.summary_label)
        self.status_label = QLabel("Chọn một tập truyện để kiểm tra dữ liệu Canon hệ truyện.")
        self.status_label.setObjectName("mutedLabel")
        self.status_label.setWordWrap(True)
        controls_layout.addWidget(self.status_label)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        self.data_tabs = QTabWidget()
        self.series_glossary_tab = CanonListTab(
            [("id", "Mã"), ("source", "Từ Gốc"), ("vi", "Tiếng Việt"), ("type", "Phân Loại"), ("status", "Trạng Thái")],
            "Không tìm thấy mục Thuật ngữ hệ truyện nào.",
        )
        self.series_relationships_tab = CanonListTab(
            [
                ("id", "Mã"),
                ("speaker", "Người Nói"),
                ("listener", "Người Nghe"),
                ("relationship", "Mối Quan Hệ"),
                ("self", "Xưng Mình"),
                ("other", "Gọi Đối Phương"),
            ],
            "Không tìm thấy quy tắc Nhân xưng hệ truyện nào.",
        )
        self.active_glossary_tab = CanonListTab(
            [("id", "Mã"), ("source", "Từ Gốc"), ("vi", "Tiếng Việt"), ("type", "Phân Loại"), ("status", "Trạng Thái")],
            "Không có Thuật ngữ tập nào tương thích.",
        )
        self.active_relationships_tab = CanonListTab(
            [
                ("id", "Mã"),
                ("speaker", "Người Nói"),
                ("listener", "Người Nghe"),
                ("relationship", "Mối Quan Hệ"),
                ("self", "Xưng Mình"),
                ("other", "Gọi Đối Phương"),
            ],
            "Không có Nhân xưng tập nào tương thích.",
        )
        self.sync_report_tab = SyncReportTab()
        self.data_tabs.addTab(self.series_glossary_tab, "Thuật Ngữ Hệ Truyện")
        self.data_tabs.addTab(self.series_relationships_tab, "Nhân Xưng Hệ Truyện")
        self.data_tabs.addTab(self.active_glossary_tab, "Thuật Ngữ Khả Dụng Tập")
        self.data_tabs.addTab(self.active_relationships_tab, "Nhân Xưng Khả Dụng Tập")
        self.data_tabs.addTab(self.sync_report_tab, "Báo Cáo Đồng Bộ")
        center_layout.addWidget(self.data_tabs)

        self.raw_json_viewer = RawJsonViewer()
        self.raw_json_viewer.clear_placeholder("Chọn một dòng dữ liệu Canon hệ truyện để xem nội dung JSON gốc.")

        for tab in (
            self.series_glossary_tab,
            self.series_relationships_tab,
            self.active_glossary_tab,
            self.active_relationships_tab,
            self.sync_report_tab,
        ):
            tab.object_selected.connect(self.raw_json_viewer.set_object)

        splitter.addWidget(controls_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(self.raw_json_viewer)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter, 1)

    def _selected_volume(self) -> int | None:
        value = self.volume_combo.currentData()
        return value if isinstance(value, int) else None

    def _set_volume_value(self, volume: int) -> None:
        index = self.volume_combo.findData(volume)
        if index >= 0:
            self.volume_combo.blockSignals(True)
            try:
                self.volume_combo.setCurrentIndex(index)
            finally:
                self.volume_combo.blockSignals(False)

    def _on_volume_changed(self) -> None:
        volume = self._selected_volume()
        if volume is None:
            self.refresh_current_view()
            return
        self.current_context = SelectionContext(scope="volume", volume=volume)
        self.refresh_current_view()

    def _run_action_batch(self, step_ids: list[str]) -> None:
        if self.workflow_service is None:
            self._show_message("Dịch vụ quy trình (Workflow service) không hoạt động.")
            return
        volume = self._selected_volume()
        if volume is None:
            self._show_message("Vui lòng chọn một tập truyện trước.")
            return

        context = SelectionContext(scope="volume", volume=volume)
        messages: list[str] = []
        try:
            self._set_busy(True)
            for step_id in step_ids:
                outcome = self.workflow_service.run_local_action(step_id, context)
                messages.append(outcome.message)
        except Exception as exc:
            self._show_error("Thao Tác Canon Hệ Truyện Thất Bại", exc)
            return
        finally:
            self._set_busy(False)

        message = "\n".join(messages)
        self.refresh_current_view()
        self.status_label.setText(message)
        self.status_message.emit(message)
        self.workflow_changed.emit()

    def _sync_button_state(self) -> None:
        enabled = self._selected_volume() is not None and not self._busy
        for button in (
            self.initialize_series_button,
            self.build_active_glossary_button,
            self.build_active_relationships_button,
            self.sync_glossary_button,
            self.sync_relationships_button,
        ):
            button.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        elif QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()
        self.volume_combo.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self._sync_button_state()

    def _show_message(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_message.emit(message)

    def _show_error(self, title: str, exc: Exception) -> None:
        message = str(exc)
        self.status_label.setText(message)
        self.status_message.emit(message)
        QMessageBox.critical(self, title, message)
