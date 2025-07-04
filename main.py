import sys
import os
import tempfile
import shutil
import zipfile
import subprocess
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QFileDialog, QTextEdit, QProgressBar, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QFrame, QDialog, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

COMPATIBLE_EXTS = {'.cue', '.bin', '.iso', '.img', '.zip'}
DISK_IMAGE_EXTS = {'.cue', '.bin', '.iso', '.img'}

class ConversionWorker(QThread):
    progress_updated = pyqtSignal(int)
    progress_text = pyqtSignal(str)  # For detailed progress messages
    log_updated = pyqtSignal(str)
    conversion_finished = pyqtSignal()
    
    def __init__(self, files, output_dir, chdman_path):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.chdman_path = chdman_path
        self.temp_dirs = []
        
    def run(self):
        total_files = len(self.files)
        current_file = 0
        
        for file_path in self.files:
            current_file += 1
            ext = os.path.splitext(file_path)[1].lower()
            
            # Update progress for starting this file
            progress_percent = int((current_file - 1) / total_files * 100)
            self.progress_updated.emit(progress_percent)
            self.progress_text.emit(f"Processing file {current_file}/{total_files}: {os.path.basename(file_path)}")
            
            if ext == '.zip':
                # Handle zip files by extracting and converting contents
                self.log_updated.emit(f'Processing zip: {file_path}')
                self.process_zip_file(file_path, current_file, total_files)
            else:
                # Handle regular disk image files
                self.convert_single_file(file_path, current_file, total_files)
                
        self.progress_updated.emit(100)
        self.progress_text.emit("Conversion complete!")
        self.log_updated.emit('Conversion complete.')
        self.conversion_finished.emit()
        
    def process_zip_file(self, zip_path, current_file, total_files):
        """Extract zip and convert all compatible files inside"""
        self.progress_text.emit(f"Extracting zip file...")
        temp_dir = tempfile.mkdtemp(prefix='chdconv_zip_')
        self.temp_dirs.append(temp_dir)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Get list of files in zip for progress tracking
                zip_files = z.namelist()
                total_zip_files = len(zip_files)
                
                for idx, zip_file in enumerate(zip_files):
                    z.extract(zip_file, temp_dir)
                    # Update progress during extraction
                    extraction_progress = int((idx + 1) / total_zip_files * 20)  # 20% for extraction
                    file_progress = int((current_file - 1) / total_files * 100)
                    total_progress = file_progress + extraction_progress
                    self.progress_updated.emit(min(total_progress, 99))
                    self.progress_text.emit(f"Extracting: {zip_file}")
            
            # Find all disk images in extracted content
            self.progress_text.emit("Scanning extracted files...")
            disk_images = []
            for root, _, files in os.walk(temp_dir):
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in DISK_IMAGE_EXTS:
                        disk_images.append(os.path.join(root, fname))
            
            # Convert each disk image found in zip
            for idx, extracted_file in enumerate(disk_images):
                self.progress_text.emit(f"Converting extracted file {idx+1}/{len(disk_images)}")
                self.convert_single_file(extracted_file, current_file, total_files)
                        
        except Exception as e:
            self.log_updated.emit(f'Failed to process zip {zip_path}: {e}')
    
    def convert_single_file(self, file_path, current_file, total_files):
        """Convert a single disk image file to CHD"""
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        chd_file = os.path.join(self.output_dir, base_name + '.chd')
        ext = os.path.splitext(file_path)[1].lower()
        
        self.log_updated.emit(f'Converting: {file_path}')
        self.progress_text.emit(f"Converting to CHD: {base_name}")
        
        try:
            if ext == '.cue':
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', chd_file]
            elif ext in {'.iso', '.bin', '.img'}:
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', chd_file]
            else:
                self.log_updated.emit(f'Skipped unsupported file: {file_path}')
                return
                
            # Use CREATE_NO_WINDOW to hide the CMD window
            # Note: chdman doesn't provide real-time progress output, so we show the command is running
            self.progress_text.emit(f"Running chdman conversion...")
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            
            if result.returncode == 0:
                self.log_updated.emit(f'Success: {chd_file}')
                self.progress_text.emit(f"✓ Completed: {base_name}.chd")
            else:
                self.log_updated.emit(f'Error converting {file_path}: {result.stderr}')
                self.progress_text.emit(f"✗ Failed: {base_name}")
                
        except Exception as e:
            self.log_updated.emit(f'Exception: {e}')
            self.progress_text.emit(f"✗ Error: {base_name}")
    
    def cleanup_temp_dirs(self):
        """Clean up temporary directories created during conversion"""
        for d in self.temp_dirs:
            try:
                shutil.rmtree(d)
            except Exception:
                pass
        self.temp_dirs = []

