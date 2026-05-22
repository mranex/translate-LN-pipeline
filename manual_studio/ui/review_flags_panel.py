from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from manual_studio.core.review_flags import ReviewFlag


class ReviewFlagsPanel(QWidget):
    HEADERS = ["Severity", "Source", "Item ID", "Message"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def set_flags(self, flags: list[ReviewFlag], message: str = "") -> None:
        self.message_label.setText(message or ("No review flags found." if not flags else ""))
        self.table.setRowCount(len(flags))
        for row_index, flag in enumerate(flags):
            self._set_item(row_index, 0, flag.severity)
            self._set_item(row_index, 1, flag.source)
            self._set_item(row_index, 2, flag.item_id)
            self._set_item(row_index, 3, flag.message)
        if flags:
            self.table.resizeRowsToContents()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Review Flags")
        title.setObjectName("titleLabel")
        layout.addWidget(title)

        self.message_label = QLabel("No review flags found.")
        self.message_label.setObjectName("mutedLabel")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label)

        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

    def _set_item(self, row: int, column: int, value: str) -> None:
        item = QTableWidgetItem(value)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, column, item)
