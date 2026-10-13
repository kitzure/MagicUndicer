import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from magicundicer.cli import dropped_paths, run
from magicundicer.core import reconstruct, safe_name


def fixture(folder):
    """Forward-pack a known image into shuffled, padded bottom-origin tiles."""
    original = Image.new("RGBA", (7, 5))
    for y in range(5):
        for x in range(7):
            original.putpixel((x, y), (x * 31, y * 47, (x + y) * 19, 128 if x % 2 else 255))
    flipped = original.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    atlas = Image.new("RGBA", (12, 12), (255, 0, 255, 255))
    indices = [3, 1, 2, 0]
    for pos, index in enumerate(indices):
        piece = flipped.crop(((pos % 2) * 4, (pos // 2) * 4, (pos % 2 + 1) * 4, (pos // 2 + 1) * 4))
        atlas.paste(piece, ((index % 2) * 6 + 1, (index // 2) * 6 + 1))
    atlas = atlas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    atlas.save(folder / "sample_Atlas0.png")
    entry = {"name": "sprites/test", "atlasName": "sample_Atlas0", "width": 7, "height": 5, "cellIndexList": indices, "transparentIndex": -1}
    data = {"cellSize": 6, "padding": 1, "textureDataList": [entry]}
    (folder / "sample.json").write_text(json.dumps(data), encoding="utf-8")
    return atlas, original, data


class ReconstructionTests(unittest.TestCase):
    def test_shuffled_tiles_padding_orientation_partial_edges_and_alpha(self):
        with tempfile.TemporaryDirectory() as d:
            atlas, original, data = fixture(Path(d))
            result = reconstruct(atlas, data["textureDataList"][0], 6, 1)
            self.assertEqual(result.size, original.size)
            self.assertEqual(result.tobytes(), original.tobytes())

    def test_transparent_index(self):
        atlas = Image.new("RGBA", (4, 4), "red")
        entry = {"name": "blank", "width": 4, "height": 4, "cellIndexList": [-1], "transparentIndex": -1}
        self.assertEqual(reconstruct(atlas, entry, 4, 0).getchannel("A").getbbox(), None)

    def test_invalid_index_and_count(self):
        atlas = Image.new("RGBA", (4, 4))
        entry = {"name": "bad", "width": 4, "height": 4, "cellIndexList": [9]}
        with self.assertRaisesRegex(ValueError, "outside atlas"):
            reconstruct(atlas, entry, 4, 0)
        entry["cellIndexList"] = []
        with self.assertRaisesRegex(ValueError, "Expected 1"):
            reconstruct(atlas, entry, 4, 0)

    def test_bulk_continues_after_error_and_rerun_skips(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(d)
            _, original, _ = fixture(root)
            (root / "broken.json").write_text("{bad", encoding="utf-8")
            out = root / "out"
            self.assertEqual(run([str(root)], out), 1)
            png = next(out.rglob("*.png"))
            with Image.open(png) as actual:
                self.assertEqual(actual.tobytes(), original.tobytes())
            before = png.stat().st_mtime_ns
            self.assertEqual(run([str(root / "sample.json"), str(root / "sample_Atlas0.png")], out), 0)
            self.assertEqual(before, png.stat().st_mtime_ns)
            report = json.loads(sorted(out.glob("report-*.json"))[-1].read_text(encoding="utf-8"))
            self.assertEqual(report["skipped"], 1)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            root = Path(d)
            fixture(root)
            out = root / "out"
            self.assertEqual(run([str(root)], out, dry_run=True), 0)
            self.assertFalse(out.exists())

    def test_ambiguous_atlas_fails(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            root = Path(d)
            fixture(root)
            Image.new("RGBA", (12, 12)).save(root / "sample_Atlas0.webp")
            self.assertEqual(run([str(root)], root / "out"), 1)
            self.assertFalse(list((root / "out").rglob("*.png")))

    def test_sibling_assetstudio_folders(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            root = Path(d)
            fixture(root)
            mono, textures = root / "MonoBehaviour", root / "Texture2D"
            mono.mkdir(); textures.mkdir()
            (root / "sample.json").rename(mono / "sample.json")
            (root / "sample_Atlas0.png").rename(textures / "sample_Atlas0.png")
            self.assertEqual(run([str(root)], root / "out"), 0)

    def test_safe_names_and_drop_parser(self):
        self.assertEqual(safe_name("../../CON"), "_CON")
        self.assertEqual(safe_name("fg/a:b"), "a_b")
        self.assertEqual(dropped_paths('"D:\\some folder\\atlas.png" "D:\\meta.json"'), ["D:\\some folder\\atlas.png", "D:\\meta.json"])

    def test_identical_metadata_separate_exports(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
            root = Path(d)
            for name in ("first", "second"):
                folder = root / name
                folder.mkdir()
                fixture(folder)
            self.assertEqual(run([str(root)], root / "out"), 0)
            self.assertEqual(len(list((root / "out").rglob("*.png"))), 2)

    def test_events_and_safe_cancellation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, data = fixture(root)
            second = dict(data["textureDataList"][0], name="second")
            data["textureDataList"].append(second)
            (root / "sample.json").write_text(json.dumps(data), encoding="utf-8")
            events = []
            def receive(event):
                events.append(event)
            status = run([str(root)], root / "out", on_event=receive,
                         should_cancel=lambda: any(e["kind"] == "item" for e in events))
            self.assertEqual(status, 130)
            self.assertEqual(len(list((root / "out").rglob("*.png"))), 1)
            self.assertEqual(events[-1]["kind"], "finished")
            self.assertTrue(events[-1]["report"]["cancelled"])
            self.assertEqual(events[-1]["report"]["created"], 1)
            self.assertTrue(Path(events[-1]["report_path"]).is_file())

    def test_jpeg_atlas_supported(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            atlas, _, _ = fixture(root)
            atlas.convert("RGB").save(root / "sample_Atlas0.JPEG")
            (root / "sample_Atlas0.png").unlink()
            events = []
            self.assertEqual(run([str(root)], root / "out", on_event=events.append), 0)
            with Image.open(next((root / "out").rglob("*.png"))) as image:
                self.assertEqual(image.size, (7, 5))
            self.assertFalse(events[-1]["report"]["missing_metadata"])

    def test_explicit_pair_does_not_process_neighbor_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            neighbor = {"cellSize": 6, "padding": 1, "textureDataList": [{
                "name": "unwanted_character", "atlasName": "Other_Atlas0", "width": 4,
                "height": 4, "cellIndexList": [0], "transparentIndex": -1}]}
            (root / "Other.json").write_text(json.dumps(neighbor), encoding="utf-8")
            Image.new("RGBA", (12, 12), "blue").save(root / "Other_Atlas0.png")
            (root / "broken_neighbor.json").write_text("{broken", encoding="utf-8")
            events = []
            self.assertEqual(run([str(root / "sample_Atlas0.png"), str(root / "sample.json")],
                                 root / "out", on_event=events.append), 0)
            self.assertEqual([p.name for p in (root / "out").rglob("*.png")], ["test.png"])
            self.assertEqual(len(events[-1]["report"]["sources"]), 1)

    def test_one_selected_atlas_from_multi_atlas_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _, _, data = fixture(root)
            data["textureDataList"].append(dict(data["textureDataList"][0], name="other", atlasName="Other_Atlas0"))
            (root / "sample.json").write_text(json.dumps(data), encoding="utf-8")
            events = []
            self.assertEqual(run([str(root / "sample_Atlas0.png"), str(root / "sample.json")],
                                 root / "out", on_event=events.append), 0)
            self.assertEqual(events[-1]["report"]["excluded"], 1)
            self.assertEqual([p.name for p in (root / "out").rglob("*.png")], ["test.png"])

    def test_mismatched_selected_pair_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fixture(root)
            other = root / "Other_Atlas0.png"
            Image.new("RGBA", (12, 12)).save(other)
            events = []
            self.assertEqual(run([str(other), str(root / "sample.json")], root / "out", on_event=events.append), 1)
            self.assertIn("does not reference", events[-1]["report"]["errors"][0]["error"])
            self.assertFalse(list((root / "out").rglob("*.png")))


if __name__ == "__main__":
    unittest.main()
