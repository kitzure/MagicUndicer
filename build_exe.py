"""Entry point for PyInstaller: pyinstaller --onefile --exclude-module numpy --name MagicUndicer-CLI --icon assets/magicundicer.ico build_exe.py."""
from magicundicer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
