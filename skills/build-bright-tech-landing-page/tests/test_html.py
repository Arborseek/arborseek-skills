import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_html

BASE = '<!doctype html><html lang="zh-CN"><head><title>测试</title><meta name="viewport" content="width=device-width"></head><body><main id="main">{}</main></body></html>'


class HtmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.page = self.root / 'index.html'

    def tearDown(self):
        self.temp.cleanup()

    def inspect(self, body):
        self.page.write_text(BASE.format(body), encoding='utf-8')
        return check_html.inspect(self.page)

    def codes(self, result):
        return {item['check'] for item in result['failed']}

    def test_example(self):
        self.assertEqual(check_html.inspect(ROOT / 'examples/landing-page.html')['status'], 'passed')

    def test_valid_anchor(self):
        self.assertEqual(self.inspect('<a href="#main">正文</a>')['failed'], [])

    def test_missing_anchor(self):
        self.assertIn('anchor', self.codes(self.inspect('<a href="#absent">失效</a>')))

    def test_duplicate_id(self):
        self.assertIn('unique_ids', self.codes(self.inspect('<p id="main">重复</p>')))

    def test_missing_asset_and_alt(self):
        self.assertTrue({'local_file', 'image_alt'} <= self.codes(self.inspect('<img src="missing.png">')))

    def test_existing_asset_decorative_alt(self):
        (self.root / 'art.svg').write_text('<svg/>', encoding='utf-8')
        self.assertEqual(self.inspect('<img src="art.svg" alt="">')['failed'], [])

    def test_external_is_unverified(self):
        result = self.inspect('<a href="https://example.com/path">外链</a>')
        self.assertEqual(result['status'], 'passed')
        self.assertTrue(result['external_references'])
        self.assertTrue(result['unverified'])

    def test_unsafe_reference(self):
        self.assertIn('unsafe_reference', self.codes(self.inspect('<a href="javascript:alert(1)">错误</a>')))

    def test_outside_root(self):
        self.assertIn('outside_root', self.codes(self.inspect('<img src="../private.png" alt="图">')))

    def test_cross_file_anchor(self):
        (self.root / 'other.html').write_text(BASE.format('<p id="ok">目标</p>'), encoding='utf-8')
        self.assertEqual(self.inspect('<a href="other.html#ok">跳转</a>')['failed'], [])

    def test_svg_title_does_not_replace_document_title(self):
        self.page.write_text('<html lang="zh"><body><main><svg><title>图标题</title></svg></main></body></html>', encoding='utf-8')
        self.assertIn('title', self.codes(check_html.inspect(self.page)))

    def test_cli_input_error_json(self):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            code = check_html.main([str(self.root / 'missing.html')])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(capture.getvalue())['status'], 'input_error')


if __name__ == '__main__':
    unittest.main()
