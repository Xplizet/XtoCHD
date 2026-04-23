"""XtoCHD - batch CHD converter (entry point + main window).

Domain-model code lives in the ``xtochd`` package: constants, validators,
temp-directory management, Qt stylesheets, conversion/scan/validation
workers, and the ConversionStats dataclass. This file only contains the
main window (``CHDConverterGUI``) and the ``if __name__ == "__main__"``
bootstrap.
"""

from __future__ import annotations

import os
import subprocess
import sys

from PyQt5.QtCore import QEvent, QFileSystemWatcher, QRect, QSettings, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPalette  # noqa: F401 - kept for theme extension
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from xtochd.constants import COMPATIBLE_EXTS
from xtochd.temp_manager import temp_manager
from xtochd.theme import ThemeManager
from xtochd.validators import get_file_info
from xtochd.workers import ConversionWorker, ScanWorker, ValidationWorker


# Role constants stored on each QListWidgetItem so the delegate can paint
# directly from the item model rather than hitting a parallel dict.
ROLE_FILE_INFO = Qt.UserRole + 1
ROLE_FILE_PATH = Qt.UserRole + 2

_BADGE_ROW_HEIGHT = 34
_BADGE_WIDTH = 56
_SIZE_COLUMN_WIDTH = 110
_STATUS_COLUMN_WIDTH = 86

# Format family colours for the file-list badge. The badge's job is to tell
# you what kind of file it is; validation state is signalled separately, so
# colour-blind users aren't forced to distinguish "green = valid" from "red
# = invalid" on the same visual element.
_FAMILY_ARCHIVE = QColor('#3f51b5')   # indigo: .zip / .rar / .7z
_FAMILY_INDEX = QColor('#f57c00')     # amber:  .cue / .gdi / .toc / .ccd
_FAMILY_DISC = QColor('#00796b')      # teal:   .iso / .bin / .img / .nrg etc.
_FAMILY_OTHER = QColor('#546e7a')     # slate:  everything else (.vhd / .dsk / ...)
_FAMILY_UNKNOWN = QColor('#6c6c6c')   # grey:   extension missing

_ARCHIVE_EXTS = {'.zip', '.rar', '.7z'}
_INDEX_EXTS = {'.cue', '.gdi', '.toc', '.ccd'}
_DISC_EXTS = {'.iso', '.bin', '.img', '.nrg', '.vcd', '.cdr'}


def _badge_colour_for_ext(ext: str) -> QColor:
    ext = (ext or '').lower()
    if not ext:
        return _FAMILY_UNKNOWN
    if ext in _ARCHIVE_EXTS:
        return _FAMILY_ARCHIVE
    if ext in _INDEX_EXTS:
        return _FAMILY_INDEX
    if ext in _DISC_EXTS:
        return _FAMILY_DISC
    return _FAMILY_OTHER


