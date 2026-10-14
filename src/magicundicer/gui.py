"""Local desktop interface. Workers publish events; only Tk's thread edits widgets."""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .cli import IMAGE_TYPES, atlas_key, run
from .interface import CONVERT, FONT, THEMES, apply_theme, build, style_titlebar

METADATA_TYPES = {".json", ".txt"}
SETTINGS_PATH = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "MagicUndicer" / "settings.json"


def open_path(path):
    path = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


def load_settings():
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


def save_settings(settings):
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def system_theme():
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return "light" if winreg.QueryValueEx(key, "AppsUseLightTheme")[0] else "dark"
        except OSError:
            pass
    return "light"


def input_kind(path):
    path = Path(path)
    if path.is_dir():
        return "folder"
    return "json" if path.suffix.casefold() in METADATA_TYPES else "atlas"


def read_details(path):
    """The cheap facts shown under each selected file."""
    path = Path(path)
    kind = input_kind(path)
    if kind == "folder":
        return {"meta": "Export folder · files matched automatically"}
    if kind == "json":
        try:
            data = json.loads(path.read_bytes().decode("utf-8-sig"))
        except (OSError, ValueError):
            return {"meta": "Can't read this JSON file", "warn": True}
        entries = data.get("textureDataList") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return {"meta": "Not an atlas JSON · will be skipped", "warn": True, "ignored": True}
        named = [entry["atlasName"] for entry in entries if isinstance(entry, dict) and entry.get("atlasName")]
        return {"meta": f"{len(entries)} image{'s' * (len(entries) != 1)}",
                # Without an atlasName on every entry we cannot predict the match.
                "atlases": {atlas_key(name) for name in named} if len(named) == len(entries) else None}
    try:
        with Image.open(path) as image:
            return {"meta": f"{image.width} × {image.height} px"}
    except (OSError, ValueError):
        return {"meta": "Can't open this image", "warn": True}


