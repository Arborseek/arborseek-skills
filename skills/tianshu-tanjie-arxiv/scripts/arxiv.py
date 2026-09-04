#!/usr/bin/env python3
"""Small, version-aware arXiv client. Python 3.9+, standard library only."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

API = "https://export.arxiv.org/api/query"
HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
ID_RE = re.compile(r"(?:\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}|[a-z][a-z0-9.-]*/\d{2}(?:0[1-9]|1[0-2])\d{3})(?:v[1-9]\d*)?")
NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


class StopRequests(RuntimeError):
    """Server denial or persistent server failure: do not try another endpoint."""


def arxiv_id(value):
    value = value.strip()
    if value.startswith("arXiv:"):
        value = value[6:].strip()
    if "://" in value:
        url = urllib.parse.urlparse(value)
        if url.scheme not in ("https", "http") or url.hostname not in HOSTS or url.username or url.password or url.port:
            raise ValueError("仅接受官方 arXiv URL")
        match = re.fullmatch(r"/(?:abs|pdf|html|src|e-print)/(.+?)/?", urllib.parse.unquote(url.path))
        if not match:
            raise ValueError("不支持的 arXiv URL 路径")
        value = match.group(1)
        if value.endswith(".pdf"):
            value = value[:-4]
    if not ID_RE.fullmatch(value):
        raise ValueError("无效的 arXiv ID：" + value)
    return value


def base_id(value):
    return re.sub(r"v\d+$", "", value)


def checked_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port:
        raise ValueError("拒绝非官方 HTTPS 下载地址或重定向")
    return url


class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self):
        self.opener = urllib.request.build_opener(Redirects())
        self.last = None

    def fetch(self, url, consumer):
        checked_url(url)
        for attempt in range(3):
            if self.last is not None:
                time.sleep(max(0, 3.1 - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            req = urllib.request.Request(url, headers={"User-Agent": "tianshu-tanjie-arxiv/1.0 (personal research client)"})
            try:
                with self.opener.open(req, timeout=45) as response:
                    checked_url(response.geturl())
                    return consumer(response)
            except urllib.error.HTTPError as exc:
                retry = exc.headers.get("Retry-After", "")
                delay = 3.1 * (2 ** attempt)
                if retry:
                    try:
                        delay = max(delay, float(retry))
                    except ValueError:
                        try:
                            delay = max(delay, parsedate_to_datetime(retry).timestamp() - time.time())
                        except (ValueError, TypeError, OverflowError):
                            pass
                exc.close()
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2 or delay > 60:
                    error = "HTTP %s；停止请求，请稍后核查（不代表没有源码）" % exc.code
                    if exc.code in (403, 429, 500, 502, 503, 504):
                        raise StopRequests(error) from exc
                    raise RuntimeError(error) from exc
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException) as exc:
                if attempt == 2:
                    raise RuntimeError("网络失败，已达到重试上限：%s" % exc) from exc
                time.sleep(3.1 * (2 ** attempt))

    def metadata(self, **params):
        def read(response):
            data = response.read(8 * 1024 * 1024 + 1)
            if len(data) > 8 * 1024 * 1024:
                raise ValueError("元数据响应过大")
            return parse_feed(data)
        return self.fetch(API + "?" + urllib.parse.urlencode(params), read)


def parse_feed(data):
    root = ET.fromstring(data)
    if root.tag != "{%s}feed" % NS["a"]:
        raise ValueError("响应不是 Atom feed")
    entries = []
    for entry in root.findall("a:entry", NS):
        def field(path):
            return " ".join((entry.findtext(path, "", NS) or "").split())
        ident = arxiv_id(field("a:id"))  # Also rejects API error entries.
        title = field("a:title")
        if not title:
            raise ValueError("元数据缺少标题")
        entries.append({"id": ident, "title": title,
                        "authors": [" ".join((a.text or "").split()) for a in entry.findall("a:author/a:name", NS)],
                        "summary": field("a:summary"), "published": field("a:published"),
                        "updated": field("a:updated"), "doi": field("x:doi"),
                        "journal_ref": field("x:journal_ref"),
                        "categories": [c.get("term", "") for c in entry.findall("a:category", NS)],
                        "url": "https://arxiv.org/abs/" + ident})
    total = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    return {"total": int(total) if total else len(entries), "papers": entries}


def filename_stem(ident, title):
    title = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', " ", title)
    title = " ".join(title.split()).strip(" .") or "paper"
    title = title.encode("utf-8")[:130].decode("utf-8", "ignore").rstrip(" .")
    return ident.replace("/", "_") + " - " + title


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cached_file(directory, ident, kind):
    for record in directory.glob(ident.replace("/", "_") + " - *.json"):
        try:
            meta = json.loads(record.read_text(encoding="utf-8"))
            name = meta["file"]
            if Path(name).name != name:
                continue
            target = directory / name
            if (meta["id"] == ident and meta["kind"] == kind and target.is_file()
                    and not target.is_symlink() and target.stat().st_size == meta["bytes"]
                    and sha256(target) == meta["sha256"]):
                return {"status": "cached", "id": ident, "file": str(target.resolve()),
                        "metadata": str(record.resolve()), "metadata_verified": meta.get("metadata_verified", False)}
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def file_extension(head, kind):
    if head.startswith(b"%PDF-"):
        return ".pdf"
    if kind == "pdf":
        raise ValueError("下载内容不是 PDF，未保存为论文")
    if head.startswith(b"\x1f\x8b"):
        return ".gz"
    if len(head) > 262 and head[257:262] == b"ustar":
        return ".tar"
    if head.startswith(b"%!PS"):
        return ".ps"
    stripped = head.lstrip().lower()
    if stripped.startswith((b"<!doctype html", b"<html", b"<?xml")):
        raise ValueError("源码接口返回 HTML/XML 错误页")
    if b"\\documentclass" in head or b"\\documentstyle" in head or b"\\input" in head:
        return ".tex"
    raise ValueError("无法识别源码格式，未保存；请检查官方页面")


def save_response(response, directory, meta, kind, url, max_bytes):
    directory.mkdir(parents=True, exist_ok=True)
    length = response.headers.get("Content-Length")
    expected = int(length) if length is not None else None
    if expected is not None and (expected < 0 or expected > max_bytes):
        raise ValueError("下载长度无效或超出大小上限")
    ctype = response.headers.get("Content-Type", "").lower()
    if "text/html" in ctype:
        raise ValueError("返回 HTML 而非论文文件")
    fd, temp_name = tempfile.mkstemp(prefix=".arxiv-", suffix=".part", dir=str(directory))
    temporary = Path(temp_name)
    try:
        size, head = 0, b""
        with os.fdopen(fd, "wb") as output:
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("下载超出大小上限")
                head = (head + chunk)[:4096] if len(head) < 4096 else head
                output.write(chunk)
        if size == 0 or (expected is not None and size != expected):
            raise ValueError("空文件或 Content-Length 不一致，下载不完整")
        extension = file_extension(head, kind)
        stem = filename_stem(meta["id"], meta["title"])
        record = dict(meta, kind=kind, bytes=size, sha256=sha256(temporary),
                      source_url=url, fetched_url=response.geturl(),
                      retrieved_at=datetime.now(timezone.utc).isoformat())
        number = 0
        while True:
            suffix = "" if number == 0 else " (%s)" % number
            target = directory / (stem + suffix + extension)
            sidecar = Path(str(target) + ".json")
            number += 1
            if sidecar.exists():
                continue
            try:
                os.link(temporary, target)  # Atomic publication, never overwrite.
            except FileExistsError:
                continue
            try:
                record["file"] = target.name
                with sidecar.open("x", encoding="utf-8") as stream:
                    json.dump(record, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
            except FileExistsError:
                target.unlink()  # Only the file this call just created.
                continue
            except OSError:
                target.unlink()
                raise
            return {"status": "downloaded", "id": meta["id"], "file": str(target.resolve()),
                    "metadata": str(sidecar.resolve()), "metadata_verified": meta["metadata_verified"]}
    finally:
        temporary.unlink(missing_ok=True)


def download(client, requested, directory, kind, max_bytes):
    explicit = bool(re.search(r"v\d+$", requested))
    if explicit:
        cached = cached_file(directory, requested, kind)
        if cached:
            return cached
    try:
        feed = client.metadata(id_list=requested, max_results=1)
    except StopRequests:
        raise
    except (RuntimeError, OSError, ValueError, ET.ParseError) as exc:
        if not explicit:
            raise ValueError("无法解析最新版本；请稍后重试或提供明确 vN：%s" % exc) from exc
        print("警告：元数据不可用，使用明确版本下载：%s" % exc, file=sys.stderr)
        meta = {"id": requested, "title": requested, "metadata_verified": False}
    else:
        if not feed["papers"]:
            raise ValueError("arXiv 未返回该论文的元数据")
        meta = feed["papers"][0]
        actual = meta["id"]
        if base_id(actual) != base_id(requested) or (explicit and actual != requested) or not re.search(r"v\d+$", actual):
            raise ValueError("元数据论文或版本不匹配，停止下载")
        meta["metadata_verified"] = True
    meta["requested_id"] = requested
    found = cached_file(directory, meta["id"], kind)
    if found:
        return found
    endpoint = "e-print" if kind == "source" else "pdf"
    url = "https://arxiv.org/%s/%s" % (endpoint, meta["id"])
    return client.fetch(url, lambda response: save_response(response, directory, meta, kind, url, max_bytes))


def selected_from_search(path, inputs):
    """Validate explicit choices without expanding them or making a request."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("papers"), list):
        raise ValueError("检索交接必须包含 papers 数组")
    available = {paper.get("id") for paper in data["papers"] if isinstance(paper, dict) and isinstance(paper.get("id"), str)}
    chosen = [arxiv_id(value) for value in inputs]
    if not chosen or any(not re.search(r"v\d+$", value) or value not in available for value in chosen):
        raise ValueError("只允许下载检索结果中明确选定的带版本 ID；不会默认下载全部或替换版本")
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*")
    search = parser.add_mutually_exclusive_group()
    search.add_argument("--search", help="自然关键词，以 AND 连接；原生语法用 --query")
    search.add_argument("--query", help="原生 arXiv 查询语法")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--sort", choices=("relevance", "submittedDate", "lastUpdatedDate"), default="relevance")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/papers"))
    parser.add_argument("--source", action="store_true")
    parser.add_argument("--from-search", type=Path, help="核对显式选择的 ID 属于此检索 JSON，不自动选文")
    parser.add_argument("--max-mb", type=int, default=100)
    args = parser.parse_args(argv)
    searching = args.search is not None or args.query is not None
    if not 1 <= args.max_results <= 50 or args.start < 0 or not 1 <= args.max_mb <= 1000:
        parser.error("max-results 须为 1–50，start 非负，max-mb 须为 1–1000")
    if searching and (args.inputs or args.source):
        parser.error("搜索不能与下载输入或 --source 同时使用")
    if not searching and not 1 <= len(args.inputs) <= 20:
        parser.error("请提供 1–20 个 ID/URL，或使用 --search/--query")
    if args.from_search:
        if searching:
            parser.error("--from-search 仅用于下载")
        try:
            args.inputs = selected_from_search(args.from_search, args.inputs)
        except (OSError, ValueError, TypeError) as exc:
            parser.error(str(exc))
    client = Client()
    if searching:
        query = args.query
        if args.search is not None:
            words = args.search.split()
            query = " AND ".join('all:"%s"' % word.replace('"', '').replace('\\', '') for word in words)
        if not query or not query.strip():
            parser.error("搜索词不能为空")
        try:
            result = client.metadata(search_query=query, start=args.start, max_results=args.max_results,
                                     sortBy=args.sort, sortOrder="descending")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False))
            return 1
    results, seen, stopped = [], set(), None
    for value in args.inputs:
        if stopped:
            results.append({"input": value, "status": "failed", "error": "服务端限制，本批次停止：" + stopped})
            continue
        try:
            ident = arxiv_id(value)
            if ident in seen:
                results.append({"input": value, "id": ident, "status": "duplicate"})
                continue
            seen.add(ident)
            result = download(client, ident, args.output_dir.expanduser(), "source" if args.source else "pdf", args.max_mb * 1024 * 1024)
            results.append(dict(result, input=value))
        except StopRequests as exc:
            stopped = str(exc)
            results.append({"input": value, "status": "failed", "error": stopped})
        except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
            results.append({"input": value, "status": "failed", "error": str(exc)})
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return 1 if any(item["status"] == "failed" for item in results) else 0


if __name__ == "__main__":
    sys.exit(main())
