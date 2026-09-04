"""Offline four-skill contract test. Network/PDF render are explicitly mocked."""
import base64
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


sys.path.insert(0, str(SKILLS / "tianshu-tanjie-paper-search/scripts"))
search = module("search_stage", SKILLS / "tianshu-tanjie-paper-search/scripts/search.py")
download = module("download_stage", SKILLS / "tianshu-tanjie-arxiv/scripts/arxiv.py")


class FakeClient:
    def metadata(self, **kwargs):
        return {"total": 1, "papers": [{"id": "1706.03762v1", "title": "Synthetic contract paper",
                "authors": ["Test author"], "summary": "Not a real research claim", "url": "https://arxiv.org/abs/1706.03762v1"}]}

    def fetch(self, url, consumer):
        response = io.BytesIO(b"%PDF-1.4\ncontract fixture only\n")
        response.headers = {"Content-Type": "application/pdf"}
        response.geturl = lambda: url
        return consumer(response)


class PipelineTests(unittest.TestCase):
    def test_search_download_reading_figure_write_and_relocation(self):
        with tempfile.TemporaryDirectory(prefix="pipeline 中文 ") as tmp:
            base = Path(tmp)
            results = search.run_search(FakeClient(), 'ti:"test"', 1, 0, "relevance")
            selection = base / "search.json"
            selection.write_text(json.dumps(results))
            selected = download.selected_from_search(selection, [results["papers"][0]["id"]])
            downloaded = download.download(FakeClient(), selected[0], base / "downloads", "pdf", 1024)
            self.assertEqual(download.download(FakeClient(), selected[0], base / "downloads", "pdf", 1024)["status"], "cached")
            # Each relocated skill is complete by itself, without sibling skills.
            reader = base / "reader-only"
            writer = base / "writer-only"
            for name, destination in [("tianshu-tanjie-paper-reading", reader), ("paper-wechat-article", writer)]:
                shutil.copytree(SKILLS / name, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            def run(script, *args):
                return subprocess.run([sys.executable, str(script), *map(str, args)], cwd=base, capture_output=True, text=True)
            ws = base / "资料"
            result = run(reader / "scripts/paper_workspace.py", "init", "--pdf", downloaded["file"], "--metadata", downloaded["metadata"], "--selection", selection, "--selected-id", selected[0], "--output-dir", ws)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            image = base / "original.png"
            image.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVZkAAAAASUVORK5CYII="))
            result = run(reader / "scripts/paper_workspace.py", "import-figure", ws, "--image", image, "--id", "fig-1", "--page", 1, "--label", "Fig. 1", "--caption", "Synthetic test figure")
            self.assertEqual(result.returncode, 0, result.stdout)
            result = run(reader / "scripts/project_assets.py", "import", ws, "--id", "site-image", "--url", "https://example.org/demo.png", "--page", "https://example.org/project", "--title", "Project fixture image", "--relation-note", "Synthetic project relation", "--kind", "image", "--basis", "Self-made fixture", "--file", image)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            manifest = ws / "paper-workspace.json"
            data = json.loads(manifest.read_text())
            data["paper"]["read_scope"] = "partial"
            data["claims"] = [{"id": "c1", "claim": "Synthetic contract claim only", "status": "verified", "locator": "PDF page 1", "notes": "fixture only"}]
            data["figures"][0].update(checked=True, credit="Test author", alt="Test figure", rights_status="cleared", rights_note="Self-made test fixture")
            data["project_assets"][0].update(checked=True, credit="Test author", alt="Project test figure", rights_status="cleared", rights_note="Self-made test fixture")
            manifest.write_text(json.dumps(data))
            moved = base / "迁移后资料"
            shutil.move(ws, moved)
            draft = moved / "draft.html"
            draft.write_text("<h2>测试问题</h2><p>这是用于验证交接的合成正文，不是真实科学结论。正文只检查结构与素材复用。</p><h2>范围</h2><p>仅部分阅读的状态必须保留，不因转为公众号文章而变成全文精读。</p>", encoding="utf-8")
            article = moved / "article.json"
            result = run(writer / "scripts/paper_article.py", "prepare", moved / "paper-workspace.json", draft, article, "--title", "合成交接测试", "--project-image", "site-image", "补充原图未覆盖的项目演示")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            package = json.loads(article.read_text())
            self.assertEqual(package["paper"]["version"], selected[0])
            self.assertEqual(package["paper"]["read_scope"], "partial")
            self.assertFalse(Path(package["visuals"]["items"][0]["local_path"]).is_absolute())
            # The article cannot be final merely because upstream extracted a file.
            self.assertNotEqual(run(writer / "scripts/paper_article.py", "check", article, "--require-ready").returncode, 0)
            package["qa"].update(content_reviewed=True, sources_reviewed=True, visuals_reviewed=True)
            for item in package["visuals"]["items"]:
                item["status"] = "ready"
            article.write_text(json.dumps(package))
            output = moved / "preview.html"
            result = run(writer / "scripts/paper_article.py", "render", article, output, "--require-ready")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(list((moved / "assets").iterdir())), 2)
            self.assertIn("Fig. 1", output.read_text())
            self.assertIn("项目网站素材，非论文原图", output.read_text())
            result = run(writer / "scripts/lint_article_output.py", output)
            self.assertEqual(result.returncode, 0, result.stdout)
            # A second move keeps both the upstream manifest and article usable.
            final_location = base / "再次移动"
            shutil.move(moved, final_location)
            self.assertEqual(run(writer / "scripts/paper_article.py", "check", final_location / "article.json", "--require-ready").returncode, 0)
            (final_location / "figures/fig-1.png").write_bytes(b"corruption")
            self.assertNotEqual(run(writer / "scripts/paper_article.py", "check", final_location / "article.json").returncode, 0)

    def test_writer_alone_accepts_private_pdf_without_fake_public_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copytree(SKILLS / "paper-wechat-article", base / "only-skill", ignore=shutil.ignore_patterns("__pycache__"))
            pdf = base / "input.pdf"
            pdf.write_bytes(b"%PDF-1.4\nprivate fixture")
            scripts = base / "only-skill/scripts"
            result = subprocess.run([sys.executable, str(scripts / "paper_workspace.py"), "init", "--pdf", str(pdf), "--title", "私有稿件", "--output-dir", str(base / "workspace")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout)
            draft = base / "draft.html"
            draft.write_text("<p>私有论文的待核验草稿。</p>", encoding="utf-8")
            result = subprocess.run([sys.executable, str(scripts / "paper_article.py"), "prepare", str(base / "workspace/paper-workspace.json"), str(draft), str(base / "article.json"), "--title", "草稿"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
