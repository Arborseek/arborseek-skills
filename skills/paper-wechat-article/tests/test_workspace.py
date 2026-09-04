import base64
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import paper_workspace as workspace

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVZkAAAAASUVORK5CYII=")


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="workspace 中文 ")
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "input.pdf"
        # A signature-only fixture tests file contracts, not PDF rendering.
        self.pdf.write_bytes(b"%PDF-1.4\nsynthetic contract fixture\n")
        self.image = self.root / "figure.png"
        self.image.write_bytes(PNG)
        self.dest = self.root / "paper"

    def tearDown(self):
        self.tmp.cleanup()

    def init(self):
        return workspace.init_workspace(self.pdf, self.dest, title="合成测试论文")

    def figure(self):
        return workspace.save_figure(self.dest, "figure-1", 1, "Fig. 1", "Synthetic fixture", image=self.image)

    def test_standalone_local_identity_and_no_claimed_reading(self):
        data = self.init()
        self.assertEqual(data["paper"]["source_url"], "urn:sha256:" + workspace.sha256(self.pdf))
        self.assertEqual(data["claims"], [])
        self.assertEqual(data["paper"]["read_scope"], "notes-only")

    def test_no_overwrite_workspace(self):
        self.init()
        before = (self.dest / workspace.MANIFEST).read_bytes()
        with self.assertRaises(FileExistsError):
            self.init()
        self.assertEqual(before, (self.dest / workspace.MANIFEST).read_bytes())

    def test_metadata_hash_mismatch_blocks_before_writing(self):
        metadata = self.root / "metadata.json"
        metadata.write_text(json.dumps({"kind": "pdf", "id": "1706.03762v1", "sha256": "wrong", "bytes": 1}))
        with self.assertRaises(ValueError):
            workspace.init_workspace(self.pdf, self.dest, metadata=metadata)
        self.assertFalse(self.dest.exists())

    def test_save_and_cache_does_not_auto_review(self):
        self.init()
        saved = self.figure()
        cached = self.figure()
        self.assertEqual(saved["status"], "saved")
        self.assertEqual(cached["status"], "cached")
        self.assertFalse(saved["figure"]["checked"])
        self.assertEqual(saved["figure"]["rights_status"], "unknown")
        self.assertEqual(len(workspace.load(self.dest)[0]["figures"]), 1)

    def test_repeated_figure_id_cannot_change_crop_or_caption(self):
        self.init()
        self.figure()
        with self.assertRaises(FileExistsError):
            workspace.save_figure(self.dest, "figure-1", 1, "Fig. 1", "Different", image=self.image)

    def test_move_directory_preserves_relative_assets(self):
        self.init()
        self.figure()
        moved = self.root / "搬迁后的资料"
        shutil.move(self.dest, moved)
        data, _ = workspace.load(moved)
        self.assertEqual(data["figures"][0]["local_path"], "figures/figure-1.png")

    def test_changed_pdf_is_rejected(self):
        self.init()
        (self.dest / "paper.pdf").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            workspace.load(self.dest)

    def test_missing_or_changed_image_is_rejected(self):
        self.init()
        self.figure()
        (self.dest / "figures/figure-1.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            workspace.load(self.dest)

    def test_foreign_version_or_hash_rejected(self):
        self.init()
        self.figure()
        data, _ = workspace.load(self.dest)
        for key in ("paper_version", "paper_sha256"):
            bad = copy.deepcopy(data)
            bad["figures"][0][key] = "other"
            with self.assertRaises(ValueError):
                workspace.validate(bad, self.dest)

    def test_traversal_and_symlink_escape_rejected(self):
        self.init()
        for path in ("../input.pdf", str(self.pdf.resolve()), ""):
            with self.assertRaises(ValueError):
                workspace.inside(self.dest, path)
        (self.dest / "escape").symlink_to(self.pdf)
        with self.assertRaises(ValueError):
            workspace.inside(self.dest, "escape")

    def test_bad_page_box_or_id_does_not_render(self):
        self.init()
        with patch.object(workspace, "render_pdf") as render:
            for page, box, ident in [(0, None, "f1"), (1, [-1, 0, 1, 1], "f1"), (1, [0, 0, float('nan'), 1], "f1"), (1, None, "../f1")]:
                with self.assertRaises(ValueError):
                    workspace.save_figure(self.dest, ident, page, "Fig. 1", "caption", box=box)
            render.assert_not_called()

    def test_capture_uses_renderer_and_reuses_saved_result(self):
        self.init()
        with patch.object(workspace, "render_pdf", return_value=PNG) as render:
            result = workspace.save_figure(self.dest, "fig-1", 1, "Fig. 1", "caption")
            self.assertEqual(result["status"], "saved")
            workspace.save_figure(self.dest, "fig-1", 1, "Fig. 1", "caption")
            render.assert_called_once()

    def test_missing_renderer_is_explicit(self):
        with self.assertRaises(RuntimeError):
            workspace.render_pdf(self.pdf, 1, [0, 0, 1, 1], 2400, "unavailable-renderer-test-only")

    def test_bad_import_does_not_create_index_entry(self):
        self.init()
        self.image.write_bytes(b"not an image")
        with self.assertRaises(ValueError):
            self.figure()
        self.assertEqual(workspace.load(self.dest)[0]["figures"], [])
        self.assertFalse((self.dest / ".figure-write.lock").exists())


if __name__ == "__main__":
    unittest.main()
