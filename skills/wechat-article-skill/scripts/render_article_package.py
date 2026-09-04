#!/usr/bin/env python3
"""Render a validated article package into deterministic standalone and fragment HTML."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from bs4 import BeautifulSoup

import style_article_html as engine
from article_package import validate_package


def materialize_asset(item: dict, package_dir: Path, output_dir: Path) -> str:
    local = str(item.get("local_path") or "")
    if local:
        source = Path(local).expanduser()
        if not source.is_absolute():
            source = package_dir / source
        if source.is_file():
            asset_dir = output_dir / "assets"
            asset_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{hashlib.sha1(str(source.resolve()).encode('utf-8')).hexdigest()[:12]}{source.suffix.lower()}"
            shutil.copy2(source, asset_dir / filename)
            return f"assets/{filename}"
    return str(item.get("source_url") or "")


def insert_visuals(fragment: str, items: list[dict], package_dir: Path, output_dir: Path) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(fragment, "html.parser")
    cover_url = ""
    inserted = []
    for item in items:
        if item.get("status") != "ready":
            continue
        src = materialize_asset(item, package_dir, output_dir)
        if not src:
            continue
        if item.get("role") == "cover" or item.get("placement") == "cover":
            cover_url = src
            inserted.append(str(item.get("id")))
            continue

        figure = soup.new_tag("figure", attrs={"class": "editorial-figure", "data-visual-id": str(item.get("id") or "")})
        image = soup.new_tag("img", attrs={"src": src, "alt": str(item.get("alt") or "文章配图")})
        figure.append(image)
        caption_text = str(item.get("caption") or item.get("credit") or "").strip()
        if caption_text:
            caption = soup.new_tag("figcaption", attrs={"class": "caption"})
            caption.string = caption_text
            figure.append(caption)

        placement = str(item.get("placement") or "")
        if placement == "after-intro":
            anchor = soup.find("p")
            anchor.insert_after(figure) if anchor else soup.append(figure)
        elif placement.startswith("before-section:"):
            try:
                section_number = max(1, int(placement.split(":", 1)[1]))
            except ValueError:
                section_number = 1
            headings = soup.select(".section-heading")
            if headings:
                headings[min(section_number - 1, len(headings) - 1)].insert_before(figure)
            else:
                soup.append(figure)
        else:
            soup.append(figure)
        inserted.append(str(item.get("id")))
    return str(soup), cover_url, inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fragment-output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.package.read_text(encoding="utf-8"))
    validation = validate_package(data, args.package.parent, args.require_ready)
    if not validation["valid"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    article = data["article"]
    title = article["title"]
    source = article["content_html"]
    chosen = str(data.get("layout", {}).get("theme") or article.get("visual_theme") or "auto")
    seed = str(data.get("layout", {}).get("seed") or "wechat-studio-v1")
    theme = engine.select_theme(title, source, seed) if chosen == "auto" else chosen
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fragment, preservation = engine.sanitize(source, title, args.package.parent, args.output.parent)
    fragment, cover_url, inserted = insert_visuals(fragment, data.get("visuals", {}).get("items", []), args.package.parent, args.output.parent)
    metadata = article.get("metadata") or {}
    meta = " · ".join(str(metadata.get(key) or "").strip() for key in ("source_label", "author", "date") if str(metadata.get(key) or "").strip())
    args.output.write_text(engine.document(title, fragment, theme, meta, cover_url), encoding="utf-8")
    if args.fragment_output:
        args.fragment_output.parent.mkdir(parents=True, exist_ok=True)
        args.fragment_output.write_text(fragment + "\n", encoding="utf-8")

    report = {
        "valid": True,
        "output": str(args.output.resolve()),
        "fragment_output": str(args.fragment_output.resolve()) if args.fragment_output else None,
        "theme": theme,
        "category": engine.content_profile(title, source)["category"],
        "inserted_visual_ids": inserted,
        "warnings": validation["warnings"],
        "preservation": preservation,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
