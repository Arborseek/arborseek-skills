#!/usr/bin/env python3
"""Analyze saved WeChat article HTML files and emit reusable typography metrics."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
import style_article_html as engine


PROPERTIES = (
    "font-size",
    "font-weight",
    "color",
    "background",
    "background-color",
    "line-height",
    "letter-spacing",
    "text-align",
    "margin-bottom",
    "border-left",
    "border-bottom",
)


def article_node(soup: BeautifulSoup):
    return soup.select_one("#js_content") or soup.select_one(".rich_media_content") or soup.select_one("article")


def parse_declarations(style: str) -> dict[str, str]:
    result = {}
    for declaration in style.split(";"):
        if ":" not in declaration:
            continue
        key, value = declaration.split(":", 1)
        key = key.strip().lower()
        value = " ".join(value.strip().lower().split())
        if key and value:
            result[key] = value
    return result


def title_of(soup: BeautifulSoup, fallback: str) -> str:
    node = soup.select_one("#activity-name") or soup.title
    return " ".join(node.get_text(" ", strip=True).split()) if node else fallback


def analyze(folder: Path) -> dict:
    aggregate = {name: collections.Counter() for name in PROPERTIES}
    articles = []
    signatures: dict[str, str] = {}

    for path in sorted(folder.glob("*.html")):
        soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
        body = article_node(soup)
        if body is None:
            continue
        text = " ".join(body.get_text(" ", strip=True).split())
        signature = hashlib.sha1(text.encode("utf-8")).hexdigest()
        duplicate_of = signatures.get(signature)
        if duplicate_of is None:
            signatures[signature] = path.name

        local = {name: collections.Counter() for name in PROPERTIES}
        for element in body.select("[style]"):
            for key, value in parse_declarations(element.get("style", "")).items():
                if key in local:
                    local[key][value] += 1
                    aggregate[key][value] += 1

        article_title = title_of(soup, path.stem)
        profile = engine.content_profile(article_title, str(body))
        articles.append({
            "file": path.name,
            "title": article_title,
            "duplicate_of": duplicate_of,
            "text_characters": len(text),
            "images": len(body.find_all("img")),
            "semantic_headings": len(body.find_all(re.compile(r"^h[1-6]$"))),
            "inline_styled_elements": len(body.select("[style]")),
            "top_font_sizes": local["font-size"].most_common(8),
            "top_line_heights": local["line-height"].most_common(8),
            "top_colors": local["color"].most_common(10),
            "category": profile["category"],
            "category_label": profile["category_label"],
            "classification_confidence": profile["confidence"],
            "recommended_themes": profile["ranked_themes"][:3],
        })

    unique = [item for item in articles if item["duplicate_of"] is None]
    return {
        "folder": str(folder.resolve()),
        "files": len(articles),
        "unique_articles": len(unique),
        "text_character_range": [
            min((item["text_characters"] for item in unique), default=0),
            max((item["text_characters"] for item in unique), default=0),
        ],
        "image_range": [
            min((item["images"] for item in unique), default=0),
            max((item["images"] for item in unique), default=0),
        ],
        "category_distribution": dict(collections.Counter(item["category"] for item in unique)),
        "aggregate": {name: counter.most_common(30) for name, counter in aggregate.items()},
        "articles": articles,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.folder)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
