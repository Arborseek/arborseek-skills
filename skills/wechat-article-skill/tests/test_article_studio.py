from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import article_package as contract  # noqa: E402
import lint_article_output as linter  # noqa: E402
import style_article_html as engine  # noqa: E402


class ArticlePackageTests(unittest.TestCase):
    def test_package_template_is_valid_without_visuals(self):
        package = contract.package_template(
            "教程：如何整理研究资料",
            "研究资料整理",
            "<h2>第一步</h2><p>先确认目标，再记录来源和日期。</p>",
            article_type="tutorial",
            image_policy="none",
        )
        report = contract.validate_package(package)
        self.assertTrue(report["valid"], report)
        self.assertEqual(package["visuals"]["items"], [])
        self.assertEqual(
            package["qa"],
            {
                "content_reviewed": False,
                "sources_reviewed": False,
                "visuals_reviewed": False,
                "browser_reviewed": False,
            },
        )

    def test_interview_hybrid_plan_searches_for_real_portrait(self):
        html = "<h2>职业选择</h2><p>主持人：为什么进入这个行业？</p><p>创始人：我希望解决真实问题。</p>"
        plan = contract.plan_visuals("对话机器人创始人", html, "hybrid", "balanced")
        self.assertEqual(plan["category"], "interview-profile")
        self.assertEqual(plan["items"][1]["role"], "portrait")
        self.assertEqual(plan["items"][1]["source_type"], "searched")
        self.assertTrue(plan["items"][1]["search_query"])
        self.assertEqual(plan["items"][0]["source_type"], "searched")
        self.assertTrue(plan["items"][0]["generation_prompt"])

    def test_generated_visual_requires_prompt(self):
        package = contract.package_template(
            "技术解读",
            "模型架构",
            "<h2>方法</h2><p>模型使用分层架构完成预测与控制。</p>",
            image_policy="generate",
        )
        package["visuals"]["items"][0]["generation_prompt"] = ""
        report = contract.validate_package(package)
        self.assertFalse(report["valid"])
        self.assertTrue(any("generation_prompt" in error for error in report["errors"]))

    def test_searched_ready_visual_requires_credit(self):
        package = contract.package_template(
            "产品发布",
            "机器人新品",
            "<h2>新品</h2><p>产品正式发布并公布功能。</p>",
            image_policy="search",
        )
        item = package["visuals"]["items"][0]
        item.update({"status": "ready", "source_url": "https://example.com/product.jpg", "credit": ""})
        report = contract.validate_package(package)
        self.assertFalse(report["valid"])
        self.assertTrue(any("credit" in error for error in report["errors"]))

    def test_require_ready_rejects_planned_assets(self):
        package = contract.package_template(
            "观点文章",
            "行业趋势",
            "<h2>变化</h2><p>行业正在形成新的协作方式。</p>",
        )
        report = contract.validate_package(package, require_ready=True)
        self.assertFalse(report["valid"])
        self.assertTrue(any("must be ready or rejected" in error for error in report["errors"]))

    def test_final_research_requires_claims_sources_and_review(self):
        package = contract.package_template(
            "技术解读",
            "模型架构",
            "<h2>方法</h2><p>模型使用分层架构完成预测与控制。</p>",
            research_mode="standard",
            image_policy="none",
        )
        report = contract.validate_package(package, require_ready=True)
        self.assertFalse(report["valid"])
        self.assertIn("researched final package must declare at least one source", report["errors"])
        self.assertIn("qa.sources_reviewed must be true before final rendering", report["errors"])

    def test_verified_claim_must_reference_declared_source(self):
        package = contract.package_template("数据报告", "指标", "<p>准确率达到 90%。</p>", image_policy="none")
        package["research"]["claims"] = [{"id": "c1", "claim": "准确率达到 90%", "status": "verified", "source_urls": ["https://example.com/paper"]}]
        report = contract.validate_package(package)
        self.assertFalse(report["valid"])
        self.assertTrue(any("undeclared source" in error for error in report["errors"]))

    def test_schema_file_is_valid_json(self):
        schema = json.loads((ROOT / "schemas" / "article-package.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["article"]["properties"]["background"]["const"], "white")


class ArticleOutputTests(unittest.TestCase):
    def test_linter_accepts_renderer_document(self):
        fragment, _ = engine.sanitize(
            "<h2>方法</h2><p>这是用于检查公众号文章排版的一段完整正文，包含足够的信息来触发结构与长度校验。</p><p>第二段继续解释细节和结论，确保移动端阅读时段落清晰。</p>",
            "测试文章",
            Path.cwd(),
            Path.cwd(),
        )
        report = linter.lint_html(engine.document("测试文章", fragment, "blueprint", "技术解读"))
        self.assertTrue(report["valid"], report)

    def test_linter_rejects_colored_background(self):
        raw = engine.document("测试", "<p>正文内容</p>", "blueprint", "").replace("background: #fff", "background: #eee", 1)
        report = linter.lint_html(raw)
        self.assertFalse(report["valid"])
        self.assertTrue(any("background" in error for error in report["errors"]))

    def test_cli_plan_validate_render_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            draft = folder / "draft.html"
            package = folder / "article.json"
            output = folder / "preview.html"
            draft.write_text("<h2>问题</h2><p>机器人需要根据当前状态预测动作后果。</p><h2>方法</h2><p>文章通过分层结构解释训练与推理过程。</p>", encoding="utf-8")
            subprocess.run([
                sys.executable, str(ROOT / "scripts" / "plan_article.py"), str(draft), str(package),
                "--title", "机器人如何预测下一步", "--image-policy", "none",
            ], check=True, capture_output=True, text=True)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_article_package.py"), str(package)], check=True, capture_output=True, text=True)
            subprocess.run([sys.executable, str(ROOT / "scripts" / "render_article_package.py"), str(package), str(output)], check=True, capture_output=True, text=True)
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "lint_article_output.py"), str(output)], check=True, capture_output=True, text=True)
            self.assertTrue(json.loads(result.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
