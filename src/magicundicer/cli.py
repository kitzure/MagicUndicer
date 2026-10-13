import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from PIL import Image

from .core import reconstruct, safe_name, save_png, settings, trim_transparency, validate_entry

IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp", ".tif", ".tiff"}


def dropped_paths(line):
    """Parse Windows terminal drag/drop text without interpreting shell commands."""
    return [m[0] or m[1] or m[2] for m in re.findall(r'"([^"\n]+)"|\x27([^\x27\n]+)\x27|([^\s]+)', line) if (m[0] or m[1] or m[2]) != "&"]


def discover(inputs, output, should_cancel=None):
    files = set()
    missing = []
    for raw in inputs:
        if should_cancel and should_cancel():
            break
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            missing.append(str(path))
        elif path.is_dir():
            for p in path.rglob("*"):
                if should_cancel and should_cancel():
                    break
                if p.is_file() and output not in p.resolve().parents:
                    files.add(p.resolve())
        else:
            files.add(path)
    return sorted(files), missing


def atlas_key(value):
    name = re.split(r"[/\\]", str(value))[-1]
    return Path(name).stem.casefold() if Path(name).suffix.casefold() in IMAGE_TYPES else name.casefold()


def find_atlas(name, manifest, images):
    candidates = [p for p in images if p.stem.casefold() == atlas_key(name)]
    if len(candidates) == 1:
        return candidates[0]
    # AssetStudio commonly uses sibling MonoBehaviour / Texture2D folders.
    for scope in (manifest.parent, manifest.parent.parent):
        local = [p for p in candidates if scope in p.parents]
        if len(local) == 1:
            return local[0]
        if len(local) > 1:
            break
    if not candidates:
        raise ValueError(f"Missing atlas '{name}'. Include its exported PNG/WebP or its folder")
    raise ValueError(f"Ambiguous atlas '{name}': " + ", ".join(str(p) for p in candidates))


