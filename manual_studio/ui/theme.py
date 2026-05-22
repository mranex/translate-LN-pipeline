from __future__ import annotations

from PyQt6.QtWidgets import QApplication

# Bộ màu Cyberpunk/Wibu Cockpit:
# - Nền tối vũ trụ: #090a0f
# - Nền bảng điều khiển: #121420
# - Nền phần nhập liệu/danh sách: #181b2a
# - Tím Neon (Chính): #a78bfa
# - Xanh Cyan Neon (AI / Prompt): #06b6d4
# - Hồng Neon (Review / Cảnh báo): #ec4899
# - Viền công nghệ: #2d314d
# - Chữ sáng: #f3f4f6
# - Chữ mờ: #9ca3af

APP_STYLESHEET = """
QWidget {
    background-color: #121420;
    color: #f3f4f6;
    font-family: "Segoe UI", "Outfit", "Inter", "Segoe UI Semibold", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #090a0f;
}

QLabel#titleLabel {
    font-size: 20px;
    font-weight: 700;
    color: #06b6d4;
    padding-bottom: 2px;
}

QLabel#mutedLabel {
    color: #9ca3af;
    font-size: 12px;
}

/* Các khung chứa (Panels) */
QFrame, QWidget#panel {
    background-color: #121420;
    border: 1px solid #2d314d;
    border-radius: 8px;
}

/* Thanh trượt kéo chia đôi cửa sổ */
QSplitter::handle {
    background-color: #2d314d;
    width: 3px;
    height: 3px;
}
QSplitter::handle:hover {
    background-color: #a78bfa;
}

/* Hộp nhập liệu & Danh sách chọn */
QTreeWidget, QTableWidget, QListWidget, QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #181b2a;
    color: #f3f4f6;
    border: 1px solid #2d314d;
    border-radius: 6px;
    padding: 6px;
    selection-background-color: #5b21b6;
    selection-color: #ffffff;
    gridline-color: #1f233a;
}

QTreeWidget:focus, QTableWidget:focus, QListWidget:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #06b6d4;
}

/* Dropdown của QComboBox */
QComboBox QAbstractItemView {
    background-color: #181b2a;
    border: 1px solid #2d314d;
    selection-background-color: #5b21b6;
    selection-color: #ffffff;
    padding: 4px;
}

QComboBox::drop-down {
    border: 0px;
    padding-right: 10px;
}

/* Mục trong Tree/Table/List */
QTreeWidget::item, QTableWidget::item, QListWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1f233a;
}

QTreeWidget::item:hover, QTableWidget::item:hover, QListWidget::item:hover {
    background-color: #1f233a;
    color: #ffffff;
}

QTreeWidget::item:selected, QTableWidget::item:selected, QListWidget::item:selected {
    background-color: #5b21b6;
    color: #ffffff;
    font-weight: 600;
}

/* Tiêu đề bảng biểu */
QHeaderView::section {
    background-color: #1a1c2e;
    color: #a78bfa;
    font-weight: 600;
    padding: 8px;
    border: 0px;
    border-right: 1px solid #2d314d;
    border-bottom: 2px solid #2d314d;
}

/* Nút bấm thiết kế kiểu Game Neon */
QPushButton {
    background-color: #1a1c2e;
    color: #a78bfa;
    border: 1px solid #7c3aed;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #7c3aed;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #5b21b6;
    color: #ffffff;
}

QPushButton:disabled {
    color: #4b5563;
    background-color: #11131e;
    border-color: #1f233a;
}

/* Nút bấm AI màu Cyan rực rỡ */
QPushButton[objectName^="aiButton"], QPushButton#generate_button {
    border-color: #06b6d4;
    color: #06b6d4;
}
QPushButton[objectName^="aiButton"]:hover, QPushButton#generate_button:hover {
    background-color: #06b6d4;
    color: #000000;
}

/* Nút bấm khẩn cấp/nguy hiểm màu hồng rực rỡ */
QPushButton[objectName^="dangerButton"], QPushButton#delete_button {
    border-color: #ec4899;
    color: #ec4899;
}
QPushButton[objectName^="dangerButton"]:hover, QPushButton#delete_button:hover {
    background-color: #ec4899;
    color: #ffffff;
}

/* Thanh điều hướng Tab phụ */
QTabWidget::pane {
    border: 1px solid #2d314d;
    background-color: #121420;
    border-radius: 6px;
    top: -1px;
}

QTabBar::tab {
    background-color: #161827;
    color: #9ca3af;
    border: 1px solid #2d314d;
    border-bottom: 0px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 10px 16px;
    margin-right: 4px;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #f3f4f6;
    background-color: #1d2136;
}

QTabBar::tab:selected {
    background-color: #121420;
    color: #a78bfa;
    font-weight: 700;
    border-top: 3px solid #a78bfa;
}

/* Thanh cuộn cao cấp tối giản */
QScrollBar:vertical {
    background-color: #090a0f;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background-color: #2d314d;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background-color: #a78bfa;
}

QScrollBar:horizontal {
    background-color: #090a0f;
    height: 10px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background-color: #2d314d;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #a78bfa;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
}

/* Thanh trạng thái dưới cùng */
QStatusBar {
    background-color: #090a0f;
    color: #9ca3af;
    border-top: 1px solid #2d314d;
    font-size: 11px;
}

QMessageBox {
    background-color: #090a0f;
}
QMessageBox QLabel {
    color: #f3f4f6;
}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
