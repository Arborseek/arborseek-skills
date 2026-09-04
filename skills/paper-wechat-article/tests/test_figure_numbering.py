import copy
from pathlib import Path
import sys
import tempfile
import unittest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from figure_numbering import number_figures
from render_article_package import insert_visuals
from style_article_html import sanitize
from paper_article import source_footer


class FigureNumberingTests(unittest.TestCase):
    def item(self, ident, label, placement="end", **kwargs):
        return dict(id=ident, caption=label + "｜误差随数据量下降", alt="误差图",
                    paper_figure={"label": label}, placement=placement, status="ready",
                    source_url="https://example.org/image.png", **kwargs)

    def test_final_dom_order_and_provenance(self):
        items = [self.item("f8", "Figure 8"), self.item("f5", "图 5", "before-section:1")]
        original = copy.deepcopy(items)
        with tempfile.TemporaryDirectory() as tmp:
            fragment, _, _ = insert_visuals('<p>引言</p><div class="section-heading">章节</div>', items, Path(tmp), Path(tmp))
        result, mapping = number_figures(fragment, items)
        self.assertEqual(list(mapping), ["f5", "f8"])
        self.assertEqual(mapping["f8"], {"article_label": "图 2", "source_label": "Figure 8"})
        self.assertEqual([c.get_text() for c in BeautifulSoup(result, "html.parser").find_all("figcaption")], ["图 1｜误差随数据量下降", "图 2｜误差随数据量下降"])
        self.assertEqual(items, original)
        self.assertEqual(number_figures(result, items)[0], result)

    def test_cover_formula_rejected_do_not_consume_numbers(self):
        items = [self.item("cover", "AI 生成概念配图，非论文原图", "cover", role="cover"), self.item("unused", "Fig. 9"), self.item("used", "Fig. 5")]
        items[1]["status"] = "rejected"
        with tempfile.TemporaryDirectory() as tmp:
            fragment, _, _ = insert_visuals('<p><img src="formula.png" alt="公式"></p>', items, Path(tmp), Path(tmp))
        result, mapping = number_figures(fragment, items)
        self.assertEqual(list(mapping), ["used"])
        self.assertEqual(mapping["used"]["article_label"], "图 1")
        self.assertIn("AI 生成概念配图，非论文原图", result)

    def test_same_intro_keeps_selection_order_and_refs_survive_sanitizer(self):
        items = [self.item("a", "Fig. 8", "after-intro"), self.item("b", "Fig. 5", "after-intro")]
        with tempfile.TemporaryDirectory() as tmp:
            fragment, _ = sanitize('<p>见<span data-figure-ref="b">图</span>。原论文图 8 不应被替换。</p>', "标题", Path(tmp), Path(tmp))
            fragment, _, _ = insert_visuals(fragment, items, Path(tmp), Path(tmp))
        result, mapping = number_figures(fragment, items)
        self.assertEqual(list(mapping), ["a", "b"])
        self.assertIn("见图 2", BeautifulSoup(result, "html.parser").get_text())
        self.assertIn("原论文图 8", result)
        self.assertNotIn("data-figure-ref", result)

    def test_missing_reference_blocks_render(self):
        with self.assertRaises(ValueError):
            number_figures('<span data-figure-ref="removed">图</span>', [])

    def test_footer_uses_article_number_not_source_number(self):
        item = self.item("f", "Fig. 8")
        item["article_label"] = "图 1"
        result = source_footer({"paper": {"title": "测试", "source_url": "https://example.org/paper", "version": "v1"}}, [item])
        self.assertIn("图片：图 1", result)
        self.assertNotIn("Fig. 8", result)