class FileListDelegate(QStyledItemDelegate):
    """Paints one file row: checkbox, format badge, filename, size, status icon.

    Data flow: ``ROLE_FILE_INFO`` carries the dict from ``get_file_info``;
    ``Qt.CheckStateRole`` is the user's include/exclude choice. The
    delegate paints from these two; clicks on the checkbox rectangle
    toggle the check state via ``editorEvent``.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Selected-row text colour varies by theme: on dark the highlight
        # is saturated blue so white text reads fine, but on light the
        # highlight is a pale blue and white disappears into it.
        # apply_theme() updates this via set_selected_text_color().
        self._selected_text_color = QColor('#ffffff')

    def set_selected_text_color(self, colour: QColor) -> None:
        self._selected_text_color = QColor(colour)

    def paint(self, painter, option, index):
        painter.save()

        # Draw the standard item chrome (selection/hover/alternating-row
        # background) but suppress everything we paint ourselves: the
        # default text, the default icon, and - critically - the default
        # check indicator, otherwise Qt draws its own checkbox at the left
        # and we'd render a second one over the top of it.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.icon = opt.icon.__class__()  # blank icon
        opt.features &= ~QStyleOptionViewItem.HasCheckIndicator
        opt.checkState = Qt.Unchecked
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        file_info = index.data(ROLE_FILE_INFO) or {}
        check_state = index.data(Qt.CheckStateRole)
        ext_raw = file_info.get('extension') or ''
        ext_label = ext_raw.lstrip('.').upper() or '?'
        name = file_info.get('name') or index.data(Qt.DisplayRole) or ''
        size_str = file_info.get('size_str') or ''
        is_valid = file_info.get('is_valid')
        # The key is absent from the dict while validation is still running;
        # that is a different state from "validated and rejected".
        validation_pending = 'is_valid' not in file_info

        rect = option.rect.adjusted(10, 0, -10, 0)
        mid_y = rect.top() + rect.height() // 2

        # --- checkbox --------------------------------------------------
        cb_size = 18
        cb_rect = QRect(rect.left(), mid_y - cb_size // 2, cb_size, cb_size)
        cb_opt = QStyleOptionButton()
        cb_opt.rect = cb_rect
        cb_opt.state = QStyle.State_Enabled
        cb_opt.state |= (
            QStyle.State_On if check_state == Qt.Checked else QStyle.State_Off
        )
        style.drawPrimitive(QStyle.PE_IndicatorCheckBox, cb_opt, painter)

        # --- format badge (colour encodes format family, NOT validity) -
        badge_rect = QRect(cb_rect.right() + 12, mid_y - 11, _BADGE_WIDTH, 22)
        painter.setRenderHint(painter.Antialiasing, True)
        painter.setPen(Qt.NoPen)
        painter.setBrush(_badge_colour_for_ext(ext_raw))
        painter.drawRoundedRect(badge_rect, 4, 4)
        badge_font = QFont(option.font)
        badge_font.setBold(True)
        badge_font.setPointSize(max(7, badge_font.pointSize() - 1))
        painter.setFont(badge_font)
        painter.setPen(QColor('#ffffff'))
        painter.drawText(badge_rect, Qt.AlignCenter, ext_label)

        # --- selected-row text colour ---------------------------------
        # QPalette.HighlightedText doesn't always follow the QSS
        # `QListWidget::item:selected { color: ... }` rule, so we carry
        # the per-theme colour on the delegate itself.
        if option.state & QStyle.State_Selected:
            text_color = self._selected_text_color
        else:
            text_color = option.palette.color(QPalette.Text)

        # --- size (right-aligned, anchored to the item right) ---------
        size_rect = QRect(
            rect.right() - _SIZE_COLUMN_WIDTH,
            rect.top(), _SIZE_COLUMN_WIDTH, rect.height(),
        )
        painter.setFont(option.font)
        painter.setPen(text_color)
        painter.drawText(size_rect, Qt.AlignRight | Qt.AlignVCenter, size_str)

        # --- status pill (invalid / pending only; valid == nothing) ---
        # "Absence is good": a clean row means the file is valid. Anything
        # odd gets a deliberately uncomfortable pill so it jumps out of a
        # long list.
        status_right = size_rect.left() - 10
        if not validation_pending and is_valid is False:
            pill_w = _STATUS_COLUMN_WIDTH
            pill_rect = QRect(status_right - pill_w, mid_y - 9, pill_w, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor('#c62828'))
            painter.drawRoundedRect(pill_rect, 4, 4)
            painter.setPen(QColor('#ffffff'))
            painter.drawText(pill_rect, Qt.AlignCenter, 'INVALID')
            name_right_limit = pill_rect.left()
        elif validation_pending:
            pill_w = _STATUS_COLUMN_WIDTH
            pill_rect = QRect(status_right - pill_w, mid_y - 9, pill_w, 18)
            pending_pen = QColor('#9e9e9e')
            painter.setPen(pending_pen)
            painter.drawText(pill_rect, Qt.AlignRight | Qt.AlignVCenter, 'validating...')
            name_right_limit = pill_rect.left()
        else:
            name_right_limit = size_rect.left()

        # --- filename (takes whatever horizontal slack is left) -------
        name_left = badge_rect.right() + 12
        name_rect = QRect(
            name_left, rect.top(),
            max(0, name_right_limit - name_left - 12), rect.height(),
        )
        painter.setPen(text_color)
        elided = option.fontMetrics.elidedText(name, Qt.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, elided)

        painter.restore()

    def sizeHint(self, _option, _index):
        return QSize(0, _BADGE_ROW_HEIGHT)

    def editorEvent(self, event, model, option, index):
        if event.type() in (QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
            rect = option.rect.adjusted(10, 0, -10, 0)
            mid_y = rect.top() + rect.height() // 2
            cb_rect = QRect(rect.left(), mid_y - 9, 18, 18)
            # Clicks anywhere on the row toggle the check state; the
            # checkbox rect gives the obvious affordance.
            if event.button() == Qt.LeftButton and (
                cb_rect.contains(event.pos()) or event.type() == QEvent.MouseButtonDblClick
            ):
                current = index.data(Qt.CheckStateRole)
                new_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
                model.setData(index, new_state, Qt.CheckStateRole)
                return True
        return super().editorEvent(event, model, option, index)


class CHDConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('XtoCHD - Batch CHD Converter')
        self.setGeometry(100, 100, 1200, 750)
        self.setMinimumSize(980, 620)
        self.temp_dirs = []
        self.found_files = []
        self.conversion_worker = None
        self.scan_worker = None

        # Persisted settings (last input/output folders, splitter state, etc.)
        self.settings = QSettings('XtoCHD', 'XtoCHD')

        # Theme management
        self.current_theme = 'dark'  # Default to dark theme

        self.init_ui()
        self.setup_menu_bar()
        self.apply_theme(self.current_theme)

        # Setup file system watcher for chdman.exe (next to this script /
        # the frozen .exe, depending on how the app was launched).
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.chdman_path = None
        self.fs_watcher = QFileSystemWatcher()
        self.fs_watcher.addPath(self.app_dir)
        self.fs_watcher.directoryChanged.connect(self.on_chdman_dir_changed)
        self.fs_watcher.fileChanged.connect(self.on_chdman_file_changed)
        self.auto_detect_chdman()
        self.update_start_button_state()

        # Perform startup cleanup of orphaned temp files
        self.perform_startup_cleanup()

        # Drag-and-drop support
        self.setAcceptDrops(True)

        # Restore last-used folders and persist any future changes.
        self._restore_last_folders()
        self.input_path_edit.textChanged.connect(self._save_last_input)
        self.output_path_edit.textChanged.connect(self._save_last_output)

    def _restore_last_folders(self):
        last_input = self.settings.value('last_input', '', type=str)
        last_output = self.settings.value('last_output', '', type=str)
        if last_input and os.path.exists(last_input):
            self.input_path_edit.setText(last_input)
            self.scan_for_files_auto(last_input)
        if last_output:
            self.output_path_edit.setText(last_output)
        self.update_start_button_state()

    def _save_last_input(self, text):
        if text:
            self.settings.setValue('last_input', text)

    def _save_last_output(self, text):
        if text:
            self.settings.setValue('last_output', text)

    def setup_menu_bar(self):
        """Setup the menu bar with theme switching options"""
        menubar = self.menuBar()

        view_menu = menubar.addMenu('View')
        theme_menu = view_menu.addMenu('Theme')

        light_action = QAction('Light Theme', self)
        light_action.setCheckable(True)
        light_action.setChecked(self.current_theme == 'light')
        light_action.triggered.connect(lambda: self.switch_theme('light'))
        theme_menu.addAction(light_action)

        dark_action = QAction('Dark Theme', self)
        dark_action.setCheckable(True)
        dark_action.setChecked(self.current_theme == 'dark')
        dark_action.triggered.connect(lambda: self.switch_theme('dark'))
        theme_menu.addAction(dark_action)

        self.light_theme_action = light_action
        self.dark_theme_action = dark_action

        tools_menu = menubar.addMenu('Tools')

        temp_info_action = QAction('Temp Directory Info', self)
        temp_info_action.triggered.connect(self.show_temp_directory_info)
        tools_menu.addAction(temp_info_action)

        cleanup_action = QAction('Clean Temp Directory', self)
        cleanup_action.triggered.connect(self.cleanup_temp_directory)
        tools_menu.addAction(cleanup_action)

    def switch_theme(self, theme):
        if theme != self.current_theme:
            self.current_theme = theme
            self.apply_theme(theme)
            if hasattr(self, 'light_theme_action'):
                self.light_theme_action.setChecked(theme == 'light')
            if hasattr(self, 'dark_theme_action'):
                self.dark_theme_action.setChecked(theme == 'dark')

    def apply_theme(self, theme):
        if theme == 'dark':
            self.setStyleSheet(ThemeManager.get_dark_theme())
        else:
            self.setStyleSheet(ThemeManager.get_light_theme())
        self.update_widget_styles_for_theme(theme)

        # Keep the file-list delegate's selected-row text colour in sync
        # with the theme's highlight background so selected rows stay
        # readable. Dark highlight (#1976d2) pairs with white; the light
        # highlight (#e3f2fd) pairs with medium blue.
        if hasattr(self, 'file_list'):
            delegate = self.file_list.itemDelegate()
            if isinstance(delegate, FileListDelegate):
                delegate.set_selected_text_color(
                    QColor('#ffffff') if theme == 'dark' else QColor('#1976d2')
                )
                self.file_list.viewport().update()

    def update_widget_styles_for_theme(self, theme):
        if not hasattr(self, 'file_info_text'):
            return
        if theme == 'dark':
            self.file_info_text.setStyleSheet(
                "QTextEdit { background-color: #404040;"
                " border: 1px solid #555555; color: #e0e0e0; }"
            )
        else:
            self.file_info_text.setStyleSheet(
                "QTextEdit { background-color: #f0f0f0;"
                " border: 1px solid #ccc; color: #333333; }"
            )

    def on_chdman_dir_changed(self, _path):
        self.auto_detect_chdman()
        self.update_start_button_state()
        chdman_file = os.path.join(self.app_dir, 'chdman.exe')
        if not os.path.isfile(chdman_file):
            if chdman_file not in self.fs_watcher.files():
                self.fs_watcher.addPath(chdman_file)
        else:
            if chdman_file in self.fs_watcher.files():
                self.fs_watcher.removePath(chdman_file)

    def on_chdman_file_changed(self, path):
        self.auto_detect_chdman()
        self.update_start_button_state()
        if os.path.isfile(path) and path in self.fs_watcher.files():
            self.fs_watcher.removePath(path)

    def auto_detect_chdman(self):
        chdman_in_app_dir = os.path.join(self.app_dir, 'chdman.exe')
        if os.path.isfile(chdman_in_app_dir):
            self.chdman_path = chdman_in_app_dir
            self.chdman_status_indicator.setText("chdman: ✓ Ready")
            self.chdman_status_indicator.setToolTip(
                f"Using chdman.exe in the application folder:\n{chdman_in_app_dir}"
            )
            self.chdman_status_indicator.setStyleSheet(
                "padding: 0 10px; font-weight: 600; color: #4caf50;"
            )
            return
        chdman_in_cwd = os.path.join(os.getcwd(), 'chdman.exe')
        if os.path.isfile(chdman_in_cwd):
            self.chdman_path = chdman_in_cwd
            self.chdman_status_indicator.setText("chdman: ✓ Ready")
            self.chdman_status_indicator.setToolTip(
                f"Using chdman.exe in the current directory:\n{chdman_in_cwd}"
            )
            self.chdman_status_indicator.setStyleSheet(
                "padding: 0 10px; font-weight: 600; color: #4caf50;"
            )
            return
        self.chdman_path = None
        self.chdman_status_indicator.setText("chdman: ✗ Missing")
        self.chdman_status_indicator.setToolTip(
            "chdman.exe not found. Place it next to XtoCHD and it will be "
            "picked up automatically."
        )
        self.chdman_status_indicator.setStyleSheet(
            "padding: 0 10px; font-weight: 600; color: #f44336;"
        )

    def update_start_button_state(self):
        if not hasattr(self, 'start_btn') or self.start_btn is None:
            return
        chdman_available = bool(
            getattr(self, 'chdman_path', None) and os.path.isfile(self.chdman_path)
        )
        files_available = bool(getattr(self, 'found_files', None))
        output_set = bool(
            hasattr(self, 'output_path_edit') and self.output_path_edit.text().strip()
        )
        self.start_btn.setEnabled(chdman_available and files_available and output_set)

    def dragEnterEvent(self, event):
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        path = urls[0].toLocalFile()
        if os.path.isdir(path):
            event.acceptProposedAction()
        elif os.path.isfile(path) and os.path.splitext(path)[1].lower() in COMPATIBLE_EXTS:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if not paths:
            return

        supported_paths = []
        unsupported_files = []
        for path in paths:
            if os.path.isfile(path):
                if os.path.splitext(path)[1].lower() in COMPATIBLE_EXTS:
                    supported_paths.append(path)
                else:
                    unsupported_files.append(os.path.basename(path))
            elif os.path.isdir(path):
                supported_paths.append(path)

        if unsupported_files:
            QMessageBox.warning(
                self, 'Unsupported File Types',
                f'The following files have unsupported extensions:\n'
                f'{", ".join(unsupported_files)}\n\n'
                f'Supported formats: {", ".join(sorted(COMPATIBLE_EXTS))}\n\n'
                f'Only supported files and folders will be processed.'
            )

        if supported_paths:
            main_path = supported_paths[0]
            self.input_path_edit.setText(main_path)
            self.auto_suggest_output_folder(main_path)
            self.status_bar.showMessage('Scanning for files...')
            self.scan_for_files_auto(supported_paths)

    def init_ui(self):
        """Layout the main window.

        Structure:
            QToolBar (actions: Add File, Add Folder, Fast Validation,
                     chdman badge, Log toggle)
            central widget:
                QVBoxLayout:
                    Input path strip  (QLineEdit, inline actions)
                    Output path strip (QLineEdit, inline actions)
                    QSplitter(horizontal):
                        Left workspace: list header, file list (dominant),
                                       collapsible info panel, progress,
                                       morphing action button
                        Right: optional log pane
                    QStatusBar
        """
        self._build_toolbar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        outer_layout = QVBoxLayout()
        outer_layout.setSpacing(6)
        outer_layout.setContentsMargins(12, 8, 12, 8)

        style = self.style()

        # ---- Path strips (compact, inline actions on the right) ----
        outer_layout.addLayout(self._build_path_strip(
            'Input',
            self._make_input_edit(),
            [],  # primary input actions live in the toolbar
        ))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText(
            'CHD output folder (auto-suggests [input]/CHD/)'
        )
        browse_action = QAction(
            style.standardIcon(QStyle.SP_DialogOpenButton), 'Choose output folder',
            self,
        )
        browse_action.triggered.connect(self.select_output)
        open_action = QAction(
            style.standardIcon(QStyle.SP_DirOpenIcon),
            'Open output folder in file manager', self,
        )
        open_action.triggered.connect(self.open_output_folder)
        self.output_path_edit.addAction(browse_action, QLineEdit.TrailingPosition)
        self.output_path_edit.addAction(open_action, QLineEdit.TrailingPosition)
        outer_layout.addLayout(self._build_path_strip(
            'Output', self.output_path_edit, []
        ))

        # ---- Splitter: workspace on left, optional log on right ----
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        outer_layout.addWidget(self.main_splitter, 1)

        self.main_splitter.addWidget(self._build_workspace())
        self.log_pane_widget = self._build_log_pane()
        self.main_splitter.addWidget(self.log_pane_widget)

        # Controls ~72%, log ~28% on first ever launch; versioned key so a
        # previously saved state from an older layout does not restore.
        self.main_splitter.setStretchFactor(0, 5)
        self.main_splitter.setStretchFactor(1, 2)
        saved_state = self.settings.value('splitter_state_v3')
        if saved_state is not None:
            self.main_splitter.restoreState(saved_state)
        else:
            self.main_splitter.setSizes([860, 320])
        self.main_splitter.splitterMoved.connect(
            lambda *_: self.settings.setValue(
                'splitter_state_v3', self.main_splitter.saveState()
            )
        )

        # Status bar spans the full width at the bottom.
        self.status_bar = QStatusBar()
        self.status_bar.showMessage('Ready to convert')
        outer_layout.addWidget(self.status_bar)
        central_widget.setLayout(outer_layout)

    # -----------------------------------------------------------------
    # init_ui helpers
    # -----------------------------------------------------------------

    def _make_input_edit(self):
        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText(
            'Drop files or folders here, or use Add File / Add Folder above'
        )
        return self.input_path_edit

    def _build_path_strip(self, label_text, line_edit, trailing_actions):
        """One row: label + QLineEdit (expanding). Trailing actions optional."""
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setFixedWidth(68)  # comfortably fits "Output:" at default weight
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet('font-weight: 500;')
        line_edit.setMinimumHeight(28)
        line_edit.setClearButtonEnabled(True)
        row.addWidget(label)
        row.addWidget(line_edit, 1)
        for action in trailing_actions:
            line_edit.addAction(action, QLineEdit.TrailingPosition)
        return row

    def _build_toolbar(self):
        """Top QToolBar: primary actions + chdman badge + log toggle."""
        style = self.style()
        self.toolbar = QToolBar('Main')
        self.toolbar.setMovable(False)
        self.toolbar.setFloatable(False)
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toolbar.setIconSize(QSize(16, 16))
        self.toolbar.setObjectName('mainToolbar')
        self.addToolBar(self.toolbar)

        self.action_add_file = QAction(
            style.standardIcon(QStyle.SP_FileIcon), 'Add File', self
        )
        self.action_add_file.setToolTip('Add a single disc image or archive')
        self.action_add_file.triggered.connect(self.select_input_file)
        self.toolbar.addAction(self.action_add_file)

        self.action_add_folder = QAction(
            style.standardIcon(QStyle.SP_DirIcon), 'Add Folder', self
        )
        self.action_add_folder.setToolTip('Scan a folder recursively for disc images')
        self.action_add_folder.triggered.connect(self.select_input_folder)
        self.toolbar.addAction(self.action_add_folder)

        self.toolbar.addSeparator()

        self.action_fast_validation = QAction('Fast Validation', self)
        self.action_fast_validation.setCheckable(True)
        self.action_fast_validation.setChecked(True)
        self.action_fast_validation.setToolTip(
            "Fast Mode (checked, default):\n"
            "• ISO: Check file size only (2 KB minimum)\n"
            "• ZIP: Check header signature only\n"
            "• CUE: Read 512 bytes instead of 1 KB\n"
            "• 5-10x faster on large files\n\n"
            "Thorough Mode (unchecked):\n"
            "• ISO: Full 32 KB header scan\n"
            "• ZIP: Complete integrity test\n"
            "• CUE: Full 1 KB structure analysis\n\n"
            "Changing this setting triggers an automatic rescan."
        )
        self.action_fast_validation.toggled.connect(self.on_validation_mode_changed)
        self.toolbar.addAction(self.action_fast_validation)

        # Right-pinned items.
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)

        self.chdman_status_indicator = QLabel()
        self.chdman_status_indicator.setStyleSheet(
            'padding: 0 10px; font-weight: 500;'
        )
        self.toolbar.addWidget(self.chdman_status_indicator)
        # setup_menu_bar / update_widget_styles_for_theme reference this.
        self.chdman_status_label = self.chdman_status_indicator

        self.toolbar.addSeparator()

        self.action_toggle_log = QAction(
            style.standardIcon(QStyle.SP_FileDialogDetailedView), 'Log', self
        )
        self.action_toggle_log.setCheckable(True)
        self.action_toggle_log.setChecked(
            self.settings.value('log_pane_visible', True, type=bool)
        )
        self.action_toggle_log.setToolTip('Show or hide the log pane')
        self.action_toggle_log.toggled.connect(self.toggle_log_pane)
        self.toolbar.addAction(self.action_toggle_log)

    def _build_workspace(self):
        """Left column of the splitter: file list + info + action row."""
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # -- list header ---------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        self.list_summary_label = QLabel('No files added yet')
        self.list_summary_label.setStyleSheet('font-weight: 600;')
        header_row.addWidget(self.list_summary_label)
        header_row.addStretch(1)

        self.select_all_btn = QToolButton()
        self.select_all_btn.setText('Select All')
        self.select_all_btn.setObjectName('linkButton')
        self.select_all_btn.setCursor(Qt.PointingHandCursor)
        self.select_all_btn.clicked.connect(self.select_all_files)
        self.select_none_btn = QToolButton()
        self.select_none_btn.setText('Select None')
        self.select_none_btn.setObjectName('linkButton')
        self.select_none_btn.setCursor(Qt.PointingHandCursor)
        self.select_none_btn.clicked.connect(self.select_none_files)
        header_row.addWidget(self.select_all_btn)
        header_row.addWidget(self.select_none_btn)
        layout.addLayout(header_row)

        # -- file list -----------------------------------------------
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setUniformItemSizes(True)
        self.file_list.setMinimumHeight(260)
        self.file_list.setItemDelegate(FileListDelegate(self.file_list))
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.setFocusPolicy(Qt.StrongFocus)
        self.file_list.itemSelectionChanged.connect(self.on_file_selection_changed)
        self.file_list.model().dataChanged.connect(self._on_file_item_data_changed)
        layout.addWidget(self.file_list, 1)

        # -- collapsible file info -----------------------------------
        self.file_info_container = QWidget()
        info_layout = QVBoxLayout(self.file_info_container)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        self.file_info_header = QToolButton()
        self.file_info_header.setText('File information')
        self.file_info_header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.file_info_header.setArrowType(Qt.DownArrow)
        self.file_info_header.setAutoRaise(True)
        self.file_info_header.setCursor(Qt.PointingHandCursor)
        self.file_info_header.setStyleSheet(
            'QToolButton { border: none; font-weight: 600; padding: 2px 0; }'
        )
        self.file_info_header.clicked.connect(self._toggle_file_info_collapse)
        info_layout.addWidget(self.file_info_header)

        self.file_info_text = QTextEdit()
        self.file_info_text.setMinimumHeight(84)
        self.file_info_text.setMaximumHeight(110)
        self.file_info_text.setReadOnly(True)
        self.file_info_text.setPlaceholderText('Select a file above to see details.')
        self.file_info_text.setStyleSheet(
            "QTextEdit { background-color: #f0f0f0; border: 1px solid #ccc; }"
        )
        info_layout.addWidget(self.file_info_text)

        # Remember user's last collapsed/expanded preference, default open.
        self._file_info_expanded = self.settings.value(
            'file_info_expanded', True, type=bool
        )
        self.file_info_text.setVisible(self._file_info_expanded)
        self.file_info_header.setArrowType(
            Qt.DownArrow if self._file_info_expanded else Qt.RightArrow
        )
        self.file_info_container.setVisible(False)  # hidden until a row is picked
        layout.addWidget(self.file_info_container)

        # -- progress bar --------------------------------------------
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumHeight(14)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # -- morphing start/stop button -----------------------------
        style = self.style()
        self.action_stack = QStackedWidget()
        self.action_stack.setFixedHeight(42)

        self.start_btn = QPushButton('Start Conversion')
        self.start_btn.setIcon(style.standardIcon(QStyle.SP_MediaPlay))
        self.start_btn.setIconSize(QSize(16, 16))
        self.start_btn.setObjectName('primaryButton')
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)

        self.stop_btn = QPushButton('Stop Conversion')
        self.stop_btn.setIcon(style.standardIcon(QStyle.SP_MediaStop))
        self.stop_btn.setIconSize(QSize(16, 16))
        self.stop_btn.setObjectName('dangerButton')
        self.stop_btn.clicked.connect(self.stop_conversion)

        self.action_stack.addWidget(self.start_btn)
        self.action_stack.addWidget(self.stop_btn)
        self.action_stack.setCurrentIndex(0)
        layout.addWidget(self.action_stack)

        return workspace

    def _build_log_pane(self):
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(4, 0, 0, 0)
        log_label = QLabel('Log')
        log_label.setStyleSheet('font-weight: 600;')
        right_layout.addWidget(log_label)
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        right_layout.addWidget(self.log_area, 1)
        # Honour the toolbar's saved log-toggle state on first paint.
        right_widget.setVisible(
            self.settings.value('log_pane_visible', True, type=bool)
        )
        return right_widget

    def toggle_log_pane(self, visible):
        self.log_pane_widget.setVisible(bool(visible))
        self.settings.setValue('log_pane_visible', bool(visible))

    def _toggle_file_info_collapse(self):
        self._file_info_expanded = not self._file_info_expanded
        self.file_info_text.setVisible(self._file_info_expanded)
        self.file_info_header.setArrowType(
            Qt.DownArrow if self._file_info_expanded else Qt.RightArrow
        )
        self.settings.setValue('file_info_expanded', self._file_info_expanded)

    def open_output_folder(self):
        folder = self.output_path_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            return
        if os.name == 'nt':
            os.startfile(folder)
        elif os.name == 'posix':
            subprocess.Popen(['xdg-open', folder])

    def select_input_file(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(
            self, 'Select File', '',
            'Compatible Files (*.cue *.bin *.iso *.img *.gdi *.toc *.ccd '
            '*.zip *.rar *.7z)',
            options=options,
        )
        if file:
            self.input_path_edit.setText(file)
            self.auto_suggest_output_folder(file)
            self.status_bar.showMessage('Scanning for files...')
            self.scan_for_files_auto(file)

    def select_input_folder(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, 'Select Folder', '', options=options)
        if folder:
            self.input_path_edit.setText(folder)
            self.auto_suggest_output_folder(folder)
            self.status_bar.showMessage('Scanning for files...')
            self.scan_for_files_auto(folder)

    def scan_for_files_auto(self, input_paths):
        """Kick off a ScanWorker (QThread) for safe background scanning."""
        if isinstance(input_paths, str):
            input_paths = [input_paths]

        valid_paths = [p for p in input_paths if p and os.path.exists(p)]
        if not valid_paths:
            self.status_bar.showMessage('Invalid input path(s).')
            return

        if not hasattr(self, 'found_files'):
            self.found_files = []

        self.update_start_button_state()
        self.status_bar.showMessage('Scanning for files...')
        if getattr(self, 'scan_worker', None) is not None:
            self.scan_worker.quit()
            self.scan_worker.wait()
        self.scan_worker = ScanWorker(valid_paths)
        self.scan_worker.scan_progress.connect(self.status_bar.showMessage)
        self.scan_worker.scan_complete.connect(self.scan_completed)
        self.scan_worker.scan_error.connect(self.scan_error)
        self.scan_worker.start()

    def scan_completed(self, found_files):
        """Merge newly-scanned files into the list, de-duplicating by base name."""
        if not hasattr(self, 'found_files'):
            self.found_files = []

        # Multi-file disc formats where a "duplicate" base name is actually
        # a required companion, not a replacement.
        multi_file_formats = {
            '.cue': ('.bin',),
            '.toc': ('.bin',),
            '.ccd': ('.img', '.sub'),
        }
        # Format priority when the same base name appears in two formats:
        # pick the smaller number. Anything not listed drops to 999.
        format_priority = {
            '.iso': 1, '.cue': 2, '.bin': 3, '.img': 4,
            '.zip': 5, '.nrg': 6, '.gdi': 7, '.toc': 8,
            '.ccd': 9, '.vcd': 10,
            '.cdr': 11, '.hdi': 12, '.vhd': 13, '.vmdk': 14, '.dsk': 15,
        }

        new_files = []
        duplicate_files = []

        for file_path in found_files:
            if file_path in self.found_files:
                continue

            file_name = os.path.basename(file_path)
            file_base, file_ext = os.path.splitext(file_name)
            file_ext = file_ext.lower()

            is_duplicate = False
            should_replace = None

            for existing in self.found_files:
                existing_name = os.path.basename(existing)
                existing_base, existing_ext = os.path.splitext(existing_name)
                existing_ext = existing_ext.lower()
                if existing_base != file_base:
                    continue

                # Is the new file a companion the existing one needs?
                is_companion = (
                    (existing_ext in multi_file_formats and file_ext in multi_file_formats[existing_ext])
                    or (file_ext in multi_file_formats and existing_ext in multi_file_formats[file_ext])
                )
                if is_companion:
                    continue

                new_priority = format_priority.get(file_ext, 999)
                existing_priority = format_priority.get(existing_ext, 999)
                if new_priority < existing_priority:
                    should_replace = existing
                    break
                duplicate_files.append(file_name)
                is_duplicate = True
                break

            if should_replace is not None:
                self.found_files.remove(should_replace)
                for i in range(self.file_list.count()):
                    item = self.file_list.item(i)
                    if item.data(ROLE_FILE_PATH) == should_replace:
                        self.file_list.takeItem(i)
                        break

            if not is_duplicate:
                self.found_files.append(file_path)
                new_files.append(file_path)

        if new_files:
            if not hasattr(self, 'file_info_cache'):
                self.file_info_cache = {}
            for file_path in new_files:
                self.add_file_to_list(file_path)
            self.start_background_validation()
            status_msg = (
                f'Scan complete: {len(new_files)} new file(s) found. '
                f'Total: {len(self.found_files)} file(s). Ready to convert!'
            )
            if duplicate_files:
                status_msg += f' Skipped {len(duplicate_files)} duplicate(s).'
            self.status_bar.showMessage(status_msg)
        elif duplicate_files:
            self.status_bar.showMessage(
                f'Scan complete: All files were duplicates. '
                f'Skipped {len(duplicate_files)} file(s).'
            )
        else:
            self.status_bar.showMessage('Scan complete: No new files found.')

        self.update_start_button_state()

    def scan_error(self, error_msg):
        self.status_bar.showMessage(error_msg)
        self.update_start_button_state()

    def auto_suggest_output_folder(self, input_path):
        """Auto-suggest output folder as [input_path]/CHD/ without creating it."""
        input_dir = os.path.dirname(input_path) if os.path.isfile(input_path) else input_path
        chd_folder = os.path.join(input_dir, 'CHD')
        self.output_path_edit.setText(chd_folder)
        self.log_area.append(f'Suggested output folder: {chd_folder}')
        self.update_start_button_state()

    def select_output(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', '', options=options)
        if folder:
            self.output_path_edit.setText(folder)
            self.log_area.append(f'Manually selected output folder: {folder}')
            self.update_start_button_state()

    def populate_file_list(self):
        """Rebuild the file list UI from self.found_files, preserving cached validation."""
        if not hasattr(self, 'file_info_cache'):
            self.file_info_cache = {}
        existing_cache = self.file_info_cache
        self.file_list.clear()
        # Drop cache entries for files that are no longer in the list.
        self.file_info_cache = {k: v for k, v in existing_cache.items() if k in self.found_files}

        for file_path in self.found_files:
            self.add_file_to_list(file_path)

        self._update_list_summary()
        self.start_background_validation()

    def add_file_to_list(self, file_path):
        """Create a QListWidgetItem carrying file path + (optionally cached) info."""
        item = QListWidgetItem()
        item.setFlags(
            Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable
        )
        item.setCheckState(Qt.Checked)
        item.setData(ROLE_FILE_PATH, file_path)

        cached = getattr(self, 'file_info_cache', {}).get(file_path)
        if cached is not None:
            item.setData(ROLE_FILE_INFO, cached)
        else:
            try:
                file_size = os.path.getsize(file_path)
                size_str = temp_manager.format_size(file_size)
            except OSError:
                file_size = 0
                size_str = 'Unknown'
            # Seed pending info so the delegate can render something sensible
            # while validation runs in the background.
            item.setData(ROLE_FILE_INFO, {
                'name': os.path.basename(file_path),
                'path': file_path,
                'size': file_size,
                'size_str': size_str,
                'extension': os.path.splitext(file_path)[1].lower(),
                # 'is_valid' deliberately omitted so the delegate paints
                # a pending/... status indicator.
                'validation_msg': 'Validating...',
            })
        item.setToolTip(file_path)
        self.file_list.addItem(item)

    def start_background_validation(self):
        """Run a ValidationWorker across files not already validated."""
        if getattr(self, 'validation_worker', None) is not None:
            self.validation_worker.quit()
            self.validation_worker.wait()

        if not hasattr(self, 'file_info_cache'):
            self.file_info_cache = {}

        unvalidated = [p for p in self.found_files if p not in self.file_info_cache]
        if not unvalidated:
            self.update_file_validation({})
            return

        # Cap workers to something sensible for the file count and CPU.
        cpu_count = os.cpu_count() or 4
        count = len(unvalidated)
        if count <= 4:
            max_workers = min(2, cpu_count)
        elif count <= 10:
            max_workers = min(4, cpu_count)
        else:
            max_workers = min(6, cpu_count)

        fast_validation = self.action_fast_validation.isChecked()
        self.validation_worker = ValidationWorker(
            unvalidated, max_workers=max_workers, fast_validation=fast_validation,
        )
        self.validation_worker.validation_progress.connect(self.update_single_file_validation)
        self.validation_worker.validation_complete.connect(self.update_file_validation)
        self.validation_worker.start()

    def update_single_file_validation(self, file_path, file_info):
        """Update a single file's row as its validation result arrives."""
        try:
            file_index = self.found_files.index(file_path)
        except ValueError:
            return
        if file_index >= self.file_list.count():
            return

        item = self.file_list.item(file_index)
        item.setData(ROLE_FILE_INFO, file_info)
        item.setToolTip(
            f"{file_info['path']}\n"
            f"{file_info['size_str']}  ({file_info['extension']})\n"
            f"{file_info['validation_msg']}"
        )
        # Ensure the delegate repaints this row now that its data changed.
        self.file_list.update(self.file_list.indexFromItem(item))

        if not hasattr(self, 'file_info_cache'):
            self.file_info_cache = {}
        self.file_info_cache[file_path] = file_info

        validated_count = len(self.file_info_cache)
        total_count = len(self.found_files)
        self.status_bar.showMessage(
            f"Validating files... ({validated_count}/{total_count} completed)"
        )
        self._update_list_summary()

    def update_file_validation(self, validation_results):
        """Final summary once all ValidationWorker results are in."""
        if validation_results:
            self.file_info_cache.update(validation_results)

        total_size = sum(
            info['size'] for info in self.file_info_cache.values() if info['is_valid']
        )
        valid_files = sum(1 for info in self.file_info_cache.values() if info['is_valid'])
        invalid_files = sum(1 for info in self.file_info_cache.values() if not info['is_valid'])

        if self.found_files:
            total_size_str = temp_manager.format_size(total_size)
            self.status_bar.showMessage(
                f"Files: {len(self.found_files)} | Valid: {valid_files} | "
                f"Invalid: {invalid_files} | Total Size: {total_size_str}"
            )
        self._update_list_summary()

        # If the user triggered this run by flipping validation mode, close
        # the loop in the log so the "Re-validating..." line isn't orphaned.
        mode = getattr(self, '_revalidation_mode_text', None)
        if mode:
            self._revalidation_mode_text = None
            if invalid_files:
                self.log_area_append(
                    f"Re-validation complete ({mode} mode): "
                    f"{valid_files} valid, {invalid_files} invalid."
                )
            else:
                self.log_area_append(
                    f"Re-validation complete ({mode} mode): all {valid_files} file(s) valid."
                )

    def on_file_selection_changed(self):
        """Show details for the selected file in the information panel."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            self.file_info_text.clear()
            self.file_info_container.setVisible(False)
            return

        item = selected_items[0]
        item_index = self.file_list.row(item)
        if item_index >= len(self.found_files):
            return

        file_path = self.found_files[item_index]
        cached = getattr(self, 'file_info_cache', {}).get(file_path)
        file_info = cached if cached is not None else get_file_info(file_path)

        info_text = (
            f"File: {file_info['name']}\n"
            f"Path: {file_info['path']}\n"
            f"Size: {file_info['size_str']}\n"
            f"Format: {file_info['extension']}\n"
            f"Status: {file_info['validation_msg']}"
        )

        # Subtle left-border accent; avoid the heavy filled background that
        # earlier versions used.
        if self.current_theme == 'dark':
            ok = ("QTextEdit { background-color: #2d2d2d;"
                  " border: 1px solid #3a3a3a; border-left: 3px solid #4caf50;"
                  " color: #e0e0e0; padding: 4px; }")
            bad = ("QTextEdit { background-color: #2d2d2d;"
                   " border: 1px solid #3a3a3a; border-left: 3px solid #f44336;"
                   " color: #e0e0e0; padding: 4px; }")
        else:
            ok = ("QTextEdit { background-color: #fafafa;"
                  " border: 1px solid #d0d0d0; border-left: 3px solid #4caf50;"
                  " color: #333333; padding: 4px; }")
            bad = ("QTextEdit { background-color: #fafafa;"
                   " border: 1px solid #d0d0d0; border-left: 3px solid #f44336;"
                   " color: #333333; padding: 4px; }")
        self.file_info_text.setStyleSheet(ok if file_info['is_valid'] else bad)
        self.file_info_text.setText(info_text)
        self.file_info_container.setVisible(True)
        # Respect collapsed preference even on reveal.
        self.file_info_text.setVisible(self._file_info_expanded)

    def select_all_files(self):
        for i in range(self.file_list.count()):
            self.file_list.item(i).setCheckState(Qt.Checked)

    def select_none_files(self):
        for i in range(self.file_list.count()):
            self.file_list.item(i).setCheckState(Qt.Unchecked)

    def get_selected_files(self):
        """Return the checked files plus warnings about invalid/unvalidated ones."""
        selected_files = []
        invalid_selected = []
        unvalidated_selected = []

        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item.checkState() != Qt.Checked:
                continue
            file_path = self.found_files[i]
            cached = getattr(self, 'file_info_cache', {}).get(file_path)
            if cached is not None:
                if cached['is_valid']:
                    selected_files.append(file_path)
                else:
                    invalid_selected.append(cached['name'])
            else:
                selected_files.append(file_path)
                unvalidated_selected.append(os.path.basename(file_path))

        if unvalidated_selected:
            self.log_area.append(
                f"Note: {len(unvalidated_selected)} file(s) haven't been validated yet "
                f"and will be converted anyway: {', '.join(unvalidated_selected)}"
            )
        if invalid_selected:
            self.log_area.append(
                f"Warning: {len(invalid_selected)} invalid file(s) were selected "
                f"and will be skipped: {', '.join(invalid_selected)}"
            )

        return selected_files

    def _on_file_item_data_changed(self, *_):
        """Keep the list-summary header and Start button state in sync with checks."""
        self._update_list_summary()
        self.update_start_button_state()

    def _update_list_summary(self):
        """Render the live summary label above the file list."""
        if not hasattr(self, 'list_summary_label'):
            return
        if not self.found_files:
            self.list_summary_label.setText('No files added yet')
            return

        cache = getattr(self, 'file_info_cache', {})
        total = len(self.found_files)
        checked = sum(
            1 for i in range(self.file_list.count())
            if self.file_list.item(i).checkState() == Qt.Checked
        )
        size_bytes = sum(
            info.get('size', 0) for info in cache.values() if info.get('is_valid')
        )
        size_str = temp_manager.format_size(size_bytes) if size_bytes else '--'

        valid = sum(1 for info in cache.values() if info.get('is_valid'))
        invalid = sum(
            1 for info in cache.values() if 'is_valid' in info and not info['is_valid']
        )
        if invalid:
            status = f'{valid} valid, {invalid} invalid'
        elif valid == total:
            status = 'All valid'
        else:
            status = f'{valid}/{total} validated'

        self.list_summary_label.setText(
            f'{checked}/{total} selected  ·  {size_str}  ·  {status}'
        )

    def start_conversion(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            self.log_area.append('No files selected for conversion.')
            return

        output_path = self.output_path_edit.text().strip()
        if not output_path:
            self.log_area.append('Please select an output folder.')
            return
        if not self.chdman_path or not os.path.isfile(self.chdman_path):
            self.log_area.append(
                'chdman.exe not found. Please place chdman.exe in the same folder as XtoCHD.'
            )
            return

        self.check_temp_directory_before_conversion()
        self.disable_ui_during_conversion()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        # Morph the single action button into its "Stop" state.
        self.action_stack.setCurrentIndex(1)
        self.status_bar.showMessage('Starting conversion...')

        self.conversion_worker = ConversionWorker(selected_files, output_path, self.chdman_path)
        self.conversion_worker.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_worker.progress_text.connect(self.status_bar.showMessage)
        self.conversion_worker.log_updated.connect(self.log_area_append)
        self.conversion_worker.conversion_finished.connect(self.conversion_completed)
        self.conversion_worker.start()

    def _set_toolbar_actions_enabled(self, enabled):
        for action in (
            getattr(self, 'action_add_file', None),
            getattr(self, 'action_add_folder', None),
            getattr(self, 'action_fast_validation', None),
        ):
            if action is not None:
                action.setEnabled(enabled)

    def disable_ui_during_conversion(self):
        self._set_toolbar_actions_enabled(False)
        for widget in (
            self.select_all_btn, self.select_none_btn,
            self.file_list, self.input_path_edit, self.output_path_edit,
        ):
            widget.setEnabled(False)

    def enable_ui_after_conversion(self):
        self._set_toolbar_actions_enabled(True)
        for widget in (
            self.select_all_btn, self.select_none_btn,
            self.file_list, self.input_path_edit, self.output_path_edit,
        ):
            widget.setEnabled(True)
        self.update_start_button_state()

    def stop_conversion(self):
        """Stop the current conversion process."""
        if self.conversion_worker and self.conversion_worker.isRunning():
            self.conversion_worker.cancel()
            self.status_bar.showMessage('Stopping conversion...')

    def conversion_completed(self):
        self.enable_ui_after_conversion()

        if self.conversion_worker:
            self.conversion_worker.cleanup_temp_dirs()
        self.cleanup_temp_dirs()

        self.progress_bar.setTextVisible(False)
        # Morph back to the "Start" state.
        self.action_stack.setCurrentIndex(0)

        if self.conversion_worker and self.conversion_worker.cancelled:
            self.status_bar.showMessage('Conversion stopped')
        else:
            self.status_bar.showMessage('Conversion completed')

    def cleanup_temp_dirs(self):
        """Clean up temp directories owned by the GUI (not the worker)."""
        cleaned_count = 0
        for d in self.temp_dirs:
            if temp_manager.cleanup_temp_dir(d):
                cleaned_count += 1
        self.temp_dirs = []
        if cleaned_count > 0:
            self.log_area.append(f'Cleaned up {cleaned_count} temporary directories.')

    def on_validation_mode_changed(self):
        """Re-validate all files when the user flips fast vs thorough."""
        if not getattr(self, 'found_files', None):
            return
        mode_text = "Fast" if self.action_fast_validation.isChecked() else "Thorough"
        count = len(self.found_files)
        self.log_area_append(
            f"Validation mode changed to {mode_text}. Re-validating {count} file(s)..."
        )
        self.status_bar.showMessage(
            f'Re-validating {count} file(s) in {mode_text} mode...'
        )

        # Clear the validation cache so every file goes through the new
        # validator again; without this, cached results from the previous
        # mode stick around and nothing actually changes.
        self.file_info_cache = {}

        # Reset every row's display state back to "pending" so the
        # delegate paints the grey "validating..." hint while the worker
        # is in flight.
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            info = dict(item.data(ROLE_FILE_INFO) or {})
            info.pop('is_valid', None)
            info['validation_msg'] = 'Validating...'
            item.setData(ROLE_FILE_INFO, info)
            self.file_list.update(self.file_list.indexFromItem(item))

        # Remember to announce completion; update_file_validation will
        # check this flag and log a closing line once the worker is done.
        self._revalidation_mode_text = mode_text
        self.start_background_validation()

    def perform_startup_cleanup(self):
        """On launch, sweep orphaned temp dirs and report current sizes."""
        try:
            cleaned_count = temp_manager.cleanup_orphaned_temp_dirs()
            temp_size = temp_manager.get_temp_dir_size()
            if cleaned_count > 0:
                self.log_area.append(
                    f'Startup cleanup: removed {cleaned_count} orphaned temp directories.'
                )
            if temp_size > 0:
                self.log_area.append(f'Temp directory size: {temp_manager.format_size(temp_size)}')
            self.log_area.append(f'Temp directory: {temp_manager.temp_base_dir}')
        except OSError as e:
            self.log_area.append(f'Warning: could not perform startup cleanup: {e}')

    def get_temp_directory_info(self):
        try:
            temp_size = temp_manager.get_temp_dir_size()
            return (
                f"Temp directory: {temp_manager.temp_base_dir}\n"
                f"Size: {temp_manager.format_size(temp_size)}"
            )
        except OSError as e:
            return (
                f"Temp directory: {temp_manager.temp_base_dir}\n"
                f"Size: Unknown (error: {e})"
            )

    def check_temp_directory_before_conversion(self):
        try:
            temp_size = temp_manager.get_temp_dir_size()
            size_str = temp_manager.format_size(temp_size)
            if temp_size > 100 * 1024 * 1024:
                self.log_area.append(
                    f'Warning: temp directory is {size_str}. Consider cleaning up.'
                )
            self.log_area.append(f'Temp directory status: {size_str}')
        except OSError as e:
            self.log_area.append(f'Warning: could not check temp directory: {e}')

    def show_temp_directory_info(self):
        QMessageBox.information(self, 'Temp Directory Info', self.get_temp_directory_info())

    def cleanup_temp_directory(self):
        """Tools menu 'Clean Temp Directory': remove everything in temp/,
        not just age-gated orphans. This runs on explicit user request so
        the safety check the startup sweep applies isn't needed here."""
        if getattr(self, 'conversion_worker', None) and self.conversion_worker.isRunning():
            QMessageBox.warning(
                self, 'Cleanup blocked',
                'A conversion is currently running; its temp files are in use. '
                'Stop the conversion first, then try again.'
            )
            return
        try:
            cleaned_count = temp_manager.purge_temp_base_dir()
            if cleaned_count > 0:
                self.log_area.append(
                    f'Manual cleanup: removed {cleaned_count} temp directories.'
                )
            else:
                self.log_area.append('Manual cleanup: temp directory was already empty.')
            temp_size = temp_manager.get_temp_dir_size()
            self.log_area.append(
                f'Current temp directory size: {temp_manager.format_size(temp_size)}'
            )
        except OSError as e:
            self.log_area.append(f'Error during manual cleanup: {e}')

    def log_area_append(self, text):
        self.log_area.append(text)
        self.log_area.moveCursor(self.log_area.textCursor().End)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CHDConverterGUI()
    window.show()
    sys.exit(app.exec_())
