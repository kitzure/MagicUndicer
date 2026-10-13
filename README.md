# MagicUndicer

Rebuild many images from one or more diced texture atlases and their **MonoBehaviour JSON**. Designed for the Utage `DicingTextures` format used by AnaDos / Another Eidos of Dragon Vein R.

Drop a whole AssetStudio export folder into the terminal and get named PNGs. No Excel, ImageMagick commands, or intermediate tile files needed. All processing happens locally.

## All-in-one download

Extract `MagicUndicer-All-in-One.zip`. It includes the GUI, CLI, and source in one folder.

- **GUI:** double-click `MagicUndicer-GUI.cmd`, or open `windows/MagicUndicer.exe` directly.
- **CLI:** use `MagicUndicer-CLI.cmd`, or run `windows/MagicUndicer-CLI.exe` from a terminal.
- **Source:** `src/`, `tests/`, and `pyproject.toml` are at the top level alongside this README.

Both Windows executables work without Python installed. The same launchers can also run a source-only checkout, installing its Python dependencies on first use.

```powershell
.\windows\MagicUndicer-CLI.exe "D:\Exports" -o "D:\Restored"
```

## Windows app

Extract `MagicUndicer-Windows.zip` and open **MagicUndicer.exe**. No Python installation is needed.

1. Use **Add atlas** for images and **Add JSON** for the matching MonoBehaviour metadata. You can also drop both together or use **Import export folder**.
2. Choose a save folder. Use **Options** to trim borders, replace existing PNGs, or filter image names.
3. Click **Check files** to validate without saving, or **Undice images** to export.
4. Inspect the results and preview. Use **Open output folder** or **Open report** for the saved files and any errors.

The window stays responsive during processing. **Stop** finishes the current image and keeps completed PNGs; run again to skip those and continue. Progress describes the current JSON source. A double-click on a result opens its PNG. The Activity tab retains the processing log.

Adding only PNG/JPEG atlas images displays a **MonoBehaviour JSON required** popup. The images remain selected, but export is blocked until you add the JSON or import a folder containing the metadata. Folder imports also show the popup if no usable MonoBehaviour JSON is found.

Selecting individual files processes only those files. Neighboring images and JSON files are never added automatically. If one JSON describes several atlases, only images belonging to the selected atlases are reconstructed. A selected pair that does not match reports an error. Importing a folder explicitly enables bulk processing of that folder.

Drag-and-drop has equivalent file picker buttons. Ctrl+O opens the file picker; Escape requests a stop. Selection, paths, and options remain available between runs in the same window.

From source, install the GUI dependency and run:

```sh
python -m pip install ".[gui]"
python -m magicundicer.gui
```

Linux installations also need their system Tk package (often `python3-tk`). Without the optional drag-and-drop library, the GUI uses file picker buttons.

## Windows CLI (optional)

Download the Windows package and extract it. Drag your atlas files **and** MonoBehaviour JSON onto `MagicUndicer-CLI.cmd`, or double-click it and paste the dragged paths at the prompt. You can also drop a folder containing both, including an AssetStudio export with `Texture2D` and `MonoBehaviour` subfolders.

The same Windows package includes `MagicUndicer-CLI.exe`; Python is not required. The source-only package's launcher uses Python 3.10+ and installs Pillow on its first run (internet required for setup).

The output is saved in the `undiced` folder beside the launcher. Terminal commands can choose any output folder, including a different drive:

```powershell
.\MagicUndicer-CLI.exe "D:\Exports" -o "D:\Restored"
.\MagicUndicer-CLI.exe "D:\Exports\bg_Atlas0.png" "D:\Exports\bg.json"
.\MagicUndicer-CLI.exe "D:\Exports" --dry-run
.\MagicUndicer-CLI.exe "D:\Exports" --filter fg_flet --trim
```

To drag many files into a terminal command, type `.\MagicUndicer-CLI.exe `, drag the files/folders into the terminal, and press Enter. You can run `.\MagicUndicer-CLI.exe` by itself for an interactive path prompt. If your terminal inserts a command prefix such as `&`, use the interactive prompt or paste quoted paths as in the examples.

