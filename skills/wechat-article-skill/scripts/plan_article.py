#!/usr/bin/env python3
"""Create or update an article-package JSON file from a topic and HTML draft."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from article_package import package_template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="UTF-8 HTML body or complete HTML draft")
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--topic")
    parser.add_argument("--article-type", default="auto")
    parser.add_argument("--tone", default="auto")
    parser.add_argument("--theme", default="auto")
    parser.add_argument("--research", choices=["none", "light", "standard", "deep"], default="none")
    parser.add_argument("--image-policy", choices=["none", "provided-only", "search", "generate", "hybrid"], default="hybrid")
    parser.add_argument("--image-density", choices=["sparse", "balanced", "rich"], default="balanced")
    args = parser.parse_args()

    raw = args.input.read_text(encoding="utf-8", errors="ignore")
    package = package_template(
        args.title,
        args.topic or args.title,
        raw,
        args.article_type,
        args.tone,
        args.theme,
        args.research,
        args.image_policy,
        args.image_density,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(package, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "visuals": len(package["visuals"]["items"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
