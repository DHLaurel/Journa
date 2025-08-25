import os
import platform
import subprocess

# Assuming the main application script is saved as 'journal.py'
# and 'icon.ico' exists in the same directory.
# For macOS, you need to create 'icon.icns' from 'icon.ico' using a tool like 'sips' 
# (e.g., sips -s format icns icon.ico --out icon.icns) or an online converter.
# Run this build script on each target platform to generate the executable for that OS.

script_name = 'journal.py'
icon_windows = 'journa.ico'
icon_mac = 'icon.icns'  # Create this if you want an icon on macOS

def build_executable():
    system = platform.system()
    base_cmd = ['pyinstaller', '--onefile', '--windowed', '--name', 'Journal']

    if system == 'Windows':
        if os.path.exists(icon_windows):
            base_cmd.append(f'--icon={icon_windows}')
    elif system == 'Darwin':  # macOS
        if os.path.exists(icon_mac):
            base_cmd.append(f'--icon={icon_mac}')
    elif system == 'Linux':
        # PyInstaller does not directly support icons for Linux executables.
        # Icons on Linux are typically handled via .desktop files for desktop integration.
        # You can create a .desktop file separately after building.
        pass
    else:
        print(f"Unsupported platform: {system}")
        return

    base_cmd.append(script_name)
    
    print(f"Running command: {' '.join(base_cmd)}")
    try:
        subprocess.check_call(base_cmd)
        print("Build completed successfully. Executable is in the 'dist' folder.")
    except subprocess.CalledProcessError as e:
        print(f"Build failed: {e}")

if __name__ == '__main__':
    build_executable()