def run(inputs, output, overwrite=False, dry_run=False, trim=False, pattern=None,
        on_event=None, should_cancel=None):
    def emit(kind, **values):
        if on_event:
            on_event({"kind": kind, **values})

    def log(message, error=False):
        if on_event:
            emit("log", message=message, error=error)
        else:
            print(message, file=sys.stderr if error else sys.stdout)

    def cancelled():
        return bool(should_cancel and should_cancel())

    output = Path(output).expanduser().resolve()
    emit("scan")
    files, missing = discover(inputs, output, should_cancel)
    images = [p for p in files if p.suffix.casefold() in IMAGE_TYPES]
    manifests = [p for p in files if p.suffix.casefold() in {".json", ".txt"}]
    # An explicit atlas selection restricts records too, even when one JSON
    # describes several atlases. Folder input intentionally enables bulk mode.
    selected_keys = {p.stem.casefold() for p in images}
    restrict_atlases = bool(images) and not any(Path(p).expanduser().is_dir() for p in inputs)
    report = {"sources": [], "created": 0, "skipped": 0, "errors": [], "dry_run": dry_run,
              "inputs": [str(Path(p).expanduser().resolve()) for p in inputs], "excluded": 0}
    for path in missing:
        report["errors"].append({"source": path, "error": "Input does not exist"})
        log(f"ERROR: input does not exist: {path}", error=True)
    count = 0
    for manifest in manifests:
        if cancelled():
            break
        try:
            raw = manifest.read_bytes()
            data = json.loads(raw.decode("utf-8-sig"))
            # Ignore unrelated JSON files in a bulk folder.
            if not isinstance(data, dict) or "textureDataList" not in data:
                continue
            cell_size, padding = settings(data)
        except Exception as exc:
            # Malformed JSON exports are visible instead of silently discarded.
            report["errors"].append({"source": str(manifest), "error": str(exc)})
            log(f"ERROR: {manifest.name}: {exc}", error=True)
            continue
        count += 1
        # Identical metadata from different export folders can reference different
        # atlases. Include the source path so one batch cannot silently skip another.
        identity = str(manifest).casefold().encode("utf-8") + b"\0" + raw
        group = safe_name(manifest.stem) + "-" + hashlib.sha256(identity).hexdigest()[:8]
        source_report = {"source": str(manifest), "folder": group, "images": []}
        report["sources"].append(source_report)
        used = set()
        cache = {}
        entries = [entry for entry in data["textureDataList"] if not pattern or
                   pattern.casefold() in (str(entry.get("name", "")) if isinstance(entry, dict) else "").casefold()]
        if restrict_atlases:
            selected_entries = [entry for entry in entries if not isinstance(entry, dict) or
                                not entry.get("atlasName") or atlas_key(entry["atlasName"]) in selected_keys]
            excluded = len(entries) - len(selected_entries)
            report["excluded"] += excluded
            if excluded:
                log(f"{manifest.name}: excluded {excluded} images belonging to unselected atlases")
            if entries and not selected_entries:
                message = "This MonoBehaviour JSON does not reference the selected atlas images. Add the matching JSON or atlas."
                report["errors"].append({"source": str(manifest), "error": message})
                log(f"ERROR: {manifest.name}: {message}", error=True)
            entries = selected_entries
        log(f"\n{manifest.name}: {len(entries)} images, cell={cell_size}, padding={padding}")
        try:
            for position, entry in enumerate(entries):
                if cancelled():
                    break
                name = str(entry.get("name", "")) if isinstance(entry, dict) else "<invalid entry>"
                emit("progress", source=manifest.name, name=name, current=position, total=len(entries))
                record = {"name": name}
                source_report["images"].append(record)
                try:
                    filename = safe_name(name) + ".png"
                    if filename.casefold() in used:
                        raise ValueError(f"Duplicate output filename '{filename}' after sanitizing names")
                    used.add(filename.casefold())
                    atlas_path = find_atlas(entry.get("atlasName", ""), manifest, images)
                    # Cache only the current atlas; keep memory bounded for bulk work.
                    if atlas_path not in cache:
                        for old in cache.values():
                            old.close()
                        cache.clear()
                        with Image.open(atlas_path) as im:
                            cache[atlas_path] = im.convert("RGBA")
                    atlas = cache[atlas_path]
                    validate_entry(entry, atlas.size, cell_size, padding)
                    destination = output / group / filename
                    record.update(atlas=str(atlas_path), output=str(destination))
                    if destination.exists() and not overwrite:
                        report["skipped"] += 1
                        record["status"] = "skipped"
                        log(f"  SKIP {filename} (already exists)")
                    elif dry_run:
                        record["status"] = "validated"
                        log(f"  READY {filename} ({entry['width']}x{entry['height']})")
                    else:
                        image = reconstruct(atlas, entry, cell_size, padding)
                        if trim:
                            image = trim_transparency(image)
                        try:
                            save_png(image, destination, overwrite)
                            record.update(status="created", width=image.width, height=image.height)
                            report["created"] += 1
                            log(f"  OK {filename} ({image.width}x{image.height})")
                        finally:
                            image.close()
                except Exception as exc:
                    record.update(status="error", error=str(exc))
                    report["errors"].append({"source": str(manifest), "name": name, "error": str(exc)})
                    log(f"  ERROR {name}: {exc}", error=True)
                emit("item", record=record.copy(), created=report["created"], skipped=report["skipped"],
                     errors=len(report["errors"]), current=position + 1, total=len(entries), source=manifest.name)
        finally:
            for atlas in cache.values():
                atlas.close()
    report["cancelled"] = cancelled()
    report["missing_metadata"] = not count and not report["cancelled"]
    if not count and not report["cancelled"]:
        message = "No supported MonoBehaviour JSON found. Export the MonoBehaviour as JSON and include it with the atlas images."
        report["errors"].append({"error": message})
        log(message, error=True)
    report_path = None
    if not dry_run:
        output.mkdir(parents=True, exist_ok=True)
        # Keep past batch reports instead of replacing them on the next run.
        from datetime import datetime
        report_path = output / ("report-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"\nReport: {report_path}")
    log(f"Created {report['created']}, skipped {report['skipped']}, errors {len(report['errors'])}")
    emit("finished", report=report, report_path=str(report_path) if report_path else None)
    return 130 if report["cancelled"] else (1 if report["errors"] else 0)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Rebuild all images from diced atlases + MonoBehaviour JSON. Drop files or folders after the command.")
    parser.add_argument("inputs", nargs="*", help="Explicit atlas images + MonoBehaviour JSON, or folders for recursive bulk processing")
    parser.add_argument("-o", "--output", default="undiced", help="Output folder (default: ./undiced)")
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output PNGs")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs without writing files")
    parser.add_argument("--trim", action="store_true", help="Remove transparent borders; otherwise preserve exact JSON dimensions")
    parser.add_argument("--filter", help="Only image names containing this text (case-insensitive)")
    args = parser.parse_args(argv)
    if not args.inputs:
        if not sys.stdin.isatty():
            parser.error("Supply files/folders, or run interactively to paste dragged paths")
        print("Drag atlas images + MonoBehaviour JSON (or their folders) into this window, then press Enter.")
        try:
            args.inputs = dropped_paths(input("> "))
        except (EOFError, KeyboardInterrupt):
            return 130
        if not args.inputs:
            parser.error("No paths supplied")
    try:
        return run(args.inputs, args.output, args.overwrite, args.dry_run, args.trim, args.filter)
    except KeyboardInterrupt:
        print("\nStopped. Completed PNGs remain; rerun to skip them.", file=sys.stderr)
        return 130
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
