#!/usr/bin/env python3
"""Static quality gates for standalone WeChat article previews."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from formula_assets import unresolved_math


def lint_html(raw: str) -> dict:
    soup = BeautifulSoup(raw, "html.parser")
    errors: list[str] = []
    warnings: list[str] = []
    body = soup.body
    article = soup.select_one("#article-content")
    style_text = "\n".join(node.get_text("\n") for node in soup.find_all("style"))

    if not soup.title or not soup.title.get_text(strip=True):
        errors.append("document title is missing")
    if body is None:
        errors.append("body is missing")
    elif len([name for name in body.get("class", []) if name.startswith("theme-")]) != 1:
        errors.append("body must have exactly one theme-* class")
    if article is None or not article.get_text(" ", strip=True):
        errors.append("article body is empty")
    if article and (unresolved_math(str(article)) or article.select("[data-formula-id]")):
        errors.append("unrendered math or unresolved formula slot remains")
    if soup.find(["script", "iframe", "object", "embed", "form", "input", "button"]):
        errors.append("executable or interactive content remains")
    if "color-scheme: light" not in style_text:
        errors.append("light color-scheme is not pinned")
    if not re.search(r"(?:html, body|html|body)[^{]*\{[^}]*background\s*:\s*(?:#fff(?:fff)?|white)", style_text, re.I | re.S):
        errors.append("white page background is not explicit")
    nonwhite_background = re.findall(r"background(?:-color)?\s*:\s*(#[0-9a-f]{3,8}|[a-z]+)", style_text, re.I)
    invalid_backgrounds = sorted({value.lower() for value in nonwhite_background if value.lower() not in {"#fff", "#ffffff", "white", "transparent"}})
    if invalid_backgrounds:
        errors.append(f"non-white component backgrounds found: {', '.join(invalid_backgrounds)}")
    if "font-size: BODY_SIZE" in style_text or "line-height: BODY_LINE" in style_text:
        errors.append("unresolved typography token remains")

    for index, image in enumerate(soup.find_all("img"), 1):
        if not str(image.get("src") or "").strip():
            errors.append(f"image {index} has no src")
        if not str(image.get("alt") or "").strip():
            errors.append(f"image {index} has no alt text")
    for index, link in enumerate(soup.find_all("a"), 1):
        href = str(link.get("href") or "")
        if urlparse(href).scheme in {"http", "https"}:
            rel = set(link.get("rel") or [])
            if not {"noopener", "noreferrer"}.issubset(rel):
                errors.append(f"external link {index} lacks noopener noreferrer")
    if article and len(article.get_text(" ", strip=True)) < 120:
        warnings.append("article body is unusually short")
    if article and not article.select(".section-heading"):
        warnings.append("article has no major section headings")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "text_characters": len(article.get_text(" ", strip=True)) if article else 0,
            "images": len(soup.find_all("img")),
            "major_sections": len(soup.select(".section-heading")),
            "external_links": len([link for link in soup.find_all("a") if urlparse(str(link.get("href") or "")).scheme in {"http", "https"}]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    report = lint_html(args.html.read_text(encoding="utf-8", errors="ignore"))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
