<p align="center">
  <img src="assets/magicundicer-logo.png" alt="MagicUndicer" width="600">
</p>

# MagicUndicer

Rebuild original images from diced texture atlases using a simple **GUI or CLI**. Made for Utage / AnaDos-style exports, without Excel commands or temporary tile files.

[Download for Windows](https://github.com/kitzure/MagicUndicer/releases) · No Python installation needed.

## How to use

1. Export the **Texture2D atlas images** and matching **MonoBehaviour JSON** from AssetStudio.
2. Open `MagicUndicer.exe`, add the atlas and JSON, and choose a save folder.
3. Click **Undice images**. Use **Import export folder** to process a whole folder.

Only selected files are processed. One atlas can produce many images, depending on its JSON.

**Why is the JSON needed?** The atlas stores the small image tiles; the MonoBehaviour JSON tells the app their order, padding, and original image sizes. The image alone is not enough to rebuild them.

Prefer the terminal?

```powershell
.\windows\MagicUndicer-CLI.exe "atlas.png" "metadata.json" -o "restored"
```

PNG, JPEG, WebP, TGA, BMP, and TIFF are supported. Use lossless exports such as PNG for the best results.
