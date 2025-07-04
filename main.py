import sys
import os
import tempfile
import shutil
import zipfile
import subprocess
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QFileDialog, QTextEdit, QProgressBar, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QFrame, QDialog, QButtonGroup, QRadioButton, QStatusBar
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
            
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        chd_file = os.path.join(self.output_dir, base_name + '.chd')
        ext = os.path.splitext(file_path)[1].lower()
        
        # Check if CHD file already exists
        if os.path.exists(chd_file):
            self.log_updated.emit(f'Skipped: {os.path.basename(file_path)} (CHD already exists)')
            self.progress_text.emit(f"⏭ Skipped: {base_name} (already exists)")
            self.conversion_stats['skipped_files'] += 1
            self.conversion_stats['skipped_files_list'].append(os.path.basename(file_path))
            return
        
        self.log_updated.emit(f'Converting: {file_path}')
        self.progress_text.emit(f"Converting {base_name} to CHD format...")
        
        # Get original file size
        original_size = os.path.getsize(file_path)
        self.conversion_stats['original_size'] += original_size
        
        try:
            if ext == '.cue':
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', chd_file]
            elif ext in {'.iso', '.bin', '.img'}:
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', chd_file]
            else:
                self.log_updated.emit(f'Skipped unsupported file: {file_path}')
                self.conversion_stats['failed_conversions'] += 1
                self.conversion_stats['failed_files'].append(os.path.basename(file_path))
                self.current_chd_file = None
                return
                
            # Use CREATE_NO_WINDOW to hide the CMD window
            self.progress_text.emit(f"Running CHD conversion on {base_name}...")
            
            # Use subprocess.run like the original working version
            self.progress_text.emit(f"Running CHD conversion on {base_name}...")
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  creationflags=subprocess.CREATE_NO_WINDOW)
            
            stdout = result.stdout
            stderr = result.stderr
            result_code = result.returncode
            
            # Process completed
            
            if result_code == 0:
                # Get compressed file size
                compressed_size = os.path.getsize(chd_file)
                self.conversion_stats['compressed_size'] += compressed_size
                
                # Add to successful conversions
                self.conversion_stats['successful_conversions'] += 1
                self.conversion_stats['successful_files'].append({
                    'name': os.path.basename(file_path),
                    'original_size_mb': original_size / (1024**2),
                    'compressed_size_mb': compressed_size / (1024**2)
                })
                
                self.log_updated.emit(f'Success: {chd_file}')
                self.progress_text.emit(f"✓ Completed: {base_name}.chd")
            else:
                # Remove incomplete CHD file on failure
                if os.path.exists(chd_file):
                    try:
                        os.remove(chd_file)
                        self.log_updated.emit(f'Removed incomplete file: {os.path.basename(chd_file)}')
                    except Exception as e:
                        self.log_updated.emit(f'Could not remove incomplete file: {e}')
                
                self.log_updated.emit(f'Error converting {file_path}: {stderr}')
                self.progress_text.emit(f"✗ Failed: {base_name}")
                self.conversion_stats['failed_conversions'] += 1
                self.conversion_stats['failed_files'].append(os.path.basename(file_path))
                
        except Exception as e:
            # Remove incomplete CHD file on exception
            if os.path.exists(chd_file):
                try:
                    os.remove(chd_file)
                    self.log_updated.emit(f'Removed incomplete file: {os.path.basename(chd_file)}')
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
            self.scan_progress.emit('Scanning for compatible files...')
            found_files = self.scan_files(self.input_path)
            
            # Remove duplicates and prioritize better formats
            deduplicated_files = self.remove_duplicates(found_files)
            
            self.scan_complete.emit(deduplicated_files)
        except Exception as e:
            self.scan_error.emit(f'Scan error: {e}')
    
    def remove_duplicates(self, files):
        """Remove duplicates and prioritize better formats"""
        # Group files by base name (without extension)
        file_groups = {}
        
        for file_path in files:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            ext = os.path.splitext(file_path)[1].lower()
            
            if base_name not in file_groups:
                file_groups[base_name] = []
            
            file_groups[base_name].append((file_path, ext))
        
        # For each group, select the best format
        deduplicated = []
        for base_name, file_list in file_groups.items():
            if len(file_list) == 1:
                # Only one file, use it
                deduplicated.append(file_list[0][0])
            else:
                # Multiple files, prioritize by format
                best_file = self.select_best_format(file_list)
                deduplicated.append(best_file)
        
        return deduplicated
    
    def select_best_format(self, file_list):
        """Select the best format from a list of files with the same base name"""
        # Priority order: .cue > .iso > .bin > .img > .zip
        priority_order = ['.cue', '.iso', '.bin', '.img', '.zip']
        
        # Sort files by priority
        sorted_files = sorted(file_list, key=lambda x: priority_order.index(x[1]) if x[1] in priority_order else 999)
        
        # Return the highest priority file
        return sorted_files[0][0]

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
        self.auto_detect_chdman()

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

    def init_ui(self):
        layout = QVBoxLayout()

        # Input path
        input_layout = QHBoxLayout()
        self.input_path_edit = QLineEdit()
        self.input_btn = QPushButton('Select File/Folder')
        self.input_btn.clicked.connect(self.select_input)
        input_layout.addWidget(QLabel('Input:'))
        input_layout.addWidget(self.input_path_edit)
        input_layout.addWidget(self.input_btn)
        layout.addLayout(input_layout)

        # Output path
        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit()
        self.output_btn = QPushButton('Select Output Folder')
        self.output_btn.clicked.connect(self.select_output)
        output_layout.addWidget(QLabel('Output:'))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(self.output_btn)
        layout.addLayout(output_layout)

        # chdman path
        chdman_layout = QHBoxLayout()
        self.chdman_path_edit = QLineEdit()
        self.chdman_btn = QPushButton('Select chdman.exe')
        self.chdman_btn.clicked.connect(self.select_chdman)
        chdman_layout.addWidget(QLabel('chdman.exe:'))
        chdman_layout.addWidget(self.chdman_path_edit)
        chdman_layout.addWidget(self.chdman_btn)
        layout.addLayout(chdman_layout)





        # Scan button
        self.scan_btn = QPushButton('Scan for Files')
        self.scan_btn.clicked.connect(self.scan_for_files)
        layout.addWidget(self.scan_btn)

        # File list section
        file_list_label = QLabel('Files to Convert:')
        layout.addWidget(file_list_label)
        
        # File list with checkboxes
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        
        # Select all/none buttons
        select_buttons_layout = QHBoxLayout()
        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.clicked.connect(self.select_all_files)
        self.select_none_btn = QPushButton('Select None')
        self.select_none_btn.clicked.connect(self.select_none_files)
        select_buttons_layout.addWidget(self.select_all_btn)
        select_buttons_layout.addWidget(self.select_none_btn)
        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)

        # Start/Stop buttons
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton('Start Conversion')
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setEnabled(False)
        
        self.stop_btn = QPushButton('Stop Conversion')
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
                    # Auto-suggest output folder
                    self.auto_suggest_output_folder(file)
            else:
                # Folder selection
                folder = QFileDialog.getExistingDirectory(
                    self, 'Select Folder', '', options=options
                )
                if folder:
                    self.input_path_edit.setText(folder)
                    # Auto-suggest output folder
                    self.auto_suggest_output_folder(folder)

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
        self.conversion_worker.log_updated.connect(self.log_area.append)
        self.conversion_worker.conversion_finished.connect(self.conversion_completed)
        self.conversion_worker.start()

    def disable_ui_during_conversion(self):
        """Disable all UI elements except stop button during conversion"""
        self.input_btn.setEnabled(False)
        self.output_btn.setEnabled(False)
        self.chdman_btn.setEnabled(False)
        self.scan_btn.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.file_list.setEnabled(False)

    def enable_ui_after_conversion(self):
        """Re-enable all UI elements after conversion"""
        self.input_btn.setEnabled(True)
        self.output_btn.setEnabled(True)
        self.chdman_btn.setEnabled(True)
        self.scan_btn.setEnabled(True)
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CHDConverterGUI()
    window.show()
    sys.exit(app.exec_()) 