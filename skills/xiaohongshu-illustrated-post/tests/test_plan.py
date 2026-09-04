"""Offline migration checks; no image generation or network requests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_plan as plan


def fixture(count=6):
    return {'title': '离线测试', 'visual_intent': '解释工作流程',
            'theme': {'id': 'test', 'reason': '测试', 'reference_assets': [],
                      'dna': {key: '测试设定' for key in plan.DNA_KEYS}},
            'pages': [{'number': index, 'role': 'cover' if index == 1 else 'content',
                       'purpose': '说明一个步骤', 'core_claim': '离线校验',
                       'information_units': ['测试信息'],
                       'layout': {'backbone': 'editorial-stack'}, 'text_blocks': []}
                      for index in range(1, count + 1)]}


class PlanTests(unittest.TestCase):
    def test_six_pages(self):
        self.assertEqual(len(plan.normalize_plan(fixture())['pages']), 6)

    def test_nine_pages(self):
        self.assertEqual(len(plan.normalize_plan(fixture(9))['pages']), 9)

    def test_ten_pages_rejected(self):
        with self.assertRaises(plan.PlanError):
            plan.normalize_plan(fixture(10))

    def test_no_reference_image_needed(self):
        item = plan.normalize_plan(fixture(1))
        prompt = plan.page_prompt(item, item['pages'][0])
        self.assertIn('Reference assets: none', prompt)
        self.assertIn('测试设定', prompt)

    def test_output_path_traversal_rejected(self):
        raw = fixture(1)
        raw['pages'][0]['output_file'] = '../unexpected.png'
        with self.assertRaises(plan.PlanError):
            plan.normalize_plan(raw)


if __name__ == '__main__':
    unittest.main()
