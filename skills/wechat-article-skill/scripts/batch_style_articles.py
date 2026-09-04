#!/usr/bin/env python3
"""Classify and style a folder of HTML articles, producing previews and a manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path

import style_article_html as engine
from bs4 import BeautifulSoup


THEME_LABELS = {
    "blueprint": "蓝图",
    "teal-editorial": "青绿评论",
    "cobalt-journal": "钴蓝期刊",
    "violet-dialogue": "紫色访谈",
    "orange-launch": "橙色发布",
    "cyan-research": "青蓝科研",
}

INDEX_CSS = """
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#fff}body{color:#25282d;font-family:"PingFang SC",-apple-system,BlinkMacSystemFont,"Helvetica Neue","Microsoft YaHei",Arial,sans-serif}.page{width:min(100%,980px);margin:0 auto;padding:32px 20px 50px;background:#fff}h1{margin:0 0 10px;font-size:26px;line-height:1.4}.intro{margin:0 0 26px;color:rgba(0,0,0,.55);font-size:14px;line-height:1.8}.list{border-top:2px solid #1b3f6b}.item{display:grid;grid-template-columns:44px minmax(0,1fr) auto;gap:14px;padding:18px 0;border-bottom:1px solid #dbe4ee;background:#fff}.num{font-weight:700;color:#1b3f6b}.title{display:block;margin:0 0 7px;color:#223170;font-size:16px;font-weight:700;line-height:1.55;text-decoration:none}.meta{color:rgba(0,0,0,.52);font-size:12px;line-height:1.6}.theme{display:inline-block;margin-right:8px;padding-left:8px;border-left:3px solid var(--swatch)}.open{align-self:center;color:#2459b3;font-size:13px;text-decoration:none}@media(max-width:620px){.item{grid-template-columns:34px minmax(0,1fr)}.open{display:none}}
"""


def index_html(items: list[dict], diversity: str) -> str:
    rows = []
    for item in items:
        theme = item["theme"]
        primary = engine.THEMES[theme][0]
        rows.append(f"""<article class="item" style="--swatch:{primary}">
<div class="num">{item['position']:02d}</div><div><a class="title" href="{escape(item['preview_file'], quote=True)}">{escape(item['title'])}</a><div class="meta"><span class="theme">{escape(THEME_LABELS[theme])}</span>{escape(item['category_label'])} · 置信度 {item['classification_confidence']:.0%}</div></div><a class="open" href="{escape(item['preview_file'], quote=True)}">预览 →</a></article>""")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>公众号文章智能排版预览</title><style>{INDEX_CSS}</style></head><body><main class="page"><h1>公众号文章智能排版预览</h1><p class="intro">根据标题、正文语义和结构特征自动分类并选择版式。多样性策略：{escape(diversity)}。所有内容保持纯白背景。</p><section class="list">{''.join(rows)}</section></main></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--glob", default="*.html")
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument("--seed", default="wechat-article-skill-v2")
    parser.add_argument("--diversity", choices=["content-first", "balanced", "high"], default="balanced")
    parser.add_argument("--write-fragments", action="store_true", help="Write body-only HTML beside each preview")
    args = parser.parse_args()

    paths = sorted(args.input_dir.rglob(args.glob) if args.recursive else args.input_dir.glob(args.glob))
    if not paths:
        raise SystemExit(f"No files matched {args.glob!r} in {args.input_dir}")

    records = []
    seen_content = {}
    for path in paths:
        title, source = engine.extract_source(path.read_text(encoding="utf-8", errors="ignore"), None)
        normalized = engine.normalize_text(BeautifulSoup(source, "html.parser").get_text(" ", strip=True))
        content_hash = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        duplicate_of = seen_content.get(content_hash)
        if duplicate_of is None:
            seen_content[content_hash] = str(path.resolve())
        records.append({"path": path, "title": title, "content": source, "content_hash": content_hash, "duplicate_of": duplicate_of})
    assignments = engine.assign_batch_styles(records, args.seed, args.diversity)

    article_dir = args.output_dir / "articles"
    article_dir.mkdir(parents=True, exist_ok=True)
    manifest_items = []
    for position, (record, assignment) in enumerate(zip(records, assignments), 1):
        stable_id = hashlib.sha1(record["path"].name.encode("utf-8")).hexdigest()[:8]
        filename = f"{position:03d}-{stable_id}.html"
        output_path = article_dir / filename
        fragment, validation = engine.sanitize(record["content"], record["title"], record["path"].parent, article_dir)
        meta = f"{assignment['category_label']} · {THEME_LABELS[assignment['theme']]} · 自动判断置信度 {assignment['confidence']:.0%}"
        output_path.write_text(engine.document(record["title"], fragment, assignment["theme"], meta, "", "../index.html"), encoding="utf-8")
        fragment_file = None
        if args.write_fragments:
            fragment_path = article_dir / f"{position:03d}-{stable_id}.fragment.html"
            fragment_path.write_text(fragment + "\n", encoding="utf-8")
            fragment_file = f"articles/{fragment_path.name}"
        manifest_items.append({
            "position": position,
            "source_file": str(record["path"].resolve()),
            "title": record["title"],
            "preview_file": f"articles/{filename}",
            "fragment_file": fragment_file,
            "content_hash": record["content_hash"],
            "duplicate_of": record["duplicate_of"],
            "theme": assignment["theme"],
            "theme_label": THEME_LABELS[assignment["theme"]],
            "category": assignment["category"],
            "category_label": assignment["category_label"],
            "classification_confidence": assignment["confidence"],
            "category_scores": assignment["category_scores"],
            "theme_scores": assignment["theme_scores"],
            "selection_reason": assignment["selection_reason"],
            "reasons": assignment["reasons"],
            "features": assignment["features"],
            "validation": validation,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "index.html").write_text(index_html(manifest_items, args.diversity), encoding="utf-8")
    distribution = Counter(item["theme"] for item in manifest_items)
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_directory": str(args.input_dir.resolve()),
        "article_count": len(manifest_items),
        "seed": args.seed,
        "diversity": args.diversity,
        "theme_distribution": dict(sorted(distribution.items())),
        "articles": manifest_items,
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("article_count", "diversity", "theme_distribution")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
