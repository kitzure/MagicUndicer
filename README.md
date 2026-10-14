<p align="center">
  <img src="assets/magicundicer-logo.png" alt="MagicUndicer" width="600">
</p>

# MagicUndicer

Rebuild the original images from diced texture atlases with a simple **GUI or CLI**. Made for Utage / AnaDos-style exports, without Excel commands or temporary tile files.

[Download for Windows](https://github.com/kitzure/MagicUndicer/releases/latest) · No Python installation needed.

## How to use

1. Export the **Texture2D atlas** and its matching **MonoBehaviour JSON** from AssetStudio.
2. Open `MagicUndicer.exe`. Add the atlas in step 1 and the JSON in step 2: click a box or drop the files on the window, and use ✕ to remove one.
3. Click **Convert**. To process a whole export at once, use **Import a whole export folder instead**.

Switch between light and dark mode with the button in the top-right corner.

## How it works

To save memory, Utage cuts every sprite into a grid of small square cells and packs them into one shared atlas. Identical cells are stored only once, so sprites that differ only in their face share most of their cells, and fully transparent cells are not stored at all. That is why an exported atlas looks like a scrambled mosaic.

The MonoBehaviour JSON is the map for putting the pieces back. It stores the cell size and padding, and for every image its name, original size, atlas, and a `cellIndexList`: which atlas cell goes into each slot of the grid. The atlas alone doesn't know which piece belongs where, so both files are needed.

MagicUndicer creates an empty canvas at the original size and walks through that list. For each slot it finds the cell in the atlas, cuts off its padding border, and pastes it into place. Transparent slots stay empty and cells on the edges are trimmed to fit. Pixels are copied exactly and saved as PNG, so nothing is lost.

## Prefer the terminal?

```powershell
.\windows\MagicUndicer-CLI.exe "atlas.png" "metadata.json" -o "restored"
```

PNG, JPEG, WebP, TGA, BMP, and TIFF atlases are supported. Use lossless exports such as PNG for the best results.
