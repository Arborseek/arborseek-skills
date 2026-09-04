#!/usr/bin/env python3
"""Local metadata transport for Tian Shu Tan Jie. Python 3.9+."""
from __future__ import annotations

import http.client
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

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
    def __init__(self, timeout=20, retries=2):
        self.timeout = timeout
        self.retries = retries
        self.opener = urllib.request.build_opener(Redirects())
        self.last = None

    def fetch(self, url, consumer):
        checked_url(url)
        for attempt in range(self.retries + 1):
            if self.last is not None:
                time.sleep(max(0, 3.1 - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            req = urllib.request.Request(url, headers={"User-Agent": "tianshu-tanjie-paper-search/1.1 (personal research client)"})
            try:
                with self.opener.open(req, timeout=self.timeout) as response:
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
                if exc.fp is not None:
                    exc.close()
                if exc.code not in (500, 502, 503, 504) or attempt == self.retries or delay > 60:
                    error = "HTTP %s；停止请求，请稍后核查" % exc.code
                    if exc.code in (403, 429, 500, 502, 503, 504):
                        raise StopRequests(error) from exc
                    raise RuntimeError(error) from exc
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, http.client.HTTPException) as exc:
                if attempt == self.retries:
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
