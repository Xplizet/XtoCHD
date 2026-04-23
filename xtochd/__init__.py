"""XtoCHD - batch CHD converter.

Modules:
    constants     - file-extension sets and disk-format priorities
    stats         - ConversionStats dataclass
    temp_manager  - crash-proof temp-directory management
    theme         - light/dark Qt stylesheets
    validators    - disc-image validation and conversion-candidate filtering
    archive       - helpers for .zip/.rar/.7z extraction
    workers       - QThread subclasses for scanning, validation, conversion

The CHDConverterGUI main window lives in ``main.py`` at the project root
(entry point for the PyInstaller build).
"""

__version__ = "2.7.0"
