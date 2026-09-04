#!/usr/bin/env python3
"""Build a WorkBuddy-compatible ZIP without changing the canonical SKILL.md."""

from __future__ import annotations

import argparse
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


SKILL_NAME = "wechat-article-skill"
WORKBUDDY_FRONTMATTER = """---
name: wechat-article-skill
display_name: 微信公众号智能创作与排版
display_name_en: WeChat Article Studio
description: 研究、撰写、配图、排版并检查微信公众号文章，输出可直接打开的完整 HTML 文件。
description_zh: 从主题研究、内容写作和配图决策，到受控 HTML 排版与交付前质量检查。
description_en: Research, write, illustrate, style, and quality-check WeChat public-account articles.
category: writing
version: {version}
author: Arborseek
user-invocable: true
---
"""

INCLUDED_PATHS = (
    "SKILL.md",
    "requirements.txt",
    "references",
    "scripts",
    "schemas",
    "examples",
)


def skill_body(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md does not start with YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("SKILL.md frontmatter is not closed")
    return text[end + len("\n---\n") :].lstrip("\n")


def copy_resource(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
    elif source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def build_package(repo_root: Path, output: Path) -> Path:
    canonical_skill = repo_root / "SKILL.md"
    if not canonical_skill.is_file():
        raise FileNotFoundError(f"Missing {canonical_skill}")
    version_match = re.search(r'^  version: "(\d+\.\d+\.\d+)"$',
                              canonical_skill.read_text(encoding="utf-8"), re.M)
    if not version_match:
        raise ValueError("Missing canonical skill version")

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wechat-skill-workbuddy-") as temp_dir:
        # WorkBuddy's upload dialog inspects the ZIP root for SKILL.md.
        # A nested skills/<name>/SKILL.md layout is valid as a catalog example
        # but is rejected by the direct importer.
        package_root = Path(temp_dir)

        for relative in INCLUDED_PATHS:
            if relative == "SKILL.md":
                continue
            copy_resource(repo_root / relative, package_root / relative)

        (package_root / "SKILL.md").write_text(
            WORKBUDDY_FRONTMATTER.format(version=version_match[1]) + "\n" + skill_body(canonical_skill),
            encoding="utf-8",
        )

        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(Path(temp_dir).rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(temp_dir))

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("dist/wechat-article-skill-workbuddy.zip"),
        help="ZIP output path (default: dist/wechat-article-skill-workbuddy.zip)",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    output = build_package(repo_root, args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
