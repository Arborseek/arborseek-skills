import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import formula_assets as math_assets
import paper_article
from lint_article_output import lint_html


class FormulaTests(unittest.TestCase):
    def package(self):
        handoff = {"paper": {"title": "合成论文", "version": "test-v1", "source_url": "https://example.org/paper", "read_scope": "full-text"}, "claims": [{"id": "test", "claim": "合成排版测试", "status": "verified", "locator": "合成测试记录", "notes": "自制测试，不是实际论文结论"}], "figures": []}
        data = paper_article.prepare(handoff, '<h2>机制</h2><p>符号 A、Z、Y 保留文字。</p><p data-formula-id="eq1"></p><p>联合概率分解示例。</p>', "公式排版测试", Path("."))
        data["qa"].update(content_reviewed=True, sources_reviewed=True, visuals_reviewed=True)
        data["formulas"] = [{"id": "eq1", "latex_lines": [r"p(A,Z,Y\mid c)", r"=\pi(A\mid c)\,p(Z\mid c,A)", r"\quad\cdot p(Y\mid c,A,Z)"], "alt": "联合概率分解公式", "locator": "合成测试，不是论文证据", "checked": True}]
        return data

    def test_slots_and_review(self):
        data = self.package()
        self.assertEqual(math_assets.validate_formulas(data, True), [])
        data["formulas"][0]["checked"] = False
        self.assertTrue(math_assets.validate_formulas(data, True))
        self.assertEqual(math_assets.validate_formulas(data, False), [])
        data["formulas"].append(copy.deepcopy(data["formulas"][0]))
        self.assertTrue(math_assets.validate_formulas(data))

    def test_missing_record_and_nonempty_slot(self):
        data = self.package()
        data["formulas"] = []
        self.assertTrue(math_assets.validate_formulas(data))
        data = self.package()
        data["article"]["content_html"] = '<p data-formula-id="eq1">不能丢失的文字</p>'
        self.assertTrue(math_assets.validate_formulas(data))

    def test_invalid_records(self):
        for lines in (None, [], [""], ["$x$"], ["x\ny"], [42], ["x"] * 9):
            data = self.package()
            data["formulas"][0]["latex_lines"] = lines
            self.assertTrue(math_assets.validate_formulas(data), repr(lines))

    def test_residual_math_not_prose_or_code(self):
        for raw in (r"<p>$$x^2$$</p>", r"<p>\[x^2\]</p>", r"<p>\frac{1}{2}</p>", "<p>p(A, Z, Y | c) = π(A|c) · p(Z|c,A) · p(Y|c,A,Z)</p>"):
            self.assertTrue(math_assets.unresolved_math(raw), raw)
            data = self.package()
            data["article"]["content_html"] += raw
            self.assertFalse(paper_article.check(data, Path("."), True)["valid"])
        for raw in ("<p>A、Z、Y，x²，x=1</p>", r"<pre>$$x$$</pre>", '<p data-formula-id="eq1"></p>'):
            self.assertFalse(math_assets.unresolved_math(raw))

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional formula renderer not installed")
    def test_png_quality_and_unsupported_syntax(self):
        from PIL import Image
        png, width = math_assets.render_png([r"\frac{x_i^2}{\sqrt{y}} = \sum_{k=1}^{n} k"])
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.mode, "RGB")
        self.assertLessEqual(abs(img.width - width * 3), 2)
        self.assertEqual(img.getpixel((0, 0)), (255, 255, 255))
        self.assertGreater(len(set(img.getdata())), 10)
        for lines in ([r"\unsupported{x}"], ["x+" * 100 + "y"]):
            with self.assertRaises(ValueError):
                math_assets.render_png(lines)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional formula renderer not installed")
    def test_cli_renders_in_place_and_assets_survive_move(self):
        from bs4 import BeautifulSoup
        import shutil
        with tempfile.TemporaryDirectory(prefix="formula 中文 ") as tmp:
            root = Path(tmp)
            package = root / "article.json"
            data = self.package()
            package.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            output = root / "out/final.html"
            result = subprocess.run([sys.executable, str(ROOT / "scripts/paper_article.py"), "render", str(package), str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            raw = output.read_text(encoding="utf-8")
            self.assertTrue(lint_html(raw)["valid"], lint_html(raw))
            soup = BeautifulSoup(raw, "html.parser")
            img = soup.select_one("#article-content img")
            self.assertIn("width:", img["style"])
            self.assertEqual(img["alt"], "联合概率分解公式")
            self.assertIn("符号", img.parent.find_previous("p").get_text())
            self.assertFalse(soup.select("[data-formula-id]"))
            shutil.move(str(root / "out"), str(root / "moved"))
            self.assertTrue((root / "moved" / img["src"]).is_file())
            self.assertEqual(json.loads(package.read_text(encoding="utf-8")), data)
