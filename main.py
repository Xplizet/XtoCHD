import sys
import os
import tempfile
import shutil
import zipfile
import subprocess
import threading
import time
import re
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QFileDialog, QTextEdit, QProgressBar, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QFrame, QDialog, QButtonGroup, QRadioButton, QStatusBar, QGroupBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

COMPATIBLE_EXTS = {
    '.cue', '.bin', '.iso', '.img', '.nrg', '.gdi', '.toc', '.ccd', '.m3u', '.vcd',
    '.chd', '.zip', '.cdr', '.hdi', '.vhd', '.vmdk', '.dsk'
}
DISK_IMAGE_EXTS = {'.cue', '.bin', '.iso', '.img'}

# System detection patterns
SYSTEM_PATTERNS = {
    'PlayStation': [r'psx', r'playstation', r'ps1', r'ps-1'],
    'PlayStation 2': [r'ps2', r'playstation2', r'ps-2'],
    'Sega Saturn': [r'saturn', r'sega\s*saturn', r'ss'],
    'Sega Dreamcast': [r'dreamcast', r'dc', r'sega\s*dreamcast'],
    'Nintendo 64': [r'n64', r'nintendo\s*64', r'nintendo64'],
    'GameCube': [r'gamecube', r'gc', r'ngc'],
    'Wii': [r'wii'],
    'Xbox': [r'xbox'],
    'Xbox 360': [r'xbox\s*360', r'x360'],
    'PC Engine': [r'pc\s*engine', r'turbografx', r'pce'],
    'Neo Geo': [r'neo\s*geo', r'neogeo', r'ng'],
    'Arcade': [r'arcade', r'mame', r'fba'],
    'Unknown': []
}

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
        self.conversion_stats = {
            'total_files': len(files),
            'successful_conversions': 0,
            'failed_conversions': 0,
            'skipped_files': 0,
            'original_size': 0,
            'compressed_size': 0,
            'successful_files': [],
            'failed_files': [],
            'skipped_files_list': []
        }
        self.cancelled = False
        
    def cancel(self):
        """Cancel the conversion process"""
        self.cancelled = True
        # Note: With subprocess.run, we can't cancel individual processes
        # The timeout will handle hanging processes
        
    def kill_chdman_process(self):
        """Kill the current chdman process and wait for termination"""
        # Not needed with subprocess.run approach
        pass
        
    def cleanup_incomplete_chd(self):
        """Remove incomplete CHD file if conversion was stopped"""
        # Not needed with subprocess.run approach
        pass
        
    def check_cancelled(self):
        """Check if conversion was cancelled and emit status"""
        if self.cancelled:
            self.progress_text.emit("Stopping conversion...")
            return True
        return False
        
    def run(self):
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            try:
                os.makedirs(self.output_dir)
                self.log_updated.emit(f'Created output directory: {self.output_dir}')
            except Exception as e:
                self.log_updated.emit(f'Failed to create output directory: {e}')
                return
        
        total_files = len(self.files)
        current_file = 0
        
        for file_path in self.files:
            if self.check_cancelled():
                break
                
            current_file += 1
            ext = os.path.splitext(file_path)[1].lower()
            
            # Update progress for starting this file
            progress_percent = int((current_file - 1) / total_files * 100)
            self.progress_updated.emit(progress_percent)
            self.progress_text.emit(f"Processing {os.path.basename(file_path)} ({current_file}/{total_files})")
            
            if ext == '.zip':
                # Handle zip files by extracting and converting contents
                self.log_updated.emit(f'Processing zip: {file_path}')
                self.process_zip_file(file_path, current_file, total_files)
            else:
                # Handle regular disk image files
                self.convert_single_file(file_path, current_file, total_files)
                
        if not self.cancelled:
            self.progress_updated.emit(100)
            self.progress_text.emit("Conversion complete!")
            self.log_updated.emit('Conversion complete.')
            
            # Generate and display summary
            self.generate_summary()
        else:
            self.progress_text.emit("Conversion stopped.")
            self.log_updated.emit('Conversion stopped by user.')
        
        self.conversion_finished.emit()
    
    def generate_summary(self):
        """Generate a comprehensive conversion summary"""
        summary = []
        summary.append("=" * 50)
        summary.append("CONVERSION SUMMARY")
        summary.append("=" * 50)
        
        # File statistics
        summary.append(f"Total files processed: {self.conversion_stats['total_files']}")
        summary.append(f"Successfully converted: {self.conversion_stats['successful_conversions']}")
        summary.append(f"Failed conversions: {self.conversion_stats['failed_conversions']}")
        summary.append(f"Skipped (already exist): {self.conversion_stats['skipped_files']}")
        
        total_processed = self.conversion_stats['successful_conversions'] + self.conversion_stats['failed_conversions'] + self.conversion_stats['skipped_files']
        if total_processed > 0:
            success_rate = (self.conversion_stats['successful_conversions'] / total_processed * 100)
            summary.append(f"Success rate: {success_rate:.1f}%")
        
        # Size statistics
        if self.conversion_stats['original_size'] > 0:
            original_gb = self.conversion_stats['original_size'] / (1024**3)
            compressed_gb = self.conversion_stats['compressed_size'] / (1024**3)
            saved_gb = original_gb - compressed_gb
            compression_ratio = (1 - (self.conversion_stats['compressed_size'] / self.conversion_stats['original_size'])) * 100
            
            summary.append("")
            summary.append("SIZE STATISTICS:")
            summary.append(f"Original total size: {original_gb:.2f} GB")
            summary.append(f"Compressed total size: {compressed_gb:.2f} GB")
            summary.append(f"Space saved: {saved_gb:.2f} GB")
            summary.append(f"Compression ratio: {compression_ratio:.1f}%")
        
        # Successful files list
        if self.conversion_stats['successful_files']:
            summary.append("")
            summary.append("SUCCESSFULLY CONVERTED:")
            for file_info in self.conversion_stats['successful_files']:
                summary.append(f"  ✓ {file_info['name']} ({file_info['original_size_mb']:.1f} MB → {file_info['compressed_size_mb']:.1f} MB)")
        
        # Skipped files list
        if self.conversion_stats['skipped_files_list']:
            summary.append("")
            summary.append("SKIPPED (CHD already exists):")
            for file_name in self.conversion_stats['skipped_files_list']:
                summary.append(f"  ⏭ {file_name}")
        
        # Failed files list
        if self.conversion_stats['failed_files']:
            summary.append("")
            summary.append("FAILED CONVERSIONS:")
            for file_name in self.conversion_stats['failed_files']:
                summary.append(f"  ✗ {file_name}")
        
        summary.append("=" * 50)
        
        # Display summary in log
        for line in summary:
            self.log_updated.emit(line)
    
    def process_zip_file(self, zip_path, current_file, total_files):
        """Extract zip and convert all compatible files inside"""
        if self.check_cancelled():
            return
            
        self.progress_text.emit(f"Extracting {os.path.basename(zip_path)}...")
        temp_dir = tempfile.mkdtemp(prefix='chdconv_zip_')
        self.temp_dirs.append(temp_dir)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Get list of files in zip for progress tracking
                zip_files = z.namelist()
                total_zip_files = len(zip_files)
                
                # First, check if any CHD files already exist for files in this zip
                existing_chd_count = 0
                for zip_file in zip_files:
                    if self.check_cancelled():
                        return
                    # Get the base name of the file in the zip
                    base_name = os.path.splitext(os.path.basename(zip_file))[0]
                    ext = os.path.splitext(zip_file)[1].lower()
                    if ext in DISK_IMAGE_EXTS:
                        chd_file = os.path.join(self.output_dir, base_name + '.chd')
                        if os.path.exists(chd_file):
                            existing_chd_count += 1
                            self.log_updated.emit(f'Skipped: {base_name} (CHD already exists)')
                            self.conversion_stats['skipped_files'] += 1
                            self.conversion_stats['skipped_files_list'].append(base_name)
                
                # If all files already exist, skip extraction entirely
                if existing_chd_count == len([f for f in zip_files if os.path.splitext(f)[1].lower() in DISK_IMAGE_EXTS]):
                    self.log_updated.emit(f'All files in {os.path.basename(zip_path)} already have CHD versions. Skipping extraction.')
                    return
                
                # Extract files that need processing
                for idx, zip_file in enumerate(zip_files):
                    if self.check_cancelled():
                        return
                    
                    # Check if this specific file already has a CHD version
                    base_name = os.path.splitext(os.path.basename(zip_file))[0]
                    ext = os.path.splitext(zip_file)[1].lower()
                    if ext in DISK_IMAGE_EXTS:
                        chd_file = os.path.join(self.output_dir, base_name + '.chd')
                        if os.path.exists(chd_file):
                            # Skip extraction for this file
                            continue
                    
                    z.extract(zip_file, temp_dir)
                    # Update progress during extraction
                    extraction_progress = int((idx + 1) / total_zip_files * 20)  # 20% for extraction
                    file_progress = int((current_file - 1) / total_files * 100)
                    total_progress = file_progress + extraction_progress
                    self.progress_updated.emit(min(total_progress, 99))
                    self.progress_text.emit(f"Extracting {zip_file} from {os.path.basename(zip_path)}")
            
            if self.check_cancelled():
                return
                
            # Find all disk images in extracted content
            self.progress_text.emit("Scanning extracted files...")
            disk_images = []
            for root, _, files in os.walk(temp_dir):
                for fname in files:
                    if self.check_cancelled():
                        return
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in DISK_IMAGE_EXTS:
                        disk_images.append(os.path.join(root, fname))
            
            # Convert each disk image found in zip
            for idx, extracted_file in enumerate(disk_images):
                if self.check_cancelled():
                    return
                self.progress_text.emit(f"Converting extracted file {os.path.basename(extracted_file)} ({idx+1}/{len(disk_images)})")
                self.convert_single_file(extracted_file, current_file, total_files)
                        
        except Exception as e:
            self.log_updated.emit(f'Failed to process zip {zip_path}: {e}')
    
    def convert_single_file(self, file_path, current_file, total_files):
        """Convert a single disk image file to CHD"""
        if self.check_cancelled():
            return
        ext = os.path.splitext(file_path)[1].lower()
        base_name = os.path.basename(file_path)
        
        self.log_updated.emit(f'Converting: {file_path}')
        self.progress_text.emit(f"Converting {base_name} to CHD format...")
        
        # Get original file size
        original_size = os.path.getsize(file_path)
        self.conversion_stats['original_size'] += original_size
        
        try:
            if ext == '.cue':
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', file_path + '.chd']
            elif ext in {'.iso', '.bin', '.img'}:
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', file_path + '.chd']
            else:
                self.log_updated.emit(f'Skipped unsupported file: {file_path}')
                self.conversion_stats['failed_conversions'] += 1
                self.conversion_stats['failed_files'].append(os.path.basename(file_path))
                return
                
            # Use CREATE_NO_WINDOW to hide the CMD window
            self.progress_text.emit(f"Running CHD conversion on {base_name}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            
            stdout = result.stdout
            stderr = result.stderr
            result_code = result.returncode
            
            # Process completed
            
            if result_code == 0:
                # Get compressed file size
                compressed_size = os.path.getsize(file_path + '.chd')
                self.conversion_stats['compressed_size'] += compressed_size
                
                # Add to successful conversions
                self.conversion_stats['successful_conversions'] += 1
                self.conversion_stats['successful_files'].append({
                    'name': os.path.basename(file_path),
                    'original_size_mb': original_size / (1024**2),
                    'compressed_size_mb': compressed_size / (1024**2)
                })
                
                self.log_updated.emit(f'Success: {file_path + ".chd"}')
                self.progress_text.emit(f"✓ Completed: {base_name}.chd")
            else:
                # Remove incomplete CHD file on failure
                if os.path.exists(file_path + '.chd'):
                    try:
                        os.remove(file_path + '.chd')
                        self.log_updated.emit(f'Removed incomplete file: {os.path.basename(file_path + ".chd")}')
                    except Exception as e:
                        self.log_updated.emit(f'Could not remove incomplete file: {e}')
                
                self.log_updated.emit(f'Error converting {file_path}: {stderr}')
                self.progress_text.emit(f"✗ Failed: {base_name}")
                self.conversion_stats['failed_conversions'] += 1
                self.conversion_stats['failed_files'].append(os.path.basename(file_path))
                
        except Exception as e:
            # Remove incomplete CHD file on exception
            if os.path.exists(file_path + '.chd'):
                try:
                    os.remove(file_path + '.chd')
                    self.log_updated.emit(f'Removed incomplete file: {os.path.basename(file_path + ".chd")}')
                except Exception as cleanup_error:
                    self.log_updated.emit(f'Could not remove incomplete file: {cleanup_error}')
            
            self.log_updated.emit(f'Exception: {e}')
            self.progress_text.emit(f"✗ Error: {base_name}")
            self.conversion_stats['failed_conversions'] += 1
            self.conversion_stats['failed_files'].append(os.path.basename(file_path))
    
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
            self.scan_progress.emit('Scanning for files...')
            found = []
            if os.path.isfile(self.input_path):
                ext = os.path.splitext(self.input_path)[1].lower()
                if ext in COMPATIBLE_EXTS:
                    found.append(self.input_path)
                    self.scan_progress.emit(f'Found: {os.path.basename(self.input_path)}')
            else:
                for root, dirs, files in os.walk(self.input_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for fname in files:
                        ext = os.path.splitext(fname)[1].lower()
                        if ext in COMPATIBLE_EXTS:
                            fpath = os.path.join(root, fname)
                            found.append(fpath)
                            self.scan_progress.emit(f'Found: {os.path.basename(fpath)}')
            self.scan_complete.emit(found)
        except Exception as e:
            self.scan_error.emit(f'Scan error: {e}')

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
        self.setGeometry(100, 100, 1100, 700)
        self.temp_dirs = []
        self.found_files = []
        self.conversion_worker = None
        self.scan_worker = None
        self.init_ui()
        self.auto_detect_chdman()
        # Drag-and-drop support
        self.setAcceptDrops(True)

    def auto_detect_chdman(self):
        """Auto-detect chdman.exe in the same directory as the application"""
        # Check if chdman.exe exists in the same directory as the application
        app_dir = os.path.dirname(os.path.abspath(__file__))
        chdman_in_app_dir = os.path.join(app_dir, 'chdman.exe')
        
        if os.path.isfile(chdman_in_app_dir):
            self.chdman_path_edit.setText(chdman_in_app_dir)
        else:
            # Fallback to current working directory
            chdman_in_cwd = os.path.join(os.getcwd(), 'chdman.exe')
            if os.path.isfile(chdman_in_cwd):
                self.chdman_path_edit.setText(chdman_in_cwd)
            else:
                # Default to empty if not found
                self.chdman_path_edit.setText('')

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if paths:
            path = paths[0]
            self.input_path_edit.setText(path)
            self.auto_suggest_output_folder(path)
            self.status_bar.showMessage('Scanning for files...')
            self.scan_for_files_auto(path)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        # Input path
        input_layout = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        self.add_file_btn = QPushButton('Add File')
        self.add_folder_btn = QPushButton('Add Folder')
        for btn in (self.add_file_btn, self.add_folder_btn):
            btn.setMinimumHeight(28)
            btn.setMinimumWidth(110)
        self.add_file_btn.clicked.connect(self.select_input_file)
        self.add_folder_btn.clicked.connect(self.select_input_folder)
        input_layout.addWidget(QLabel('Input:'))
        input_layout.addWidget(self.input_path_edit)
        input_layout.addWidget(self.add_file_btn)
        input_layout.addWidget(self.add_folder_btn)
        layout.addLayout(input_layout)

        # Output path
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_btn = QPushButton('Select Output Folder')
        self.output_btn.setMinimumHeight(28)
        self.output_btn.clicked.connect(self.select_output)
        # Open Output Folder button
        self.open_output_btn = QPushButton('Open Output Folder')
        self.open_output_btn.setMinimumHeight(28)
        self.open_output_btn.clicked.connect(self.open_output_folder)
        output_layout.addWidget(QLabel('Output:'))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.addWidget(self.open_output_btn)
        layout.addLayout(output_layout)

        # chdman path
        chdman_layout = QHBoxLayout()
        self.chdman_path_edit = QLineEdit()
        self.chdman_btn = QPushButton('Select chdman.exe')
        self.chdman_btn.setMinimumHeight(28)
        self.chdman_btn.clicked.connect(self.select_chdman)
        chdman_layout.addWidget(QLabel('chdman.exe:'))
        chdman_layout.addWidget(self.chdman_path_edit)
        chdman_layout.addWidget(self.chdman_btn)
        layout.addLayout(chdman_layout)

        # File list section
        file_list_label = QLabel('Files to Convert:')
        layout.addWidget(file_list_label)
        # File list with checkboxes and sizes
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        # Select all/none buttons
        select_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.setMinimumHeight(28)
        self.select_all_btn.clicked.connect(self.select_all_files)
        self.select_none_btn = QPushButton('Select None')
        self.select_none_btn.setMinimumHeight(28)
        self.select_none_btn.clicked.connect(self.select_none_files)
        select_buttons_layout.addWidget(self.select_all_btn)
        select_buttons_layout.addWidget(self.select_none_btn)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)
        # Start/Stop buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton('Start Conversion')
        self.start_btn.setMinimumHeight(28)
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        self.stop_btn = QPushButton('Stop Conversion')
        self.stop_btn.setMinimumHeight(28)
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        layout.addLayout(button_layout)
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        # Log area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(QLabel('Log:'))
        layout.addWidget(self.log_area)
        # Status bar at bottom
        self.status_bar = QStatusBar()
        self.status_bar.showMessage('Ready to convert')
        layout.addWidget(self.status_bar)
        self.setLayout(layout)

    def open_output_folder(self):
        import os
        import subprocess
        folder = self.output_path_edit.text().strip()
        if folder and os.path.isdir(folder):
            if os.name == 'nt':
                os.startfile(folder)
            elif os.name == 'posix':
                subprocess.Popen(['xdg-open', folder])

    def select_input_file(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(self, 'Select File', '',
            'Compatible Files (*.cue *.bin *.iso *.img *.zip *.nrg *.gdi *.toc *.ccd *.m3u *.vcd *.chd *.cdr *.hdi *.vhd *.vmdk *.dsk);;All Files (*)', options=options)
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

    def scan_for_files_auto(self, input_path):
        # Use ScanWorker (QThread) for safe background scanning
        if not input_path or not os.path.exists(input_path):
            self.status_bar.showMessage('Invalid input path.')
            return
        self.found_files = []
        self.file_list.clear()
        self.start_btn.setEnabled(False)
        self.status_bar.showMessage('Scanning for files...')
        # If a previous scan_worker exists, clean up
        if hasattr(self, 'scan_worker') and self.scan_worker is not None:
            self.scan_worker.quit()
            self.scan_worker.wait()
        self.scan_worker = ScanWorker(input_path)
        self.scan_worker.scan_progress.connect(self.status_bar.showMessage)
        self.scan_worker.scan_complete.connect(self.scan_completed)
        self.scan_worker.scan_error.connect(self.scan_error)
        self.scan_worker.start()

    def scan_completed(self, found_files):
        self.found_files = found_files
        self.populate_file_list()
        self.status_bar.showMessage(f'Scan complete: {len(found_files)} file(s) found.')
        self.start_btn.setEnabled(len(found_files) > 0)

    def scan_error(self, error_msg):
        self.status_bar.showMessage(error_msg)
        self.start_btn.setEnabled(False)

    def auto_suggest_output_folder(self, input_path):
        """Auto-suggest output folder as [input_path]/CHD/ without creating it"""
        if os.path.isfile(input_path):
            # If input is a file, use its directory
            input_dir = os.path.dirname(input_path)
        else:
            # If input is a folder, use it directly
            input_dir = input_path
        
        # Create CHD subfolder path
        chd_folder = os.path.join(input_dir, 'CHD')
        
        # Set the output path (don't create folder yet)
        self.output_path_edit.setText(chd_folder)
        self.log_area.append(f'Suggested output folder: {chd_folder}')

    def select_output(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', '', options=options)
        if folder:
            self.output_path_edit.setText(folder)
            # Clear the auto-suggestion log since user manually selected
            self.log_area.append(f'Manually selected output folder: {folder}')

    def select_chdman(self):
        options = QFileDialog.Options()
        file, _ = QFileDialog.getOpenFileName(self, 'Select chdman.exe', '', 'Executable (*.exe);;All Files (*)', options=options)
        if file:
            self.chdman_path_edit.setText(file)
    
    def populate_file_list(self):
        self.file_list.clear()
        for file_path in self.found_files:
            item = QListWidgetItem()
            try:
                size = os.path.getsize(file_path)
                size_mb = size / (1024 * 1024)
                size_str = f" ({size_mb:.2f} MB)"
            except Exception:
                size_str = ""
            checkbox = QCheckBox(os.path.basename(file_path) + size_str)
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
        
        if not output_path:
            self.log_area.append('Please select an output folder.')
            return
        if not chdman_path or not os.path.isfile(chdman_path):
            self.log_area.append('Invalid chdman.exe path.')
            return

        # Disable all UI elements during conversion
        self.disable_ui_during_conversion()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage('Starting conversion...')
        
        # Start conversion in separate thread
        self.conversion_worker = ConversionWorker(selected_files, output_path, chdman_path)
        self.conversion_worker.progress_updated.connect(self.progress_bar.setValue)
        self.conversion_worker.progress_text.connect(self.status_bar.showMessage)
        self.conversion_worker.log_updated.connect(self.log_area_append)
        self.conversion_worker.conversion_finished.connect(self.conversion_completed)
        self.conversion_worker.start()

    def disable_ui_during_conversion(self):
        """Disable all UI elements except stop button during conversion"""
        self.add_file_btn.setEnabled(False)
        self.add_folder_btn.setEnabled(False)
        self.output_btn.setEnabled(False)
        self.chdman_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.file_list.setEnabled(False)

    def enable_ui_after_conversion(self):
        """Re-enable all UI elements after conversion"""
        self.add_file_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.output_btn.setEnabled(True)
        self.chdman_btn.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.file_list.setEnabled(True)

    def stop_conversion(self):
        """Stop the current conversion process"""
        if self.conversion_worker and self.conversion_worker.isRunning():
            self.conversion_worker.cancel()
            self.status_bar.showMessage('Stopping conversion...')

    def conversion_completed(self):
        self.enable_ui_after_conversion()
        
        # Clean up temp dirs from conversion worker
        if self.conversion_worker:
            self.conversion_worker.cleanup_temp_dirs()
        self.cleanup_temp_dirs()
        
        # Update status based on completion
        if self.conversion_worker and self.conversion_worker.cancelled:
            self.status_bar.showMessage('Conversion stopped')
        else:
            self.status_bar.showMessage('Conversion completed')

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

    def log_area_append(self, text):
        self.log_area.append(text)
        self.log_area.moveCursor(self.log_area.textCursor().End)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CHDConverterGUI()
    window.show()
    sys.exit(app.exec_()) 