class App:
    def __init__(self, root, inputs=()):
        self.root = root
        root.title("MagicUndicer")
        root.geometry("1060x820+40+40")
        root.minsize(940, 700)
        self.settings = load_settings()
        self.theme_name = self.settings.get("theme") if self.settings.get("theme") in THEMES else system_theme()
        self.palette = THEMES[self.theme_name]
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.closing = False
        self.dry_run = False
        self.paths = []
        self.details = {}
        self.selected_input = None
        self.records = {}
        self.report_path = None
        self.preview_path = None
        self.preview_photo = None
        self.locked_widgets = []
        self.options_dialog = None
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        self.output = tk.StringVar(value=str(base / "undiced"))
        self.pattern = tk.StringVar()
        self.trim = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Add an atlas image and its MonoBehaviour JSON, then press Convert.")
        self.counters = tk.StringVar()
        self.readiness = tk.StringVar()
        self.options_summary = tk.StringVar(value="Original size · skip existing files")
        self.preview_label = tk.StringVar(value="Preview")
        self.view = tk.StringVar(value="results")
        build(self)
        apply_theme(self)
        self.render_inputs()
        self.add_paths(inputs)
        for variable in (self.trim, self.overwrite, self.pattern):
            variable.trace_add("write", self.update_options_summary)
        root.bind_all("<FocusIn>", self.reveal_control, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-o>", lambda _: self.add_files())
        root.bind("<Control-Return>", lambda _: self.start())
        root.bind("<Escape>", lambda _: self.stop())
        self.poll_after = root.after(80, self.poll)

    def button(self, parent, text, command, style="TButton", lock=True):
        widget = ttk.Button(parent, text=text, command=command, style=style)
        if lock:
            self.locked_widgets.append(widget)
        return widget

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.palette = THEMES[self.theme_name]
        self.settings["theme"] = self.theme_name
        save_settings(self.settings)
        apply_theme(self)

    def add_paths(self, paths):
        if self.running:
            return
        existing = {p.casefold() for p in self.paths}
        for raw in paths:
            path = str(Path(raw).expanduser().resolve())
            if path.casefold() in existing:
                continue
            self.paths.append(path)
            existing.add(path.casefold())
            # Show the first atlas straight away so the user sees what they added.
            if self.selected_input is None and input_kind(path) == "atlas":
                self.selected_input = path
                self.show_preview(path, "Atlas preview")
        self.render_inputs()

    def remove_path(self, path):
        if self.running or path not in self.paths:
            return
        section = self.json_section if input_kind(path) == "json" else self.atlas_section
        self.paths.remove(path)
        self.details.pop(path, None)
        if self.selected_input == path:
            self.selected_input = next((p for p in self.paths if input_kind(p) == "atlas"), None)
            if self.selected_input:
                self.show_preview(self.selected_input, "Atlas preview")
            else:
                self.clear_preview()
        self.render_inputs()
        section.focus()

    def select_input(self, path):
        if input_kind(path) != "atlas":
            return
        self.selected_input = path
        self.atlas_section.restyle()
        self.show_preview(path, "Atlas preview")

    def input_counts(self):
        images = sum(Path(p).suffix.casefold() in IMAGE_TYPES and not Path(p).is_dir() for p in self.paths)
        metadata = sum(Path(p).suffix.casefold() in METADATA_TYPES and not Path(p).is_dir() for p in self.paths)
        folders = sum(Path(p).is_dir() for p in self.paths)
        return images, metadata, folders

    def render_inputs(self):
        for path in self.paths:
            if path not in self.details:
                self.details[path] = read_details(path)
        kinds = {path: input_kind(path) for path in self.paths}
        atlases = {Path(p).stem.casefold() for p, kind in kinds.items() if kind == "atlas"}
        manifests = [self.details[p] for p, kind in kinds.items() if kind == "json" and not self.details[p].get("warn")]
        referenced = set()
        for info in manifests:
            referenced |= info["atlases"] or set()
        # Folders bring their own files, so only check explicit pairs.
        check = "folder" not in kinds.values()
        known = check and manifests and all(info["atlases"] is not None for info in manifests)
        mismatch = False
        rows = {"atlas": [], "json": []}
        for path, kind in kinds.items():
            info = self.details[path]
            meta, warn = info["meta"], info.get("warn", False)
            if kind == "atlas" and known and Path(path).stem.casefold() not in referenced:
                meta, warn = meta + " · no selected JSON uses it", True
            elif kind == "json" and check and atlases and info.get("atlases") is not None and not info["atlases"] & atlases:
                meta, warn = meta + " · not for the selected atlas", True
            mismatch |= warn
            glyph, style = {"atlas": ("▦", "RowGlyph"), "json": ("{ }", "RowJson"), "folder": ("▤", "RowGlyph")}[kind]
            rows["json" if kind == "json" else "atlas"].append(dict(
                path=path, glyph=glyph, glyph_style=style, name=Path(path).name, meta=meta, warn=warn,
                clickable=kind == "atlas"))
        self.atlas_section.render(rows["atlas"])
        self.json_section.render(rows["json"])
        self.update_readiness(mismatch)

    def update_readiness(self, mismatch=False):
        images, metadata, folders = self.input_counts()
        if folders:
            message, style = "Export folder added. Atlases and JSON inside it are matched automatically.", "Good"
        elif images and not metadata:
            message, style = "MonoBehaviour JSON is missing. Add the .json exported with this atlas.", "Warning"
        elif metadata and not images:
            message, style = "Now add the atlas image this JSON belongs to.", "Warning"
        elif images and metadata and mismatch:
            message, style = "Some files may not belong together. Check the notes above.", "Warning"
        elif images and metadata:
            message, style = "Ready. Press Convert.", "Good"
        else:
            message, style = "Add an atlas image and its MonoBehaviour JSON.", "Hint"
        self.readiness.set(message)
        self.readiness_label.configure(style=style + ".TLabel")

    def missing_metadata_popup(self, force=False):
        images, metadata, folders = self.input_counts()
        if not force and (not images or metadata or folders):
            return
        self.status.set("MonoBehaviour JSON required. Add the metadata to continue.")
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0, style="Error.Horizontal.TProgressbar")
        messagebox.showerror("MonoBehaviour JSON required",
            "You need the matching MonoBehaviour JSON to convert these images.\n\n"
            "A PNG or JPEG alone does not contain the tile order or original image sizes.\n\n"
            "Add the MonoBehaviour JSON exported by AssetStudio in step 2, "
            "or import an export folder containing both the atlas images and JSON.", parent=self.root)
        self.json_section.focus()

    def reveal_control(self, event):
        canvas = self.control_canvas
        widget = event.widget
        parent = widget
        while parent is not None and parent is not canvas:
            parent = getattr(parent, "master", None)
        if parent is not canvas:
            return
        self.root.update_idletasks()
        box = canvas.bbox("all")
        if not box or box[3] <= canvas.winfo_height():
            return
        top = widget.winfo_rooty() - canvas.winfo_rooty()
        if top < 0 or top + widget.winfo_height() > canvas.winfo_height():
            visible_top = canvas.canvasy(0)
            canvas.yview_moveto(max(0, (visible_top + top - 10) / box[3]))

    def update_options_summary(self, *_):
        self.options_summary.set(("Trim borders" if self.trim.get() else "Original size") +
            (" · replace existing" if self.overwrite.get() else " · skip existing files") +
            (f"\nName filter: {self.pattern.get()}" if self.pattern.get().strip() else ""))

    def toggle_options(self):
        if self.running:
            return
        if self.options_dialog and self.options_dialog.winfo_exists():
            self.options_dialog.focus_set()
            return
        dialog = tk.Toplevel(self.root)
        self.options_dialog = dialog
        dialog.title("Options")
        dialog.configure(background=self.palette["surface"])
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=22)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Options", style="Heading.TLabel").pack(anchor="w", pady=(0, 10))
        first = ttk.Checkbutton(frame, text="Trim transparent borders", variable=self.trim)
        first.pack(anchor="w")
        ttk.Checkbutton(frame, text="Replace existing PNGs", variable=self.overwrite).pack(anchor="w")
        ttk.Label(frame, text="Only image names containing", style="Hint.TLabel").pack(anchor="w", pady=(14, 5))
        ttk.Entry(frame, textvariable=self.pattern, width=36).pack(fill="x")
        ttk.Label(frame, text="Leave blank to export every image.", style="Hint.TLabel").pack(anchor="w", pady=(5, 16))

        def close_dialog(*_):
            dialog.grab_release()
            dialog.destroy()
            self.options_dialog = None
            self.options_button.focus_set()

        def check_files():
            close_dialog()
            self.start(True)
        ttk.Button(frame, text="Done", command=close_dialog, style="Primary.TButton").pack(fill="x")
        ttk.Button(frame, text="Check files without exporting", command=check_files,
                   style="Link.TButton").pack(anchor="w", pady=(10, 0))
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Escape>", close_dialog)
        dialog.bind("<Return>", close_dialog)
        dialog.geometry(f"+{self.root.winfo_rootx()+70}+{self.root.winfo_rooty()+110}")
        style_titlebar(dialog, self.palette)
        dialog.grab_set()
        first.focus_set()

    def drop(self, event):
        self.add_paths(self.root.tk.splitlist(event.data))
        return event.action

    def add_files(self):
        if not self.running:
            self.add_paths(filedialog.askopenfilenames(parent=self.root, title="Choose atlas images and MonoBehaviour JSON",
                filetypes=[("Images and metadata", "*.png *.jpg *.jpeg *.webp *.tga *.bmp *.tif *.tiff *.json *.txt"), ("All files", "*.*")]))

    def add_images(self):
        if not self.running:
            self.add_paths(filedialog.askopenfilenames(parent=self.root, title="Add atlas images",
                filetypes=[("Atlas images", "*.png *.jpg *.jpeg *.webp *.tga *.bmp *.tif *.tiff"), ("All files", "*.*")]))

    def add_metadata(self):
        if not self.running:
            self.add_paths(filedialog.askopenfilenames(parent=self.root, title="Add matching MonoBehaviour JSON",
                filetypes=[("MonoBehaviour JSON", "*.json *.txt"), ("All files", "*.*")]))

    def add_folder(self):
        if not self.running:
            folder = filedialog.askdirectory(parent=self.root, title="Choose an AssetStudio export folder")
            if folder:
                self.add_paths([folder])

    def choose_output(self):
        folder = filedialog.askdirectory(parent=self.root, title="Choose where to save restored images")
        if folder:
            self.output.set(folder)

    def primary_action(self):
        if self.running:
            self.stop()
        else:
            self.start()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in self.locked_widgets + self.atlas_section.buttons + self.json_section.buttons:
            if widget.winfo_exists():
                widget.configure(state=state)
        self.start_button.configure(text="■  Stop" if busy else CONVERT,
                                    style="Stop.TButton" if busy else "Primary.TButton", state="normal")
        for section in self.sections:
            section.zone.draw()

    def start(self, dry_run=False):
        if self.running:
            return
        if not self.paths:
            self.status.set("Add an atlas image and its MonoBehaviour JSON first.")
            self.atlas_section.focus()
            return
        images, metadata, folders = self.input_counts()
        if images and not metadata and not folders:
            self.missing_metadata_popup()
            return
        if not self.output.get().strip():
            self.status.set("Choose an output folder before starting.")
            return
        destination = Path(self.output.get().strip()).expanduser().resolve()
        # Do not let recursive exclusion hide an input directory.
        for raw in self.paths:
            path = Path(raw)
            if path == destination or destination in path.parents:
                self.status.set("Choose an output folder separate from, or inside, the input folder.")
                return
        self.running = True
        self.dry_run = dry_run
        self.cancel.clear()
        self.report_path = None
        self.records.clear()
        self.results.delete(*self.results.get_children())
        self.report_button.configure(state="disabled")
        self.counters.set("0 created · 0 skipped · 0 errors")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.show_view("results")
        self.set_busy(True)
        self.status.set("Scanning inputs…")
        self.progress.configure(mode="indeterminate", style="Horizontal.TProgressbar")
        self.progress.start(12)
        # Read Tk variables here, before handing work to the background thread.
        args = dict(inputs=list(self.paths), output=str(destination), overwrite=self.overwrite.get(),
                    dry_run=dry_run, trim=self.trim.get(), pattern=self.pattern.get().strip() or None,
                    on_event=self.events.put, should_cancel=self.cancel.is_set)
        threading.Thread(target=self.worker, args=(args,), daemon=True).start()

    def worker(self, args):
        try:
            run(**args)
        except Exception as exc:
            self.events.put({"kind": "failed", "message": str(exc)})

    def stop(self):
        if self.running:
            self.cancel.set()
            self.start_button.configure(text="Stopping…", state="disabled")
            self.status.set("Stopping after the current image. Completed PNGs will be kept.")

    def show_view(self, view=None):
        if view:
            self.view.set(view)
        (self.log_frame if self.view.get() == "log" else self.results_frame).tkraise()

    def poll(self):
        try:
            # Bound each poll so huge batches cannot starve Tk's event loop.
            for _ in range(150):
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        if self.closing and not self.running:
            self.destroy()
            return
        self.poll_after = self.root.after(80, self.poll)

    def handle(self, event):
        kind = event["kind"]
        if kind == "log":
            self.log.configure(state="normal")
            self.log.insert("end", event["message"] + "\n", "error" if event.get("error") else ())
            self.log.see("end")
            self.log.configure(state="disabled")
        elif kind in {"progress", "item"}:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=100 * event["current"] / max(1, event["total"]))
            if not self.cancel.is_set():
                self.status.set(f"{event['source']}: {event['current']} / {event['total']} images")
            if kind == "item":
                record = event["record"]
                status = {"created": "Created", "skipped": "Skipped", "validated": "Ready", "error": "Error"}[record["status"]]
                tags = {"error": ("error",), "skipped": ("skipped",)}.get(record["status"], ())
                item = self.results.insert("", "end", values=(status, record["name"]), tags=tags)
                self.records[item] = record
                self.results.see(item)
                self.counters.set(f"{event['created']} created · {event['skipped']} skipped · {event['errors']} errors")
                # Show the first PNG automatically, then leave selection to the user.
                if len(self.records) == 1:
                    self.results.selection_set(item)
        elif kind in {"finished", "failed"}:
            self.running = False
            self.progress.stop()
            self.set_busy(False)
            if kind == "failed":
                self.status.set("Could not finish: " + event["message"])
                self.progress.configure(value=0, style="Error.Horizontal.TProgressbar")
                self.handle({"kind": "log", "message": event["message"], "error": True})
            else:
                report = event["report"]
                self.report_path = event["report_path"]
                if self.report_path:
                    self.report_button.configure(state="normal")
                errors = len(report["errors"])
                self.counters.set(f"{report['created']} created · {report['skipped']} skipped · {errors} errors")
                if report["cancelled"]:
                    self.status.set("Stopped. Completed PNGs are kept. Convert again to continue.")
                elif errors:
                    self.status.set("Could not export every image. The log lists the specific errors.")
                    self.show_view("log")
                    self.progress.configure(style="Error.Horizontal.TProgressbar")
                    if report.get("missing_metadata"):
                        self.missing_metadata_popup(force=True)
                elif not self.records:
                    self.status.set("No images matched. Clear the name filter in Options and try again.")
                elif self.dry_run:
                    self.status.set(f"Check complete: {len(self.records)} images ready. Press Convert to export them.")
                else:
                    self.status.set("Done! Select an image to preview it, or open the output folder.")
                if not report["cancelled"] and not errors:
                    self.progress.configure(value=100)
                self.start_button.focus_set()

    def preview_result(self, _=None):
        selected = self.results.selection()
        if not selected:
            return
        record = self.records.get(selected[0], {})
        self.detail.configure(text=record.get("error") or record.get("output") or record.get("name", ""))
        if record.get("status") in {"created", "skipped"}:
            self.show_preview(record["output"], "Restored image")
        elif record.get("status") == "validated":
            self.show_preview(record["atlas"], "Atlas preview · file check passed")

    def show_preview(self, path, label):
        self.preview_path = str(path)
        self.preview_label.set(label)
        self.redraw_preview()

    def clear_preview(self):
        self.preview_path = None
        self.preview_label.set("Preview")
        self.preview_caption.configure(text="Your atlas appears here once you add it.")
        self.redraw_preview()

    def redraw_preview(self, _=None):
        p = self.palette
        width, height = self.preview.winfo_width(), self.preview.winfo_height()
        self.preview.delete("all")
        if width < 10 or height < 10:
            return
        if not self.preview_path:
            middle = height / 2
            if self.mark_photo:
                self.preview.create_image(width / 2, middle - 22, image=self.mark_photo)
                middle += self.mark_photo.height() / 2
            self.preview.create_text(width / 2, middle, text="Atlas in, original images out", fill=p["text"],
                                     font=(FONT, 12, "bold"), justify="center", width=max(100, width - 40))
            self.preview.create_text(width / 2, middle + 24, text="Add your files on the left to get started",
                                     fill=p["muted"], font=(FONT, 10), justify="center", width=max(100, width - 40))
            return
        # Checkerboard makes transparent areas visible.
        for y in range(0, height, 16):
            for x in range(0, width, 16):
                self.preview.create_rectangle(x, y, x + 16, y + 16, outline="",
                                              fill=p["check_a"] if (x // 16 + y // 16) % 2 else p["check_b"])
        try:
            with Image.open(self.preview_path) as source:
                dimensions = source.size
                image = source.convert("RGBA")
                image.thumbnail((max(1, width - 24), max(1, height - 24)), Image.Resampling.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image, master=self.root)
            self.preview.create_image(width / 2, height / 2, image=self.preview_photo)
            self.preview_caption.configure(text=f"{Path(self.preview_path).name}  ·  {dimensions[0]} × {dimensions[1]} px")
        except (OSError, ValueError) as exc:
            self.preview.create_text(width / 2, height / 2, text="Preview unavailable", fill=p["muted"])
            self.preview_caption.configure(text=str(exc))

    def open_output(self):
        path = Path(self.output.get()).expanduser()
        if path.is_dir():
            try:
                open_path(path)
            except OSError as exc:
                self.status.set(str(exc))
        else:
            self.status.set("The output folder will be created when you convert images.")

    def open_report(self):
        if self.report_path:
            try:
                open_path(self.report_path)
            except OSError as exc:
                self.status.set(str(exc))

    def open_result(self, _=None):
        selected = self.results.selection()
        if selected:
            record = self.records.get(selected[0], {})
            path = record.get("output")
            if path and Path(path).is_file():
                try:
                    open_path(path)
                except OSError as exc:
                    self.status.set(str(exc))

    def close(self):
        if self.running:
            self.closing = True
            self.stop()
            self.status.set("Stopping safely before closing…")
        else:
            self.destroy()

    def destroy(self):
        if self.poll_after:
            try:
                self.root.after_cancel(self.poll_after)
            except tk.TclError:
                pass
        self.root.destroy()


def make_root():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            # Group the taskbar button under MagicUndicer's own icon, not Python's.
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MagicUndicer")
        except (AttributeError, OSError):
            pass
    try:
        from tkinterdnd2 import TkinterDnD
        return TkinterDnD.Tk()
    except (ImportError, RuntimeError, tk.TclError):
        return tk.Tk()


def main():
    root = make_root()
    App(root, sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()
