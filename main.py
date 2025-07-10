import sys
import os
import tempfile
import shutil
import zipfile
import subprocess
import threading
import time
import re
import struct
import atexit
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QFileDialog, QTextEdit, QProgressBar, QListWidget, QListWidgetItem, QCheckBox,
    QScrollArea, QFrame, QDialog, QButtonGroup, QRadioButton, QStatusBar, QGroupBox,
    QAction, QMenuBar, QMenu, QMainWindow
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QFileSystemWatcher
from PyQt5.QtGui import QColor, QPalette, QFont

COMPATIBLE_EXTS = {
    '.cue', '.bin', '.iso', '.img', '.nrg', '.gdi', '.toc', '.ccd', '.vcd',
    '.chd', '.zip', '.cdr', '.hdi', '.vhd', '.vmdk', '.dsk'
}
DISK_IMAGE_EXTS = {'.cue', '.bin', '.iso', '.img'}

# Global temp directory management
class TempFileManager:
    """Manages temporary files and directories with crash-proof cleanup"""
    
    def __init__(self):
        if getattr(sys, 'frozen', False):
            # Running as compiled .exe
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
        self.temp_base_dir = os.path.join(self.app_dir, 'temp')
        self.temp_dirs = []
        self.cleanup_on_exit = True
        
        # Create temp directory if it doesn't exist
        self._ensure_temp_dir()
        
        # Register cleanup on application exit
        atexit.register(self.cleanup_all_temp_dirs)
    
    def _ensure_temp_dir(self):
        """Ensure the temp directory exists"""
        try:
            if not os.path.exists(self.temp_base_dir):
                os.makedirs(self.temp_base_dir)
        except Exception as e:
            print(f"Warning: Could not create temp directory {self.temp_base_dir}: {e}")
    
    def create_temp_dir(self, prefix='chdconv_'):
        """Create a temporary directory within the app's temp folder"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            temp_dir = os.path.join(self.temp_base_dir, f"{prefix}{timestamp}_{os.getpid()}")
            os.makedirs(temp_dir, exist_ok=True)
            self.temp_dirs.append(temp_dir)
            return temp_dir
        except Exception as e:
            print(f"Warning: Could not create temp directory: {e}")
            # Fallback to system temp directory
            fallback_dir = tempfile.mkdtemp(prefix=prefix)
            self.temp_dirs.append(fallback_dir)
            return fallback_dir
    
    def cleanup_temp_dir(self, temp_dir):
        """Clean up a specific temp directory"""
        if temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    self.temp_dirs.remove(temp_dir)
                    return True
            except Exception as e:
                print(f"Warning: Could not clean up temp dir {temp_dir}: {e}")
        return False
    
    def cleanup_all_temp_dirs(self):
        """Clean up all tracked temp directories"""
        if not self.cleanup_on_exit:
            return
            
        cleaned_count = 0
        for temp_dir in self.temp_dirs[:]:  # Copy list to avoid modification during iteration
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    cleaned_count += 1
            except Exception as e:
                print(f"Warning: Could not clean up temp dir {temp_dir}: {e}")
        
        self.temp_dirs.clear()
        return cleaned_count
    
    def cleanup_orphaned_temp_dirs(self):
        """Clean up any orphaned temp directories from previous runs"""
        if not os.path.exists(self.temp_base_dir):
            return 0
            
        cleaned_count = 0
        try:
            for item in os.listdir(self.temp_base_dir):
                item_path = os.path.join(self.temp_base_dir, item)
                if os.path.isdir(item_path):
                    # Check if this is an old temp directory (older than 1 hour)
                    try:
                        stat = os.stat(item_path)
                        age_hours = (time.time() - stat.st_mtime) / 3600
                        if age_hours > 1:  # Clean up directories older than 1 hour
                            shutil.rmtree(item_path)
                            cleaned_count += 1
                    except Exception as e:
                        print(f"Warning: Could not check/clean temp dir {item_path}: {e}")
        except Exception as e:
            print(f"Warning: Could not scan temp directory: {e}")
        
        return cleaned_count
    
    def get_temp_dir_size(self):
        """Get the total size of the temp directory in bytes"""
        if not os.path.exists(self.temp_base_dir):
            return 0
            
        total_size = 0
        try:
            for root, dirs, files in os.walk(self.temp_base_dir):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                    except (OSError, IOError):
                        pass
        except Exception:
            pass
        
        return total_size
    
    def format_size(self, size_bytes):
        """Format bytes into human readable format"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

# Global temp file manager instance
temp_manager = TempFileManager()

# Theme management
class ThemeManager:
    @staticmethod
    def get_light_theme():
        return """
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
        QPushButton:hover {
            background-color: #d0d0d0;
        }
        QPushButton:pressed {
            background-color: #c0c0c0;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #999999;
        }
        QLineEdit {
            background-color: white;
            border: 1px solid #cccccc;
            border-radius: 3px;
            padding: 4px;
        }
        QLineEdit:focus {
            border: 2px solid #4a90e2;
        }
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
        QListWidget::item {
            padding: 4px;
        }
        QListWidget::item:selected {
            background-color: #e3f2fd;
            color: #1976d2;
        }
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 3px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #4caf50;
            border-radius: 2px;
        }
        QStatusBar {
            background-color: #e0e0e0;
            border-top: 1px solid #cccccc;
        }
        QMenuBar {
            background-color: #f5f5f5;
            border-bottom: 1px solid #cccccc;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background-color: #e0e0e0;
        }
        QMenu {
            background-color: white;
            border: 1px solid #cccccc;
        }
        QMenu::item {
            padding: 6px 20px;
        }
        QMenu::item:selected {
            background-color: #e3f2fd;
        }
        """

    @staticmethod
    def get_dark_theme():
        return """
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
        QPushButton:hover {
            background-color: #505050;
        }
        QPushButton:pressed {
            background-color: #353535;
        }
        QPushButton:disabled {
            background-color: #353535;
            color: #666666;
        }
        QLineEdit {
            background-color: #404040;
            border: 1px solid #555555;
            border-radius: 3px;
            padding: 4px;
            color: #e0e0e0;
        }
        QLineEdit:focus {
            border: 2px solid #64b5f6;
        }
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
        QListWidget::item {
            padding: 4px;
        }
        QListWidget::item:selected {
            background-color: #1976d2;
            color: white;
        }
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 3px;
            text-align: center;
            background-color: #404040;
        }
        QProgressBar::chunk {
            background-color: #4caf50;
            border-radius: 2px;
        }
        QStatusBar {
            background-color: #404040;
            border-top: 1px solid #555555;
        }
        QMenuBar {
            background-color: #2d2d2d;
            border-bottom: 1px solid #555555;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background-color: #404040;
        }
        QMenu {
            background-color: #404040;
            border: 1px solid #555555;
        }
        QMenu::item {
            padding: 6px 20px;
        }
        QMenu::item:selected {
            background-color: #1976d2;
        }
        QCheckBox {
            color: #e0e0e0;
        }
        QCheckBox::indicator {
            width: 16px;
            height: 16px;
        }
        QCheckBox::indicator:unchecked {
            border: 2px solid #555555;
            background-color: #404040;
        }
        QCheckBox::indicator:checked {
            border: 2px solid #64b5f6;
            background-color: #1976d2;
        }
        QLabel {
            color: #e0e0e0;
        }
        """

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

