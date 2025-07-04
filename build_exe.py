import PyInstaller.__main__
import os
import sys

def build_exe():
    """Build the XtoCHD executable using PyInstaller"""
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define the spec file path
    spec_file = os.path.join(script_dir, 'xtochd.spec')
    
    # PyInstaller arguments
    args = [
        'main.py',                          # Main script
        '--onefile',                        # Create a single executable
        '--windowed',                       # Hide console window (GUI app)
        '--name=XtoCHD',                    # Name of the executable
        '--icon=icon.ico',                  # Icon file (if available)
        '--add-data=chdman.exe;.',          # Include chdman.exe in the bundle
        '--distpath=dist',                  # Output directory
        '--workpath=build',                 # Build directory
        '--specpath=.',                     # Spec file directory
        '--clean',                          # Clean cache before building
        '--noconfirm',                      # Overwrite output directory without asking
    ]
    
    # Remove icon argument if icon file doesn't exist
    if not os.path.exists('icon.ico'):
        args.remove('--icon=icon.ico')
    
    # Remove chdman.exe from bundle if it doesn't exist
    if not os.path.exists('chdman.exe'):
        args.remove('--add-data=chdman.exe;.')
    
    print("Building XtoCHD executable...")
    print(f"Arguments: {' '.join(args)}")
    
    try:
        PyInstaller.__main__.run(args)
        print("\nBuild completed successfully!")
        print("Executable location: dist/XtoCHD.exe")
        
    except Exception as e:
        print(f"Build failed: {e}")
        return False
    
    return True

if __name__ == '__main__':
    build_exe() 