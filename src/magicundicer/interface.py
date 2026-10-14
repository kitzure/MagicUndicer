"""Desktop layout, palettes and styles for the atlas reconstruction workflow."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

ASSETS = Path(__file__).with_name("assets")
FONT = "Segoe UI"
CONVERT = "✦  Convert"

# Colours come from the logo: navy wordmark, teal tiles and the gold star.
THEMES = {
    "light": {
        "dark": False,
        "bg": "#EDF3F3", "surface": "#FFFFFF", "surface_alt": "#F3F8F8", "hover": "#E4F0F0",
        "border": "#D2E1E1", "text": "#0A2E3A", "muted": "#587480",
        "accent": "#0E7C7B", "accent_hover": "#0A6564", "accent_text": "#FFFFFF", "accent_soft": "#D3EEEC",
        "gold": "#E89B0C", "warn": "#9A6100", "danger": "#C0392B", "danger_soft": "#FBE5E2",
        "danger_hover": "#F6D2CD", "check_a": "#E3ECEC", "check_b": "#F7FAFA",
        "disabled_bg": "#DCE7E7", "disabled_fg": "#8399A2",
    },
    "dark": {
        "dark": True,
        "bg": "#0A1C23", "surface": "#10272F", "surface_alt": "#15323C", "hover": "#1A3C47",
        "border": "#22454F", "text": "#E3F1F1", "muted": "#8EA9B1",
        "accent": "#2DB5B2", "accent_hover": "#4CCAC7", "accent_text": "#03222A", "accent_soft": "#174A50",
        "gold": "#FBB532", "warn": "#FBB532", "danger": "#FF7A6B", "danger_soft": "#3E2328",
        "danger_hover": "#4C2B31", "check_a": "#183640", "check_b": "#122C35",
        "disabled_bg": "#1A3640", "disabled_fg": "#5E7E87",
    },
}
# File rows restyle themselves through these prefixes ("Hover.Row.TFrame", ...).
ROW_STATES = {"": "surface_alt", "Hover.": "hover", "Selected.": "accent_soft"}


def load_image(name, height=None):
    try:
        with Image.open(ASSETS / name) as source:
            image = source.convert("RGBA")
    except OSError:
        return None
    if height:
        image = image.resize((max(1, round(image.width * height / image.height)), height), Image.Resampling.LANCZOS)
    return image


def shorten(text, limit=38):
    return text if len(text) <= limit else text[:limit - 13] + "…" + text[-12:]


def style_titlebar(window, palette):
    """Match the Windows title bar to the theme; ignored where unsupported."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        def colorref(value):
            return ctypes.c_int(int(value[5:7], 16) << 16 | int(value[3:5], 16) << 8 | int(value[1:3], 16))
        # 20: dark mode (Windows 10+), 35/36: caption and title colours (Windows 11).
        for attribute, value in ((20, ctypes.c_int(palette["dark"])), (35, colorref(palette["bg"])),
                                 (36, colorref(palette["text"]))):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value))
    except (AttributeError, OSError, tk.TclError):
        pass