# File validation functions
def validate_file(file_path, fast_mode=True):
    """Basic file validation - check if file exists and has valid header"""
    try:
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        if not os.path.isfile(file_path):
            return False, "Not a file"
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return False, "Empty file"
        
        # Read first 2KB for header validation
        with open(file_path, 'rb') as f:
            header = f.read(2048)
        
        if len(header) == 0:
            return False, "Cannot read file"
        
        # Basic validation based on file extension
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.iso':
            return validate_iso_file(header, file_size, fast_mode)
        elif ext == '.cue':
            return validate_cue_file(file_path, fast_mode)
        elif ext == '.bin':
            return validate_bin_file(header, file_size)
        elif ext == '.img':
            return validate_img_file(header, file_size)
        elif ext == '.zip':
            return validate_zip_file(file_path, fast_mode)
        else:
            # For other supported formats, just check if file is readable
            return True, "File appears valid"
            
    except Exception as e:
        return False, f"Validation error: {str(e)}"

def validate_iso_file(header, file_size, fast_mode=True):
    """Validate ISO file format"""
    try:
        if fast_mode:
            # Fast mode: only check file size (2KB minimum)
            if file_size >= 2048:
                return True, "ISO file appears valid (fast mode)"
            else:
                return False, "ISO file too small"
        else:
            # Full mode: check for ISO 9660 signature
            if len(header) >= 32768:  # ISO files should be at least 32KB
                # Look for ISO 9660 volume descriptor
                for i in range(0, min(len(header), 32768), 2048):
                    if i + 7 < len(header):
                        if header[i:i+6] == b'CD001\x01':
                            return True, "Valid ISO 9660 format"
            
            # Check for other common ISO formats
            if file_size >= 2048:  # Minimum size for any ISO
                return True, "ISO file appears valid"
            else:
                return False, "ISO file too small"
            
    except Exception as e:
        return False, f"ISO validation error: {str(e)}"

def validate_cue_file(file_path, fast_mode=True):
    """Validate CUE file format"""
    try:
        if fast_mode:
            # Fast mode: read 512 bytes instead of 1KB
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(512)
        else:
            # Full mode: read 1KB
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(1024)
            
        if not content.strip():
            return False, "Empty CUE file"
        
        # Check for basic CUE file structure
        lines = content.split('\n')
        has_file = False
        has_track = False
        
        for line in lines:
            line = line.strip().upper()
            if line.startswith('FILE'):
                has_file = True
            elif line.startswith('TRACK'):
                has_track = True
                
        if has_file and has_track:
            mode_text = " (fast mode)" if fast_mode else ""
            return True, f"Valid CUE file{mode_text}"
        else:
            return False, "Invalid CUE file structure"
            
    except Exception as e:
        return False, f"CUE validation error: {str(e)}"

def validate_bin_file(header, file_size):
    """Validate BIN file format"""
    try:
        # BIN files should be at least 1KB and have some data
        if file_size >= 1024:
            return True, "BIN file appears valid"
        else:
            return False, "BIN file too small"
            
    except Exception as e:
        return False, f"BIN validation error: {str(e)}"

def validate_img_file(header, file_size):
    """Validate IMG file format"""
    try:
        # IMG files should be at least 1KB
        if file_size >= 1024:
            return True, "IMG file appears valid"
        else:
            return False, "IMG file too small"
            
    except Exception as e:
        return False, f"IMG validation error: {str(e)}"

def validate_zip_file(file_path, fast_mode=True):
    """Validate ZIP file format"""
    try:
        if fast_mode:
            # Fast mode: only check header signature
            with open(file_path, 'rb') as f:
                header = f.read(4)
            if header == b'PK\x03\x04':
                return True, "Valid ZIP file (fast mode)"
            else:
                return False, "Invalid ZIP file format"
        else:
            # Full mode: complete integrity test
            with zipfile.ZipFile(file_path, 'r') as z:
                # Check if ZIP is valid
                test_result = z.testzip()
                if test_result is None:
                    return True, "Valid ZIP file"
                else:
                    return False, f"ZIP file corrupted: {test_result}"
    except zipfile.BadZipFile:
        return False, "Invalid ZIP file format"
    except Exception as e:
        return False, f"ZIP validation error: {str(e)}"



