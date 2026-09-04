import base64
import copy
import io
import json
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_assets as assets
import paper_workspace as workspace

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jVZkAAAAASUVORK5CYII=")


class Response(io.BytesIO):
    def __init__(self, body=b"hello", status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = headers or {}

    def getheader(self, key, default=None):
        return self.headers.get(key, default)


class Connection:
    def __init__(self, response):
        self.response = response
        self.closed = False
    def request(self, *args, **kwargs):
        pass
    def getresponse(self):
        return self.response
    def close(self):
        self.closed = True


class ProjectAssetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="project 素材 ")
        self.base = Path(self.tmp.name)
        self.pdf = self.base / "input.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\nfixture only")
        self.ws = self.base / "workspace"
        workspace.init_workspace(self.pdf, self.ws, title="Test paper")
        self.png = self.base / "image.png"
        self.png.write_bytes(PNG)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, ident="demo", **kwargs):
        defaults = dict(url="https://example.org/image.png", page="https://example.org/project",
                        title="Project demo", relation_note="Synthetic paper page links to this synthetic project",
                        mode="import", kind="image", basis="Self-made fixture", local=self.png)
        defaults.update(kwargs)
        return assets.archive(self.ws, ident, **defaults)

    def test_import_preserves_provenance_without_claiming_rights_or_version(self):
        result = self.save()
        self.assertEqual(result["status"], "saved")
        item = result["asset"]
        self.assertEqual(item["rights_status"], "unknown")
        self.assertEqual(item["website_version"], "unverified")
        self.assertFalse(item["checked"])
        self.assertEqual(item["local_path"], "project-assets/demo.png")
        self.assertEqual(workspace.load(self.ws)[0]["figures"], [])

    def test_video_and_supplement_pdf_signatures(self):
        video = self.base / "clip.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\0" * 20)
        self.assertEqual(self.save("video", kind="video", local=video)["status"], "saved")
        self.assertEqual(self.save("supplement", kind="document", local=self.pdf)["status"], "saved")

    def test_disallowed_media_stays_failed_without_file(self):
        self.png.write_bytes(b"<html>please log in</html>")
        result = self.save()
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("local_path", result["asset"])
        self.assertFalse((self.ws / "project-assets/demo.png").exists())
        self.assertFalse((self.ws / ".figure-write.lock").exists())

    def test_link_only_never_fetches(self):
        with patch.object(assets, "fetch_https") as fetch:
            result = self.save(mode="link", kind="link", local=None, reason="Embedded player; keep public page only")
        fetch.assert_not_called()
        self.assertEqual(result["status"], "link-only")

    def test_cache_then_modified_id_is_not_overwritten(self):
        self.save()
        self.assertEqual(self.save()["status"], "cached")
        with self.assertRaises(FileExistsError):
            self.save(url="https://example.org/new.png")

    def test_relocation_preserves_files_and_changed_file_is_rejected(self):
        self.save()
        moved = self.base / "搬迁"
        shutil.move(self.ws, moved)
        self.assertEqual(len(workspace.load(moved)[0]["project_assets"]), 1)
        (moved / "project-assets/demo.png").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            workspace.load(moved)

    def test_other_paper_binding_is_rejected(self):
        self.save()
        data = workspace.load(self.ws)[0]
        data["project_assets"][0]["paper_version"] = "different"
        with self.assertRaises(ValueError):
            workspace.validate(data, self.ws)

    def test_large_limit_needs_explicit_approval(self):
        with self.assertRaises(ValueError):
            self.save(max_mb=51)
        with self.assertRaises(ValueError):
            self.save(max_mb=251, large_approved=True)
        self.assertEqual(workspace.load(self.ws)[0].get("project_assets", []), [])

    def test_video_frame_records_parent_hash_and_timestamp(self):
        video = self.base / "clip.mp4"
        video.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\0" * 20)
        self.save("video", kind="video", local=video, url="https://example.org/demo.mp4")
        frame = self.save("frame", parent_id="video", timestamp=1.5, url="https://example.org/demo.mp4")["asset"]
        self.assertEqual(frame["origin"], "video-frame")
        self.assertEqual(frame["timestamp_seconds"], 1.5)
        data = workspace.load(self.ws)[0]
        data["project_assets"][1]["parent_sha256"] = "wrong"
        with self.assertRaises(ValueError):
            workspace.validate(data, self.ws)

    def test_invalid_parent_does_not_import_frame(self):
        with self.assertRaises(ValueError):
            self.save(parent_id="missing", timestamp=3)

    def test_failed_fetch_is_recorded_without_asset(self):
        with patch.object(assets, "fetch_https", side_effect=ValueError("HTTP 403; stopped")):
            result = self.save(mode="fetch", local=None)
        self.assertEqual(result["status"], "failed")
        self.assertIn("403", result["asset"]["reason"])

    def test_candidate_scan_is_bounded_and_does_not_execute_html(self):
        parser = assets.Candidates("https://example.org/project/")
        parser.feed('<script>fetch("/secret")</script><img src="a.png"><video src="v.mp4"></video><source srcset="a.png 1x, b.webp 2x"><a href="extra.pdf">PDF</a><a href="javascript:alert(1)">bad</a>')
        self.assertEqual(len(parser.items), 4)
        self.assertTrue(all(item["verified"] is False for item in parser.items))
        parser.feed("".join('<img src="%s.png">' % i for i in range(100)))
        self.assertEqual(len(parser.items), 50)

    def test_credentials_and_non_https_urls_rejected(self):
        for url in ("http://example.org", "file:///secret", "https://user:pass@example.org", "https://example.org/?token=secret", "https://example.org:8000/a", "https://example.org/a\r\nX:1"):
            with self.assertRaises(ValueError):
                assets.safe_url(url)

    def test_private_and_mixed_dns_answers_rejected(self):
        for addresses in (["127.0.0.1"], ["10.0.0.1"], ["::1"], ["8.8.8.8", "192.168.1.1"]):
            result = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses]
            with patch.object(socket, "getaddrinfo", return_value=result):
                with self.assertRaises(ValueError):
                    assets.public_address("example.org")

    def fetch(self, response, limit=50):
        connection = Connection(response)
        with patch.object(assets, "public_address", return_value="8.8.8.8"), patch.object(assets, "PinnedHTTPS", return_value=connection):
            try:
                return assets.fetch_https("https://example.org/asset", {"example.org"}, limit, io.BytesIO())
            finally:
                self.assertTrue(connection.closed)

    def test_fetch_valid_length_and_final_source(self):
        result = self.fetch(Response(b"hello", headers={"Content-Length": "5"}))
        self.assertEqual(result["bytes"], 5)

    def test_size_and_incomplete_response_fail(self):
        for response in (Response(b"hello", headers={"Content-Length": "500"}), Response(b"hello", headers={"Content-Length": "6"}), Response(b"x" * 100)):
            with self.assertRaises(ValueError):
                self.fetch(response)

    def test_redirect_to_unapproved_host_stops(self):
        with self.assertRaises(ValueError):
            self.fetch(Response(status=302, headers={"Location": "https://other.example/asset"}))

    def test_no_retry_after_access_denial_or_rate_limit(self):
        for status in (401, 403, 429):
            with self.assertRaises(ValueError):
                self.fetch(Response(status=status))


if __name__ == "__main__":
    unittest.main()
