# Changelog

All notable changes to XtoCHD will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<<<<<<< HEAD
## [v2.6.0] - 2025-07-09

### Added
- **Comprehensive Temp File Management System**
  - Dedicated temp directory within app folder (`[XtoCHD_directory]/temp/`)
  - Crash-proof cleanup using `atexit` handler for application exit
  - Startup cleanup of orphaned temp files (removes directories older than 1 hour)
  - Per-file cleanup after each individual CHD conversion
  - Age-based cleanup with configurable thresholds
  - Process ID tracking in temp directory names for uniqueness
  - Automatic fallback to system temp directory if dedicated temp fails

- **Enhanced Temp File Monitoring**
  - Real-time temp directory size monitoring with warnings for large directories (>100MB)
  - Temp directory size and location display in logs
  - Manual cleanup options via new Tools menu
  - "Temp Directory Info" shows location and current size
  - "Clean Temp Directory" for manual cleanup operations
  - Enhanced logging with emojis for better visibility (🧹, 📁, 📂, ⚠️)

- **Tools Menu**
  - New Tools menu in menu bar with temp directory management options
  - "Temp Directory Info" displays temp directory location and size
  - "Clean Temp Directory" performs manual cleanup of orphaned files

### Changed
- **Temp File Location**: All temp files now stored in dedicated `temp/` directory within app folder
- **Cleanup Strategy**: Immediate per-file cleanup instead of batch cleanup at end
- **Error Handling**: Graceful degradation with fallback to system temp directory
- **User Feedback**: Enhanced logging with clear status messages and warnings
- **Startup Process**: Added temp directory cleanup and status reporting on startup

### Technical
- **TempFileManager Class**: Centralized temp file management with comprehensive error handling
- **atexit Integration**: Automatic cleanup registration for crash-proof operation
- **Directory Naming**: Timestamp and process ID based naming for uniqueness
- **Size Monitoring**: Efficient temp directory size calculation and formatting
- **Orphaned File Detection**: Age-based cleanup of old temp directories

## [v2.5.0] - 2025-01-XX
=======
## [v2.5.0] - 2025-07-09
>>>>>>> 892504ed2ee2979a51cbe4d0f80fd607d618cdda

### Added
- **Fast Validation Mode**
  - New toggle for switching between fast and thorough file validation
  - Fast mode provides 5-10x faster validation for large files
  - ISO files: Only check file size (2KB minimum) instead of 32KB header reads
  - ZIP files: Only check header signature instead of full integrity test
  - CUE files: Read 512 bytes instead of 1KB
  - Default enabled for optimal performance
  - Toggle triggers automatic file rescan with new validation mode
  - Enhanced tooltip with detailed explanation of validation modes
  - Clear user notification when validation mode changes

### Removed
- **M3U Playlist Support**: Removed all M3U playlist handling functionality to simplify the codebase and focus on core CHD conversion features.

### Changed
- Simplified file validation with performance-optimized default mode
- Streamlined UI by removing M3U playlist processing options
- Enhanced user feedback with validation mode change notifications
- Improved validation worker threading for better performance

## [v2.4.0] - 2025-07-05

### Added
- **Dark Mode Theme**: Complete dark theme with modern styling
- **Theme Switching**: Menu bar option to switch between light and dark themes
- **Theme-Aware UI**: All UI elements adapt to the selected theme
- **Persistent Theme**: Theme selection is maintained during the session

## [v2.3.1] - 2025-07-05

### Fixed
- Fixed duplicate detection to properly handle multi-file formats (CUE+BIN, TOC+BIN, CCD+IMG+SUB)
- Fixed issue where CUE and BIN files with same base name were incorrectly treated as duplicates
- Enhanced smart duplicate detection to distinguish between true duplicates and required multi-file relationships

## [v2.3.0] - 2025-07-05

