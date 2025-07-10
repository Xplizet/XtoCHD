# What's New in v2.6.1

## Temp Directory Fix
- **Fixed temp directory location** for compiled executables
- **Cross-platform compatibility** between Python script and .exe execution
- **Consistent behavior** regardless of how the application is run
- **Proper app directory detection** using `sys.executable` for bundled executables

## What Was Fixed
- **Python script vs .exe inconsistency**: Temp directory now created in the same location for both execution methods
- **PyInstaller compatibility**: Fixed `__file__` behavior differences in bundled executables
- **Application folder detection**: Updated to use the correct directory path for both execution modes

## Technical Details
- **App directory detection**: Uses `sys.executable` for bundled executables, `__file__` for scripts
- **Consistent temp location**: Temp directory always created in the application folder
- **No user impact**: Existing functionality remains the same, just more reliable

## Installation
- Extract the ZIP file and run XtoCHD.exe
- chdman.exe is included in the release
- Temp directory is automatically created in the application folder

## Usage
- **No changes required**: All existing functionality works the same
- **More reliable**: Temp directory creation now works consistently
- **Better compatibility**: Works correctly with both Python and compiled versions

## Documentation
- 📋 [Full Changelog](CHANGELOG.md)
- 📖 [README](README.md)

---

Thank you for using XtoCHD! 