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
    
    # Create versioned folder
    version_folder = f"dist/XtoCHD_v{version}"
    if os.path.exists(version_folder):
        shutil.rmtree(version_folder)
    os.makedirs(version_folder)
    
    # Move executable to versioned folder
    exe_source = f"dist/{exe_name}.exe"
    exe_dest = f"{version_folder}/XtoCHD.exe"
    shutil.move(exe_source, exe_dest)
    
    # Copy chdman.exe if it exists (only to versioned folder)
    if os.path.exists("chdman.exe"):
        shutil.copy2("chdman.exe", f"{version_folder}/chdman.exe")
        print(f"chdman.exe copied to {version_folder}/")
    else:
        print(f"\nWarning: chdman.exe not found in current directory")
        print(f"Please download chdman.exe from the MAME project and place it in {version_folder}/")
    
    # Clean up any chdman.exe that might have been copied to dist/ root
    dist_chdman = "dist/chdman.exe"
    if os.path.exists(dist_chdman):
        os.remove(dist_chdman)
        print("Cleaned up chdman.exe from dist/ root folder")
    
    # Also clean up any other potential duplicates in dist/
    for item in os.listdir("dist"):
        if item.startswith("chdman") and item != "chdman.exe":
            os.remove(os.path.join("dist", item))
            print(f"Cleaned up duplicate: {item}")
    
    print(f"\nDistribution ready in {version_folder}/ folder!")
    print(f"Executable: {version_folder}/XtoCHD.exe")
    print(f"Folder structure: {version_folder}/")

if __name__ == "__main__":
    main() 