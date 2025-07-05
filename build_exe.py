#!/usr/bin/env python3
"""
Build script for XtoCHD executable using PyInstaller
"""

import os
import sys
import subprocess
import shutil
import re

def extract_version_from_changelog():
    """Extract the current version from CHANGELOG.md"""
    try:
        with open("CHANGELOG.md", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Look for the latest version entry (first one after [Unreleased])
        version_pattern = r'## \[v(\d+\.\d+\.\d+)\]'
        matches = re.findall(version_pattern, content)
        
        if matches:
            # Get the first version (latest one)
            version = matches[0]
            print(f"Extracted version from changelog: v{version}")
            return version
        else:
            print("Warning: No version found in CHANGELOG.md, using default")
            return "2.3.0"  # Default fallback
    except Exception as e:
        print(f"Warning: Could not read CHANGELOG.md: {e}")
        return "2.3.0"  # Default fallback

def main():
    print("Building XtoCHD executable...")
    
    # Extract version from changelog
    version = extract_version_from_changelog()
    exe_name = f"XtoCHD_v{version}"
    
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
    
    # Build the executable with versioned name
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--name={exe_name}",
        "--icon=icon.ico" if os.path.exists("icon.ico") else "",
        "main.py"
    ]
    
    # Remove empty icon parameter if no icon exists
    cmd = [arg for arg in cmd if arg]
    
    print(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    
    print(f"\nBuild complete!")
    print(f"Executable created in: dist/{exe_name}.exe")
    
    # Copy chdman.exe if it exists
    if os.path.exists("chdman.exe"):
        shutil.copy2("chdman.exe", "dist/chdman.exe")
        print("chdman.exe copied to dist/ folder")
    else:
        print("\nWarning: chdman.exe not found in current directory")
        print("Please download chdman.exe from the MAME project and place it in the dist/ folder")
    
    print(f"\nDistribution ready in dist/ folder!")
    print(f"Executable: {exe_name}.exe")

if __name__ == "__main__":
    main() 