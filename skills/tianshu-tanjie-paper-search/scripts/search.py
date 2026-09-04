#!/usr/bin/env python3
"""Search metadata only; never download papers or schedule tasks."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from pathlib import Path

from arxiv_api import Client, arxiv_id, base_id


def valid_day(value):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("日期须为 YYYY-MM-DD")
    return date.fromisoformat(value)


def build_query(query=None, keywords=None, categories=None, since=None, until=None):
    if (query is not None) == (keywords is not None):
        raise ValueError("只能选择 query 或 keywords 其中一种")
    if query is not None:
        core = query.strip()
        if not core:
            raise ValueError("查询不能为空")
    else:
        terms = [" ".join(term.split()) for term in keywords]
        if not terms or any(not term or re.search(r'["\\]', term) for term in terms):
            raise ValueError("关键词不能为空或包含引号/反斜线；复杂语法请使用 --query")
        core = " AND ".join('(ti:"%s" OR abs:"%s")' % (term, term) for term in terms)
    if any(ord(c) < 32 for c in core) or len(core) > 2000:
        raise ValueError("查询含控制字符或超过 2000 字符")
    pieces = ["(" + core + ")"]
    if categories:
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]*", cat) for cat in categories):
            raise ValueError("分类代码格式无效")
        pieces.append("(" + " OR ".join("cat:" + c for c in dict.fromkeys(categories)) + ")")
    if since or until:
        lower = valid_day(since) if since else date(1991, 1, 1)
        upper = valid_day(until) if until else datetime.now(timezone.utc).date()
        if lower > upper:
            raise ValueError("起始日期不得晚于结束日期")
        pieces.append("submittedDate:[%s0000 TO %s2359]" % (lower.strftime("%Y%m%d"), upper.strftime("%Y%m%d")))
    return " AND ".join(pieces)


def unique_papers(papers):
    results = {}
    for paper in papers:
        ident = arxiv_id(paper["id"])
        key = base_id(ident)
        version = re.search(r"v(\d+)$", ident)
        version = int(version.group(1)) if version else 0
        previous = results.get(key)
        if previous and previous[0] >= version:
            continue
        item = dict(paper)
        item.update(id=ident, base_id=key, version=version or None,
                    pdf_url="https://arxiv.org/pdf/" + ident,
                    read_scope="metadata_and_abstract" if item.get("summary") else "metadata_only")
        results[key] = (version, item)
    return [item[1] for item in results.values()]


def run_search(client, query, maximum, start, sort):
    feed = client.metadata(search_query=query, max_results=maximum, start=start,
                           sortBy=sort, sortOrder="descending")
    papers = unique_papers(feed["papers"])
    return {"schema_version": 1, "source": "arxiv_api", "query": query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "timezone": "UTC",
            "date_filter_field": "submittedDate", "sort": sort, "start": start,
            "requested": maximum, "total_available": feed["total"],
            "returned_before_dedup": len(feed["papers"]), "count": len(papers),
            "coverage": "one_result_page_not_full_literature", "papers": papers}


def save_new_json(path, payload):
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".search-", suffix=".part", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.link(name, path)  # Publish atomically, never overwrite an existing result.
    finally:
        Path(name).unlink(missing_ok=True)
    return str(path.resolve())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--query", "-q")
    mode.add_argument("--keywords", nargs="+", help="每个参数是一个短语；各短语之间 AND")
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--since", help="首次提交日期，UTC，YYYY-MM-DD，含当天")
    parser.add_argument("--until", help="首次提交日期，UTC，YYYY-MM-DD，含当天")
    parser.add_argument("--max-results", "-n", type=int, default=10)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--sort", choices=("relevance", "submittedDate", "lastUpdatedDate"), default="relevance")
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="仅检查查询，不联网或写文件")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args(argv)
    if not 1 <= args.max_results <= 100 or not 0 <= args.start < 30000 or args.start + args.max_results > 30000:
        parser.error("数量须为 1–100，分页须位于前 30000 条内")
    if not 1 <= args.timeout <= 60 or not 0 <= args.retries <= 2:
        parser.error("timeout 须为 1–60 秒，retries 须为 0–2")
    try:
        query = build_query(args.query, args.keywords, args.category, args.since, args.until)
    except ValueError as exc:
        parser.error(str(exc))
    if args.dry_run:
        print(json.dumps({"query": query, "sort": args.sort, "start": args.start,
                          "max_results": args.max_results, "network_requested": False}, ensure_ascii=False, indent=2))
        return 0
    if args.output and (args.output.expanduser().exists() or args.output.expanduser().is_symlink()):
        parser.error("结果文件已存在，请使用新文件名")
    try:
        payload = run_search(Client(args.timeout, args.retries), query, args.max_results, args.start, args.sort)
        if args.output:
            saved = save_new_json(args.output, payload)
            print("已保存：" + saved, file=sys.stderr)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, ET.ParseError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc), "query": query}, ensure_ascii=False))
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
