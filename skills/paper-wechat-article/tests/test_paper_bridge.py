import copy
import base64
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

    def project_handoff(self):
        import paper_workspace
        import project_assets
        pdf = self.base / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4\nproject integration fixture")
        root = self.base / "workspace"
        paper_workspace.init_workspace(pdf, root, title="Project test paper")
        png = self.base / "site.png"
        png.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVZkAAAAASUVORK5CYII="))
        project_assets.archive(root, "site-image", "https://example.org/demo.png", "https://example.org/project", "Demo image", "Fixture project relation", mode="import", kind="image", basis="Self-made fixture", local=png)
        return paper_workspace.load(root)[0], root

    def test_project_assets_are_retained_but_not_automatically_inserted(self):
        handoff, root = self.project_handoff()
        package = bridge.prepare(handoff, self.draft, "测试", root)
        self.assertEqual(len(package["project_assets"]), 1)
        self.assertEqual(package["visuals"]["items"], [])

    def test_selected_project_image_has_source_label_and_final_gate(self):
        handoff, root = self.project_handoff()
        package = bridge.prepare(handoff, self.draft, "测试", root, [("site-image", "论文图未包含网站演示场景")])
        self.assertTrue(bridge.check(package, root)["valid"])
        image = package["visuals"]["items"][0]
        self.assertIn("项目网站素材，非论文原图", image["caption"])
        self.assertNotIn("https://example.org/project", image["caption"])
        self.assertIn("https://example.org/project", bridge.source_footer(package, [image]))
        self.assertFalse(image["paper_figure"]["use_as_evidence"])
        self.assertFalse(bridge.check(self.approve(package), root, True)["valid"])

    def test_project_image_cannot_be_relabelled_or_silently_changed(self):
        handoff, root = self.project_handoff()
        package = bridge.prepare(handoff, self.draft, "测试", root, [("site-image", "补充网站演示")])
        package["visuals"]["items"][0]["paper_figure"]["kind"] = "original"
        self.assertFalse(bridge.check(package, root)["valid"])
        package["visuals"]["items"][0]["paper_figure"]["kind"] = "project"
        (root / "project-assets/site-image.png").write_bytes(b"changed")
        self.assertFalse(bridge.check(package, root)["valid"])

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
        self.assertEqual(item["caption"], "Fig. 1｜合成测试图片")
        self.assertNotIn("PDF 第", item["caption"])
        self.assertEqual(item["paper_figure"]["locator"], "PDF 第 2 页")
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

    def test_candidate_draft_is_visible_without_changing_approval(self):
        from render_article_package import insert_visuals
        data = self.original()
        before = copy.deepcopy(data)
        fragment, _, inserted = insert_visuals(self.draft, data["visuals"]["items"], self.base,
                                                self.base / "draft-preview", include_candidates=True)
        self.assertIn("不可直接发布", fragment)
        self.assertEqual(inserted, ["f1"])
        self.assertEqual(data, before)
        self.assertFalse(bridge.check(data, self.base, True)["valid"])

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
        self.assertIn("图 1", output)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(output, "html.parser")
        self.assertEqual(soup.figcaption.get_text(), "图 1｜合成测试图片")
        self.assertIn("测试作者", soup.select_one(".paper-references").get_text())
        self.assertNotIn("PDF 第", output)
        self.assertNotIn("草稿素材", output)
        self.assertEqual(len(list((target.parent / "assets").iterdir())), 1)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/lint_article_output.py"), str(target)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_render_is_final_by_default_and_draft_is_explicit(self):
        data = self.original()
        package = self.base / "article.json"
        package.write_text(json.dumps(data), encoding="utf-8")
        target = self.base / "final.html"
        self.assertNotEqual(self.run_cli("render", package, target).returncode, 0)
        self.assertFalse(target.exists())
        preview = self.base / "preview.html"
        result = self.run_cli("render", package, preview, "--draft-images")
        self.assertEqual(result.returncode, 0, result.stdout)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(preview.read_text(), "html.parser")
        self.assertEqual(len(soup.select(".internal-preview-notice")), 1)
        self.assertNotIn("不可直接发布", soup.figcaption.get_text())

    def test_short_caption_preserves_internal_evidence(self):
        self.original()
        self.handoff["figures"][0]["reader_caption"] = "不同训练数据量的对齐表现"
        data = self.approve(self.package())
        item = data["visuals"]["items"][0]
        self.assertEqual(item["caption"], "Fig. 1｜不同训练数据量的对齐表现")
        self.assertEqual(item["paper_figure"]["caption"], self.handoff["figures"][0]["caption"])
        self.assertTrue(bridge.check(data, self.base, True)["valid"])

    def test_final_rejects_worklog_in_body_or_caption(self):
        for marker in ("【草稿素材：使用权限待确认】", "待补图", "视觉未验收"):
            data = self.approve(self.original())
            data["article"]["content_html"] += "<p>" + marker + "</p>"
            self.assertFalse(bridge.check(data, self.base, True)["valid"])
            data = self.approve(self.original())
            data["visuals"]["items"][0]["caption"] += marker
            self.assertFalse(bridge.check(data, self.base, True)["valid"])

    def test_sources_deduplicate_and_exclude_rejected_figures(self):
        data = self.approve(self.original())
        one = data["visuals"]["items"][0]
        two = copy.deepcopy(one)
        two["paper_figure"].update(label="Fig. 2", attribution="CC BY credit fixture")
        footer = bridge.source_footer(data, [one, two])
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(footer, "html.parser")
        self.assertEqual(len(soup.find_all("a", href=self.handoff["paper"]["source_url"])), 1)
        self.assertIn("Fig. 2", soup.get_text())
        self.assertIn("CC BY credit fixture", soup.get_text())
        self.assertNotIn("rights_status", footer)

    def test_lower_renderer_cannot_bypass_final_gate(self):
        package = self.base / "article.json"
        package.write_text(json.dumps(self.original()), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/render_article_package.py"),
                                 str(package), str(self.base / "bypass.html")], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.base / "bypass.html").exists())


if __name__ == "__main__":
    unittest.main()
