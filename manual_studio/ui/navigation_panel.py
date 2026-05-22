from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from manual_studio.core.project_index import ProjectIndex
from manual_studio.core.workspace import Workspace


class NavigationPanel(QWidget):
    selection_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.workspace: Workspace | None = None
        self.index: ProjectIndex | None = None
        self._build_ui()

    def set_workspace(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.index = ProjectIndex(workspace)
        self.reload()

    def reload(self) -> None:
        self.tree.clear()
        self.empty_label.hide()

        if self.index is None:
            self.empty_label.setText("Chưa mở dự án nào.")
            self.empty_label.show()
            return

        volumes = self.index.list_volumes()
        if not volumes:
            self.empty_label.setText("Không tìm thấy tập truyện gốc nào cho dự án này.")
            self.empty_label.show()
            return

        for volume in volumes:
            volume_item = QTreeWidgetItem([f"📖 Tập {volume:02d}"])
            volume_item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                {"scope": "volume", "volume": volume, "selected_id": f"Volume {volume:02d}"},
            )
            self.tree.addTopLevelItem(volume_item)

            chapters_group = QTreeWidgetItem(["📜 Danh sách Chương"])
            chapters_group.setFlags(chapters_group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            volume_item.addChild(chapters_group)
            for chapter_record in self.index.get_chapter_records(volume):
                chapter_label = f"c{int(chapter_record.get('chapter', 0)):03d}"
                display_label = f"📜 Chương {int(chapter_record.get('chapter', 0)):02d}"
                chapter_item = QTreeWidgetItem([display_label])
                chapter_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {
                        "scope": "chapter",
                        "volume": volume,
                        "chapter": chapter_record.get("chapter"),
                        "chapter_id": chapter_label,
                        "selected_id": chapter_label,
                    },
                )
                chapters_group.addChild(chapter_item)

            segments_group = QTreeWidgetItem(["🔸 Danh sách Phân đoạn"])
            segments_group.setFlags(segments_group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            volume_item.addChild(segments_group)
            for segment_id in self.index.list_segments(volume):
                display_segment = f"🔸 Đoạn {segment_id}"
                segment_item = QTreeWidgetItem([display_segment])
                segment_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    {"scope": "segment", "volume": volume, "segment_id": segment_id, "selected_id": segment_id},
                )
                segments_group.addChild(segment_item)

        self.tree.expandAll()
        self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def select_payload(self, payload: dict) -> bool:
        target = self._find_item_by_payload(payload)
        if target is None:
            return False
        self.tree.blockSignals(True)
        try:
            self.tree.setCurrentItem(target)
        finally:
            self.tree.blockSignals(False)
        return True

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        label = QLabel("Điều Hướng Dự Án")
        label.setObjectName("titleLabel")
        layout.addWidget(label)

        self.empty_label = QLabel("")
        self.empty_label.setObjectName("mutedLabel")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setAlternatingRowColors(False)
        self.tree.setIndentation(16)
        self.tree.itemSelectionChanged.connect(self._emit_selection)
        layout.addWidget(self.tree, 1)

    def _emit_selection(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict):
            self.selection_changed.emit(payload)

    def _find_item_by_payload(self, payload: dict) -> QTreeWidgetItem | None:
        for index in range(self.tree.topLevelItemCount()):
            found = self._find_item_recursive(self.tree.topLevelItem(index), payload)
            if found is not None:
                return found
        return None

    def _find_item_recursive(self, item: QTreeWidgetItem, payload: dict) -> QTreeWidgetItem | None:
        item_payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(item_payload, dict) and item_payload == payload:
            return item
        for index in range(item.childCount()):
            found = self._find_item_recursive(item.child(index), payload)
            if found is not None:
                return found
        return None
