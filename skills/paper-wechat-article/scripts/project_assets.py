"""Archive explicitly selected public project media; no crawling, cookies, or player extraction."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import tempfile
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

from paper_workspace import inside, load, sha256, validate


def safe_url(value):
    if not isinstance(value, str) or any(ord(c) < 33 for c in value) or "\\" in value:
        raise ValueError("Invalid URL")
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError("Only public HTTPS URLs on port 443 without credentials are supported")
    if any(re.search(r"token|signature|credential|secret|api.?key", k, re.I) for k, _ in parse_qsl(p.query)):
        raise ValueError("Signed/credential-bearing URLs are not stored; retain the public page link instead")
    return urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, ""))


def public_address(host):
    addresses = list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("Local/private/reserved network targets are not allowed")
    return addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=15, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        # Connect to the already checked IP; TLS still verifies the DNS host.
        raw = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_https(url, hosts, limit, sink):
    start = time.monotonic()
    for _ in range(4):
        url = safe_url(url)
        parsed = urlsplit(url)
        if parsed.hostname not in hosts:
            raise ValueError("Redirect host not approved; inspect destination before adding --allow-host")
        connection = PinnedHTTPS(parsed.hostname, public_address(parsed.hostname))
        try:
            connection.request("GET", urlunsplit(("", "", parsed.path, parsed.query, "")),
                               headers={"User-Agent": "Arborseek-Research-Archive/1.0", "Accept-Encoding": "identity"})
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirect without Location")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError("HTTP %s; stopped without retry or access-control bypass" % response.status)
            length = response.getheader("Content-Length")
            length = int(length) if length is not None else None
            if length is not None and not 0 < length <= limit:
                raise ValueError("Download size is empty or exceeds the approved limit")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ValueError("Unexpected content encoding")
            size, head = 0, b""
            while True:
                if time.monotonic() - start > 60:
                    raise TimeoutError("Download time budget exceeded")
                chunk = response.read(min(65536, limit + 1 - size))
                if not chunk:
                    break
                size += len(chunk)
                if size > limit:
                    raise ValueError("Download exceeds the approved limit")
                if len(head) < 4096:
                    head = (head + chunk)[:4096]
                sink.write(chunk)
            if not size or (length is not None and length != size):
                raise ValueError("Empty or incomplete download")
            return {"final_url": url, "bytes": size, "content_type": response.getheader("Content-Type", ""), "head": head}
        finally:
            connection.close()
    raise ValueError("Too many redirects")


def media_extension(head, kind):
    if kind == "image":
        if head.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if head.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if head[:6] in (b"GIF87a", b"GIF89a"):
            return ".gif"
        if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            return ".webp"
    if kind == "video":
        if head[4:8] == b"ftyp" and head[8:12] in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ", b"dash"):
            return ".mp4"
        if head.startswith(b"\x1aE\xdf\xa3") and b"webm" in head[:512]:
            return ".webm"
    if kind == "document" and head.lstrip().startswith(b"%PDF-"):
        return ".pdf"
    raise ValueError("Unsupported file signature; no HTML/SVG/scripts, playlists, or fake media accepted")


class Candidates(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base, self.items, self.seen = base, [], set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        urls = []
        if tag in ("img", "video", "source"):
            urls += [attrs.get("src", ""), attrs.get("poster", "")]
            urls += [s.strip().split()[0] for s in attrs.get("srcset", "").split(",") if s.strip()]
        if tag == "a":
            urls.append(attrs.get("href", ""))
        for candidate in urls:
            if not candidate or len(self.items) >= 50:
                continue
            try:
                url = safe_url(urljoin(self.base, candidate))
            except ValueError:
                continue
            if url in self.seen:
                continue
            suffix = Path(urlsplit(url).path).suffix.lower()
            kind = "image" if suffix in (".png", ".jpg", ".jpeg", ".gif", ".webp") else "video" if suffix in (".mp4", ".webm") else "document" if suffix == ".pdf" else "link"
            self.seen.add(url)
            self.items.append({"url": url, "kind_hint": kind, "source_page_url": self.base, "verified": False})


def archive(manifest, ident, url, page, title, relation_note, mode="link", kind="link", basis="",
            local=None, max_mb=50, large_approved=False, allow_hosts=(), reason="", parent_id=None, timestamp=None):
    data, manifest = load(manifest)
    root = manifest.parent
    url, page = safe_url(url), safe_url(page)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", ident) or not title.strip() or not relation_note.strip():
        raise ValueError("Asset ID, title, and verified project-to-paper relation note are required")
    if not 1 <= max_mb <= 250 or (max_mb > 50 and not large_approved):
        raise ValueError("Over 50 MiB requires explicit large-file approval; hard limit is 250 MiB")
    if mode != "link" and (kind not in ("image", "video", "document") or not basis.strip()):
        raise ValueError("Saving needs a media kind and lawful download/use basis")
    entries = data.get("project_assets", [])
    parent = None
    if parent_id:
        parent = next((p for p in entries if p["id"] == parent_id), None)
        if not parent or parent["status"] != "saved" or parent["media_type"] != "video" or mode != "import" or kind != "image":
            raise ValueError("Video frames must be imported from a saved video in this workspace")
        if timestamp is None or not math.isfinite(timestamp) or timestamp < 0 or url != parent["source_url"]:
            raise ValueError("Video frame needs source video URL and a nonnegative timestamp in seconds")
    elif timestamp is not None:
        raise ValueError("Timestamp requires --parent-id")
    request = {"source_url": url, "source_page_url": page, "media_type": kind, "mode": mode,
               "parent_id": parent_id, "timestamp_seconds": timestamp}
    if local:
        request["import_sha256"] = sha256(local)
    for old in entries:
        if old["id"] == ident:
            if old.get("request") == request and old["status"] in ("saved", "link-only"):
                return {"status": "cached", "asset": old}
            raise FileExistsError("Asset ID already exists; use a new ID for retries or revised website material")
    lock = root / ".figure-write.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        if load(manifest)[0] != data:
            raise RuntimeError("Workspace changed; reload before retrying")
        asset = dict(request, id=ident, title=title, relation_note=relation_note, request=request,
                     retrieved_at=datetime.now(timezone.utc).isoformat(), paper_sha256=data["paper"]["sha256"],
                     paper_version=data["paper"]["version"], website_version="unverified", download_basis=basis,
                     rights_status="unknown", rights_note="", checked=False, credit="", alt=title,
                     status="link-only", reason=reason or "Reference only; no media downloaded")
        if parent:
            asset.update(origin="video-frame", parent_sha256=parent["sha256"])
        else:
            asset["origin"] = "project-site"
        if mode != "link":
            try:
                with tempfile.TemporaryDirectory(prefix=".project-download-", dir=root) as tmp:
                    temporary = Path(tmp) / "asset.part"
                    with temporary.open("xb") as out:
                        if mode == "import":
                            if not local or not 0 < Path(local).stat().st_size <= max_mb * 1024 * 1024:
                                raise ValueError("Imported file size exceeds limit or file is empty")
                            with Path(local).open("rb") as src:
                                total = 0
                                while True:
                                    block = src.read(65536)
                                    if not block:
                                        break
                                    total += len(block)
                                    if total > max_mb * 1024 * 1024:
                                        raise ValueError("Import exceeds size limit")
                                    out.write(block)
                            result = {"final_url": url, "bytes": total, "content_type": "host-export"}
                        else:
                            hosts = {urlsplit(url).hostname, urlsplit(page).hostname, *allow_hosts}
                            result = fetch_https(url, hosts, max_mb * 1024 * 1024, out)
                    with temporary.open("rb") as stream:
                        extension = media_extension(stream.read(4096), kind)
                    relative = "project-assets/" + ident + extension
                    target = inside(root, relative)
                    target.parent.mkdir(exist_ok=True)
                    os.link(temporary, target)  # Atomic no-overwrite publication.
                    result.pop("head", None)
                    asset.update(result, local_path=relative, sha256=sha256(target), status="saved", reason="")
            except (OSError, ValueError, http.client.HTTPException) as exc:
                asset.update(status="failed", reason=str(exc))
        data.setdefault("project_assets", []).append(asset)
        validate(data, root)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=".manifest-", delete=False) as stream:
            temp_manifest = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temp_manifest, manifest)
        finally:
            temp_manifest.unlink(missing_ok=True)
        return {"status": asset["status"], "asset": asset}
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    discover = subs.add_parser("discover")
    discover.add_argument("--page", required=True)
    discover.add_argument("--output", type=Path, required=True)
    discover.add_argument("--allow-host", action="append", default=[])
    for mode in ("fetch", "import", "link"):
        p = subs.add_parser(mode)
        p.add_argument("manifest", type=Path)
        for field in ("id", "url", "page", "title", "relation-note"):
            p.add_argument("--" + field, required=True)
        p.add_argument("--kind", choices=("image", "video", "document", "link"), default="link")
        p.add_argument("--basis", default="")
        p.add_argument("--file", type=Path)
        p.add_argument("--max-mb", type=int, default=50)
        p.add_argument("--large-file-approved", action="store_true")
        p.add_argument("--allow-host", action="append", default=[])
        p.add_argument("--reason", default="")
        p.add_argument("--parent-id")
        p.add_argument("--timestamp", type=float)
    args = parser.parse_args()
    try:
        if args.command == "discover":
            import io
            if args.output.exists():
                raise FileExistsError("Candidate output already exists")
            page = safe_url(args.page)
            sink = io.BytesIO()
            fetched = fetch_https(page, {urlsplit(page).hostname, *args.allow_host}, 2 * 1024 * 1024, sink)
            if "text/html" not in fetched["content_type"].lower():
                raise ValueError("Project page did not return HTML")
            found = Candidates(fetched["final_url"])
            found.feed(sink.getvalue().decode("utf-8", errors="replace"))
            result = {"page": fetched["final_url"], "retrieved_at": datetime.now(timezone.utc).isoformat(),
                      "candidates": found.items, "coverage": "one static HTML page; not verified, not downloaded; dynamic players require host inspection"}
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as out:
                json.dump(result, out, ensure_ascii=False, indent=2)
        else:
            result = archive(args.manifest, args.id, args.url, args.page, args.title, args.relation_note,
                             args.command, args.kind, args.basis, args.file, args.max_mb, args.large_file_approved,
                             args.allow_host, args.reason, args.parent_id, args.timestamp)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("status") == "failed" else 0
    except (OSError, ValueError, RuntimeError, http.client.HTTPException) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
