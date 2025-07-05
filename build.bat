@echo off
echo Building XtoCHD executable...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Install requirements if needed
echo Installing requirements...
pip install -r requirements.txt

REM Build the executable
echo.
echo Building executable...
python build_exe.py

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo Executable created with version number from changelog
echo.

REM Build script handles chdman.exe copying to versioned folder
echo.
echo Distribution ready in versioned folder!
echo Check dist\XtoCHD_v* folder for the release

echo.
pause 