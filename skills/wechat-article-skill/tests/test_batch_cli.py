from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BatchCliTests(unittest.TestCase):
    def test_batch_writes_explainable_manifest_and_fragments(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source = temp / "input"
            output = temp / "output"
            source.mkdir()
            (source / "interview.html").write_text(
                "<html><title>对话创始人</title><article><p>主持人：为什么创业？</p><p>创始人：为了真正解决问题。</p></article></html>",
                encoding="utf-8",
            )
            (source / "report.html").write_text(
                "<html><title>模型 Benchmark 提升 20%</title><article><h2>实验</h2><p>评测准确率达到 91.7%。</p></article></html>",
                encoding="utf-8",
            )
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/batch_style_articles.py"), str(source), str(output), "--write-fragments", "--seed", "test"],
                check=True,
                capture_output=True,
                text=True,
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["article_count"], 2)
            self.assertNotIn("database_updated", manifest)
            for item in manifest["articles"]:
                self.assertIn("selection_reason", item)
                self.assertIn("theme_scores", item)
                self.assertIn("features", item)
                self.assertTrue((output / item["preview_file"]).is_file())
                self.assertTrue((output / item["fragment_file"]).is_file())


if __name__ == "__main__":
    unittest.main()
