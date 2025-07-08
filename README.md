# XtoCHD

A powerful GUI application to convert disk images to CHD format using chdman with advanced features and comprehensive statistics.

![XtoCHD Screenshot](screenshot.png)

## What is XtoCHD?

XtoCHD helps you convert various disk image formats (like .cue, .bin, .iso, .img, .zip) to .CHD format. This is useful for retro gaming and emulation. The application provides a user-friendly interface with advanced features for batch processing and detailed conversion reporting.

## Download

### For End Users (No Installation Required)
1. Download the latest release ZIP file from the [Releases](https://github.com/Xplizet/XtoCHD/releases) page
2. Extract the ZIP file to any folder
3. Double-click `XtoCHD.exe` to run (chdman.exe is included in the release)

### For Developers
1. Clone this repository
2. Install Python 3.7+
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py`

## Windows Defender False Positive

**⚠️ Important**: Some antivirus software, including Windows Defender, may flag XtoCHD as a potential threat. This is a **false positive**.

### Why This Happens
- **Heuristic Detection**: Antivirus software uses machine learning to detect patterns that might indicate threats
- **File Operations**: XtoCHD performs many file operations (reading, writing, extracting ZIPs) which can trigger security heuristics
- **Subprocess Calls**: The app calls external programs (`chdman.exe`) which can look suspicious to antivirus software
- **Python Packaging**: Compiled Python applications often trigger false positives

### This is NOT a Virus
XtoCHD is **completely safe**:
- ✅ **Open Source**: Code is publicly available on GitHub
- ✅ **No Network Activity**: App doesn't connect to the internet
- ✅ **Local Only**: All operations performed on your local files
- ✅ **No Data Collection**: App doesn't send any data anywhere
- ✅ **File Operations Only**: Only reads/writes files you specify

### How to Handle This

#### Option 1: Add Exception (Recommended)
1. Open Windows Security
2. Go to "Virus & threat protection"
3. Click "Manage settings" under "Virus & threat protection settings"
4. Scroll down to "Exclusions"
5. Add the XtoCHD folder as an exclusion

#### Option 2: Run from Source
If you're concerned, run the Python source directly:
```bash
python main.py
```

### Why This is Common
Many legitimate software tools get false positives:
- **7-Zip** (file compression)
- **AutoHotkey** (automation)
- **Python applications** (especially when packaged)
- **Game modding tools**
- **File conversion utilities**

The application is completely safe to use. This is a known issue with antivirus software and Python applications.

## How to Use

1. **Select Input**: Choose a file or folder containing disk images, or drag and drop files/folders directly onto the application
2. **Select Output**: Pick where to save the converted .CHD files (auto-suggests `[input]/CHD/`)
3. **Set chdman Path**: The app will auto-detect `chdman.exe` if it's in the same folder, or you can manually browse to it
4. **Configure Validation**: Use the "Fast Validation Mode" toggle to choose between fast (5-10x faster) or thorough validation
5. **Scan Files**: Files are automatically scanned when you select input (scanning runs in background for better responsiveness)
6. **Review Validation**: Check file validation status with visual indicators (✓ for valid, ✗ for invalid)
7. **Select Files**: Check/uncheck which files to convert (file sizes are displayed for reference)
8. **Start Conversion**: Click "Start Conversion" and monitor progress
9. **Stop if Needed**: Use the "Stop Conversion" button to cancel at any time
10. **Review Results**: Check the comprehensive conversion summary at the end
11. **View Output**: Use the "Open Output Folder" button to quickly access your converted files

## Supported Formats

- **Input**: .cue, .bin, .iso, .img, .nrg, .gdi, .toc, .ccd, .vcd, .chd, .zip, .cdr, .hdi, .vhd, .vmdk, .dsk
- **Output**: .CHD

## Requirements

- Windows 10/11
- No Python installation needed for the executable
- chdman.exe is included in the release (from MAME project)

## Features

### 🎯 Smart Processing
- **Format Prioritization**: Automatically selects the best format when duplicates exist
- **Existing File Detection**: Skips files that already have CHD versions
- **Batch Processing**: Convert multiple files or entire folders at once
- **ZIP Support**: Extract and convert files from ZIP archives

### 📈 Comprehensive Reporting
- **Success Rate**: Shows percentage of successful conversions
- **Size Analysis**: Original vs compressed file sizes
- **Space Savings**: Total space saved and compression ratios
- **Detailed Lists**: Complete breakdown of all processed files

### 🎮 User-Friendly Interface
- **Real-time Progress**: Live status updates and progress tracking
- **Intuitive Controls**: Easy-to-use interface with clear feedback
- **Error Handling**: Clear error messages and recovery options
- **Responsive Design**: UI remains responsive during long conversions
- **Drag & Drop**: Support for dragging files and folders directly onto the application
- **Background Scanning**: File scanning runs in background threads for better responsiveness
- **Theme Support**: Light and dark themes with automatic UI adaptation
- **File Validation**: Real-time file validation with visual status indicators
- **Fast Validation Mode**: Toggle between fast (5-10x faster) and thorough validation

### 🔧 Advanced Features
- **Stop Conversion**: Cancel running conversions with proper cleanup
- **Auto-suggest Output**: Automatically suggests output folder location
- **Smart Duplicate Detection**: Handles multiple formats of the same content
- **Enhanced ZIP Support**: Smart extraction with existing file detection
- **File Size Display**: Shows file sizes in the conversion list
- **Open Output Folder**: Quick access to view converted files
- **Auto-scrolling Log**: Log area automatically scrolls to show latest messages
- **File Information Panel**: Detailed file information with validation status
- **Validation Mode Toggle**: Switch between fast and thorough file validation
- **Automatic chdman Detection**: Real-time detection of chdman.exe presence

## Building from Source

### For Developers
```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Building Executable
```bash
# Install dependencies
pip install -r requirements.txt

# Build executable
python build_exe.py
```

### Windows Users
Simply double-click `build.bat` to build the executable automatically.

The executable will be created in the `dist/` folder as `XtoCHD.exe`.

**Note**: The build process will include chdman.exe in the distribution.

## Credits

This application relies on **chdman** from the [MAME project](https://www.mamedev.org/). Special thanks to the MAME development team for creating and maintaining this essential tool.

- **chdman**: Part of the MAME project - [GitHub](https://github.com/mamedev/mame)
- **MAME**: Multiple Arcade Machine Emulator

**Note**: chdman.exe is included in this distribution for user convenience. It is free software from the MAME project and is used in accordance with their license terms.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

If you encounter issues:
1. Ensure your input files are valid
2. Check the conversion summary for detailed error information
3. Create an issue on GitHub with details 