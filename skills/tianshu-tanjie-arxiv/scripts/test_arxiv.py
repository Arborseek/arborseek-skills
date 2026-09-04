"""Offline regression tests: python3 -m unittest discover -s SKILL_DIR/scripts."""
import contextlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

import arxiv

PDF = b"%PDF-1.4\nsynthetic signature fixture, not a parseable research paper\n%%EOF\n"
FEED = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>http://arxiv.org/abs/1706.03762v1</id><title>Attention Test</title>
<author><name>A. Author</name></author><summary>Only a fixture</summary>
<published>2017-06-12</published><updated>2017-06-12</updated></entry></feed>'''


class Response(io.BytesIO):
    def __init__(self, data=PDF, headers=None):
        super().__init__(data)
        self.headers = headers if headers is not None else {"Content-Length": str(len(data))}

    def geturl(self):
        return "https://arxiv.org/pdf/1706.03762v1"


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.meta = {"id": "1706.03762v1", "title": "Test / paper", "metadata_verified": True}

    def tearDown(self):
        self.temp.cleanup()

    def save(self, response=None, kind="pdf", limit=10000):
        return arxiv.save_response(response or Response(), self.directory, self.meta, kind,
                                   "https://arxiv.org/pdf/1706.03762v1", limit)

    def test_version_preserved(self):
        self.assertEqual(arxiv.arxiv_id("https://arxiv.org/pdf/1706.03762v2.pdf?download=1"), "1706.03762v2")

    def test_legacy_id(self):
        self.assertEqual(arxiv.arxiv_id("https://arxiv.org/abs/hep-th/9901001v3"), "hep-th/9901001v3")

    def test_prefix_and_html(self):
        self.assertEqual(arxiv.arxiv_id("arXiv: 1706.03762v1"), "1706.03762v1")
        self.assertEqual(arxiv.arxiv_id("https://arxiv.org/html/1706.03762v1"), "1706.03762v1")

    def test_reject_invalid_inputs(self):
        for value in ["https://evil.test/1706.03762", "https://arxiv.org.evil/abs/1706.03762", "prefix1706.03762suffix",
                      "1700.12345", "1713.12345", "1706.03762v0", "../../1706.03762", "https://x@arxiv.org/abs/1706.03762"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                arxiv.arxiv_id(value)

    def test_reject_redirects(self):
        for value in ["http://arxiv.org/pdf/1706.03762", "https://evil.test/file", "file:///etc/passwd"]:
            with self.assertRaises(ValueError):
                arxiv.checked_url(value)

    def test_metadata(self):
        data = arxiv.parse_feed(FEED)
        self.assertEqual(data["papers"][0]["id"], "1706.03762v1")
        self.assertEqual(data["papers"][0]["authors"], ["A. Author"])

    def test_api_error_entry(self):
        with self.assertRaises(ValueError):
            arxiv.parse_feed(FEED.replace(b"http://arxiv.org/abs/1706.03762v1", b"http://arxiv.org/api/errors"))

    def test_non_feed(self):
        with self.assertRaises(ValueError):
            arxiv.parse_feed(b"<html>Unavailable</html>")

    def test_unicode_filename(self):
        stem = arxiv.filename_stem("hep-th/9901001v1", "研究" * 180 + "<>\n/")
        self.assertNotIn("/", stem)
        self.assertLess(len(stem.encode("utf-8")), 200)

    def test_save_and_manifest(self):
        result = self.save()
        path = Path(result["file"])
        self.assertEqual(path.read_bytes(), PDF)
        meta = json.loads(Path(result["metadata"]).read_text())
        self.assertEqual(meta["sha256"], arxiv.sha256(path))
        self.assertEqual(meta["bytes"], len(PDF))
        self.assertFalse(list(self.directory.glob("*.part")))

    def test_cache_hit(self):
        saved = self.save()
        result = arxiv.cached_file(self.directory, "1706.03762v1", "pdf")
        self.assertEqual(result["file"], saved["file"])
        self.assertEqual(result["status"], "cached")

    def test_corrupt_cache(self):
        saved = self.save()
        Path(saved["file"]).write_bytes(b"corrupted")
        self.assertIsNone(arxiv.cached_file(self.directory, "1706.03762v1", "pdf"))

    def test_cache_wrong_kind(self):
        self.save()
        self.assertIsNone(arxiv.cached_file(self.directory, "1706.03762v1", "source"))

    def test_no_overwrite(self):
        first, second = self.save(), self.save()
        self.assertNotEqual(first["file"], second["file"])
        self.assertEqual(Path(first["file"]).read_bytes(), PDF)

    def test_html_rejected(self):
        with self.assertRaises(ValueError):
            self.save(Response(b"<html>rate limit</html>"))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_wrong_content_type(self):
        with self.assertRaises(ValueError):
            self.save(Response(PDF, {"Content-Type": "text/html"}))

    def test_truncated_rejected(self):
        with self.assertRaises(ValueError):
            self.save(Response(PDF, {"Content-Length": "900"}))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_size_limit(self):
        with self.assertRaises(ValueError):
            self.save(Response(PDF, {}), limit=10)
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_source_formats(self):
        for data, extension in [(b"\x1f\x8bdata", ".gz"), (PDF, ".pdf"),
                                (b"\\documentclass{article}", ".tex"), (b"%!PS-Adobe", ".ps")]:
            self.assertEqual(arxiv.file_extension(data, "source"), extension)

    def test_unknown_source(self):
        with self.assertRaises(ValueError):
            arxiv.file_extension(b"access denied", "source")

    def test_pin_latest(self):
        client = Mock()
        client.metadata.return_value = arxiv.parse_feed(FEED)
        client.fetch.return_value = {"status": "downloaded"}
        arxiv.download(client, "1706.03762", self.directory, "pdf", 10000)
        self.assertEqual(client.fetch.call_args[0][0], "https://arxiv.org/pdf/1706.03762v1")

    def test_mismatched_version_stops(self):
        client = Mock()
        client.metadata.return_value = arxiv.parse_feed(FEED)
        with self.assertRaises(ValueError):
            arxiv.download(client, "1706.03762v2", self.directory, "pdf", 10000)
        client.fetch.assert_not_called()

    def test_unversioned_no_metadata_stops(self):
        client = Mock()
        client.metadata.side_effect = RuntimeError("offline")
        with self.assertRaises(ValueError):
            arxiv.download(client, "1706.03762", self.directory, "pdf", 10000)
        client.fetch.assert_not_called()

    def test_explicit_metadata_fallback(self):
        client = Mock()
        client.metadata.side_effect = RuntimeError("offline")
        with contextlib.redirect_stderr(io.StringIO()):
            arxiv.download(client, "1706.03762v1", self.directory, "pdf", 10000)
        self.assertIn("1706.03762v1", client.fetch.call_args[0][0])

    def test_server_stop_no_fallback(self):
        client = Mock()
        client.metadata.side_effect = arxiv.StopRequests("HTTP 429")
        with self.assertRaises(arxiv.StopRequests):
            arxiv.download(client, "1706.03762v1", self.directory, "pdf", 10000)
        client.fetch.assert_not_called()

    def test_mixed_batch_exit_code(self):
        with patch.object(arxiv, "download", return_value={"status": "downloaded"}), contextlib.redirect_stdout(io.StringIO()) as output:
            code = arxiv.main(["1706.03762v1", "bad-input", "--output-dir", str(self.directory)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["results"][1]["status"], "failed")

    def test_batch_halts_on_server_limit(self):
        with patch.object(arxiv, "download", side_effect=arxiv.StopRequests("HTTP 429")) as call, contextlib.redirect_stdout(io.StringIO()):
            code = arxiv.main(["1706.03762v1", "1706.03763v1"])
        self.assertEqual(code, 1)
        self.assertEqual(call.call_count, 1)

    def test_search_conflict(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            arxiv.main(["1706.03762", "--search", "test"])
        self.assertEqual(error.exception.code, 2)

    def test_empty_search_is_success(self):
        with patch.object(arxiv.Client, "metadata", return_value={"total": 0, "papers": []}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(arxiv.main(["--search", "nothing"]), 0)

    def test_long_retry_after_stops(self):
        client = arxiv.Client()
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError(arxiv.API, 429, "Limited", {"Retry-After": "3600"}, io.BytesIO())
        with patch.object(arxiv.time, "sleep") as sleep, self.assertRaises(arxiv.StopRequests):
            client.fetch(arxiv.API, lambda r: r.read())
        sleep.assert_not_called()

    def test_retry_is_bounded(self):
        client = arxiv.Client()
        client.opener = Mock()
        client.opener.open.side_effect = [urllib.error.HTTPError(arxiv.API, 503, "Unavailable", {}, io.BytesIO()) for _ in range(3)]
        with patch.object(arxiv.time, "sleep"), self.assertRaises(arxiv.StopRequests):
            client.fetch(arxiv.API, lambda r: r.read())
        self.assertEqual(client.opener.open.call_count, 3)

    def test_request_spacing(self):
        client = arxiv.Client()
        client.opener = Mock()
        client.opener.open.side_effect = [Response(), Response()]
        with patch.object(arxiv.time, "monotonic", side_effect=[100.0, 101.0, 103.1]), patch.object(arxiv.time, "sleep") as sleep:
            client.fetch("https://arxiv.org/pdf/1706.03762v1", lambda r: r.read())
            client.fetch("https://arxiv.org/pdf/1706.03762v1", lambda r: r.read())
        self.assertAlmostEqual(sleep.call_args[0][0], 2.1)

    def test_socket_timeout_is_bounded(self):
        client = arxiv.Client()
        client.opener = Mock()
        client.opener.open.side_effect = arxiv.socket.timeout("read timed out")
        with patch.object(arxiv.time, "sleep"), self.assertRaises(RuntimeError):
            client.fetch(arxiv.API, lambda r: r.read())
        self.assertEqual(client.opener.open.call_count, 3)


if __name__ == "__main__":
    unittest.main()
