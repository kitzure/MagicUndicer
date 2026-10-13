"""Entry point for PyInstaller: pyinstaller --onefile --name MagicUndicer-CLI build_exe.py."""
from magicundicer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
