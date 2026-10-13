"""Utage DicingTextures reconstruction, using exported top-left-origin images."""

import math
import re
from pathlib import Path

from PIL import Image


def safe_name(value):
    # Strip exported Unity directories and protect Windows output filenames.
    name = re.split(r"[/\\]", str(value))[-1]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name:
        raise ValueError("Image name is empty")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}:
        name = "_" + name
    return name


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def settings(data):
    if not isinstance(data, dict) or not isinstance(data.get("textureDataList"), list):
        raise ValueError("Expected MonoBehaviour JSON with textureDataList")
    size = integer(data.get("cellSize"), "cellSize")
    padding = integer(data.get("padding"), "padding")
    if padding < 0 or size <= 2 * padding:
        raise ValueError("cellSize must be positive and greater than twice padding")
    return size, padding


def validate_entry(entry, atlas_size, cell_size, padding, max_pixels=100_000_000):
    if not isinstance(entry, dict):
        raise ValueError("Image entry must be an object")
    safe_name(entry.get("name", ""))
    width = integer(entry.get("width"), "width")
    height = integer(entry.get("height"), "height")
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ValueError(f"Invalid image dimensions {width}x{height} (limit {max_pixels} pixels)")
    payload = cell_size - 2 * padding
    columns, rows = math.ceil(width / payload), math.ceil(height / payload)
    indices = entry.get("cellIndexList")
    if not isinstance(indices, list) or len(indices) != columns * rows:
        raise ValueError(f"Expected {columns * rows} cell indices for {width}x{height}")
    aw, ah = atlas_size
    if aw % cell_size or ah % cell_size:
        raise ValueError(f"Atlas {aw}x{ah} is not divisible by cellSize {cell_size}")
    transparent = integer(entry.get("transparentIndex", -1), "transparentIndex")
    count = (aw // cell_size) * (ah // cell_size)
    for index in indices:
        integer(index, "Cell index")
        if index != transparent and not 0 <= index < count:
            raise ValueError(f"Cell index {index} is outside atlas (0..{count - 1})")
    return width, height, columns, payload, transparent


def reconstruct(atlas, entry, cell_size, padding):
    width, height, columns, payload, transparent = validate_entry(entry, atlas.size, cell_size, padding)
    # Work in Unity's bottom-left coordinate system. Flip once at the end.
    flipped = atlas.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    canvas = Image.new("RGBA", (width, height))
    atlas_columns = atlas.width // cell_size
    for position, index in enumerate(entry["cellIndexList"]):
        if index == transparent:
            continue
        sx = (index % atlas_columns) * cell_size + padding
        sy = (index // atlas_columns) * cell_size + padding
        dx, dy = (position % columns) * payload, (position // columns) * payload
        tw, th = min(payload, width - dx), min(payload, height - dy)
        tile = flipped.crop((sx, sy, sx + tw, sy + th))
        # No mask: preserve the original RGBA bytes without double-applying alpha.
        canvas.paste(tile, (dx, dy))
    return canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def trim_transparency(image):
    box = image.getchannel("A").getbbox()
    return image.crop(box) if box else image


def save_png(image, destination, overwrite=False):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects against concurrent jobs overwriting files.
    with destination.open("wb" if overwrite else "xb") as stream:
        try:
            image.save(stream, format="PNG")
        except Exception:
            stream.close()
            destination.unlink(missing_ok=True)
            raise