def styles(root, p):
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", font=(FONT, 10), background=p["bg"], foreground=p["text"], bordercolor=p["border"],
                lightcolor=p["bg"], darkcolor=p["bg"], troughcolor=p["surface_alt"], focuscolor=p["accent"],
                selectbackground=p["accent_soft"], selectforeground=p["text"], fieldbackground=p["surface"],
                insertcolor=p["text"], arrowcolor=p["muted"])
    s.configure("TFrame", background=p["bg"])
    s.configure("Panel.TFrame", background=p["surface"])
    s.configure("TLabel", background=p["bg"], foreground=p["text"])
    s.configure("Muted.TLabel", foreground=p["muted"])
    s.configure("Title.TLabel", font=(FONT, 20, "bold"))
    s.configure("Panel.TLabel", background=p["surface"])
    s.configure("Heading.TLabel", background=p["surface"], font=(FONT, 11, "bold"))
    s.configure("Step.TLabel", background=p["accent"], foreground=p["accent_text"], font=(FONT, 9, "bold"), padding=(7, 1))
    s.configure("Hint.TLabel", background=p["surface"], foreground=p["muted"], font=(FONT, 9))
    s.configure("Warning.TLabel", background=p["surface"], foreground=p["warn"], font=(FONT, 9, "bold"))
    s.configure("Good.TLabel", background=p["surface"], foreground=p["accent"], font=(FONT, 9, "bold"))

    for prefix, key in ROW_STATES.items():
        bg = p[key]
        s.configure(prefix + "Row.TFrame", background=bg)
        s.configure(prefix + "RowName.TLabel", background=bg, foreground=p["text"])
        s.configure(prefix + "RowMeta.TLabel", background=bg, foreground=p["muted"], font=(FONT, 9))
        s.configure(prefix + "RowWarn.TLabel", background=bg, foreground=p["warn"], font=(FONT, 9))
        s.configure(prefix + "RowGlyph.TLabel", background=bg, foreground=p["accent"], font=(FONT, 13))
        s.configure(prefix + "RowJson.TLabel", background=bg, foreground=p["gold"], font=(FONT, 10, "bold"))
        flat_button(s, p, prefix + "Remove.TButton", bg, p["muted"], p["danger_soft"], hover_fg=p["danger"],
                    padding=(6, 2), font=(FONT, 10), disabled_bg=bg)

    flat_button(s, p, "TButton", p["surface_alt"], p["text"], p["hover"], border=p["border"], padding=(12, 6))
    flat_button(s, p, "Primary.TButton", p["accent"], p["accent_text"], p["accent_hover"], padding=(16, 11),
                font=(FONT, 11, "bold"), focuscolor=p["accent_hover"])
    flat_button(s, p, "Stop.TButton", p["danger_soft"], p["danger"], p["danger_hover"], padding=(16, 11),
                font=(FONT, 11, "bold"), focuscolor=p["danger"])
    flat_button(s, p, "Ghost.TButton", p["surface"], p["text"], p["hover"], border=p["border"], padding=(12, 6),
                disabled_bg=p["surface"])
    flat_button(s, p, "Link.TButton", p["surface"], p["accent"], p["surface"], hover_fg=p["accent_hover"],
                padding=(0, 4), disabled_bg=p["surface"])

    s.configure("TEntry", fieldbackground=p["surface_alt"], foreground=p["text"], bordercolor=p["border"],
                lightcolor=p["surface_alt"], darkcolor=p["surface_alt"], insertcolor=p["text"], padding=(8, 6))
    s.map("TEntry", bordercolor=[("focus", p["accent"])], lightcolor=[("focus", p["accent"])],
          fieldbackground=[("disabled", p["disabled_bg"])], foreground=[("disabled", p["disabled_fg"])])

    s.configure("Treeview", background=p["surface"], fieldbackground=p["surface"], foreground=p["text"],
                rowheight=28, borderwidth=0, bordercolor=p["surface"], lightcolor=p["surface"], darkcolor=p["surface"])
    s.map("Treeview", background=[("selected", p["accent_soft"])], foreground=[("selected", p["text"])])
    s.configure("Treeview.Heading", background=p["surface"], foreground=p["muted"], font=(FONT, 9, "bold"),
                relief="flat", borderwidth=0, bordercolor=p["border"], lightcolor=p["surface"],
                darkcolor=p["surface"], padding=(8, 4))
    s.map("Treeview.Heading", background=[("active", p["surface"])])

    # Slim, arrowless scrollbars.
    for orient in ("Vertical", "Horizontal"):
        s.layout(orient + ".TScrollbar", [(orient + ".Scrollbar.trough", {"sticky": "nswe", "children": [
            (orient + ".Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    s.configure("TScrollbar", background=p["border"], troughcolor=p["surface"], bordercolor=p["surface"],
                lightcolor=p["border"], darkcolor=p["border"], arrowsize=8, gripsize=0)
    s.map("TScrollbar", background=[("active", p["muted"])], lightcolor=[("active", p["muted"])],
          darkcolor=[("active", p["muted"])])

    # Clam's bar cannot be made thin, so borrow the flat elements of the default theme.
    if "Flat.Progressbar.pbar" not in s.element_names():
        s.element_create("Flat.Progressbar.trough", "from", "default")
        s.element_create("Flat.Progressbar.pbar", "from", "default")
    s.layout("Horizontal.TProgressbar", [("Flat.Progressbar.trough", {"sticky": "nswe", "children": [
        ("Flat.Progressbar.pbar", {"side": "left", "sticky": "ns"})]})])
    s.configure("Horizontal.TProgressbar", background=p["accent"], troughcolor=p["border"], thickness=6,
                borderwidth=0, troughborderwidth=0, troughrelief="flat", pbarrelief="flat")
    s.configure("Error.Horizontal.TProgressbar", background=p["danger"], troughcolor=p["danger_soft"])

    s.configure("TCheckbutton", background=p["surface"], foreground=p["text"], indicatorbackground=p["surface_alt"],
                indicatorforeground=p["accent_text"], upperbordercolor=p["border"], lowerbordercolor=p["border"],
                padding=(0, 4))
    s.map("TCheckbutton", background=[("active", p["surface"])],
          indicatorbackground=[("selected", p["accent"]), ("pressed", p["hover"])])

    s.configure("Seg.Toolbutton", background=p["surface"], foreground=p["muted"], padding=(12, 5),
                bordercolor=p["surface"], lightcolor=p["surface"], darkcolor=p["surface"], relief="flat")
    s.map("Seg.Toolbutton", background=[("selected", p["accent_soft"]), ("active", p["hover"])],
          foreground=[("selected", p["text"]), ("active", p["text"])],
          lightcolor=[("selected", p["accent_soft"]), ("active", p["hover"])],
          darkcolor=[("selected", p["accent_soft"]), ("active", p["hover"])],
          bordercolor=[("selected", p["accent_soft"]), ("active", p["hover"])],
          relief=[("selected", "flat"), ("pressed", "flat"), ("active", "flat")])


def flat_button(s, p, name, bg, fg, hover, border=None, hover_fg=None, disabled_bg=None, **options):
    border = border or bg
    disabled_bg = disabled_bg or p["disabled_bg"]
    s.configure(name, background=bg, foreground=fg, bordercolor=border, lightcolor=bg, darkcolor=bg,
                relief="flat", **options)
    # Clam bevels with light/dark colours; keeping them equal to the fill makes the button flat.
    fill = [("disabled", disabled_bg), ("pressed", hover), ("active", hover)]
    s.map(name, background=fill, lightcolor=fill, darkcolor=fill,
          bordercolor=fill if border == bg else [("disabled", border)],
          foreground=[("disabled", p["disabled_fg"]), ("active", hover_fg or fg)])


class AutoScrollbar(ttk.Scrollbar):
    """A scrollbar that only takes space while there is something to scroll."""

    def set(self, first, last):
        if float(first) <= 0 and float(last) >= 1:
            self.grid_remove()
        else:
            self.grid()
        super().set(first, last)


class DropZone(tk.Canvas):
    """Dashed click-or-drop target shown while a file list is empty."""

    def __init__(self, app, parent, title, hint, command):
        super().__init__(parent, height=96, highlightthickness=0, borderwidth=0, takefocus=1, cursor="hand2")
        self.app, self.title, self.hint = app, title, hint
        self.hover = self.focused = False
        self.bind("<Configure>", self.draw)
        self.bind("<Enter>", lambda _: self.set_state(hover=True))
        self.bind("<Leave>", lambda _: self.set_state(hover=False))
        self.bind("<FocusIn>", lambda _: self.set_state(focused=True))
        self.bind("<FocusOut>", lambda _: self.set_state(focused=False))
        for sequence in ("<Button-1>", "<Return>", "<space>"):
            self.bind(sequence, lambda _: command())

    def set_state(self, **values):
        for key, value in values.items():
            setattr(self, key, value)
        self.draw()

    def draw(self, _=None):
        p = self.app.palette
        active = (self.hover or self.focused) and not self.app.running
        self.configure(background=p["surface"])
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        if width < 20 or height < 20:
            return
        self.create_rectangle(1, 1, width - 2, height - 2, dash=(5, 3), width=1,
                              outline=p["accent"] if active else p["border"],
                              fill=p["accent_soft"] if active else p["surface_alt"])
        self.create_text(width / 2, height / 2 - 11, text="+  " + self.title, fill=p["text"], font=(FONT, 10, "bold"))
        self.create_text(width / 2, height / 2 + 12, text=self.hint, fill=p["muted"], font=(FONT, 9),
                         width=max(80, width - 24), justify="center")


class FileRow(ttk.Frame):
    """One selected file with its details and a remove (✕) button."""

    def __init__(self, section, path, glyph, glyph_style, name, meta, warn=False, clickable=False):
        super().__init__(section.list, style="Row.TFrame")
        self.app, self.path, self.glyph_style, self.warn = section.app, path, glyph_style, warn
        self.hover = False
        self.columnconfigure(1, weight=1)
        self.glyph = ttk.Label(self, text=glyph, width=3, anchor="center")
        self.glyph.grid(row=0, column=0, rowspan=2, padx=(8, 4))
        self.name = ttk.Label(self, text=shorten(name))
        self.name.grid(row=0, column=1, sticky="sw", pady=(7, 0))
        self.meta = ttk.Label(self, text=meta)
        self.meta.grid(row=1, column=1, sticky="nw", pady=(0, 7))
        self.remove = ttk.Button(self, text="✕", width=2, command=lambda: self.app.remove_path(path))
        self.remove.grid(row=0, column=2, rowspan=2, padx=(4, 8))
        if self.app.running:
            self.remove.configure(state="disabled")
        for widget in (self, self.glyph, self.name, self.meta, self.remove):
            widget.bind("<Enter>", self.enter)
            widget.bind("<Leave>", self.leave)
        if clickable:
            for widget in (self, self.glyph, self.name, self.meta):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _: self.app.select_input(path))
        self.restyle()

    def enter(self, _):
        self.hover = True
        self.restyle()

    def leave(self, event):
        try:
            inside = self.winfo_containing(event.x_root, event.y_root)
        except (KeyError, tk.TclError):
            inside = None
        while inside is not None and inside is not self:
            inside = getattr(inside, "master", None)
        if inside is not self:
            self.hover = False
            self.restyle()

    def restyle(self):
        prefix = "Selected." if self.app.selected_input == self.path else ("Hover." if self.hover else "")
        self.configure(style=prefix + "Row.TFrame")
        self.glyph.configure(style=prefix + self.glyph_style + ".TLabel")
        self.name.configure(style=prefix + "RowName.TLabel")
        self.meta.configure(style=prefix + ("RowWarn" if self.warn else "RowMeta") + ".TLabel")
        self.remove.configure(style=prefix + "Remove.TButton")


class FileSection:
    """A numbered step: an empty drop zone, or the chosen files with ✕ buttons."""

    def __init__(self, app, parent, row, step, title, empty_title, empty_hint, command):
        self.app = app
        self.frame = ttk.Frame(parent, style="Panel.TFrame")
        self.frame.grid(row=row, column=0, sticky="ew", pady=(0, 20))
        self.frame.columnconfigure(0, weight=1)
        head = ttk.Frame(self.frame, style="Panel.TFrame")
        head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(head, text=step, style="Step.TLabel").pack(side="left")
        ttk.Label(head, text=title, style="Heading.TLabel").pack(side="left", padx=(8, 0))
        self.add = ttk.Button(head, text="+ Add more", style="Link.TButton", command=command)
        self.zone = DropZone(app, self.frame, empty_title, empty_hint, command)
        self.list = ttk.Frame(self.frame, style="Panel.TFrame")
        self.list.columnconfigure(0, weight=1)
        self.rows = []
        self.render([])

    @property
    def buttons(self):
        return [self.add] + [row.remove for row in self.rows]

    def render(self, items):
        for row in self.rows:
            row.destroy()
        self.rows = [FileRow(self, **item) for item in items]
        for index, row in enumerate(self.rows):
            row.grid(row=index, column=0, sticky="ew", pady=(0 if index == 0 else 6, 0))
        if items:
            self.zone.grid_remove()
            self.list.grid(row=1, column=0, sticky="ew")
            self.add.pack(side="right")
            self.add.configure(state="disabled" if self.app.running else "normal")
        else:
            self.list.grid_remove()
            self.add.pack_forget()
            self.zone.grid(row=1, column=0, sticky="ew")

    def restyle(self):
        for row in self.rows:
            row.restyle()

    def focus(self):
        (self.add if self.rows else self.zone).focus_set()


def build(app):
    root = app.root
    scale = root.winfo_fpixels("1i") / 96
    icon = load_image("icon.png")
    if icon:
        app.icon_photo = ImageTk.PhotoImage(icon.resize((64, 64), Image.Resampling.LANCZOS), master=root)
        root.iconphoto(True, app.icon_photo)
        app.mark_photo = ImageTk.PhotoImage(icon.resize((round(72 * scale),) * 2, Image.Resampling.LANCZOS), master=root)
    else:
        app.mark_photo = None
    app.can_drop = False
    try:
        from tkinterdnd2 import DND_FILES
        root.drop_target_register(DND_FILES)
        root.dnd_bind("<<Drop>>", app.drop)
        app.can_drop = True
    except (ImportError, AttributeError, tk.TclError):
        pass

    main = ttk.Frame(root, padding=(24, 18, 24, 16))
    main.pack(fill="both", expand=True)
    main.columnconfigure(0, weight=1)
    main.rowconfigure(1, weight=1)

    header = ttk.Frame(main)
    header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
    header.columnconfigure(0, weight=1)
    app.logo_label = ttk.Label(header)
    app.logo_label.grid(row=0, column=0, sticky="w")
    ttk.Label(header, text="Rebuild the original images from a diced atlas and its MonoBehaviour JSON.",
              style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 0))
    app.theme_button = ttk.Button(header, style="Ghost.TButton", command=app.toggle_theme)
    app.theme_button.grid(row=0, column=1, sticky="ne")

    workspace = ttk.Frame(main)
    workspace.grid(row=1, column=0, sticky="nsew")
    workspace.columnconfigure(1, weight=1)
    workspace.rowconfigure(0, weight=1)

    # Left: the two inputs scroll if needed; save + Convert stay pinned below.
    left_shell = ttk.Frame(workspace, style="Panel.TFrame", width=round(384 * scale))
    left_shell.grid(row=0, column=0, sticky="ns", padx=(0, 16))
    left_shell.grid_propagate(False)
    left_shell.columnconfigure(0, weight=1)
    left_shell.rowconfigure(0, weight=1)
    app.control_canvas = canvas = tk.Canvas(left_shell, highlightthickness=0, borderwidth=0)
    canvas.grid(row=0, column=0, sticky="nsew")
    control_scroll = AutoScrollbar(left_shell, command=canvas.yview)
    control_scroll.grid(row=0, column=1, sticky="ns")
    canvas.configure(yscrollcommand=control_scroll.set)
    left = ttk.Frame(canvas, style="Panel.TFrame", padding=(20, 20, 20, 4))
    inner = canvas.create_window(0, 0, window=left, anchor="nw")
    left.columnconfigure(0, weight=1)

    left.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(inner, width=e.width))

    drop = "Drop" if app.can_drop else "Click to add"
    app.atlas_section = FileSection(app, left, 0, "1", "Atlas image", f"{drop} your atlas image",
                                    ("or click to browse · " if app.can_drop else "") + "PNG, JPG, WebP, TGA, BMP, TIFF",
                                    app.add_images)
    app.json_section = FileSection(app, left, 1, "2", "MonoBehaviour JSON", f"{drop} the MonoBehaviour JSON",
                                   ("or click to browse · " if app.can_drop else "") + "the .json exported with the atlas",
                                   app.add_metadata)
    app.sections = (app.atlas_section, app.json_section)
    app.button(left, "Import a whole export folder instead", app.add_folder, style="Link.TButton").grid(
        row=2, column=0, sticky="w", pady=(0, 6))

    app.divider = tk.Frame(left_shell, height=1, borderwidth=0)
    app.divider.grid(row=1, column=0, columnspan=2, sticky="ew")
    bottom = ttk.Frame(left_shell, style="Panel.TFrame", padding=(20, 14, 20, 18))
    bottom.grid(row=2, column=0, columnspan=2, sticky="ew")
    bottom.columnconfigure(0, weight=1)
    ttk.Label(bottom, text="Save to", style="Hint.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    app.output_entry = ttk.Entry(bottom, textvariable=app.output)
    app.output_entry.grid(row=1, column=0, sticky="ew")
    app.locked_widgets.append(app.output_entry)
    app.button(bottom, "Browse…", app.choose_output).grid(row=1, column=1, padx=(8, 0))
    app.readiness_label = ttk.Label(bottom, textvariable=app.readiness, style="Hint.TLabel", wraplength=round(330 * scale))
    app.readiness_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 8))
    app.start_button = ttk.Button(bottom, text=CONVERT, style="Primary.TButton", command=app.primary_action)
    app.start_button.grid(row=3, column=0, columnspan=2, sticky="ew")
    options = ttk.Frame(bottom, style="Panel.TFrame")
    options.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    app.options_button = app.button(options, "Options", app.toggle_options, style="Link.TButton")
    app.options_button.pack(side="left")
    ttk.Label(options, textvariable=app.options_summary, style="Hint.TLabel").pack(side="left", padx=(10, 0))

    # Right: preview on top, results/log underneath.
    right = ttk.Frame(workspace, style="Panel.TFrame", padding=20)
    right.grid(row=0, column=1, sticky="nsew")
    right.columnconfigure(0, weight=1)
    right.rowconfigure(1, weight=3)
    right.rowconfigure(4, weight=2)
    ttk.Label(right, textvariable=app.preview_label, style="Heading.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
    app.preview = tk.Canvas(right, borderwidth=0, highlightthickness=0, height=240)
    app.preview.grid(row=1, column=0, sticky="nsew")
    app.preview.bind("<Configure>", app.redraw_preview)
    app.preview_caption = ttk.Label(right, text="Your atlas appears here once you add it.", style="Hint.TLabel")
    app.preview_caption.grid(row=2, column=0, sticky="w", pady=(8, 14))

    tabs = ttk.Frame(right, style="Panel.TFrame")
    tabs.grid(row=3, column=0, sticky="ew", pady=(0, 8))
    for text, value in (("Restored images", "results"), ("Log", "log")):
        ttk.Radiobutton(tabs, text=text, value=value, variable=app.view, style="Seg.Toolbutton",
                        command=app.show_view).pack(side="left", padx=(0, 4))
    ttk.Label(tabs, textvariable=app.counters, style="Hint.TLabel").pack(side="right")

    body = ttk.Frame(right, style="Panel.TFrame")
    body.grid(row=4, column=0, sticky="nsew")
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)
    app.results_frame = ttk.Frame(body, style="Panel.TFrame")
    app.log_frame = ttk.Frame(body, style="Panel.TFrame")
    for frame in (app.results_frame, app.log_frame):
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
    app.results = ttk.Treeview(app.results_frame, columns=("status", "name"), show="headings", selectmode="browse", height=4)
    app.results.heading("status", text="RESULT", anchor="w")
    app.results.heading("name", text="IMAGE", anchor="w")
    app.results.column("status", width=90, stretch=False)
    app.results.column("name", width=360)
    app.results.grid(row=0, column=0, sticky="nsew")
    result_scroll = AutoScrollbar(app.results_frame, command=app.results.yview)
    result_scroll.grid(row=0, column=1, sticky="ns")
    app.results.configure(yscrollcommand=result_scroll.set)
    app.results.bind("<<TreeviewSelect>>", app.preview_result)
    app.results.bind("<Double-1>", app.open_result)
    app.results.bind("<Return>", app.open_result)
    app.detail = ttk.Label(app.results_frame, text="Converted images are listed here. Double-click one to open it.",
                           style="Hint.TLabel")
    app.detail.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    app.log = tk.Text(app.log_frame, font=("Consolas", 10), state="disabled", wrap="word", relief="flat",
                      borderwidth=0, padx=10, pady=8, height=4)
    app.log.grid(row=0, column=0, sticky="nsew")
    log_scroll = AutoScrollbar(app.log_frame, command=app.log.yview)
    log_scroll.grid(row=0, column=1, sticky="ns")
    app.log.configure(yscrollcommand=log_scroll.set)
    app.show_view()

    footer = ttk.Frame(main)
    footer.grid(row=2, column=0, sticky="ew", pady=(14, 0))
    footer.columnconfigure(0, weight=1)
    app.progress = ttk.Progressbar(footer, maximum=100)
    app.progress.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
    app.status_label = ttk.Label(footer, textvariable=app.status, style="Muted.TLabel")
    app.status_label.grid(row=1, column=0, sticky="w")
    app.report_button = app.button(footer, "Open report", app.open_report, style="Ghost.TButton", lock=False)
    app.report_button.grid(row=1, column=1, padx=(8, 0))
    app.report_button.configure(state="disabled")
    app.button(footer, "Open output folder", app.open_output, style="Ghost.TButton", lock=False).grid(row=1, column=2, padx=(8, 0))

    main.bind("<Configure>", lambda e: app.status_label.configure(wraplength=max(100, e.width - 360)))
    right.bind("<Configure>", lambda e: (app.preview_caption.configure(wraplength=max(100, e.width - 40)),
                                       app.detail.configure(wraplength=max(100, e.width - 40))))
    if app.can_drop:
        for widget in (left, app.preview, *(s.zone for s in app.sections), *(s.list for s in app.sections)):
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<Drop>>", app.drop)

    def scroll_controls(event):
        if left.winfo_reqheight() <= canvas.winfo_height():
            return
        widget = event.widget
        while widget is not None:
            if widget is left_shell:
                canvas.yview_scroll(-int(event.delta / 120), "units")
                break
            widget = getattr(widget, "master", None)
    root.bind("<MouseWheel>", scroll_controls, add="+")


def apply_theme(app):
    p = app.palette
    root = app.root
    styles(root, p)
    root.configure(background=p["bg"])
    app.control_canvas.configure(background=p["surface"])
    app.divider.configure(background=p["border"])
    app.preview.configure(background=p["surface_alt"])
    app.log.configure(background=p["surface"], foreground=p["text"], insertbackground=p["text"],
                      selectbackground=p["accent_soft"], selectforeground=p["text"])
    app.log.tag_configure("error", foreground=p["danger"])
    app.results.tag_configure("error", foreground=p["danger"])
    app.results.tag_configure("skipped", foreground=p["muted"])
    logo = load_image("logo-dark.png" if p["dark"] else "logo-light.png", round(40 * root.winfo_fpixels("1i") / 96))
    if logo:
        app.logo_photo = ImageTk.PhotoImage(logo, master=root)
        app.logo_label.configure(image=app.logo_photo)
    else:
        app.logo_label.configure(text="MagicUndicer", style="Title.TLabel")
    app.theme_button.configure(text="☀  Light mode" if p["dark"] else "☾  Dark mode")
    for section in app.sections:
        section.zone.draw()
    if app.options_dialog and app.options_dialog.winfo_exists():
        app.options_dialog.configure(background=p["surface"])
        style_titlebar(app.options_dialog, p)
    style_titlebar(root, p)
    app.redraw_preview()
