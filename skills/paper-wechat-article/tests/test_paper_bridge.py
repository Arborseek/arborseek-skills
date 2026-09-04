import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import paper_article as bridge


class PaperBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper 中文 ")
        self.base = Path(self.tmp.name)
        self.draft = "<h2>研究问题</h2><p>这是一份合成测试稿，不代表真实研究成果。下面说明方法的作用与证据边界。</p><h2>局限</h2><p>所有描述都仅为格式测试，不应作为论文事实传播。</p>"
        self.handoff = {"paper": {"title": "合成论文", "version": "test-v1", "source_url": "https://example.org/paper", "read_scope": "full-text"},
                        "claims": [{"id": "c1", "claim": "测试陈述", "status": "verified", "locator": "PDF 第 2 页", "notes": "合成测试依据"}], "figures": []}

    def tearDown(self):
        self.tmp.cleanup()

    def package(self):
        return bridge.prepare(self.handoff, self.draft, "测试文章", self.base)

    def original(self):
        asset = self.base / "figure.svg"
        asset.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="320" height="160"><rect width="320" height="160" fill="white"/><text x="30" y="80">SYNTHETIC TEST FIGURE</text></svg>', encoding="utf-8")
        self.handoff["figures"] = [{"id": "f1", "kind": "original", "label": "Fig. 1", "locator": "PDF 第 2 页", "local_path": "figure.svg", "alt": "合成测试图片", "caption": "用于测试的图，不是真实论文原图", "credit": "测试作者", "rights_status": "cleared", "rights_note": "测试自制素材", "checked": True, "use_as_evidence": True}]
        return self.package()

    def approve(self, data):
        data["qa"].update(content_reviewed=True, sources_reviewed=True, visuals_reviewed=True)
        for item in data["visuals"]["items"]:
            item["status"] = "ready"
        return data

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "scripts/paper_article.py"), *map(str, args)], cwd=self.base, capture_output=True, text=True)

    def test_preserves_identity_locator_and_does_not_auto_approve(self):
        data = self.package()
        self.assertEqual(data["paper"], self.handoff["paper"])
        self.assertIn("PDF 第 2 页", data["research"]["claims"][0]["notes"])
        self.assertFalse(data["qa"]["sources_reviewed"])
        self.assertTrue(bridge.check(data, self.base)["valid"])

    def test_original_is_candidate_and_path_is_relocated(self):
        data = self.original()
        item = data["visuals"]["items"][0]
        self.assertEqual(item["status"], "candidate")
        self.assertEqual(item["local_path"], str((self.base / "figure.svg").resolve()))
        self.assertIn("Fig. 1", item["caption"])
        self.assertIn("论文原图", item["caption"])
        self.assertTrue(bridge.check(data, self.base)["valid"])

    def test_final_needs_actual_review(self):
        self.assertFalse(bridge.check(self.original(), self.base, True)["valid"])

    def test_final_original_with_review_passes(self):
        self.assertTrue(bridge.check(self.approve(self.original()), self.base, True)["valid"])

    def test_rights_unknown_blocks_even_provided_image(self):
        data = self.approve(self.original())
        data["visuals"]["items"][0]["paper_figure"]["rights_status"] = "unknown"
        self.assertFalse(bridge.check(data, self.base, True)["valid"])

    def test_missing_asset_cannot_use_remote_url_to_bypass(self):
        data = self.approve(self.original())
        item = data["visuals"]["items"][0]
        item["local_path"] = "missing.png"
        item["source_url"] = "https://example.org/image.png"
        self.assertFalse(bridge.check(data, self.base, True)["valid"])

    def test_generated_requires_fallback_and_cannot_be_evidence(self):
        self.original()
        figure = self.handoff["figures"][0]
        figure.update(kind="generated", generation_prompt="抽象概念测试图")
        self.assertFalse(bridge.check(self.package(), self.base)["valid"])
        figure.update(fallback_reason="已检查 Fig. 1，只有密集数据图，不适合概念封面", use_as_evidence=False)
        data = self.package()
        self.assertTrue(bridge.check(data, self.base)["valid"])
        self.assertIn("非论文原图", data["visuals"]["items"][0]["caption"])

    def test_original_cannot_lose_caption_as_cover(self):
        data = self.original()
        data["visuals"]["items"][0]["role"] = "cover"
        self.assertFalse(bridge.check(data, self.base)["valid"])

    def test_generated_cover_preserves_visible_disclosure(self):
        from render_article_package import insert_visuals
        self.original()
        self.handoff["figures"][0].update(kind="generated", generation_prompt="合成测试",
            use_as_evidence=False, fallback_reason="原图为数据图，不适合作概念封面")
        data = self.approve(self.package())
        data["visuals"]["items"][0].update(role="cover", placement="cover")
        self.assertTrue(bridge.check(data, self.base, True)["valid"])
        fragment, _, inserted = insert_visuals(self.draft, data["visuals"]["items"], self.base, self.base / "rendered")
        self.assertIn("AI 生成概念配图，非论文原图", fragment)
        self.assertIn("合成测试图片", fragment)
        self.assertEqual(inserted, ["f1"])

    def test_embedded_untracked_image_is_rejected(self):
        data = self.package()
        data["article"]["content_html"] += '<img src="secret.png">'
        self.assertFalse(bridge.check(data, self.base)["valid"])

    def test_missing_locator_or_undeclared_evidence_fails(self):
        data = self.package()
        data["research"]["claims"][0]["locator"] = ""
        self.assertFalse(bridge.check(data, self.base)["valid"])
        data = self.package()
        data["research"]["mode"] = "none"
        self.assertFalse(bridge.check(data, self.base)["valid"])

    def test_unverified_stays_unverified_and_cannot_be_final(self):
        self.handoff["paper"]["read_scope"] = "abstract"
        self.handoff["claims"][0]["status"] = "unverified"
        data = self.approve(self.package())
        self.assertEqual(data["research"]["claims"][0]["status"], "unverified")
        self.assertTrue(bridge.check(data, self.base)["warnings"])
        self.assertFalse(bridge.check(data, self.base, True)["valid"])

    def test_malformed_package_fails_without_throwing(self):
        for data in (None, [], {"article": [], "research": {"claims": 4}}, {"paper": None}):
            self.assertFalse(bridge.check(data, self.base)["valid"])

    def test_check_does_not_mutate_package(self):
        data = self.original()
        before = copy.deepcopy(data)
        bridge.check(data, self.base)
        self.assertEqual(before, data)

    def test_cli_prepare_and_refuse_overwrite(self):
        handoff = self.base / "handoff.json"
        handoff.write_text(json.dumps(self.handoff), encoding="utf-8")
        draft = self.base / "draft.html"
        draft.write_text(self.draft, encoding="utf-8")
        target = self.base / "article.json"
        result = self.run_cli("prepare", handoff, draft, target, "--title", "测试文章")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        before = target.read_bytes()
        self.assertEqual(self.run_cli("prepare", handoff, draft, target, "--title", "改名").returncode, 2)
        self.assertEqual(before, target.read_bytes())

    def test_cli_final_render_and_lint_with_local_figure(self):
        data = self.approve(self.original())
        package = self.base / "article.json"
        package.write_text(json.dumps(data), encoding="utf-8")
        target = self.base / "output" / "final.html"
        result = self.run_cli("render", package, target, "--require-ready")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = target.read_text(encoding="utf-8")
        self.assertIn("论文原图", output)
        self.assertIn("Fig. 1", output)
        self.assertEqual(len(list((target.parent / "assets").iterdir())), 1)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/lint_article_output.py"), str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
