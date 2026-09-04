from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import style_article_html as engine  # noqa: E402


class ContentClassificationTests(unittest.TestCase):
    def test_interview_profile_prefers_violet(self):
        html = """<article><p>主持人：你为什么选择机器人行业？</p><p>创始人：我们希望把场景真正跑出来。</p><blockquote>长期主义最重要。</blockquote></article>"""
        profile = engine.content_profile("对话某机器人创始人：产品如何落地", html)
        self.assertEqual(profile["category"], "interview-profile")
        self.assertEqual(profile["ranked_themes"][0], "violet-dialogue")

    def test_benchmark_report_prefers_cyan(self):
        html = """<article><h2>实验设置</h2><p>在 Benchmark 上进行评测。</p><h2>实验结果</h2><p>准确率提升 28.2%，性能排名第一。</p><table><tr><td>91.7%</td></tr></table></article>"""
        profile = engine.content_profile("ECCV 论文：新模型闭环评测提升 28.2%", html)
        self.assertEqual(profile["category"], "data-report")
        self.assertEqual(profile["ranked_themes"][0], "cyan-research")

    def test_launch_news_prefers_orange(self):
        html = """<article><p>新品正式发布，售价 9999 元，并同步宣布开源。</p><img src="https://example.com/a.png"></article>"""
        profile = engine.content_profile("刚刚！万元级机器人新品正式发布", html)
        self.assertEqual(profile["category"], "launch-news")
        self.assertEqual(profile["ranked_themes"][0], "orange-launch")

    def test_event_title_overrides_technical_body(self):
        html = "<article><p>本次直播讨论研究 Agent、模型训练和论文方法，欢迎报名参与。</p></article>"
        profile = engine.content_profile("【直播预告】你的研究 Agent 为什么每次都从零开始？", html)
        self.assertEqual(profile["category"], "event-promo")

    def test_reflective_title_beats_release_word(self):
        html = "<article><h2>路线演进</h2><p>模型发布后，我们重新分析它的技术意义与未来竞争。</p></article>"
        profile = engine.content_profile("看完刚发布的 Atlas，我觉得竞争才刚刚开始", html)
        self.assertEqual(profile["category"], "editorial-analysis")
        self.assertEqual(profile["ranked_themes"][0], "teal-editorial")

    def test_tutorial_detects_steps_and_guide_intent(self):
        html = "<article><h2>第一步</h2><p>安装工具并完成配置。</p><h2>第二步</h2><ol><li>运行示例</li><li>检查输出</li></ol></article>"
        profile = engine.content_profile("从零入门：完整实操指南", html)
        self.assertEqual(profile["category"], "tutorial")
        self.assertIn(profile["ranked_themes"][0], {"blueprint", "cobalt-journal", "cyan-research"})

    def test_single_selection_is_deterministic(self):
        title = "机器人世界模型技术论文"
        html = "<article><h2>方法</h2><p>模型架构与训练方法。</p></article>"
        self.assertEqual(engine.select_theme(title, html, "seed-a"), engine.select_theme(title, html, "seed-a"))

    def test_batch_manifest_data_is_deterministic(self):
        articles = [
            {"title": "对话创始人", "content": "<p>主持人：为什么？</p><p>创始人：回答。</p>"},
            {"title": "模型评测提升 20%", "content": "<h2>实验</h2><p>Benchmark 结果 90%</p>"},
            {"title": "新品正式发布", "content": "<p>刚刚发布，售价一万元。</p>"},
        ]
        first = engine.assign_batch_styles(articles, "stable", "balanced")
        second = engine.assign_batch_styles(articles, "stable", "balanced")
        self.assertEqual([item["theme"] for item in first], [item["theme"] for item in second])


class HtmlTransformationTests(unittest.TestCase):
    def test_sanitizes_executable_content_and_preserves_structure(self):
        raw = """<article><script>alert(1)</script><h2>一、方法</h2><p>正文<strong>重点</strong></p><img src="https://example.com/a.png"><table><tr><td>1</td></tr></table></article>"""
        with tempfile.TemporaryDirectory() as tmp:
            fragment, report = engine.sanitize(raw, "测试", Path(tmp), Path(tmp))
        self.assertNotIn("<script", fragment)
        self.assertIn("section-heading", fragment)
        self.assertIn("table-wrap", fragment)
        self.assertEqual(report["output_images"], 1)

    def test_generated_document_pins_white_background(self):
        html = engine.document("测试文章", "<p>正文</p>", "cobalt-journal", "测试元信息")
        self.assertIn("color-scheme: light", html)
        self.assertIn("background: #fff", html)
        self.assertIn('class="theme-cobalt-journal"', html)

    def test_video_is_promoted_out_of_misused_quote_container(self):
        raw = """<article><blockquote><div><strong><video><source src="https://example.com/demo.mp4" type="video/mp4"></video></strong></div><p>正文引言</p></blockquote></article>"""
        with tempfile.TemporaryDirectory() as tmp:
            fragment, _ = engine.sanitize(raw, "视频文章", Path(tmp), Path(tmp))
        soup = engine.BeautifulSoup(fragment, "html.parser")
        video = soup.find("video")
        self.assertIsNotNone(video)
        self.assertIsNone(video.find_parent("blockquote"))
        self.assertIsNone(soup.find("blockquote"))
        self.assertEqual(video.get("controls"), "controls")
        self.assertEqual(video.find("source").get("src"), "https://example.com/demo.mp4")

    def test_video_css_uses_full_width_sixteen_by_nine_player(self):
        css = engine.css_for("cobalt-journal")
        self.assertIn(".article-body video", css)
        self.assertIn("aspect-ratio: 16 / 9", css)
        self.assertIn("word-break: break-all", css)


if __name__ == "__main__":
    unittest.main()
