from __future__ import annotations

from PyQt6.QtWidgets import QApplication


APP_STYLESHEET = """
QWidget {
    background: #14181d;
    color: #e3e8ef;
    font-size: 13px;
}
QMainWindow, QDialog {
    background: #101419;
}
QLabel#titleLabel {
    font-size: 18px;
    font-weight: 600;
    color: #eef2f7;
}
QLabel#mutedLabel {
    color: #9ca8b6;
}
QFrame, QWidget#panel {
    background: #171c22;
}
QTreeWidget, QTableWidget, QListWidget, QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {
    background: #171c22;
    color: #e3e8ef;
    border: 1px solid #262d36;
    border-radius: 6px;
    selection-background-color: #31404f;
    selection-color: #f4f7fb;
    gridline-color: #1b2128;
    alternate-background-color: #171c22;
}
QComboBox QAbstractItemView {
    background: #171c22;
    selection-background-color: #31404f;
    selection-color: #f4f7fb;
}
QTreeWidget::item,
QTableWidget::item,
QListWidget::item {
    padding: 4px;
    border: 0;
}
QTreeWidget::item:selected,
QTableWidget::item:selected,
QListWidget::item:selected {
    background: #31404f;
    color: #f4f7fb;
}
QHeaderView::section {
    background: #181e25;
    color: #b9c3cf;
    padding: 6px 8px;
    border: 0;
    border-right: 1px solid #232a33;
    border-bottom: 1px solid #232a33;
}
QPushButton {
    background: #1b222a;
    color: #e3e8ef;
    border: 1px solid #2a323c;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover {
    background: #202934;
    border-color: #344050;
}
QPushButton:pressed {
    background: #242f3a;
}
QPushButton:disabled {
    color: #6f7b88;
    background: #14181d;
    border-color: #20262d;
}
QPushButton:checked {
    background: #2a3643;
    border-color: #435367;
}
QTabWidget::pane {
    border: 1px solid #232a33;
    background: #14181d;
}
QTabBar::tab {
    background: #171c22;
    color: #9ca8b6;
    border: 1px solid #232a33;
    border-bottom: 0;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 12px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background: #1d242c;
    color: #eef2f7;
}
QTabBar::tab:hover {
    color: #d5dce5;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #12171c;
    border: 0;
    margin: 0;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2a323c;
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}
QSplitter::handle {
    background: #11161b;
}
QStatusBar {
    background: #0f1317;
    color: #c8d0da;
}
QMessageBox {
    background: #101419;
}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
