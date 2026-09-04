#!/usr/bin/env python3
"""Explain an article's inferred editorial category and recommended visual styles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import style_article_html as engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--title")
    args = parser.parse_args()

    title, source = engine.extract_source(args.input.read_text(encoding="utf-8", errors="ignore"), args.title)
    profile = engine.content_profile(title, source)
    print(json.dumps({"title": title, **profile}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