class ScanWorker(QThread):
    scan_progress = pyqtSignal(str)
    scan_complete = pyqtSignal(list)
    scan_error = pyqtSignal(str)
    
    def __init__(self, input_path):
        super().__init__()
        self.input_path = input_path
        
    def run(self):
        try:
            self.scan_progress.emit('Scanning for compatible files...')
            found_files = self.scan_files(self.input_path)
            self.scan_complete.emit(found_files)
        except Exception as e:
            self.scan_error.emit(f'Scan error: {e}')
    
    def scan_files(self, path):
        found_files = []
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in COMPATIBLE_EXTS:
                found_files.append(path)
        else:
            # Use faster directory scanning
            for root, dirs, files in os.walk(path):
                # Skip hidden directories for speed
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in COMPATIBLE_EXTS:
                        fpath = os.path.join(root, fname)
                        found_files.append(fpath)
        return found_files

class InputSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Input Type")
        self.setModal(True)
        self.setFixedSize(300, 150)
        self.selected_path = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("What would you like to convert?")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Radio buttons
        self.file_radio = QRadioButton("Select a single file")
        self.folder_radio = QRadioButton("Select a folder (batch processing)")
        self.folder_radio.setChecked(True)  # Default to folder selection
        
        layout.addWidget(self.file_radio)
        layout.addWidget(self.folder_radio)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_selection_type(self):
        return "file" if self.file_radio.isChecked() else "folder"

class CHDConverterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('XtoCHD - Batch CHD Converter')
        self.setGeometry(100, 100, 1000, 700)
        self.init_ui()
        self.temp_dirs = []
        self.found_files = []
        self.conversion_worker = None
        self.scan_worker = None

    def init_ui(self):
        layout = QVBoxLayout()

        # Input path
        input_layout = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        input_btn = QPushButton('Select File/Folder')
        input_btn.clicked.connect(self.select_input)
        input_layout.addWidget(QLabel('Input:'))
        input_layout.addWidget(self.input_path_edit)
        input_layout.addWidget(input_btn)
        layout.addLayout(input_layout)

        # Output path
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        output_btn = QPushButton('Select Output Folder')
        output_btn.clicked.connect(self.select_output)
        output_layout.addWidget(QLabel('Output:'))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(output_btn)
        layout.addLayout(output_layout)

        # chdman path
        chdman_layout = QHBoxLayout()
        self.chdman_path_edit = QLineEdit(os.path.join(os.getcwd(), 'chdman.exe'))
        chdman_btn = QPushButton('Select chdman.exe')
        chdman_btn.clicked.connect(self.select_chdman)
        chdman_layout.addWidget(QLabel('chdman.exe:'))
        chdman_layout.addWidget(self.chdman_path_edit)
        chdman_layout.addWidget(chdman_btn)
        layout.addLayout(chdman_layout)

        # Scan button
        scan_btn = QPushButton('Scan for Files')
        scan_btn.clicked.connect(self.scan_for_files)
        layout.addWidget(scan_btn)

        # File list section
        file_list_label = QLabel('Files to Convert:')
        layout.addWidget(file_list_label)
        
        # File list with checkboxes
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        
        # Select all/none buttons
        select_buttons_layout = QHBoxLayout()
        select_all_btn = QPushButton('Select All')
        select_all_btn.clicked.connect(self.select_all_files)
        select_none_btn = QPushButton('Select None')
        select_none_btn.clicked.connect(self.select_none_files)
        select_buttons_layout.addWidget(select_all_btn)
        select_buttons_layout.addWidget(select_none_btn)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)

        # Start button
        self.start_btn = QPushButton('Start Conversion')
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        layout.addWidget(self.start_btn)

        # Progress section
        progress_layout = QVBoxLayout()
        
        # Progress text label
        self.progress_label = QLabel('Ready to convert')
        self.progress_label.setStyleSheet("color: gray; font-style: italic;")
        progress_layout.addWidget(self.progress_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)

        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(QLabel('Log:'))
        layout.addWidget(self.log_area)

        self.setLayout(layout)

    def select_input(self):
        # Show selection dialog first
        dialog = InputSelectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            selection_type = dialog.get_selection_type()
            
            options = QFileDialog.Options()
            
            if selection_type == "file":
                # File selection
                file, _ = QFileDialog.getOpenFileName(
                    self, 'Select File', '', 
                    'Compatible Files (*.cue *.bin *.iso *.img *.zip);;All Files (*)', 
                    options=options
                )
                if file:
                    self.input_path_edit.setText(file)
            else:
                # Folder selection
                folder = QFileDialog.getExistingDirectory(
                    self, 'Select Folder', '', options=options
                )
                if folder:
                    self.input_path_edit.setText(folder)

    def select_output(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', '', options=options)
        if folder:
            self.output_path_edit.setText(folder)

    def select_chdman(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(self, 'Select chdman.exe', '', 'Executable (*.exe);;All Files (*)', options=options)
        if file:
            self.chdman_path_edit.setText(file)

    def scan_for_files(self):
        input_path = self.input_path_edit.text().strip()
        if not input_path or not os.path.exists(input_path):
            self.log_area.append('Invalid input path.')
            return
        
        # Disable scan button during scanning
        self.sender().setEnabled(False)
        self.log_area.append('Starting scan...')
        
        # Start scan in background thread
        self.scan_worker = ScanWorker(input_path)
        self.scan_worker.scan_progress.connect(self.log_area.append)
        self.scan_worker.scan_complete.connect(self.scan_completed)
        self.scan_worker.scan_error.connect(self.scan_error)
        self.scan_worker.start()

    def scan_completed(self, found_files):
        self.found_files = found_files
        self.populate_file_list()
        self.log_area.append(f'Found {len(self.found_files)} compatible files.')
        self.start_btn.setEnabled(len(self.found_files) > 0)
        
        # Re-enable scan button
        for child in self.children():
            if isinstance(child, QPushButton) and child.text() == 'Scan for Files':
                child.setEnabled(True)
                break

    def scan_error(self, error_msg):
        self.log_area.append(error_msg)
        # Re-enable scan button
        for child in self.children():
            if isinstance(child, QPushButton) and child.text() == 'Scan for Files':
                child.setEnabled(True)
                break

    def populate_file_list(self):
        self.file_list.clear()
        for file_path in self.found_files:
            item = QListWidgetItem()
            checkbox = QCheckBox(os.path.basename(file_path))
            checkbox.setChecked(True)
            checkbox.setToolTip(file_path)
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, checkbox)

    def select_all_files(self):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            checkbox.setChecked(True)

    def select_none_files(self):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            checkbox.setChecked(False)

    def get_selected_files(self):
        selected_files = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            if checkbox.isChecked():
                # Get the full path from the original found_files list
                selected_files.append(self.found_files[i])
        return selected_files

    def start_conversion(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            self.log_area.append('No files selected for conversion.')
            return
            
        output_path = self.output_path_edit.text().strip()
        chdman_path = self.chdman_path_edit.text().strip()
        
        if not output_path or not os.path.isdir(output_path):
            self.log_area.append('Invalid output folder.')
            return
        if not chdman_path or not os.path.isfile(chdman_path):
            self.log_area.append('Invalid chdman.exe path.')
            return

        # Disable UI during conversion
        self.start_btn.setEnabled(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_label.setText('Starting conversion...')
        
        # Start conversion in separate thread
        self.conversion_worker = ConversionWorker(selected_files, output_path, chdman_path)
        self.conversion_worker.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_worker.progress_text.connect(self.progress_label.setText)
        self.conversion_worker.log_updated.connect(self.log_area.append)
        self.conversion_worker.conversion_finished.connect(self.conversion_completed)
        self.conversion_worker.start()

    def conversion_completed(self):
        self.start_btn.setEnabled(True)
        # Clean up temp dirs from conversion worker
        if self.conversion_worker:
            self.conversion_worker.cleanup_temp_dirs()
        self.cleanup_temp_dirs()
        self.log_area.append('Temp files cleaned up.')

    def cleanup_temp_dirs(self):
        """Clean up temporary directories created during scanning and conversion"""
        cleaned_count = 0
        for d in self.temp_dirs:
            try:
                if os.path.exists(d):
                    shutil.rmtree(d)
                    cleaned_count += 1
            except Exception as e:
                self.log_area.append(f'Warning: Could not clean up temp dir {d}: {e}')
        self.temp_dirs = []
        if cleaned_count > 0:
            self.log_area.append(f'Cleaned up {cleaned_count} temporary directories.')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CHDConverterGUI()
    window.show()
    sys.exit(app.exec_()) 