"""Offline search regression tests; fixtures never contact arXiv."""
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import arxiv_api as api
import search

FEED = b'''<feed xmlns="http://www.w3.org/2005/Atom"
xmlns:o="http://a9.com/-/spec/opensearch/1.1/">
<o:totalResults>3</o:totalResults><entry>
<id>https://arxiv.org/abs/1706.03762v1</id><title>Test Paper</title>
<summary>Test abstract</summary><author><name>Test Author</name></author>
<published>2017-06-12T00:00:00Z</published><updated>2017-06-12T00:00:00Z</updated>
</entry></feed>'''


class Response(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {}

    def geturl(self):
        return api.API


class Tests(unittest.TestCase):
    def test_phrases_and_boolean(self):
        query = search.build_query(keywords=["graph neural network", "forecasting"])
        self.assertIn('ti:"graph neural network" OR abs:"graph neural network"', query)
        self.assertIn(' AND (ti:"forecasting"', query)

    def test_native_expression_grouped(self):
        query = search.build_query(query="ti:A OR ti:B", categories=["cs.LG", "cs.AI"])
        self.assertEqual(query, "(ti:A OR ti:B) AND (cat:cs.LG OR cat:cs.AI)")

    def test_dates(self):
        query = search.build_query(keywords=["test"], since="2024-02-29", until="2024-03-01")
        self.assertIn("submittedDate:[202402290000 TO 202403012359]", query)

    def test_reversed_dates(self):
        with self.assertRaises(ValueError):
            search.build_query(query="ti:A", since="2026-09-01", until="2026-08-01")

    def test_impossible_date(self):
        with self.assertRaises(ValueError):
            search.build_query(query="ti:A", since="2025-02-29")

    def test_empty_query(self):
        with self.assertRaises(ValueError):
            search.build_query(query=" ")

    def test_exclusive_modes(self):
        with self.assertRaises(ValueError):
            search.build_query(query="test", keywords=["test"])

    def test_keyword_quote_rejected(self):
        with self.assertRaises(ValueError):
            search.build_query(keywords=['a" OR all:b'])

    def test_category_injection_rejected(self):
        with self.assertRaises(ValueError):
            search.build_query(query="test", categories=["cs.LG OR all:test"])

    def test_control_char_rejected(self):
        with self.assertRaises(ValueError):
            search.build_query(query="test\nother")

    def test_parse_metadata(self):
        result = api.parse_feed(FEED)
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["papers"][0]["id"], "1706.03762v1")
        self.assertEqual(result["papers"][0]["authors"], ["Test Author"])

    def test_api_error_rejected(self):
        with self.assertRaises(ValueError):
            api.parse_feed(FEED.replace(b"https://arxiv.org/abs/1706.03762v1", b"https://arxiv.org/api/errors"))

    def test_non_feed_rejected(self):
        with self.assertRaises(ValueError):
            api.parse_feed(b"<html>Error</html>")

    def test_version_dedup(self):
        item = api.parse_feed(FEED)["papers"][0]
        papers = search.unique_papers([item, dict(item, id="1706.03762v10"), dict(item, id="1706.03762v2")])
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["version"], 10)
        self.assertEqual(papers[0]["pdf_url"], "https://arxiv.org/pdf/1706.03762v10")

    def test_missing_abstract_scope(self):
        papers = search.unique_papers([{"id": "1706.03762v1", "summary": ""}])
        self.assertEqual(papers[0]["read_scope"], "metadata_only")

    def test_legacy_id_handoff(self):
        papers = search.unique_papers([{"id": "hep-th/9901001v1", "summary": "test"}])
        self.assertEqual(papers[0]["base_id"], "hep-th/9901001")
        self.assertEqual(api.arxiv_id(papers[0]["pdf_url"]), papers[0]["id"])

    def test_query_record_and_counts(self):
        client = Mock()
        client.metadata.return_value = api.parse_feed(FEED)
        result = search.run_search(client, "ti:test", 10, 20, "submittedDate")
        self.assertEqual(result["total_available"], 3)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["start"], 20)
        self.assertEqual(result["query"], "ti:test")
        self.assertNotIn("selected_ids", result)
        self.assertEqual(result["coverage"], "one_result_page_not_full_literature")

    def test_atomic_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            search.save_new_json(path, {"first": True})
            with self.assertRaises(FileExistsError):
                search.save_new_json(path, {"second": True})
            self.assertEqual(json.loads(path.read_text()), {"first": True})
            self.assertEqual(len(list(Path(tmp).iterdir())), 1)

    def test_dry_run_no_network_no_file(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(search, "Client") as client, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp) / "output.json"
            self.assertEqual(search.main(["--keywords", "test", "--dry-run", "--output", str(path)]), 0)
            client.assert_not_called()
            self.assertFalse(path.exists())

    def test_empty_result_is_success(self):
        with patch.object(search.Client, "metadata", return_value={"total": 0, "papers": []}), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(search.main(["--keywords", "nothing"]), 0)
        self.assertEqual(json.loads(output.getvalue())["count"], 0)

    def test_failure_is_not_empty_success(self):
        with patch.object(search.Client, "metadata", side_effect=api.StopRequests("HTTP 429")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(search.main(["--keywords", "test"]), 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "failed")

    def test_invalid_limit(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            search.main(["--keywords", "test", "--max-results", "101"])
        self.assertEqual(error.exception.code, 2)

    def test_rate_limit_stops_immediately(self):
        client = api.Client()
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError(api.API, 429, "Limited", {}, io.BytesIO())
        with patch.object(api.time, "sleep") as sleep, self.assertRaises(api.StopRequests):
            client.metadata(search_query="test")
        self.assertEqual(client.opener.open.call_count, 1)
        sleep.assert_not_called()

    def test_zero_retries_timeout(self):
        client = api.Client(timeout=1, retries=0)
        client.opener = Mock()
        client.opener.open.side_effect = api.socket.timeout("timeout")
        with patch.object(api.time, "sleep"), self.assertRaises(RuntimeError):
            client.metadata(search_query="test")
        self.assertEqual(client.opener.open.call_count, 1)

    def test_transport_returns_atom(self):
        client = api.Client()
        client.opener = Mock()
        client.opener.open.return_value = Response(FEED)
        self.assertEqual(client.metadata(search_query="test")["total"], 3)

    def test_redirect_restriction(self):
        with self.assertRaises(ValueError):
            api.checked_url("https://example.org/private")


if __name__ == "__main__":
    unittest.main()
