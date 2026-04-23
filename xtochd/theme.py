"""Light/dark Qt stylesheets."""

from __future__ import annotations


_LIGHT = """
QWidget {
    background-color: #f5f5f5;
    color: #333333;
}
QPushButton {
    background-color: #e0e0e0;
    border: 1px solid #cccccc;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover { background-color: #d0d0d0; }
QPushButton:pressed { background-color: #c0c0c0; }
QPushButton:disabled { background-color: #f0f0f0; color: #999999; }
QLineEdit {
    background-color: white;
    border: 1px solid #cccccc;
    border-radius: 3px;
    padding: 4px;
}
QLineEdit:focus { border: 2px solid #4a90e2; }
QTextEdit {
    background-color: white;
    border: 1px solid #cccccc;
    border-radius: 3px;
}
QListWidget {
    background-color: white;
    border: 1px solid #cccccc;
    border-radius: 3px;
    alternate-background-color: #f9f9f9;
}
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background-color: #e3f2fd; color: #1976d2; }
QProgressBar {
    border: 1px solid #cccccc;
    border-radius: 3px;
    text-align: center;
}
QProgressBar::chunk { background-color: #4caf50; border-radius: 2px; }
QStatusBar { background-color: #e0e0e0; border-top: 1px solid #cccccc; }
QMenuBar { background-color: #f5f5f5; border-bottom: 1px solid #cccccc; }
QMenuBar::item { background-color: transparent; padding: 4px 8px; }
QMenuBar::item:selected { background-color: #e0e0e0; }
QMenu { background-color: white; border: 1px solid #cccccc; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background-color: #e3f2fd; }
QFrame#sectionDivider {
    color: #d0d0d0;
    background: #d0d0d0;
    max-height: 1px;
    min-height: 1px;
    margin: 4px 0 4px 0;
}
QToolBar#mainToolbar {
    border: none;
    border-bottom: 1px solid #d0d0d0;
    padding: 4px 6px;
    spacing: 4px;
    background-color: #f0f0f0;
}
QToolBar#mainToolbar QToolButton {
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    color: #333333;
}
QToolBar#mainToolbar QToolButton:hover {
    background-color: #e0e0e0;
    border-color: #c4c4c4;
}
QToolBar#mainToolbar QToolButton:pressed { background-color: #cfcfcf; }
QToolBar#mainToolbar QToolButton:checked {
    background-color: #1976d2;
    border-color: #1565c0;
    color: white;
}
QToolBar#mainToolbar QToolButton:disabled { color: #999999; }
QToolButton#linkButton {
    border: 1px solid #c4c4c4;
    border-radius: 4px;
    padding: 4px 12px;
    background: transparent;
    color: #333333;
}
QToolButton#linkButton:hover {
    background-color: #e8e8e8;
    border-color: #9e9e9e;
}
QToolButton#linkButton:pressed { background-color: #d5d5d5; }
QPushButton#primaryButton {
    background-color: #2e7d32;
    border: 1px solid #1b5e20;
    color: white;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton#primaryButton:hover { background-color: #388e3c; }
QPushButton#primaryButton:pressed { background-color: #1b5e20; }
QPushButton#primaryButton:disabled {
    background-color: #c8e6c9;
    border: 1px solid #bdbdbd;
    color: #757575;
}
QPushButton#dangerButton {
    background-color: #c62828;
    border: 1px solid #8e0000;
    color: white;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton#dangerButton:hover { background-color: #d32f2f; }
QPushButton#dangerButton:pressed { background-color: #8e0000; }
QPushButton#dangerButton:disabled {
    background-color: #ffcdd2;
    border: 1px solid #bdbdbd;
    color: #757575;
}
"""