## Python / macOS / Linux

```sh
python -m pip install .
magicundicer /path/to/export -o /path/to/restored
# Equivalent:
python -m magicundicer /path/to/export
```

## What to export

From AssetStudio, export the **Texture2D atlas images** and the matching **MonoBehaviour as JSON**. You can use `.json` or a `.txt` containing valid JSON. Atlases may be PNG, JPEG, WebP, TGA, BMP, or TIFF; matching uses the image filename without its extension. Lossless atlas exports preserve pixels best.

The JSON must contain `cellSize`, `padding`, and `textureDataList`. Each image record needs `name`, `atlasName`, `width`, `height`, `cellIndexList`, and optionally `transparentIndex` (default `-1`). For example:

```json
{
  "cellSize": 64,
  "padding": 3,
  "textureDataList": [{
    "name": "fg_example_0",
    "atlasName": "fg_example_Atlas0",
    "width": 58,
    "height": 58,
    "cellIndexList": [0],
    "transparentIndex": -1
  }]
}
```

The atlas alone does not contain the image order or original dimensions. A raw `.bundle`, serialized MonoBehaviour binary, or AssetStudio text dump is not a JSON export and is not supported by this version. Export them first.

## Batch behavior

- Folders are searched recursively. Individual file selection stays limited to those files, in both the GUI and CLI.
- Atlas names are matched without case sensitivity. Local files take priority. Ambiguous matches report an error rather than choosing an arbitrary atlas.
- Each JSON gets an output folder named from its filename and a short hash of its path and contents. This separates exports with identical metadata and different atlases. Images use the names from the JSON, with directory prefixes removed and invalid Windows filename characters replaced.
- Existing PNGs are skipped. Use `--overwrite` to replace them.
- Exact JSON dimensions and alpha are preserved by default. `--trim` removes transparent borders, like the reference spreadsheet's cleanup command. Completely transparent images keep their original dimensions.
- `--dry-run` checks atlas matches, dimensions, tile counts, and indices without writing files.
- One malformed file or missing atlas does not stop other images. A timestamped JSON report records successes, skips, and errors. Exit code: `0` success, `1` errors, `130` interrupted.
- The output folder is excluded when scanning an input folder. Keep game exports in a separate folder from the source repository.

## How reconstruction works

Atlas tile indices use bottom-left origin. The tool flips the exported image vertically, indexes square `cellSize` tiles row by row, crops `padding` pixels off every side, and places their contents in `cellIndexList` order. The usable size is `cellSize - 2 * padding` (58 for a 64-pixel cell with 3-pixel padding). It crops to the JSON dimensions and flips the assembled image back. Tiles matching `transparentIndex` remain transparent.

This follows the user-supplied **AnaDos - Atlas to Image v2** workbook and the [Decoding the Sprite Atlas walkthrough](https://docs.google.com/presentation/d/1UQ9wlCigqpyhXgDj4PzgN3oMiJThbu_E9JlJbX9_FTY/edit). The spreadsheet hardcodes 58 in some montage formulas; this tool calculates it from each JSON.

## Development

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m pip install pyinstaller
pyinstaller --onefile --name MagicUndicer-CLI build_exe.py
# Desktop GUI (after installing .[gui]):
pyinstaller --onefile --windowed --collect-all tkinterdnd2 --name "MagicUndicer" build_gui.py
```

Tests cover shuffled tiles, orientation, padding, partial edge cells, alpha, transparent indices, invalid metadata, ambiguous matches, batch continuation, rerun skipping, dry-run, and AssetStudio subfolders. CI runs on Windows and Linux.

## GitHub

Use this source code for a GitHub repository named `MagicUndicer`. Extract `MagicUndicer-Source.zip` and upload the extracted files to the repository, including the `.github` folder and `.gitignore`. Upload `MagicUndicer-Windows.zip` separately as a release asset. No game images, MonoBehaviour exports, extracted assets, or build caches are included in the source ZIP.
