#!/usr/bin/env python3
"""
Build script for XtoCHD executable using PyInstaller
"""

import os
import sys
import subprocess
import shutil

def main():
    print("Building XtoCHD executable...")
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    
    # Build the executable
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        "--name=XtoCHD",
        "--icon=icon.ico" if os.path.exists("icon.ico") else "",
        "main.py"
    ]
    
    # Remove empty icon parameter if no icon exists
    cmd = [arg for arg in cmd if arg]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    print("\nBuild complete!")
    print("Executable created in: dist/XtoCHD.exe")
    
    # Copy chdman.exe if it exists
    if os.path.exists("chdman.exe"):
        shutil.copy2("chdman.exe", "dist/chdman.exe")
        print("chdman.exe copied to dist/ folder")
    else:
        print("\nWarning: chdman.exe not found in current directory")
        print("Please download chdman.exe from the MAME project and place it in the dist/ folder")
    
    print("\nDistribution ready in dist/ folder!")

if __name__ == "__main__":
    main() 