def get_file_info(file_path, fast_validation=True):
    """Get comprehensive file information"""
    try:
        file_size = os.path.getsize(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        # Format file size
        if file_size >= 1024**3:
            size_str = f"{file_size / (1024**3):.2f} GB"
        elif file_size >= 1024**2:
            size_str = f"{file_size / (1024**2):.2f} MB"
        elif file_size >= 1024:
            size_str = f"{file_size / 1024:.2f} KB"
        else:
            size_str = f"{file_size} bytes"
        
        # Validate file
        is_valid, validation_msg = validate_file(file_path, fast_validation)
        
        return {
            'name': os.path.basename(file_path),
            'path': file_path,
            'size': file_size,
            'size_str': size_str,
            'extension': ext,
            'is_valid': is_valid,
            'validation_msg': validation_msg
        }
        
    except Exception as e:
        return {
            'name': os.path.basename(file_path),
            'path': file_path,
            'size': 0,
            'size_str': 'Unknown',
            'extension': os.path.splitext(file_path)[1].lower(),
            'is_valid': False,
            'validation_msg': f"Error reading file: {str(e)}"
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
        temp_dir = temp_manager.create_temp_dir(prefix='chdconv_zip_')
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
        base_name_without_ext = os.path.splitext(base_name)[0]
        
        # Check if CHD file already exists in output directory
        output_chd_path = os.path.join(self.output_dir, base_name_without_ext + '.chd')
        if os.path.exists(output_chd_path):
            self.log_updated.emit(f'Skipped: {base_name} (CHD already exists: {os.path.basename(output_chd_path)})')
            self.conversion_stats['skipped_files'] += 1
            self.conversion_stats['skipped_files_list'].append(base_name)
            return
        
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
            elif ext in COMPATIBLE_EXTS:
                # For other supported formats, try the same command
                cmd = [self.chdman_path, 'createcd', '-i', file_path, '-o', file_path + '.chd']
            else:
                self.log_updated.emit(f'Skipped unsupported file type ({ext}): {file_path}')
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
                # Get the generated CHD file path
                chd_file_path = file_path + '.chd'
                
                # Create output filename
                base_name_without_ext = os.path.splitext(base_name)[0]
                output_chd_path = os.path.join(self.output_dir, base_name_without_ext + '.chd')
                
                # Move CHD file to output directory
                try:
                    # Ensure output directory exists
                    os.makedirs(self.output_dir, exist_ok=True)
                    
                    # Move the file to output directory
                    shutil.move(chd_file_path, output_chd_path)
                    
                    # Get compressed file size
                    compressed_size = os.path.getsize(output_chd_path)
                    self.conversion_stats['compressed_size'] += compressed_size
                    
                    # Add to successful conversions
                    self.conversion_stats['successful_conversions'] += 1
                    self.conversion_stats['successful_files'].append({
                        'name': os.path.basename(output_chd_path),
                        'original_size_mb': original_size / (1024**2),
                        'compressed_size_mb': compressed_size / (1024**2)
                    })
                    
                    self.log_updated.emit(f'Success: {output_chd_path}')
                    self.progress_text.emit(f"✓ Completed: {os.path.basename(output_chd_path)}")
                    
                    # Clean up temp files for this specific conversion
                    self.cleanup_temp_files_for_file(file_path)
                    
                except Exception as move_error:
                    # If move fails, try to clean up and report error
                    if os.path.exists(chd_file_path):
                        try:
                            os.remove(chd_file_path)
                        except:
                            pass
                    self.log_updated.emit(f'Error moving file to output directory: {move_error}')
                    self.progress_text.emit(f"✗ Failed to move: {base_name}")
                    self.conversion_stats['failed_conversions'] += 1
                    self.conversion_stats['failed_files'].append(os.path.basename(file_path))
            else:
                # Remove incomplete CHD file on failure
                chd_file_path = file_path + '.chd'
                if os.path.exists(chd_file_path):
                    try:
                        os.remove(chd_file_path)
                        self.log_updated.emit(f'Removed incomplete file: {os.path.basename(chd_file_path)}')
                    except Exception as e:
                        self.log_updated.emit(f'Could not remove incomplete file: {e}')
                
                self.log_updated.emit(f'Error converting {file_path}: {stderr}')
                self.progress_text.emit(f"✗ Failed: {base_name}")
                self.conversion_stats['failed_conversions'] += 1
                self.conversion_stats['failed_files'].append(os.path.basename(file_path))
                
        except Exception as e:
            # Remove incomplete CHD file on exception
            chd_file_path = file_path + '.chd'
            if os.path.exists(chd_file_path):
                try:
                    os.remove(chd_file_path)
                    self.log_updated.emit(f'Removed incomplete file: {os.path.basename(chd_file_path)}')
                except Exception as cleanup_error:
                    self.log_updated.emit(f'Could not remove incomplete file: {cleanup_error}')
            
            self.log_updated.emit(f'Exception: {e}')
            self.progress_text.emit(f"✗ Error: {base_name}")
            self.conversion_stats['failed_conversions'] += 1
            self.conversion_stats['failed_files'].append(os.path.basename(file_path))
    
    def cleanup_temp_files_for_file(self, file_path):
        """Clean up temp files related to a specific file conversion"""
        try:
            # Look for any temp files that might have been created for this specific file
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # Check if there are any temp files with this base name
            for temp_dir in self.temp_dirs:
                if os.path.exists(temp_dir):
                    for root, dirs, files in os.walk(temp_dir):
                        for file in files:
                            if base_name in file:
                                try:
                                    file_path_to_remove = os.path.join(root, file)
                                    os.remove(file_path_to_remove)
                                except Exception:
                                    pass
        except Exception:
            pass  # Silently fail if cleanup fails
    
    def cleanup_temp_dirs(self):
        """Clean up temporary directories created during conversion"""
        cleaned_count = 0
        for d in self.temp_dirs:
            if temp_manager.cleanup_temp_dir(d):
                cleaned_count += 1
        self.temp_dirs = []
        return cleaned_count

class ScanWorker(QThread):
    scan_progress = pyqtSignal(str)
    scan_complete = pyqtSignal(list)
    scan_error = pyqtSignal(str)
    
    def __init__(self, input_paths):
        super().__init__()
        self.input_paths = input_paths if isinstance(input_paths, list) else [input_paths]
        
    def run(self):
        try:
            self.scan_progress.emit('Scanning for files...')
            found = []
            
            for input_path in self.input_paths:
                if os.path.isfile(input_path):
                    ext = os.path.splitext(input_path)[1].lower()
                    if ext in COMPATIBLE_EXTS:
                        found.append(input_path)
                        self.scan_progress.emit(f'Found: {os.path.basename(input_path)}')
                else:
                    for root, dirs, files in os.walk(input_path):
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

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class ValidationWorker(QThread):
    validation_complete = pyqtSignal(dict)
    validation_progress = pyqtSignal(str, dict)  # file_path, file_info
    
    def __init__(self, file_paths, max_workers=4, fast_validation=True):
        super().__init__()
        self.file_paths = file_paths
        self.max_workers = max_workers
        self.fast_validation = fast_validation
        self._lock = threading.Lock()
        
    def validate_single_file(self, file_path):
        """Validate a single file - used by thread pool"""
        try:
            file_info = get_file_info(file_path, self.fast_validation)
            return file_path, file_info
        except Exception as e:
            # If validation fails, create basic info
            file_info = {
                'name': os.path.basename(file_path),
                'path': file_path,
                'size': 0,
                'size_str': 'Unknown',
                'extension': os.path.splitext(file_path)[1].lower(),
                'is_valid': False,
                'validation_msg': f"Validation error: {str(e)}"
            }
            return file_path, file_info
        
    def run(self):
        """Validate files in parallel using thread pool"""
        validation_results = {}
        
        # Use ThreadPoolExecutor for parallel validation
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all validation tasks
            future_to_file = {executor.submit(self.validate_single_file, file_path): file_path 
                            for file_path in self.file_paths}
            
            # Process completed validations as they finish
            for future in as_completed(future_to_file):
                file_path, file_info = future.result()
                
                # Thread-safe update of results
                with self._lock:
                    validation_results[file_path] = file_info
                
                # Emit individual result as it completes
                self.validation_progress.emit(file_path, file_info)
        
        # Emit final complete signal with all results
        self.validation_complete.emit(validation_results)

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
        
        central_widget.setLayout(layout)
    
    def get_selection_type(self):
        return "file" if self.file_radio.isChecked() else "folder"

class CHDConverterGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('XtoCHD - Batch CHD Converter')
        self.setGeometry(100, 100, 1100, 700)
        self.temp_dirs = []
        self.found_files = []
        self.conversion_worker = None
        self.scan_worker = None
        
        # Theme management
        self.current_theme = 'dark'  # Default to dark theme
        
        self.init_ui()
        self.setup_menu_bar()
        self.apply_theme(self.current_theme)
        
        # Setup file system watcher for chdman.exe
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

    def setup_menu_bar(self):
        """Setup the menu bar with theme switching options"""
        menubar = self.menuBar()
        
        # View menu
        view_menu = menubar.addMenu('View')
        
        # Theme submenu
        theme_menu = view_menu.addMenu('Theme')
        
        # Light theme action
        light_action = QAction('Light Theme', self)
        light_action.setCheckable(True)
        light_action.setChecked(self.current_theme == 'light')
        light_action.triggered.connect(lambda: self.switch_theme('light'))
        theme_menu.addAction(light_action)
        
        # Dark theme action
        dark_action = QAction('Dark Theme', self)
        dark_action.setCheckable(True)
        dark_action.setChecked(self.current_theme == 'dark')
        dark_action.triggered.connect(lambda: self.switch_theme('dark'))
        theme_menu.addAction(dark_action)
        
        # Store actions for later use
        self.light_theme_action = light_action
        self.dark_theme_action = dark_action
        
        # Tools menu
        tools_menu = menubar.addMenu('Tools')
        
        # Temp directory management
        temp_info_action = QAction('Temp Directory Info', self)
        temp_info_action.triggered.connect(self.show_temp_directory_info)
        tools_menu.addAction(temp_info_action)
        
        cleanup_action = QAction('Clean Temp Directory', self)
        cleanup_action.triggered.connect(self.cleanup_temp_directory)
        tools_menu.addAction(cleanup_action)

    def switch_theme(self, theme):
        """Switch between light and dark themes"""
        if theme != self.current_theme:
            self.current_theme = theme
            self.apply_theme(theme)
            
            # Update menu checkmarks
            if hasattr(self, 'light_theme_action'):
                self.light_theme_action.setChecked(theme == 'light')
            if hasattr(self, 'dark_theme_action'):
                self.dark_theme_action.setChecked(theme == 'dark')

    def apply_theme(self, theme):
        """Apply the specified theme to the application"""
        if theme == 'dark':
            self.setStyleSheet(ThemeManager.get_dark_theme())
        else:
            self.setStyleSheet(ThemeManager.get_light_theme())
        
        # Update specific widget styles that need custom handling
        self.update_widget_styles_for_theme(theme)

    def update_widget_styles_for_theme(self, theme):
        """Update specific widget styles that need custom handling"""
        if theme == 'dark':
            # Update file info text background for dark theme
            if hasattr(self, 'file_info_text'):
                self.file_info_text.setStyleSheet("""
                    QTextEdit { 
                        background-color: #404040; 
                        border: 1px solid #555555; 
                        color: #e0e0e0;
                    }
                """)
        else:
            # Update file info text background for light theme
            if hasattr(self, 'file_info_text'):
                self.file_info_text.setStyleSheet("""
                    QTextEdit { 
                        background-color: #f0f0f0; 
                        border: 1px solid #ccc; 
                        color: #333333;
                    }
                """)

    def on_chdman_dir_changed(self, path):
        # Directory changed, re-check for chdman.exe
        self.auto_detect_chdman()
        self.update_start_button_state()
        # If chdman.exe is still not present, watch for the file directly
        import os
        chdman_file = os.path.join(self.app_dir, 'chdman.exe')
        if not os.path.isfile(chdman_file):
            if chdman_file not in self.fs_watcher.files():
                self.fs_watcher.addPath(chdman_file)
        else:
            # If found, stop watching the file directly
            if chdman_file in self.fs_watcher.files():
                self.fs_watcher.removePath(chdman_file)

    def on_chdman_file_changed(self, path):
        # chdman.exe file changed (created, deleted, or modified)
        self.auto_detect_chdman()
        self.update_start_button_state()
        # If chdman.exe is now present, stop watching the file
        import os
        if os.path.isfile(path):
            if path in self.fs_watcher.files():
                self.fs_watcher.removePath(path)

    def auto_detect_chdman(self):
        # Check if chdman.exe exists in the app directory or cwd
        import os
        chdman_in_app_dir = os.path.join(self.app_dir, 'chdman.exe')
        if os.path.isfile(chdman_in_app_dir):
            self.chdman_path = chdman_in_app_dir
            self.chdman_status_indicator.setText("✓ Found in application folder")
            self.chdman_status_indicator.setStyleSheet("font-weight: bold; color: green;")
        else:
            chdman_in_cwd = os.path.join(os.getcwd(), 'chdman.exe')
            if os.path.isfile(chdman_in_cwd):
                self.chdman_path = chdman_in_cwd
                self.chdman_status_indicator.setText("✓ Found in current directory")
                self.chdman_status_indicator.setStyleSheet("font-weight: bold; color: green;")
            else:
                self.chdman_path = None
                self.chdman_status_indicator.setText("✗ Not found - Please place chdman.exe in the same folder as XtoCHD")
                self.chdman_status_indicator.setStyleSheet("font-weight: bold; color: red;")

    def update_start_button_state(self):
        """Update start button enabled state based on chdman availability and other conditions"""
        if not hasattr(self, 'start_btn') or self.start_btn is None:
            return
        chdman_available = bool(hasattr(self, 'chdman_path') and self.chdman_path and os.path.isfile(self.chdman_path))
        files_available = bool(hasattr(self, 'found_files') and len(self.found_files) > 0)
        output_set = bool(hasattr(self, 'output_path_edit') and self.output_path_edit.text().strip() != "")
        self.start_btn.setEnabled(chdman_available and files_available and output_set)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # Check if the dropped item is a supported file or folder
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    # Always accept folders
                    event.acceptProposedAction()
                elif os.path.isfile(path):
                    # Only accept supported file types
                    ext = os.path.splitext(path)[1].lower()
                    if ext in COMPATIBLE_EXTS:
                        event.acceptProposedAction()
                    else:
                        # Reject unsupported files
                        event.ignore()
                else:
                    event.ignore()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if not paths:
            return
            
        # Handle multiple files/folders
        supported_paths = []
        unsupported_files = []
        
        for path in paths:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in COMPATIBLE_EXTS:
                    supported_paths.append(path)
                else:
                    unsupported_files.append(os.path.basename(path))
            elif os.path.isdir(path):
                supported_paths.append(path)
        
        # Show warning for unsupported files
        if unsupported_files:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, 'Unsupported File Types', 
                f'The following files have unsupported extensions:\n{", ".join(unsupported_files)}\n\n'
                f'Supported formats: {", ".join(sorted(COMPATIBLE_EXTS))}\n\n'
                f'Only supported files and folders will be processed.')
        
        # Process supported files/folders
        if supported_paths:
            # Use the first path for the input field display
            main_path = supported_paths[0]
            self.input_path_edit.setText(main_path)
            self.auto_suggest_output_folder(main_path)
            self.status_bar.showMessage('Scanning for files...')
            # Pass all supported paths to the scanner
            self.scan_for_files_auto(supported_paths)

    def init_ui(self):
        # Create central widget for QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
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

        # chdman status indicator
        chdman_layout = QHBoxLayout()
        self.chdman_status_label = QLabel('chdman.exe:')
        self.chdman_status_indicator = QLabel()
        self.chdman_status_indicator.setStyleSheet("font-weight: bold;")
        chdman_layout.addWidget(self.chdman_status_label)
        chdman_layout.addWidget(self.chdman_status_indicator)
        chdman_layout.addStretch()
        layout.addLayout(chdman_layout)

        # Conversion options
        options_layout = QHBoxLayout()
        self.fast_validation_cb = QCheckBox("Fast Validation Mode")
        self.fast_validation_cb.setChecked(True)  # Default enabled
        self.fast_validation_cb.setToolTip(
            "Fast Mode (Default):\n"
            "• ISO: Check file size only (2KB minimum)\n"
            "• ZIP: Check header signature only\n"
            "• CUE: Read 512 bytes instead of 1KB\n"
            "• 5-10x faster for large files\n\n"
            "Thorough Mode (Unchecked):\n"
            "• ISO: Full 32KB header validation\n"
            "• ZIP: Complete integrity test\n"
            "• CUE: Full 1KB structure analysis\n"
            "• Slower but more thorough validation\n\n"
            "Note: Changing this setting will automatically rescan all files."
        )
        self.fast_validation_cb.toggled.connect(self.on_validation_mode_changed)
        options_layout.addWidget(self.fast_validation_cb)
        options_layout.addStretch()
        layout.addLayout(options_layout)

        # File list section with label and buttons on same line
        file_list_header_layout = QHBoxLayout()
        file_list_label = QLabel('Files to Convert:')
        file_list_header_layout.addWidget(file_list_label)
        file_list_header_layout.addStretch()  # Push buttons to the right
        
        # Create Select All/None buttons
        self.select_all_btn = QPushButton('Select All')
        self.select_all_btn.setMinimumHeight(28)
        self.select_all_btn.clicked.connect(self.select_all_files)
        self.select_none_btn = QPushButton('Select None')
        self.select_none_btn.setMinimumHeight(28)
        self.select_none_btn.clicked.connect(self.select_none_files)
        
        file_list_header_layout.addWidget(self.select_all_btn)
        file_list_header_layout.addWidget(self.select_none_btn)
        layout.addLayout(file_list_header_layout)
        
        # File list with checkboxes and sizes
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.on_file_selection_changed)
        layout.addWidget(self.file_list)
        
        # File information panel
        self.file_info_label = QLabel('File Information:')
        self.file_info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.file_info_label)
        
        self.file_info_text = QTextEdit()
        self.file_info_text.setMaximumHeight(80)
        self.file_info_text.setReadOnly(True)
        self.file_info_text.setStyleSheet("QTextEdit { background-color: #f0f0f0; border: 1px solid #ccc; }")
        layout.addWidget(self.file_info_text)
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
        central_widget.setLayout(layout)

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
            'Compatible Files (*.cue *.bin *.iso *.img *.zip *.nrg *.gdi *.toc *.ccd *.vcd *.chd *.cdr *.hdi *.vhd *.vmdk *.dsk)', options=options)
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
        # Use ScanWorker (QThread) for safe background scanning
        if isinstance(input_paths, str):
            input_paths = [input_paths]
        
        # Validate all paths
        valid_paths = []
        for path in input_paths:
            if path and os.path.exists(path):
                valid_paths.append(path)
        
        if not valid_paths:
            self.status_bar.showMessage('Invalid input path(s).')
            return
            
        # Initialize found_files if it doesn't exist (don't clear existing files)
        if not hasattr(self, 'found_files'):
            self.found_files = []
        
        self.update_start_button_state()
        self.status_bar.showMessage('Scanning for files...')
        # If a previous scan_worker exists, clean up
        if hasattr(self, 'scan_worker') and self.scan_worker is not None:
            self.scan_worker.quit()
            self.scan_worker.wait()
        self.scan_worker = ScanWorker(valid_paths)
        self.scan_worker.scan_progress.connect(self.status_bar.showMessage)
        self.scan_worker.scan_complete.connect(self.scan_completed)
        self.scan_worker.scan_error.connect(self.scan_error)
        self.scan_worker.start()

    def scan_completed(self, found_files):
        # Append new files to existing list instead of replacing
        if not hasattr(self, 'found_files'):
            self.found_files = []
        
        # Track new files and duplicates
        new_files = []
        duplicate_files = []
        
        for file_path in found_files:
            if file_path not in self.found_files:
                # Check for duplicates by name and size
                file_name = os.path.basename(file_path)
                try:
                    file_size = os.path.getsize(file_path)
                except (OSError, IOError):
                    file_size = 0
                
                # Check for duplicates by base name (without extension)
                # This handles cases like game.iso, game.zip, game.cue containing same content
                file_base_name = os.path.splitext(file_name)[0]
                file_ext = os.path.splitext(file_name)[1].lower()
                is_duplicate = False
                should_replace_existing = False
                existing_file_to_remove = None
                
                # Define multi-file format relationships
                multi_file_formats = {
                    '.cue': ['.bin'],  # CUE files need BIN files
                    '.toc': ['.bin'],  # TOC files need BIN files
                    '.ccd': ['.img', '.sub']  # CCD files need IMG and SUB files
                }
                
                for existing_file in self.found_files:
                    try:
                        existing_name = os.path.basename(existing_file)
                        existing_base_name = os.path.splitext(existing_name)[0]
                        existing_ext = os.path.splitext(existing_name)[1].lower()
                        
                        # Check if base names match (regardless of size)
                        if existing_base_name == file_base_name:
                            
                            # Check if this is a multi-file format relationship
                            is_multi_file_relationship = False
                            
                            # Check if existing file needs the new file
                            if existing_ext in multi_file_formats:
                                if file_ext in multi_file_formats[existing_ext]:
                                    is_multi_file_relationship = True
                            
                            # Check if new file needs the existing file
                            if file_ext in multi_file_formats:
                                if existing_ext in multi_file_formats[file_ext]:
                                    is_multi_file_relationship = True
                            
                            # If it's a multi-file relationship, don't treat as duplicate
                            if is_multi_file_relationship:
                                continue
                            
                            # Format priority: prefer ISO > CUE > BIN > IMG > ZIP > others
                            format_priority = {
                                '.iso': 1, '.cue': 2, '.bin': 3, '.img': 4, 
                                '.zip': 5, '.nrg': 6, '.gdi': 7, '.toc': 8, 
                                '.ccd': 9, '.vcd': 10, '.chd': 11,
                                '.cdr': 12, '.hdi': 13, '.vhd': 14, '.vmdk': 15, '.dsk': 16
                            }
                            
                            existing_priority = format_priority.get(existing_ext, 999)
                            new_priority = format_priority.get(file_ext, 999)
                            
                            if new_priority < existing_priority:
                                # New file has higher priority, replace existing
                                should_replace_existing = True
                                existing_file_to_remove = existing_file
                                break
                            else:
                                # Existing file has higher or equal priority, skip new file
                                duplicate_files.append(file_name)
                                is_duplicate = True
                                break
                    except (OSError, IOError):
                        # Skip files that can't be accessed
                        continue
                
                # If we should replace an existing file, remove it first
                if should_replace_existing and existing_file_to_remove:
                    self.found_files.remove(existing_file_to_remove)
                    # Remove from file list UI
                    for i in range(self.file_list.count()):
                        item = self.file_list.item(i)
                        checkbox = self.file_list.itemWidget(item)
                        if checkbox.toolTip().startswith(f"Path: {existing_file_to_remove}"):
                            self.file_list.takeItem(i)
                            break
                
                if not is_duplicate:
                    self.found_files.append(file_path)
                    new_files.append(file_path)
        
        # Show immediate feedback about new files
        if new_files:
            # Initialize file_info_cache if it doesn't exist
            if not hasattr(self, 'file_info_cache'):
                self.file_info_cache = {}
            
            # Add new files to the list immediately
            for file_path in new_files:
                self.add_file_to_list(file_path)
            
            # Start validation for new files
            self.start_background_validation()
            
            status_msg = f'Scan complete: {len(new_files)} new file(s) found. Total: {len(self.found_files)} file(s). Ready to convert!'
            if duplicate_files:
                status_msg += f' Skipped {len(duplicate_files)} duplicate(s).'
            self.status_bar.showMessage(status_msg)
        elif duplicate_files:
            self.status_bar.showMessage(f'Scan complete: All files were duplicates. Skipped {len(duplicate_files)} file(s).')
        else:
            self.status_bar.showMessage('Scan complete: No new files found.')
        
        self.update_start_button_state()

    def scan_error(self, error_msg):
        self.status_bar.showMessage(error_msg)
        self.update_start_button_state()

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
        # Update start button state since output path changed
        self.update_start_button_state()

    def select_output(self):
        options = QFileDialog.Options()
        folder = QFileDialog.getExistingDirectory(self, 'Select Output Folder', '', options=options)
        if folder:
            self.output_path_edit.setText(folder)
            # Clear the auto-suggestion log since user manually selected
            self.log_area.append(f'Manually selected output folder: {folder}')
            # Update start button state since output path changed
            self.update_start_button_state()


    
    def populate_file_list(self):
        """Populate file list with basic info first, then validate in background"""
        # Initialize file_info_cache if it doesn't exist
        if not hasattr(self, 'file_info_cache'):
            self.file_info_cache = {}
        
        # Clear the list but preserve validation cache for existing files
        existing_cache = self.file_info_cache
        self.file_list.clear()
        
        # Keep existing validation results for files that are still in the list
        self.file_info_cache = {k: v for k, v in existing_cache.items() if k in self.found_files}
        
        # First pass: Show files with basic info (fast)
        for file_path in self.found_files:
            self.add_file_to_list(file_path)
        
        # Update status bar with basic info
        if len(self.found_files) > 0:
            validated_count = len([f for f in self.found_files if f in self.file_info_cache])
            if validated_count == len(self.found_files):
                status_msg = f"Files: {len(self.found_files)} | All files validated. Ready to convert!"
            else:
                status_msg = f"Files: {len(self.found_files)} | Validating files in background... (You can start conversion anytime)"
            self.status_bar.showMessage(status_msg)
        
        # Start background validation for new files only
        self.start_background_validation()
    
    def add_file_to_list(self, file_path):
        """Add a single file to the list with appropriate display"""
        try:
            item = QListWidgetItem()
            
            # Check if we already have validation info for this file
            if hasattr(self, 'file_info_cache') and file_path in self.file_info_cache:
                file_info = self.file_info_cache[file_path]
                # Use existing validation result
                if file_info['is_valid']:
                    status_icon = "✓"
                    display_text = f"{status_icon} {file_info['name']} ({file_info['size_str']})"
                    checkbox = QCheckBox(display_text)
                    checkbox.setStyleSheet("QCheckBox { color: green; }")
                else:
                    status_icon = "✗"
                    display_text = f"{status_icon} {file_info['name']} ({file_info['size_str']}) - {file_info['validation_msg']}"
                    checkbox = QCheckBox(display_text)
                    checkbox.setStyleSheet("QCheckBox { color: red; }")
                
                # Update tooltip with detailed information
                tooltip_text = f"Path: {file_info['path']}\n"
                tooltip_text += f"Size: {file_info['size_str']}\n"
                tooltip_text += f"Format: {file_info['extension']}\n"
                tooltip_text += f"Status: {file_info['validation_msg']}"
                checkbox.setToolTip(tooltip_text)
            else:
                # New file - show with loading indicator
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size >= 1024**3:
                        size_str = f"{file_size / (1024**3):.2f} GB"
                    elif file_size >= 1024**2:
                        size_str = f"{file_size / (1024**2):.2f} MB"
                    elif file_size >= 1024:
                        size_str = f"{file_size / 1024:.2f} KB"
                    else:
                        size_str = f"{file_size} bytes"
                except (OSError, IOError):
                    size_str = "Unknown size"
                
                display_text = f"⏳ {os.path.basename(file_path)} ({size_str})"
                checkbox = QCheckBox(display_text)
                checkbox.setToolTip(f"Path: {file_path}\nSize: {size_str}\nValidating...")
                checkbox.setStyleSheet("QCheckBox { color: gray; }")
            
            checkbox.setChecked(True)
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, checkbox)
        except Exception as e:
            # If there's any error adding the file to the list, log it but don't crash
            print(f"Error adding file {file_path} to list: {e}")
            # Add a basic entry to prevent crashes
            item = QListWidgetItem()
            checkbox = QCheckBox(f"Error: {os.path.basename(file_path)}")
            checkbox.setStyleSheet("QCheckBox { color: red; }")
            checkbox.setChecked(False)
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, checkbox)
    
    def start_background_validation(self):
        """Start background validation of files"""
        if hasattr(self, 'validation_worker') and self.validation_worker is not None:
            self.validation_worker.quit()
            self.validation_worker.wait()
        
        # Initialize file_info_cache if it doesn't exist
        if not hasattr(self, 'file_info_cache'):
            self.file_info_cache = {}
        
        # Only validate files that haven't been validated yet
        unvalidated_files = []
        for file_path in self.found_files:
            if file_path not in self.file_info_cache:
                unvalidated_files.append(file_path)
        
        if not unvalidated_files:
            # All files already validated, just update the final summary
            self.update_file_validation({})
            return
        
        # Determine optimal number of workers based on file count and system capabilities
        import os
        cpu_count = os.cpu_count() or 4
        file_count = len(unvalidated_files)
        
        # Use fewer workers for small file counts, more for larger counts
        # But cap at CPU count to avoid overwhelming the system
        if file_count <= 4:
            max_workers = min(2, cpu_count)
        elif file_count <= 10:
            max_workers = min(4, cpu_count)
        else:
            max_workers = min(6, cpu_count)
        
        # Get the current fast validation setting
        fast_validation = self.fast_validation_cb.isChecked()
        self.validation_worker = ValidationWorker(unvalidated_files, max_workers=max_workers, fast_validation=fast_validation)
        self.validation_worker.validation_progress.connect(self.update_single_file_validation)
        self.validation_worker.validation_complete.connect(self.update_file_validation)
        self.validation_worker.start()
    
    def update_single_file_validation(self, file_path, file_info):
        """Update a single file's validation status as it completes"""
        # Find the file in the list
        try:
            file_index = self.found_files.index(file_path)
            if file_index < self.file_list.count():
                item = self.file_list.item(file_index)
                checkbox = self.file_list.itemWidget(item)
                
                # Update display text with validation status
                if file_info['is_valid']:
                    status_icon = "✓"
                    checkbox.setStyleSheet("QCheckBox { color: green; }")
                else:
                    status_icon = "✗"
                    checkbox.setStyleSheet("QCheckBox { color: red; }")
                
                # Format display text
                display_text = f"{status_icon} {file_info['name']} ({file_info['size_str']})"
                if not file_info['is_valid']:
                    display_text += f" - {file_info['validation_msg']}"
                
                checkbox.setText(display_text)
                
                # Update tooltip with detailed information
                tooltip_text = f"Path: {file_info['path']}\n"
                tooltip_text += f"Size: {file_info['size_str']}\n"
                tooltip_text += f"Format: {file_info['extension']}\n"
                tooltip_text += f"Status: {file_info['validation_msg']}"
                checkbox.setToolTip(tooltip_text)
                
                # Store in cache
                if not hasattr(self, 'file_info_cache'):
                    self.file_info_cache = {}
                self.file_info_cache[file_path] = file_info
                
                # Update status bar with progress
                validated_count = len(self.file_info_cache)
                total_count = len(self.found_files)
                status_msg = f"Validating files... ({validated_count}/{total_count} completed)"
                self.status_bar.showMessage(status_msg)
        except ValueError:
            # File not found in list (shouldn't happen, but safety check)
            pass

    def update_file_validation(self, validation_results):
        """Update file list with validation results (final summary)"""
        # Calculate final statistics from cached results
        total_size = 0
        valid_files = 0
        invalid_files = 0
        
        for file_info in self.file_info_cache.values():
            if file_info['is_valid']:
                valid_files += 1
                total_size += file_info['size']
            else:
                invalid_files += 1
        
        # Update status bar with final summary
        if len(self.found_files) > 0:
            total_size_str = ""
            if total_size >= 1024**3:
                total_size_str = f"{total_size / (1024**3):.2f} GB"
            elif total_size >= 1024**2:
                total_size_str = f"{total_size / (1024**2):.2f} MB"
            elif total_size >= 1024:
                total_size_str = f"{total_size / 1024:.2f} KB"
            else:
                total_size_str = f"{total_size} bytes"
            
            status_msg = f"Files: {len(self.found_files)} | Valid: {valid_files} | Invalid: {invalid_files} | Total Size: {total_size_str}"
            self.status_bar.showMessage(status_msg)
        
        # Store validation results for later use (already done in update_single_file_validation)
        self.file_info_cache = validation_results
    
    def on_file_selection_changed(self):
        """Update file information panel when selection changes"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            self.file_info_text.clear()
            return
        
        # Get the first selected item
        item = selected_items[0]
        item_index = self.file_list.row(item)
        
        if item_index < len(self.found_files):
            file_path = self.found_files[item_index]
            
            # Use cached validation results if available
            if hasattr(self, 'file_info_cache') and file_path in self.file_info_cache:
                file_info = self.file_info_cache[file_path]
            else:
                # Fallback to direct validation if cache not available
                file_info = get_file_info(file_path)
            
            # Create detailed information text
            info_text = f"File: {file_info['name']}\n"
            info_text += f"Path: {file_info['path']}\n"
            info_text += f"Size: {file_info['size_str']}\n"
            info_text += f"Format: {file_info['extension']}\n"
            info_text += f"Status: {file_info['validation_msg']}"
            
            # Color code the text based on validation status and current theme
            if self.current_theme == 'dark':
                if file_info['is_valid']:
                    self.file_info_text.setStyleSheet("QTextEdit { background-color: #1b5e20; border: 1px solid #4caf50; color: #e0e0e0; }")
                else:
                    self.file_info_text.setStyleSheet("QTextEdit { background-color: #b71c1c; border: 1px solid #f44336; color: #e0e0e0; }")
            else:
                if file_info['is_valid']:
                    self.file_info_text.setStyleSheet("QTextEdit { background-color: #e8f5e8; border: 1px solid #4caf50; color: #333333; }")
                else:
                    self.file_info_text.setStyleSheet("QTextEdit { background-color: #ffe8e8; border: 1px solid #f44336; color: #333333; }")
            
            self.file_info_text.setText(info_text)

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
        invalid_selected = []
        unvalidated_selected = []
        
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            if checkbox.isChecked():
                file_path = self.found_files[i]
                
                # Check if validation is complete for this file
                if hasattr(self, 'file_info_cache') and file_path in self.file_info_cache:
                    file_info = self.file_info_cache[file_path]
                    if file_info['is_valid']:
                        selected_files.append(file_path)
                    else:
                        invalid_selected.append(file_info['name'])
                else:
                    # File hasn't been validated yet - include it but warn user
                    selected_files.append(file_path)
                    unvalidated_selected.append(os.path.basename(file_path))
        
        # Warn about unvalidated files
        if unvalidated_selected:
            warning_msg = f"Note: {len(unvalidated_selected)} file(s) haven't been validated yet and will be converted anyway: {', '.join(unvalidated_selected)}"
            self.log_area.append(warning_msg)
        
        # Warn about invalid files that were selected
        if invalid_selected:
            warning_msg = f"Warning: {len(invalid_selected)} invalid file(s) were selected and will be skipped: {', '.join(invalid_selected)}"
            self.log_area.append(warning_msg)
        
        return selected_files

    def start_conversion(self):
        selected_files = self.get_selected_files()
        if not selected_files:
            self.log_area.append('No files selected for conversion.')
            return
            
        output_path = self.output_path_edit.text().strip()
        
        if not output_path:
            self.log_area.append('Please select an output folder.')
            return
        if not hasattr(self, 'chdman_path') or not self.chdman_path or not os.path.isfile(self.chdman_path):
            self.log_area.append('chdman.exe not found. Please place chdman.exe in the same folder as XtoCHD.')
            return

        # Check temp directory before starting conversion
        self.check_temp_directory_before_conversion()

        # Disable all UI elements during conversion
        self.disable_ui_during_conversion()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage('Starting conversion...')
        
        # Start conversion in separate thread
        self.conversion_worker = ConversionWorker(selected_files, output_path, self.chdman_path)
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
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.file_list.setEnabled(False)
        self.fast_validation_cb.setEnabled(False)

    def enable_ui_after_conversion(self):
        """Re-enable all UI elements after conversion"""
        self.add_file_btn.setEnabled(True)
        self.add_folder_btn.setEnabled(True)
        self.output_btn.setEnabled(True)
        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.update_start_button_state()
        self.stop_btn.setEnabled(False)
        self.file_list.setEnabled(True)
        self.fast_validation_cb.setEnabled(True)

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
            if temp_manager.cleanup_temp_dir(d):
                cleaned_count += 1
        self.temp_dirs = []
        if cleaned_count > 0:
            self.log_area.append(f'Cleaned up {cleaned_count} temporary directories.')

    def on_validation_mode_changed(self):
        """Handle validation mode toggle - trigger rescan"""
        if hasattr(self, 'found_files') and self.found_files:
            # Show prominent notification in log area
            mode_text = "Fast" if self.fast_validation_cb.isChecked() else "Thorough"
            self.log_area_append(f"🔄 Validation mode changed to {mode_text} mode. Rescanning files...")
            self.status_bar.showMessage(f'Validation mode changed to {mode_text} mode. Rescanning files...')
            self.scan_for_files_auto(self.input_path_edit.text().strip())
    
    def perform_startup_cleanup(self):
        """Perform cleanup of orphaned temp files on startup"""
        try:
            # Clean up orphaned temp directories
            cleaned_count = temp_manager.cleanup_orphaned_temp_dirs()
            
            # Get current temp directory size
            temp_size = temp_manager.get_temp_dir_size()
            
            if cleaned_count > 0:
                self.log_area.append(f'🧹 Startup cleanup: Removed {cleaned_count} orphaned temporary directories.')
            
            if temp_size > 0:
                size_str = temp_manager.format_size(temp_size)
                self.log_area.append(f'📁 Temp directory size: {size_str}')
            
            # Log temp directory location
            self.log_area.append(f'📂 Temp directory: {temp_manager.temp_base_dir}')
            
        except Exception as e:
            self.log_area.append(f'⚠️ Warning: Could not perform startup cleanup: {e}')
    
    def get_temp_directory_info(self):
        """Get information about the temp directory"""
        try:
            temp_size = temp_manager.get_temp_dir_size()
            size_str = temp_manager.format_size(temp_size)
            return f"Temp directory: {temp_manager.temp_base_dir}\nSize: {size_str}"
        except Exception as e:
            return f"Temp directory: {temp_manager.temp_base_dir}\nSize: Unknown (error: {e})"
    
    def check_temp_directory_before_conversion(self):
        """Check temp directory status before starting conversion"""
        try:
            temp_size = temp_manager.get_temp_dir_size()
            size_mb = temp_size / (1024 * 1024)
            
            if size_mb > 100:  # Warn if temp directory is larger than 100MB
                size_str = temp_manager.format_size(temp_size)
                self.log_area.append(f'⚠️ Warning: Temp directory is {size_str}. Consider cleaning up.')
            
            # Log current temp directory status
            size_str = temp_manager.format_size(temp_size)
            self.log_area.append(f'📁 Temp directory status: {size_str}')
            
        except Exception as e:
            self.log_area.append(f'⚠️ Warning: Could not check temp directory: {e}')
    
    def show_temp_directory_info(self):
        """Show information about the temp directory"""
        from PyQt5.QtWidgets import QMessageBox
        
        info = self.get_temp_directory_info()
        QMessageBox.information(self, 'Temp Directory Info', info)
    
    def cleanup_temp_directory(self):
        """Manually clean up the temp directory"""
        try:
            cleaned_count = temp_manager.cleanup_orphaned_temp_dirs()
            if cleaned_count > 0:
                self.log_area.append(f'🧹 Manual cleanup: Removed {cleaned_count} temporary directories.')
            else:
                self.log_area.append('🧹 Manual cleanup: No temporary directories to clean up.')
            
            # Update temp directory info
            temp_size = temp_manager.get_temp_dir_size()
            size_str = temp_manager.format_size(temp_size)
            self.log_area.append(f'📁 Current temp directory size: {size_str}')
            
        except Exception as e:
            self.log_area.append(f'⚠️ Error during manual cleanup: {e}')
    
    def log_area_append(self, text):
        self.log_area.append(text)
        self.log_area.moveCursor(self.log_area.textCursor().End)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = CHDConverterGUI()
    window.show()
    sys.exit(app.exec_()) 