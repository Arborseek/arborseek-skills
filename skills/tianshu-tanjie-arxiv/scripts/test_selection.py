import json
import tempfile
import unittest
from pathlib import Path
from arxiv import selected_from_search


class SearchSelectionTests(unittest.TestCase):
    def test_explicit_subset_and_version_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search.json"
            path.write_text(json.dumps({"papers": [{"id": "1706.03762v1"}, {"id": "1706.03762v7"}]}))
            self.assertEqual(selected_from_search(path, ["https://arxiv.org/pdf/1706.03762v1"]), ["1706.03762v1"])
            for ids in ([], ["1706.03762"], ["1706.03762v2"]):
                with self.assertRaises(ValueError):
                    selected_from_search(path, ids)

    def test_malformed_selection_is_not_an_empty_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "search.json"
            for value in ({}, [], {"papers": "wrong"}):
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    selected_from_search(path, ["1706.03762v1"])
