"""PyInstaller entry point for the desktop application.

pyinstaller --onefile --windowed --exclude-module numpy --name MagicUndicer --icon assets/magicundicer.ico ^
    --collect-all tkinterdnd2 ^
    --add-data "src/magicundicer/assets;magicundicer/assets" build_gui.py
"""
from magicundicer.gui import main

if __name__ == "__main__":
    main()
