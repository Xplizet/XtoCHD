# XtoCHD

A simple GUI application to convert disk images to CHD format using chdman.

![XtoCHD Screenshot](screenshot.png)

## What is XtoCHD?

XtoCHD helps you convert various disk image formats (like .cue, .bin, .iso, .img, .zip) to .CHD format. This is useful for retro gaming and emulation.

## Download

### For End Users (No Installation Required)
1. Download the latest release from the [Releases](https://github.com/yourusername/XtoCHD/releases) page
2. Extract the ZIP file
3. Download `chdman.exe` from the [MAME project](https://www.mamedev.org/) and place it in the same folder as `XtoCHD.exe`
4. Double-click `XtoCHD.exe` to run

### For Developers
1. Clone this repository
2. Install Python 3.7+
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main.py`

## How to Use

1. **Select Input**: Choose a file or folder containing disk images
2. **Select Output**: Pick where to save the converted .CHD files
3. **Set chdman Path**: The app will auto-detect `chdman.exe` if it's in the same folder, or you can manually browse to it
4. **Scan Files**: Click "Scan for Files" to find compatible images
5. **Select Files**: Check/uncheck which files to convert
6. **Start Conversion**: Click "Start Conversion" and wait

## Supported Formats

- **Input**: .cue, .bin, .iso, .img, .zip
- **Output**: .CHD

## Requirements

- Windows 10/11
- chdman.exe (from MAME project) - will be auto-detected if in the same folder
- No Python installation needed for the executable

## Building from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Build executable
python build_exe.py
```

## Credits

This application relies on **chdman** from the [MAME project](https://www.mamedev.org/). Special thanks to the MAME development team for creating and maintaining this essential tool.

- **chdman**: Part of the MAME project - [GitHub](https://github.com/mamedev/mame)
- **MAME**: Multiple Arcade Machine Emulator

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

If you encounter issues:
1. Make sure you have `chdman.exe` (download from MAME project)
2. Ensure your input files are valid
3. Create an issue on GitHub with details 