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

REM Check if chdman.exe exists and copy it
if exist "chdman.exe" (
    copy "chdman.exe" "dist\chdman.exe" >nul
    echo chdman.exe copied to dist\ folder
    echo.
    echo Distribution ready in dist\ folder!
) else (
    echo Warning: chdman.exe not found in current directory
    echo Please download chdman.exe from the MAME project and place it in the dist\ folder
)

echo.
pause 