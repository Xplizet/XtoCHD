# Changelog

All notable changes to XtoCHD will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Advanced file management features (naming schemes, organization, system/region detection, etc.) have been removed for now due to reliability concerns. I may revisit these features in a future version.
- Support for all chdman-compatible formats: .cue, .bin, .iso, .img, .nrg, .gdi, .toc, .ccd, .m3u, .vcd, .chd, .zip, .cdr, .hdi, .vhd, .vmdk, .dsk (with .flac and .wav supported only as part of a .cue set, not as standalone input)
- File/folder scanning is now done in a background thread with proper Qt signals/slots, preventing crashes when selecting files or folders.
- All UI updates from scanning are now safely performed in the main thread.
- Drag-and-drop support for adding files or folders as input.
- Log area now auto-scrolls to show the latest message.
- 'Open Output Folder' button opens the output folder in your file manager.
- File picker defaults to supported formats but allows 'All Files' as an option.
- File sizes are now displayed in the 'Files to Convert' list.

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
- **Unreleased**: Advanced file management system (current development)

## Contributing

When adding new features or making changes, please update this changelog by adding entries under the [Unreleased] section following the format above. 