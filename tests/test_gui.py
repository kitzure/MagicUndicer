import tempfile
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from test_undice import fixture


class GuiValidationTests(unittest.TestCase):
    def setUp(self):
        try:
            from magicundicer.gui import App, make_root
            self.root = make_root()
        except Exception as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.app = App(self.root)
        self.app.output.set(str(self.folder / "out"))

    def tearDown(self):
        if hasattr(self, "root"):
            self.app.close()
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def finish(self):
        deadline = time.monotonic() + 10
        while self.app.running and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.01)
        self.assertFalse(self.app.running)
        self.root.update()

    def test_png_only_popup_on_convert_and_no_output(self):
        fixture(self.folder)
        # Even a sibling JSON must be explicitly added for image-only GUI input.
        with patch("magicundicer.gui.messagebox.showerror") as popup:
            self.app.add_paths([self.folder / "sample_Atlas0.png"])
            self.root.update()
            popup.assert_not_called()
            self.app.start()
            popup.assert_called_once()
            self.assertEqual(popup.call_args.args[0], "MonoBehaviour JSON required")
            self.assertIn("matching MonoBehaviour JSON", popup.call_args.args[1])
            self.assertFalse(self.app.running)
            self.assertFalse((self.folder / "out").exists())
            self.assertEqual(len(self.app.paths), 1)
            self.app.add_paths([self.folder / "sample.json"])
            self.app.start(True)
            self.finish()
            self.assertIn("Check complete", self.app.status.get())

    def test_jpeg_only_warns_without_popup(self):
        image = self.folder / "atlas.JPEG"
        Image.new("RGB", (64, 64)).save(image)
        with patch("magicundicer.gui.messagebox.showerror") as popup:
            self.app.add_paths([image])
            self.root.update()
            popup.assert_not_called()
            self.assertIn("JSON is missing", self.app.readiness.get())
            self.assertEqual(self.app.selected_input, str(image.resolve()))

    def test_remove_button_drops_file(self):
        fixture(self.folder)
        self.app.add_paths([self.folder / "sample_Atlas0.png", self.folder / "sample.json"])
        self.assertIn("Ready", self.app.readiness.get())
        self.assertEqual(self.app.atlas_section.rows[0].meta.cget("text"), "12 × 12 px")
        self.assertEqual(self.app.json_section.rows[0].meta.cget("text"), "1 image")
        self.app.json_section.rows[0].remove.invoke()
        self.assertEqual(self.app.paths, [str((self.folder / "sample_Atlas0.png").resolve())])
        self.assertEqual(self.app.json_section.rows, [])
        self.assertIn("JSON is missing", self.app.readiness.get())
        self.app.atlas_section.rows[0].remove.invoke()
        self.assertEqual(self.app.paths, [])
        self.assertIsNone(self.app.preview_path)

    def test_unrelated_and_mismatched_json_are_flagged(self):
        fixture(self.folder)
        (self.folder / "IgnoreMe.json").write_text('{"foo": 1}', encoding="utf-8")
        other = self.folder / "Other_Atlas0.png"
        Image.new("RGBA", (12, 12)).save(other)
        self.app.add_paths([other, self.folder / "sample.json", self.folder / "IgnoreMe.json"])
        notes = [row.meta.cget("text") for row in self.app.json_section.rows]
        self.assertIn("not for the selected atlas", notes[0])
        self.assertIn("Not an atlas JSON", notes[1])
        self.assertIn("no selected JSON uses it", self.app.atlas_section.rows[0].meta.cget("text"))
        self.assertIn("may not belong together", self.app.readiness.get())

    def test_theme_toggle_is_saved(self):
        settings = self.folder / "settings.json"
        with patch("magicundicer.gui.SETTINGS_PATH", settings):
            before = self.app.theme_name
            self.app.toggle_theme()
            self.assertNotEqual(self.app.theme_name, before)
            self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), {"theme": self.app.theme_name})
            self.assertEqual(self.app.preview.cget("background"), self.app.palette["surface_alt"])

    def test_combined_drop_does_not_warn(self):
        _, _, other = fixture(self.folder)
        other["textureDataList"][0].update(name="unwanted_character", atlasName="Other_Atlas0")
        (self.folder / "Other.json").write_text(json.dumps(other), encoding="utf-8")
        Image.new("RGBA", (12, 12)).save(self.folder / "Other_Atlas0.png")
        with patch("magicundicer.gui.messagebox.showerror") as popup:
            self.app.add_paths([self.folder / "sample_Atlas0.png", self.folder / "sample.json"])
            self.root.update()
            popup.assert_not_called()
            self.app.start()
            self.finish()
            self.assertIn("1 created", self.app.counters.get())
            self.assertEqual([record["name"] for record in self.app.records.values()], ["sprites/test"])

    def test_folder_missing_metadata_popup_after_check(self):
        Image.new("RGB", (64, 64)).save(self.folder / "atlas.png")
        with patch("magicundicer.gui.messagebox.showerror") as popup:
            self.app.add_paths([self.folder])
            self.app.start(True)
            self.finish()
            popup.assert_called_once()
            self.assertEqual(float(self.app.progress.cget("value")), 0)
            self.assertFalse((self.folder / "out").exists())

    def test_options_dialog_retains_settings(self):
        self.app.toggle_options()
        self.assertIsNotNone(self.app.options_dialog)
        self.app.trim.set(True)
        self.app.pattern.set("expression")
        self.assertIn("Trim borders", self.app.options_summary.get())
        self.assertIn("expression", self.app.options_summary.get())
        self.app.options_dialog.event_generate("<Escape>")
        self.root.update()
