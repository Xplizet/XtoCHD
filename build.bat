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
echo Executable created in: dist\XtoCHD.exe
echo.
echo Note: Users will need to download chdman.exe separately and place it in the same folder.
echo.
pause 