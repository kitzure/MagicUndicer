"""Local desktop interface. Workers publish events; only Tk's thread edits widgets."""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .cli import IMAGE_TYPES, run

from .interface import BG, TEXT, MUTED, ACCENT


def open_path(path):
    path = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(path)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])


class App:
    def __init__(self, root, inputs=()):
        self.root = root
        root.title("MagicUndicer")
        root.geometry("1060x820+40+40")
        root.minsize(940, 700)
        root.configure(bg=BG)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.running = False
        self.closing = False
        self.paths = []
        self.records = {}
        self.report_path = None
        self.preview_path = None
        self.preview_photo = None
        self.locked_widgets = []
        self.input_paths = {}
        self.warned_missing = False
        self.options_dialog = None
        self.warning_after = None
        base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
        self.output = tk.StringVar(value=str(base / "undiced"))
        self.pattern = tk.StringVar()
        self.trim = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Add an export folder, or atlas images and their MonoBehaviour JSON.")
        self.counters = tk.StringVar(value="0 created    0 skipped    0 errors")
        self.queue_label = tk.StringVar(value="Inputs · 0 selected")
        self.readiness = tk.StringVar(value="Add an atlas and its matching MonoBehaviour JSON.")
        self.options_summary = tk.StringVar(value="Original dimensions · skip existing files")
        self.preview_label = tk.StringVar(value="Image preview")
        self._styles()
        self._build()
        self.add_paths(inputs)
        for variable in (self.trim, self.overwrite, self.pattern):
            variable.trace_add("write", self.update_options_summary)
        for widget in self.locked_widgets:
            widget.bind("<FocusIn>", self.reveal_control, add="+")
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Control-o>", lambda _: self.add_files())
        root.bind("<Escape>", lambda _: self.stop())
        self.poll_after = root.after(80, self.poll)

    def _styles(self):
        from .interface import styles
        styles(self.root)

    def button(self, parent, text, command, primary=False, lock=True):
        widget = ttk.Button(parent, text=text, command=command,
                            style="Primary.TButton" if primary else "TButton")
        if lock:
            self.locked_widgets.append(widget)
        return widget

    def _build(self):
        from .interface import build
        build(self)

    def add_paths(self, paths):
        if self.running:
            return
        existing = {str(Path(p).resolve()).casefold() for p in self.paths}
        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if str(path).casefold() in existing:
                continue
            self.paths.append(str(path))
            existing.add(str(path).casefold())
            kind = "Folder" if path.is_dir() else ("JSON" if path.suffix.casefold() in {".json", ".txt"} else "Atlas")
            item = self.inputs.insert("", "end", values=(kind, path.name))
            self.input_paths[item] = str(path)
        self.update_readiness()
        images, metadata, folders = self.input_counts()
        if images and not metadata and not folders and not self.warned_missing:
            self.warned_missing = True
            self.warning_after = self.root.after_idle(self.missing_metadata_popup)

    def input_counts(self):
        images = sum(Path(p).suffix.casefold() in IMAGE_TYPES and not Path(p).is_dir() for p in self.paths)
        metadata = sum(Path(p).suffix.casefold() in {".json", ".txt"} and not Path(p).is_dir() for p in self.paths)
        folders = sum(Path(p).is_dir() for p in self.paths)
        return images, metadata, folders

    def update_readiness(self):
        images, metadata, folders = self.input_counts()
        self.queue_label.set(f"{images} atlas images · {metadata} JSON files" + (f" · {folders} folders" if folders else ""))
        if metadata or folders:
            self.warned_missing = False
        if folders:
            self.readiness.set("The export folder will be checked for atlases and MonoBehaviour JSON.")
            self.readiness_label.configure(style="Hint.TLabel")
        elif images and not metadata:
            self.readiness.set("MonoBehaviour JSON is missing. Add the matching JSON to continue.")
            self.readiness_label.configure(style="Warning.TLabel")
        elif images and metadata:
            self.readiness.set("Atlas + JSON selected. Ready to check or undice.")
            self.readiness_label.configure(style="Good.TLabel")
        elif metadata:
            self.readiness.set("JSON selected. Add the atlas images it references, or import their export folder.")
            self.readiness_label.configure(style="Hint.TLabel")
        else:
            self.readiness.set("Add an atlas and its matching MonoBehaviour JSON.")
            self.readiness_label.configure(style="Hint.TLabel")
            self.warned_missing = False

    def missing_metadata_popup(self, force=False):
        images, metadata, folders = self.input_counts()
        if not force and (not images or metadata or folders):
            return
        self.status.set("MonoBehaviour JSON required — add the metadata to continue.")
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0, style="Error.Horizontal.TProgressbar")
        messagebox.showerror("MonoBehaviour JSON required",
            "You need the matching MonoBehaviour JSON to undice these images.\n\n"
            "A PNG or JPEG alone does not contain the tile order or original image sizes.\n\n"
            "Click Add JSON and select the MonoBehaviour exported by AssetStudio, "
            "or import an export folder containing both the atlas images and JSON.", parent=self.root)
        self.metadata_button.focus_set()

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
        self.options_summary.set(("Trim borders" if self.trim.get() else "Original dimensions") +
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
        dialog.title("Export options")
        dialog.configure(bg="white")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, style="Panel.TFrame", padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Export options", style="Heading.TLabel").pack(anchor="w", pady=(0, 10))
        first = ttk.Checkbutton(frame, text="Trim transparent borders", variable=self.trim)
        first.pack(anchor="w")
        ttk.Checkbutton(frame, text="Replace existing PNGs", variable=self.overwrite).pack(anchor="w")
        ttk.Label(frame, text="Only image names containing", style="Hint.TLabel").pack(anchor="w", pady=(12, 5))
        ttk.Entry(frame, textvariable=self.pattern, width=35).pack(fill="x")
        ttk.Label(frame, text="Leave blank to export every image.", style="Hint.TLabel").pack(anchor="w", pady=(5, 14))
        def close_dialog(*_):
            dialog.grab_release()
            dialog.destroy()
            self.options_dialog = None
            self.options_button.focus_set()
        ttk.Button(frame, text="Done", command=close_dialog, style="Primary.TButton").pack(fill="x")
        dialog.protocol("WM_DELETE_WINDOW", close_dialog)
        dialog.bind("<Escape>", close_dialog)
        dialog.bind("<Return>", close_dialog)
        dialog.geometry(f"+{self.root.winfo_rootx()+70}+{self.root.winfo_rooty()+110}")
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

    def remove_selected(self):
        if self.running:
            return
        for item in self.inputs.selection():
            path = self.input_paths.pop(item)
            self.paths.remove(path)
            self.inputs.delete(item)
        self.update_readiness()

    def choose_output(self):
        folder = filedialog.askdirectory(parent=self.root, title="Choose where to save restored images")
        if folder:
            self.output.set(folder)

    def start(self, dry_run=False):
        if self.running:
            return
        if not self.paths:
            self.status.set("Add a folder, or atlas images and their MonoBehaviour JSON, before starting.")
            self.inputs.focus_set()
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
        self.counters.set("0 created    0 skipped    0 errors")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        for widget in self.locked_widgets:
            widget.configure(state="disabled")
        self.stop_button.configure(state="normal")
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
            self.stop_button.configure(state="disabled")
            self.status.set("Stopping after the current image. Completed PNGs will be kept.")

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
                self.status.set(f"{event['source']} — {event['current']} / {event['total']} images in this source")
            if kind == "item":
                record = event["record"]
                status = {"created": "Created", "skipped": "Skipped", "validated": "Ready", "error": "Error"}[record["status"]]
                item = self.results.insert("", "end", values=(status, record["name"]))
                self.records[item] = record
                self.results.see(item)
                self.counters.set(f"{event['created']} created    {event['skipped']} skipped    {event['errors']} errors")
                # Show the first PNG automatically, then leave selection to the user.
                if len(self.records) == 1:
                    self.results.selection_set(item)
        elif kind in {"finished", "failed"}:
            self.running = False
            self.progress.stop()
            self.stop_button.configure(state="disabled")
            for widget in self.locked_widgets:
                widget.configure(state="normal")
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
                self.counters.set(f"{report['created']} created    {report['skipped']} skipped    {errors} errors")
                if report["cancelled"]:
                    self.status.set("Stopped. Completed PNGs are kept. Run again to continue.")
                elif errors:
                    self.status.set("Could not export every image. Open the Activity log for the specific errors.")
                    self.notebook.select(1)
                    self.progress.configure(style="Error.Horizontal.TProgressbar")
                    if report.get("missing_metadata"):
                        self.missing_metadata_popup(force=True)
                elif not self.records:
                    self.status.set("No images matched. Clear the name filter in Export options and try again.")
                elif self.dry_run:
                    self.status.set(f"Check complete: {len(self.records)} images ready. Click Undice images to export them.")
                else:
                    self.status.set("Finished. Select an image to preview it, or open the output folder.")
                if not report["cancelled"] and not errors:
                    self.progress.configure(value=100)
                self.start_button.focus_set()

    def preview_input(self, _=None):
        selected = self.inputs.selection()
        if selected:
            path = Path(self.input_paths[selected[-1]])
            if path.suffix.casefold() in IMAGE_TYPES:
                self.show_preview(path, "Atlas preview")

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

    def redraw_preview(self, _=None):
        width, height = self.preview.winfo_width(), self.preview.winfo_height()
        self.preview.delete("all")
        if width < 10 or height < 10:
            return
        if not self.preview_path:
            self.preview.create_text(width / 2, height / 2, text="Atlas → original images\n\nAdd your files to get started", fill=MUTED,
                                     font=("Segoe UI", 13), justify="center", width=max(100, width-40))
            return
        # Checkerboard makes transparent areas visible.
        for y in range(0, height, 18):
            for x in range(0, width, 18):
                self.preview.create_rectangle(x, y, x + 18, y + 18, fill="#e3e9e5" if (x // 18 + y // 18) % 2 else "#f8faf8", outline="")
        try:
            with Image.open(self.preview_path) as source:
                dimensions = source.size
                image = source.convert("RGBA")
                image.thumbnail((max(1, width - 20), max(1, height - 20)), Image.Resampling.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image, master=self.root)
            self.preview.create_image(width / 2, height / 2, image=self.preview_photo)
            self.preview_caption.configure(text=f"{Path(self.preview_path).name}\n{dimensions[0]} × {dimensions[1]} pixels")
        except (OSError, ValueError) as exc:
            self.preview.create_text(width / 2, height / 2, text="Preview unavailable", fill=MUTED)
            self.preview_caption.configure(text=str(exc))

    def open_output(self):
        path = Path(self.output.get()).expanduser()
        if path.is_dir():
            try:
                open_path(path)
            except OSError as exc:
                self.status.set(str(exc))
        else:
            self.status.set("The output folder will be created when you undice images.")

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
        for callback in (self.poll_after, self.warning_after):
            if callback:
                try:
                    self.root.after_cancel(callback)
                except tk.TclError:
                    pass
        self.root.destroy()


def make_root():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
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
