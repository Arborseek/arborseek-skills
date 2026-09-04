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


def insert_visuals(fragment: str, items: list[dict], package_dir: Path, output_dir: Path, include_candidates: bool = False) -> tuple[str, str, list[str]]:
    soup = BeautifulSoup(fragment, "html.parser")
    cover_url = ""
    inserted = []
    intro_tail = None
    for item in items:
        candidate = include_candidates and item.get("status") == "candidate"
        if item.get("status") != "ready" and not candidate:
            continue
        src = materialize_asset(item, package_dir, output_dir)
        if not src:
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
        # Keep covers as semantic figures so credit, alt text, and AI disclosure
        # remain visible instead of disappearing into the generic header image.
        if item.get("role") == "cover" or placement == "cover":
            soup.insert(0, figure)
        elif placement == "after-intro":
            anchor = intro_tail if intro_tail is not None else soup.find("p")
            anchor.insert_after(figure) if anchor else soup.append(figure)
            intro_tail = figure
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
    if include_candidates:
        notice = soup.new_tag("aside", attrs={"class": "internal-preview-notice"})
        notice.string = "内部预览，不可直接发布；待办见核查记录。"
        soup.insert(0, notice)
    return str(soup), cover_url, inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fragment-output", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    parser.add_argument("--include-candidates", action="store_true")
    args = parser.parse_args()
    if args.require_ready and args.include_candidates:
        parser.error("Candidate images cannot be included in a final render")

    data = json.loads(args.package.read_text(encoding="utf-8"))
    if "paper" in data:
        from paper_article import check, source_footer
        validation = check(data, args.package.parent, not args.include_candidates)
    else:
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
    if data.get("formulas"):
        from formula_assets import materialize_formulas
        try:
            source = materialize_formulas(source, data["formulas"], args.output.parent)
        except ValueError as exc:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
            raise SystemExit(1)
    fragment, preservation = engine.sanitize(source, title, args.package.parent, args.output.parent)
    if data.get("formulas"):
        formula_soup = BeautifulSoup(fragment, "html.parser")
        for img in formula_soup.select("img[width]"):
            width = int(img["width"])
            img["style"] = f"display:block;width:{width}px;max-width:100%;height:auto;margin:16px auto;"
        fragment = str(formula_soup)
    fragment, cover_url, inserted = insert_visuals(fragment, data.get("visuals", {}).get("items", []), args.package.parent, args.output.parent, args.include_candidates)
    figure_numbers = {}
    if "paper" in data:
        from figure_numbering import number_figures
        try:
            fragment, figure_numbers = number_figures(fragment, data.get("visuals", {}).get("items", []))
        except ValueError as exc:
            print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
            raise SystemExit(1)
        used = [dict(item, article_label=figure_numbers.get(str(item.get("id")), {}).get("article_label", "封面")) for item in data.get("visuals", {}).get("items", []) if str(item.get("id")) in inserted]
        fragment += source_footer(data, used)
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
        "figure_numbers": figure_numbers,
        "warnings": validation["warnings"],
        "preservation": preservation,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
