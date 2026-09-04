#!/usr/bin/env python3
"""Validate the article contract before rendering or publication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from article_package import validate_package


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.package.read_text(encoding="utf-8"))
    report = validate_package(data, args.package.parent, args.require_ready)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