_DARK = """
QWidget {
    background-color: #2d2d2d;
    color: #e0e0e0;
}
QPushButton {
    background-color: #404040;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 12px;
    font-weight: bold;
    color: #e0e0e0;
}
QPushButton:hover { background-color: #505050; }
QPushButton:pressed { background-color: #353535; }
QPushButton:disabled { background-color: #353535; color: #666666; }
QLineEdit {
    background-color: #404040;
    border: 1px solid #555555;
    border-radius: 3px;
    padding: 4px;
    color: #e0e0e0;
}
QLineEdit:focus { border: 2px solid #64b5f6; }
QTextEdit {
    background-color: #404040;
    border: 1px solid #555555;
    border-radius: 3px;
    color: #e0e0e0;
}
QListWidget {
    background-color: #404040;
    border: 1px solid #555555;
    border-radius: 3px;
    alternate-background-color: #353535;
}
QListWidget::item { padding: 4px; }
QListWidget::item:selected { background-color: #1976d2; color: white; }
QProgressBar {
    border: 1px solid #555555;
    border-radius: 3px;
    text-align: center;
    background-color: #404040;
}
QProgressBar::chunk { background-color: #4caf50; border-radius: 2px; }
QStatusBar { background-color: #404040; border-top: 1px solid #555555; }
QMenuBar { background-color: #2d2d2d; border-bottom: 1px solid #555555; }
QMenuBar::item { background-color: transparent; padding: 4px 8px; }
QMenuBar::item:selected { background-color: #404040; }
QMenu { background-color: #404040; border: 1px solid #555555; }
QMenu::item { padding: 6px 20px; }
QMenu::item:selected { background-color: #1976d2; }
QCheckBox { color: #e0e0e0; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { border: 2px solid #555555; background-color: #404040; }
QCheckBox::indicator:checked { border: 2px solid #64b5f6; background-color: #1976d2; }
QLabel { color: #e0e0e0; }
QFrame#sectionDivider {
    color: #3a3a3a;
    background: #3a3a3a;
    max-height: 1px;
    min-height: 1px;
    margin: 4px 0 4px 0;
}
QToolBar#mainToolbar {
    border: none;
    border-bottom: 1px solid #3a3a3a;
    padding: 4px 6px;
    spacing: 4px;
    background-color: #252525;
}
QToolBar#mainToolbar QToolButton {
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    color: #e0e0e0;
}
QToolBar#mainToolbar QToolButton:hover {
    background-color: #3a3a3a;
    border-color: #4a4a4a;
}
QToolBar#mainToolbar QToolButton:pressed { background-color: #2a2a2a; }
QToolBar#mainToolbar QToolButton:checked {
    background-color: #1976d2;
    border-color: #1976d2;
    color: white;
}
QToolBar#mainToolbar QToolButton:disabled { color: #6c6c6c; }
QToolButton#linkButton {
    border: 1px solid #4a4a4a;
    border-radius: 4px;
    padding: 4px 12px;
    background: transparent;
    color: #e0e0e0;
}
QToolButton#linkButton:hover {
    background-color: #3a3a3a;
    border-color: #666666;
}
QToolButton#linkButton:pressed { background-color: #2a2a2a; }
QPushButton#primaryButton {
    background-color: #2e7d32;
    border: 1px solid #1b5e20;
    color: white;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton#primaryButton:hover { background-color: #388e3c; }
QPushButton#primaryButton:pressed { background-color: #1b5e20; }
QPushButton#primaryButton:disabled {
    background-color: #2c2c2c;
    border: 1px solid #3a3a3a;
    color: #6c6c6c;
}
QPushButton#dangerButton {
    background-color: #c62828;
    border: 1px solid #8e0000;
    color: white;
    font-weight: bold;
    padding: 6px 14px;
}
QPushButton#dangerButton:hover { background-color: #d32f2f; }
QPushButton#dangerButton:pressed { background-color: #8e0000; }
QPushButton#dangerButton:disabled {
    background-color: #2c2c2c;
    border: 1px solid #3a3a3a;
    color: #6c6c6c;
}
"""


class ThemeManager:
    """Container for the Qt stylesheets."""

    @staticmethod
    def get_light_theme() -> str:
        return _LIGHT

    @staticmethod
    def get_dark_theme() -> str:
        return _DARK
