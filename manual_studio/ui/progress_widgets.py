from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from manual_studio.core.progress import StepProgress


class ProgressTableWidget(QTableWidget):
    HEADERS = ["Bước Dịch", "Phạm Vi", "Hoàn Thành", "Tỉ Lệ (%)", "Trạng Thái"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(False)
        self.setShowGrid(False)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

    def set_progress(self, rows: list[StepProgress]) -> None:
        self.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            # Việt hóa nhãn bước dịch nếu cần
            label = row.label
            if label == "Build Segment Pronouns":
                label = "Xây Dựng Đại Từ Phân Đoạn"
            elif label == "Build Dialogue Labels":
                label = "Xây Dựng Nhãn Hội Thoại"
            elif label == "Translate Draft":
                label = "Dịch Bản Thảo (Draft)"
            elif label == "Apply Quick Fixes":
                label = "Áp Dụng Sửa Lỗi Nhanh"
            elif label == "Review and Refine":
                label = "Rà Soát & Tinh Chỉnh"

            # Việt hóa phạm vi
            scope = row.scope
            if scope == "volume":
                scope = "Tập"
            elif scope == "segment":
                scope = "Phân Đoạn"

            # Việt hóa trạng thái
            status = row.status
            if status == "Done":
                status_display = "🟢 Đã chốt"
            elif status == "Partial":
                status_display = "🟡 Đang dịch"
            elif status == "Not Started":
                status_display = "⚪ Chưa bắt đầu"
            else:
                status_display = status

            self._set_item(row_index, 0, label)
            self._set_item(row_index, 1, scope)
            self._set_item(row_index, 2, f"{row.done} / {row.total}")
            self._set_item(row_index, 3, f"{row.percent:.2f}%")
            self._set_item(row_index, 4, status_display)
        if rows:
            self.resizeRowsToContents()

    def _set_item(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, column, item)