### Added
- **File Preview & Validation**
  - Real-time file validation with format-specific checks
  - Progressive validation updates - each file updates as soon as validation completes
  - Visual validation status indicators (green checkmarks, red X's, loading spinners)
  - Detailed file information panel showing format, size, and validation details
  - Background validation that doesn't block UI responsiveness
  - Smart tooltips with validation results and error details
  - Automatic exclusion of invalid files from conversion
  - Warning system for unvalidated files during conversion
  - Support for validating ISO, CUE, BIN, IMG, and ZIP formats
  - Asynchronous validation worker thread for smooth UI experience
  - File picker restricted to supported formats only
  - Drag-and-drop validation - only accepts supported files and folders
  - Multi-file drag-and-drop support - scan all dropped files and folders
  - Incremental file addition - new files are added to existing list instead of replacing
  - Immediate file display - new files appear in list instantly, not waiting for validation
  - Smart validation caching - only validates new files, preserves existing validation results
  - Smart duplicate detection - prevents adding files with same base name (regardless of size)
  - Clear error messages when attempting to add unsupported files
  - Proper file management - CHD files are moved to output directory after conversion
  - Automatic cleanup - incomplete files are removed on conversion failure
  - Existing CHD file detection - skips conversion if CHD already exists in output directory
  - Smart duplicate detection - handles multiple formats of same content with format priority (ISO > CUE > BIN > IMG > ZIP > others)

- **Simplified chdman Integration**
  - Removed manual chdman.exe selection - now automatically detected
  - Status indicator shows chdman.exe location (application folder or current directory)
  - Clear error message if chdman.exe is missing with instructions to place in same folder as XtoCHD
  - Streamlined UI with fewer configuration options

- **Automatic chdman Detection**
  - Real-time file system monitoring for chdman.exe presence
  - Automatic UI updates when chdman.exe is added or removed
  - No restart required - detection works while application is running
  - Smart start button that enables/disables based on chdman availability

### Changed
- File list now shows validation status immediately with progressive updates
- Conversion process now warns about invalid/unvalidated files
- Enhanced user feedback with color-coded status indicators
- Improved file selection workflow with validation awareness
- Select All/None buttons moved to right side of "Files to Convert:" label
- Start button automatically enables/disables based on chdman availability, file presence, and output path

### Fixed
- Fixed TypeError when start button was accessed before UI initialization
- Fixed issue where adding new files would clear the existing file list
- Fixed crashes when file_info_cache wasn't initialized before use
- Fixed issue where converted CHD files weren't moved to the specified output folder
- Fixed missing check for existing CHD files to prevent unnecessary re-conversion
- Fixed issue where unsupported files caused the program to do nothing instead of showing clear error messages
- Fixed drag-and-drop to handle multiple files/folders instead of just one at a time

### Technical
- Added ValidationWorker thread for background file validation
- Implemented parallel validation using ThreadPoolExecutor for faster processing
- Dynamic worker count based on file count and system CPU cores
- Implemented format-specific validation functions
- Enhanced UI responsiveness during file scanning and validation
- Added comprehensive error handling for validation failures
- Added QFileSystemWatcher for automatic chdman.exe detection
- Improved start button state management with centralized update logic

## [v2.2.0] - 2024-07-05

### Added
- **Enhanced Format Support**
  - Support for all chdman-compatible formats: .cue, .bin, .iso, .img, .nrg, .gdi, .toc, .ccd, .vcd, .chd, .zip, .cdr, .hdi, .vhd, .vmdk, .dsk
  - Note: .flac and .wav files supported only as part of a .cue set, not as standalone input

- **Improved User Experience**
  - Drag-and-drop support for adding files or folders as input
  - Log area now auto-scrolls to show the latest message
  - 'Open Output Folder' button opens the output folder in your file manager
  - File picker defaults to supported formats but allows 'All Files' as an option
  - File sizes are now displayed in the 'Files to Convert' list

### Changed
- File/folder scanning is now done in a background thread with proper Qt signals/slots, preventing crashes when selecting files or folders
- All UI updates from scanning are now safely performed in the main thread

### Technical
- Enhanced thread safety with proper Qt signal/slot implementation
- Improved UI responsiveness during file scanning operations
- Better error handling for file selection operations

## [v2.1.0] - 2025-07-04

### Added
- **Simplified Setup**
  - Included chdman.exe in distribution for one-click setup
  - No manual download and placement required
  - Zero-configuration installation process

### Changed
- Updated build scripts to automatically include chdman.exe
- Enhanced build_exe.py to copy chdman.exe to dist folder
- Updated build.bat with chdman.exe detection and copying
- Simplified installation instructions in README
- Removed manual chdman.exe download steps from documentation

### Technical
- Modified build_exe.py to copy chdman.exe if present
- Enhanced build.bat with chdman.exe copying functionality
- Updated documentation to reflect simplified setup process

## [v2.0.0] - 2025-07-04

### Added
- **Comprehensive Conversion Summary**
  - Detailed statistics with success/failure/skip counts
  - File size analysis (original vs compressed)
  - Space savings and compression ratio reporting
  - Complete lists of successful, failed, and skipped files

- **Smart Duplicate Detection**
  - Automatic format prioritization (CUE > ISO > BIN > IMG)
  - Intelligent handling of multiple formats for same content
  - Skip existing CHD files automatically

- **Enhanced User Experience**
  - Stop conversion button with proper cleanup
  - Auto-suggest output folder as `[input]/CHD/`
  - Status bar for real-time progress messages
  - Better UI states during conversion (disable all buttons except stop)

- **Improved ZIP Support**
  - Smart extraction with existing file detection
  - Skip extraction if all files already have CHD versions
  - Enhanced progress tracking during ZIP processing

### Changed
- Complete UI/UX overhaul with better feedback and controls
- Enhanced progress tracking and status reporting
- Improved error handling and user feedback
- Better thread management and UI responsiveness

### Technical
- Refactored subprocess handling for improved reliability
- Added conversion statistics tracking
- Enhanced file processing with cancellation support
- Better temporary file cleanup
- Improved duplicate detection and removal logic

## [v1.0.0] - 2025-07-04

### Added
- **Core Functionality**
  - GUI application for converting disk images to CHD format
  - Support for .cue, .bin, .iso, .img, and .zip files
  - Batch processing of multiple files and folders
  - ZIP file extraction and conversion of contents

- **User Interface**
  - Clean, intuitive PyQt5-based GUI
  - File/folder selection with input type dialog
  - File list with checkboxes for selective conversion
  - Progress bar and detailed status messages
  - Comprehensive log area for conversion feedback

- **Technical Features**
  - Multi-threaded conversion to keep UI responsive
  - Hidden CMD windows during chdman execution
  - Automatic temporary directory cleanup
  - Error handling and user feedback
  - Cross-platform Python implementation

- **File Handling**
  - Recursive directory scanning for compatible files
  - ZIP archive extraction and processing
  - Support for all major disk image formats
  - Automatic output directory creation
  - Proper file path handling

- **User Experience**
  - Auto-suggestion of chdman.exe location
  - Clear progress indication during conversion
  - Detailed logging of all operations
  - Simple, straightforward workflow
  - Professional application appearance

---

## Version History

- **v1.0.0**: Initial release with basic functionality
- **v2.0.0**: Major feature update with statistics, smart detection, stop button, etc.
- **v2.1.0**: Setup simplification with chdman.exe inclusion
- **v2.2.0**: UI and stability improvements, background scanning, drag-and-drop, and more
- **v2.3.0**: File preview & validation system with enhanced UX and automatic chdman detection
- **v2.3.1**: Bug fix for multi-file format handling (CUE+BIN, TOC+BIN, etc.)
- **v2.4.0**: Dark mode theme with theme switching and improved user experience

## Contributing

When adding new features or making changes, please update this changelog by adding entries under the [Unreleased] section following the format above. 
