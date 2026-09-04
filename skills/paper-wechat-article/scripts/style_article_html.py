#!/usr/bin/env python3
"""Normalize article HTML and render one of six white-background publication styles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag


THEMES = {
    "blueprint": ("#004080", "#223170", "#ffdf21", "#1306fa", "#3e3e3e", "15px", "1.95"),
    "teal-editorial": ("#008a73", "#14665b", "#72c7b7", "#007d6a", "#343b3a", "16px", "1.95"),
    "cobalt-journal": ("#153f77", "#2f6feb", "#8cb4ff", "#2459b3", "#27384d", "16px", "1.82"),
    "violet-dialogue": ("#660874", "#a65bcb", "#d5a9e5", "#7d2990", "#3d3540", "15.5px", "1.95"),
    "orange-launch": ("#b94a1c", "#ff6827", "#ffbd9c", "#c94f1d", "#3e3937", "15px", "1.82"),
    "cyan-research": ("#006c9c", "#0e88eb", "#8dd8ff", "#0879c9", "#303b43", "15px", "1.9"),
}

CATEGORY_LABELS = {
    "technical-paper": "技术论文 / 方法解读",
    "data-report": "数据报告 / 实验评测",
    "interview-profile": "访谈 / 人物",
    "launch-news": "产品发布 / 快讯",
    "editorial-analysis": "观点 / 深度分析",
    "event-promo": "活动 / 招募",
    "tutorial": "教程 / 操作指南",
}

CATEGORY_KEYWORDS = {
    "technical-paper": {
        "论文": 2.2, "模型": 1.3, "算法": 1.8, "架构": 1.5, "训练": 1.2,
        "推理": 1.1, "机器人": 1.0, "具身": 1.4, "强化学习": 1.8, "vla": 2.0,
        "transformer": 1.7, "arxiv": 2.0, "方法": 1.0, "研究": 0.8,
    },
    "data-report": {
        "实验": 1.6, "评测": 2.2, "benchmark": 2.4, "性能": 1.5, "数据集": 1.8,
        "提升": 1.4, "准确率": 1.7, "指标": 1.5, "结果": 1.0, "对比": 1.2,
        "eccv": 2.2, "cvpr": 2.2, "iclr": 2.2, "neurips": 2.2,
    },
    "interview-profile": {
        "对话": 3.0, "访谈": 3.0, "专访": 3.0, "创始人": 2.3, "负责人": 2.0,
        "嘉宾": 1.8, "问答": 2.4, "他说": 1.2, "表示": 0.7, "人物": 1.2,
    },
    "launch-news": {
        "刚刚": 2.6, "发布": 2.0, "推出": 1.8, "新品": 2.4, "售价": 2.3,
        "万元": 2.0, "融资": 2.3, "开源": 1.5, "登场": 2.0, "首发": 2.0,
        "官宣": 2.4, "完成": 0.6,
    },
    "editorial-analysis": {
        "为什么": 2.4, "如何": 1.8, "分析": 2.2, "观点": 2.1, "思考": 1.8,
        "重新认识": 2.5, "看完": 2.1, "我觉得": 2.0, "意味着": 1.0, "本质": 1.2, "趋势": 1.2, "未来": 0.8,
        "问题": 0.6, "原因": 0.8,
    },
    "event-promo": {
        "直播": 3.0, "报名": 3.0, "活动": 2.0, "奖池": 2.6, "招募": 2.6,
        "社区开放": 2.4, "预告": 2.5, "参与": 1.2, "名额": 1.8, "福利": 1.8,
    },
    "tutorial": {
        "教程": 3.0, "指南": 2.8, "步骤": 2.3, "实操": 2.5, "入门": 2.0,
        "配置": 1.5, "安装": 1.8, "操作": 1.3, "示例": 1.2, "第一步": 1.8,
        "怎么做": 2.2, "从零": 2.0, "最佳实践": 1.8,
    },
}

TITLE_INTENT = {
    "data-report": (("benchmark", "评测", "eccv", "cvpr", "iclr", "neurips"), 5.0),
    "interview-profile": (("对话", "访谈", "专访"), 6.0),
    "launch-news": (("刚刚", "发布", "融资", "售价", "万元", "新品", "官宣"), 4.0),
    "editorial-analysis": (("为什么", "如何", "分析", "重新认识", "看完", "我觉得"), 5.0),
    "event-promo": (("直播", "报名", "活动", "奖池", "招募", "预告", "社区开放"), 6.0),
    "tutorial": (("教程", "指南", "步骤", "实操", "入门", "怎么做", "从零"), 5.5),
}

THEME_AFFINITY = {
    "technical-paper": {"blueprint": 3.7, "teal-editorial": 1.0, "cobalt-journal": 4.0, "violet-dialogue": 0.5, "orange-launch": 0.7, "cyan-research": 3.4},
    "data-report": {"blueprint": 2.5, "teal-editorial": 0.8, "cobalt-journal": 3.2, "violet-dialogue": 0.4, "orange-launch": 1.0, "cyan-research": 4.2},
    "interview-profile": {"blueprint": 0.7, "teal-editorial": 2.2, "cobalt-journal": 1.8, "violet-dialogue": 4.3, "orange-launch": 1.0, "cyan-research": 0.5},
    "launch-news": {"blueprint": 1.7, "teal-editorial": 1.2, "cobalt-journal": 1.5, "violet-dialogue": 0.9, "orange-launch": 4.3, "cyan-research": 1.2},
    "editorial-analysis": {"blueprint": 1.3, "teal-editorial": 4.2, "cobalt-journal": 3.5, "violet-dialogue": 1.3, "orange-launch": 0.8, "cyan-research": 1.1},
    "event-promo": {"blueprint": 0.8, "teal-editorial": 1.2, "cobalt-journal": 0.8, "violet-dialogue": 3.3, "orange-launch": 3.8, "cyan-research": 0.5},
    "tutorial": {"blueprint": 3.6, "teal-editorial": 2.0, "cobalt-journal": 3.2, "violet-dialogue": 0.5, "orange-launch": 1.3, "cyan-research": 2.5},
}

BASE_CSS = r"""
:root { color-scheme: light; }
* { box-sizing: border-box; }
html, body { margin: 0; min-height: 100%; background: #fff; }
body {
  --primary: PRIMARY; --accent: ACCENT; --marker: MARKER; --link: LINK; --ink: INK;
  color: var(--ink);
  font-family: "PingFang SC NEW", "PingFang SC", -apple-system, BlinkMacSystemFont,
    "Helvetica Neue", "Microsoft YaHei", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
.page { width: min(100%, 717px); margin: 0 auto; padding: 20px; background: #fff; }
.preview-nav { display: inline-block; margin: 0 0 20px; color: var(--primary); font-size: 13px; line-height: 20px; text-decoration: none; }
.article-title { margin: 0 0 14px; color: rgba(0,0,0,.9); font-size: 22px; font-weight: 500; line-height: 1.4; overflow-wrap: anywhere; word-break: break-all; }
.article-meta { margin: 0 0 22px; color: rgba(0,0,0,.5); font-size: 14px; line-height: 1.55; }
.cover { display: block; width: 100%; height: auto; margin: 0 0 22px; border: 0; }
.article-body { color: var(--ink); font-size: BODY_SIZE; font-weight: 400; line-height: BODY_LINE; letter-spacing: .015em; text-align: justify; overflow-wrap: anywhere; }
.article-body p { margin: 0 0 16px; }
.article-body a { color: var(--link); text-decoration: none; overflow-wrap: anywhere; }
.article-body strong, .article-body b { color: inherit; font-weight: 700; }
.article-body .accent { color: var(--accent); }
.article-body img { display: block; width: auto; max-width: 100%; height: auto; margin: 16px auto 8px; border: 0; }
.article-body video { display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 16 / 9; margin: 16px 0 20px; border: 0; background: #fff; }
.editorial-figure { margin: 22px 0 20px; background: #fff; }
.editorial-figure img { margin: 0 auto 8px; }
.editorial-figure figcaption { margin-bottom: 0 !important; }
.image-block { margin: 0 0 8px !important; text-align: center !important; }
.caption { margin: 0 0 16px !important; color: #71777f; font-size: 12px !important; font-weight: 600; line-height: 1.8 !important; text-align: center !important; }
.section-heading { margin: 34px 0 20px; background: #fff; text-align: left; }
.section-heading h2 { margin: 0; color: var(--primary); font-size: 20px; font-weight: 700; line-height: 1.55; text-align: left; }
.section-number { color: var(--accent); font-weight: 700; }
.article-body h3 { margin: 24px 0 12px; padding: 0 0 7px; color: var(--primary); font-size: 16px; font-weight: 700; line-height: 1.7; text-align: left; border-bottom: 1px solid #dbe4ee; background: #fff; }
.article-body h4, .article-body h5, .article-body h6 { margin: 20px 0 10px; color: var(--primary); font-size: 15px; font-weight: 700; line-height: 1.75; text-align: left; background: #fff; }
.article-body ul, .article-body ol { margin: 0 0 16px; padding-left: 1.55em; }
.article-body li { margin: 5px 0; }
.article-body blockquote { margin: 18px 0; padding: 9px 0 9px 15px; color: #555d66; border-left: 4px solid var(--marker); background: #fff; }
.article-body blockquote p:last-child { margin-bottom: 0; }
.table-wrap { width: 100%; margin: 18px 0; overflow-x: auto; background: #fff; }
.article-body table { width: 100%; border-collapse: collapse; background: #fff; font-size: 13px; line-height: 1.7; }
.article-body th, .article-body td { padding: 8px 10px; border: 1px solid #dbe4ee; background: #fff; text-align: left; vertical-align: top; }
.article-body pre, .article-body code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #fff; }
.article-body pre { margin: 16px 0; padding: 12px; border: 1px solid #dbe4ee; overflow-x: auto; font-size: 13px; line-height: 1.6; }
.article-body hr { height: 0; margin: 28px 0; border: 0; border-top: 1px solid #dbe4ee; }

/* Numbered technical blueprint */
.theme-blueprint .section-heading { display: grid; grid-template-columns: 54px minmax(0,1fr); align-items: end; gap: 12px; padding-bottom: 8px; border-bottom: 2px solid var(--primary); }
.theme-blueprint .section-number { font-size: 30px; line-height: 42px; letter-spacing: -1px; color: var(--primary); text-shadow: 2px 2px 0 var(--marker); }
.theme-blueprint .section-heading h2 { padding-bottom: 4px; font-size: 18px; }

/* Opinion/editorial rail */
.theme-teal-editorial .section-heading { padding: 2px 0 2px 14px; border-left: 5px solid var(--primary); }
.theme-teal-editorial .section-number { display: block; margin-bottom: 3px; color: var(--accent); font-size: 12px; line-height: 1.2; letter-spacing: .14em; }
.theme-teal-editorial .section-heading h2 { font-size: 20px; }

/* Calm research journal */
.theme-cobalt-journal .section-heading { padding: 2px 0 2px 12px; border-left: 4px solid var(--accent); }
.theme-cobalt-journal .section-number { display: block; margin-bottom: 2px; color: #738096; font-size: 11px; line-height: 1.3; letter-spacing: .12em; }
.theme-cobalt-journal .section-heading h2 { font-size: 21px; font-weight: 750; letter-spacing: .01em; }

/* Interview/profile divider */
.theme-violet-dialogue .section-heading { padding: 13px 0 12px; border-top: 1px solid var(--marker); border-bottom: 1px solid var(--marker); text-align: center; }
.theme-violet-dialogue .section-number { display: block; margin-bottom: 3px; font-size: 11px; line-height: 1.2; letter-spacing: .16em; text-transform: uppercase; }
.theme-violet-dialogue .section-heading h2 { font-size: 19px; text-align: center; }

/* Product/launch statement */
.theme-orange-launch .section-heading { position: relative; padding-bottom: 12px; }
.theme-orange-launch .section-heading::after { content: ""; position: absolute; left: 0; bottom: 0; width: 54px; border-bottom: 3px solid var(--accent); }
.theme-orange-launch .section-number { margin-right: 9px; font-size: 16px; }
.theme-orange-launch .section-heading h2 { display: inline; color: #3e3937; font-size: 20px; }

/* Quantitative research bracket */
.theme-cyan-research .section-heading { display: grid; grid-template-columns: 42px minmax(0,1fr); gap: 10px; align-items: center; padding: 8px 0; border-top: 1px solid var(--marker); border-bottom: 1px solid var(--marker); }
.theme-cyan-research .section-number { color: var(--accent); font-size: 13px; line-height: 1; letter-spacing: .05em; }
.theme-cyan-research .section-number::before { content: "["; }.theme-cyan-research .section-number::after { content: "]"; }
.theme-cyan-research .section-heading h2 { font-size: 19px; }

@media (max-width: 560px) {
  .page { padding: 18px 20px 30px; }
  .theme-blueprint .section-heading { grid-template-columns: 46px minmax(0,1fr); gap: 9px; }
  .theme-blueprint .section-number { font-size: 27px; }
}
@media print { .preview-nav { display: none; } .page { width: 100%; padding: 0; } }
"""


def normalize_text(value: str) -> str:
    return " ".join(value.split())


def content_profile(title: str, content: str) -> dict:
    """Return explainable content/category/theme scores from text and structure."""
    soup = BeautifulSoup(content, "html.parser")
    text = normalize_text(soup.get_text(" ", strip=True))
    title_lower = title.lower()
    text_lower = text.lower()
    headings = len(soup.find_all(re.compile(r"^h[1-6]$")))
    paragraphs = len(soup.find_all("p")) or max(1, text.count("。"))
    images = len(soup.find_all("img"))
    tables = len(soup.find_all("table"))
    blockquotes = len(soup.find_all("blockquote"))
    digit_count = len(re.findall(r"\d", text))
    percent_count = len(re.findall(r"\d(?:\.\d+)?\s*%", text))
    question_count = text.count("？") + text.count("?")
    quote_pairs = min(text.count("“"), text.count("”"))
    speaker_lines = len(re.findall(r"(?:^|[。\n])[^。\n：:]{1,12}[：:]", text))
    text_length = len(text)
    features = {
        "text_characters": text_length,
        "paragraphs": paragraphs,
        "headings": headings,
        "images": images,
        "tables": tables,
        "blockquotes": blockquotes,
        "digit_ratio": round(digit_count / max(1, text_length), 4),
        "percent_mentions": percent_count,
        "question_marks": question_count,
        "quote_pairs": quote_pairs,
        "speaker_lines": speaker_lines,
        "images_per_1000_chars": round(images * 1000 / max(1, text_length), 2),
    }

    scores = {category: 0.2 for category in CATEGORY_LABELS}
    reasons = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        matched = []
        lexical_score = 0.0
        for keyword, weight in keywords.items():
            title_hits = title_lower.count(keyword)
            body_hits = text_lower.count(keyword)
            hits = min(4, title_hits * 2 + body_hits)
            if hits:
                lexical_score += hits * weight
                matched.append(keyword)
        scores[category] += min(14.0, lexical_score)
        if matched:
            reasons.append(f"{CATEGORY_LABELS[category]}关键词：{'、'.join(matched[:6])}")

    for category, (keywords, boost) in TITLE_INTENT.items():
        matched = [keyword for keyword in keywords if keyword in title_lower]
        if matched:
            scores[category] += boost + min(2.0, (len(matched) - 1) * 0.8)
            reasons.append(f"标题意图优先：{CATEGORY_LABELS[category]}（{'、'.join(matched)}）")

    scores["technical-paper"] += min(2.4, headings * 0.18) + min(1.4, tables * 0.7)
    scores["data-report"] += min(2.2, features["digit_ratio"] * 45) + min(2.0, percent_count * 0.4) + min(1.5, tables * 0.75)
    scores["interview-profile"] += min(2.0, speaker_lines * 0.35) + min(1.2, quote_pairs * 0.06) + min(0.8, blockquotes * 0.25)
    scores["launch-news"] += min(1.3, images * 1000 / max(1, text_length) * 0.16) + min(0.8, title.count("！") * 0.4)
    scores["editorial-analysis"] += min(1.5, question_count * 0.18) + (0.9 if text_length >= 3500 else 0.0)
    scores["event-promo"] += min(0.8, title.count("【") * 0.4 + title.count("！") * 0.15)
    ordered_markers = len(re.findall(r"(?:第[一二三四五六七八九十]+步|步骤\s*\d+|step\s*\d+)", text_lower))
    scores["tutorial"] += min(2.0, ordered_markers * 0.5) + min(1.0, len(soup.find_all(["ol", "pre", "code"])) * 0.25)

    ranked_categories = sorted(scores, key=lambda category: (-scores[category], category))
    category = ranked_categories[0]
    top_score = scores[category]
    second_score = scores[ranked_categories[1]]
    confidence = max(0.0, min(1.0, (top_score - second_score) / max(1.0, top_score)))

    theme_scores = dict(THEME_AFFINITY[category])
    for secondary in ranked_categories[1:3]:
        influence = min(0.35, scores[secondary] / max(1.0, top_score) * 0.28)
        for theme in THEMES:
            theme_scores[theme] += THEME_AFFINITY[secondary][theme] * influence
    if headings >= 6:
        theme_scores["blueprint"] += 0.7
        theme_scores["cyan-research"] += 0.35
    if features["digit_ratio"] >= 0.035 or percent_count >= 3 or tables:
        theme_scores["cyan-research"] += 0.8
    if speaker_lines >= 3 or quote_pairs >= 10:
        theme_scores["violet-dialogue"] += 0.7
    if text_length >= 5000:
        theme_scores["cobalt-journal"] += 0.5
    if question_count >= 4:
        theme_scores["teal-editorial"] += 0.45
    if features["images_per_1000_chars"] >= 4:
        theme_scores["orange-launch"] += 0.35

    ranked_themes = sorted(theme_scores, key=lambda theme: (-theme_scores[theme], theme))
    reasons.extend([
        f"结构：{text_length}字、{headings}个标题、{images}张图、{tables}个表格、{blockquotes}个引用",
        f"主题判断：{CATEGORY_LABELS[category]}，首选风格 {ranked_themes[0]}",
    ])
    return {
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "confidence": round(confidence, 3),
        "category_scores": {key: round(value, 3) for key, value in scores.items()},
        "theme_scores": {key: round(value, 3) for key, value in theme_scores.items()},
        "ranked_themes": ranked_themes,
        "features": features,
        "reasons": reasons[:10],
    }


def eligible_themes(title: str, content: str) -> list[str]:
    return content_profile(title, content)["ranked_themes"][:3]


def _stable_jitter(seed: str, title: str, theme: str) -> float:
    digest = hashlib.sha256(f"{seed}|{title}|{theme}".encode("utf-8")).digest()
    return int.from_bytes(digest[:2], "big") / 65535 * 0.08


def select_theme(title: str, content: str, seed: str) -> str:
    profile = content_profile(title, content)
    best = profile["theme_scores"]
    return max(THEMES, key=lambda theme: (best[theme] + _stable_jitter(seed, title, theme), theme))


def assign_batch_styles(articles: list[dict], seed: str, diversity: str = "balanced") -> list[dict]:
    """Assign content-compatible themes with optional soft diversity pressure."""
    if diversity not in {"content-first", "balanced", "high"}:
        raise ValueError("diversity must be content-first, balanced, or high")
    count_penalty = {"content-first": 0.0, "balanced": 0.42, "high": 0.78}[diversity]
    compatibility_gap = {"content-first": 0.55, "balanced": 1.8, "high": 2.8}[diversity]
    counts = {name: 0 for name in THEMES}
    assigned = []
    chosen_themes = []

    for article in articles:
        title = str(article.get("title") or "")
        content = str(article.get("content") or article.get("html") or article.get("text") or "")
        profile = content_profile(title, content)
        raw_scores = profile["theme_scores"]
        maximum = max(raw_scores.values())
        candidates = [theme for theme in THEMES if raw_scores[theme] >= maximum - compatibility_gap]
        adjusted = {}
        for theme in candidates:
            repeat_penalty = 1.4 if len(chosen_themes) >= 2 and chosen_themes[-1] == chosen_themes[-2] == theme else 0.0
            adjusted[theme] = raw_scores[theme] - counts[theme] * count_penalty - repeat_penalty + _stable_jitter(seed, title, theme)
        chosen = max(candidates, key=lambda theme: (adjusted[theme], theme))
        counts[chosen] += 1
        chosen_themes.append(chosen)
        assigned.append({
            **profile,
            "theme": chosen,
            "selection_score": round(adjusted[chosen], 3),
            "selection_reason": f"{profile['category_label']}；{diversity} 多样性；在内容兼容候选中选择 {chosen}",
        })
    return assigned


def assign_batch_themes(articles: list[dict], seed: str, diversity: str = "balanced") -> list[str]:
    return [item["theme"] for item in assign_batch_styles(articles, seed, diversity)]


def heading_text(value: str) -> str:
    value = re.sub(r"^[一二三四五六七八九十百]+[、.．]\s*", "", value)
    value = re.sub(r"^第[一二三四五六七八九十百]+[章节篇]\s*[：:]?\s*", "", value)
    value = re.sub(r"^\d+[、.．]\s*", "", value)
    value = re.sub(r"^\d+\s+(?=\D)", "", value)
    return value.strip() or "本节"


def promote_visual_headings(soup: BeautifulSoup) -> None:
    candidates = list(soup.find_all(["p", "section", "div"]))
    for node in reversed(candidates):
        if node.attrs is None or node.find(["img", "table"]) or node.find(re.compile(r"^h[1-6]$")):
            continue
        text = normalize_text(node.get_text(" ", strip=True))
        if not text or len(text) > 80:
            continue
        style = " ".join([str(node.get("style") or ""), *[str(child.get("style") or "") for child in node.select("[style]")]]).lower()
        font_sizes = [float(value) for value in re.findall(r"font-size\s*:\s*([0-9.]+)px", style)]
        prominent = bool(node.find(["strong", "b"])) or "font-weight: bold" in style or any(size >= 18 for size in font_sizes)
        major = re.match(r"^(?:[一二三四五六七八九十]+[、.]|第.+[章节]|\d+[、.．\s])", text)
        minor = re.match(r"^\d+\.\d+", text)
        standalone_large = len(text) <= 50 and any(size >= 19 for size in font_sizes) and not node.find(["p", "section", "div"])
        if minor and prominent:
            node.name = "h3"
        elif (major and prominent) or standalone_large:
            node.name = "h2"


def extract_source(raw: str, supplied_title: Optional[str]) -> tuple[str, str]:
    soup = BeautifulSoup(raw, "html.parser")
    body = soup.select_one("#js_content") or soup.select_one(".rich_media_content") or soup.select_one("article") or soup.body or soup
    title_node = soup.select_one("#activity-name") or soup.find("h1") or soup.title
    title = supplied_title or (normalize_text(title_node.get_text(" ", strip=True)) if title_node else "未命名文章")
    return title, str(body)


def sanitize(fragment: str, title: str, source_dir: Path, output_dir: Path) -> tuple[str, dict]:
    soup = BeautifulSoup(fragment, "html.parser")
    before_images = len(soup.find_all("img"))
    copied_assets = 0
    for node in soup.find_all(["script", "style", "link", "meta", "iframe", "object", "embed", "form", "input", "button", "noscript"]):
        node.decompose()
    before_text = normalize_text(soup.get_text(" ", strip=True))
    promote_visual_headings(soup)

    # Some rich-text editors misuse blockquote as a generic container around
    # a video and its introduction. Such content is not a quotation and must
    # not inherit the theme's quotation rail. Promote video-only wrappers so
    # downstream clients can split rich text and native video safely.
    for quote in list(soup.find_all("blockquote")):
        if quote.find("video"):
            quote.unwrap()
    for video in list(soup.find_all("video")):
        while video.parent is not soup and video.parent.name in {"div", "p", "strong", "b"}:
            parent = video.parent
            other_text = normalize_text(parent.get_text(" ", strip=True))
            other_tags = [node for node in parent.find_all(recursive=False) if node is not video and node.name != "source"]
            if other_text or other_tags:
                break
            parent.unwrap()

    allowed = {
        "span": {"data-figure-ref"},
        "a": {"href", "title"}, "img": {"src", "data-src", "alt", "title", "width", "height"},
        "video": {"src", "poster", "controls"}, "source": {"src", "type"},
        "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"},
    }
    for node in soup.find_all(True):
        local_src = str(node.get("src") or "") if node.name == "img" else ""
        remote_src = str(node.get("data-src") or "") if node.name == "img" else ""
        data_type = str(node.get("data-type") or "") if node.name == "img" else ""
        node.attrs = {key: value for key, value in node.attrs.items() if key in allowed.get(node.name, set())}
        if node.name == "a":
            node["target"] = "_blank"
            node["rel"] = "noopener noreferrer nofollow"
        elif node.name == "img":
            resolved_local = None
            if local_src and not re.match(r"^(?:https?:|data:|//)", local_src, re.I):
                candidate = (source_dir / unquote(local_src.split("#", 1)[0].split("?", 1)[0])).resolve()
                if candidate.is_file():
                    resolved_local = candidate
            if resolved_local is not None:
                suffix = resolved_local.suffix
                if not suffix and data_type.lower() in {"png", "gif", "webp", "jpeg", "jpg"}:
                    suffix = ".jpg" if data_type.lower() in {"jpeg", "jpg"} else f".{data_type.lower()}"
                asset_dir = output_dir / "assets"
                asset_dir.mkdir(parents=True, exist_ok=True)
                asset_name = f"{hashlib.sha1(str(resolved_local).encode('utf-8')).hexdigest()[:12]}{suffix}"
                shutil.copy2(resolved_local, asset_dir / asset_name)
                node["src"] = f"assets/{asset_name}"
                copied_assets += 1
            elif remote_src:
                node["src"] = remote_src
            node.attrs.pop("data-src", None)
            if not node.get("src"):
                node.decompose()
                continue
            node["alt"] = node.get("alt") or "文章插图"
        elif node.name == "video":
            node["controls"] = "controls"

    first_content = soup.find(["h1", "h2", "p"])
    if first_content and normalize_text(first_content.get_text(" ", strip=True)) == normalize_text(title):
        first_content.decompose()

    major_nodes = list(soup.find_all(["h1", "h2"]))
    for index, node in enumerate(major_nodes, 1):
        if node.attrs is None:
            continue
        text = heading_text(normalize_text(node.get_text(" ", strip=True)))
        wrapper = soup.new_tag("div", attrs={"class": "section-heading"})
        number = soup.new_tag("span", attrs={"class": "section-number"})
        number.string = f"{index:02d}"
        heading = soup.new_tag("h2")
        heading.string = text
        wrapper.extend([number, heading])
        node.replace_with(wrapper)

    for paragraph in soup.find_all("p"):
        if paragraph.attrs is None:
            continue
        text = normalize_text(paragraph.get_text(" ", strip=True))
        if paragraph.find("img") and not text:
            paragraph["class"] = ["image-block"]
        elif len(text) <= 90 and re.match(r"^(图|表)\s*[0-9一二三四五六七八九十]+(?:[：:、.．\-]|\s)", text):
            paragraph["class"] = ["caption"]

    for strong in soup.find_all(["strong", "b"]):
        if strong.attrs is None or strong.find_parent(["h2", "h3", "h4", "h5", "h6"]):
            continue
        text = normalize_text(strong.get_text(" ", strip=True))
        if 0 < len(text) <= 42:
            strong["class"] = ["accent"]

    for table in list(soup.find_all("table")):
        wrapper = soup.new_tag("div", attrs={"class": "table-wrap"})
        table.wrap(wrapper)

    for node in list(soup.find_all(["p", "div", "span", "section"])):
        if node.attrs is None or node.get("class") in (["section-heading"], ["table-wrap"]):
            continue
        if not node.get_text(strip=True) and not node.find(["img", "video", "table", "hr"]):
            node.decompose()

    text_copy = BeautifulSoup(str(soup), "html.parser")
    for number in text_copy.select(".section-number"):
        number.decompose()
    after_text = normalize_text(text_copy.get_text(" ", strip=True))
    report = {
        "source_text_characters": len(before_text),
        "output_text_characters": len(after_text),
        "text_preservation_ratio": round(len(after_text) / max(1, len(before_text)), 4),
        "source_images": before_images,
        "output_images": len(soup.find_all("img")),
        "copied_local_assets": copied_assets,
        "major_sections": len(soup.select(".section-heading")),
    }
    return str(soup), report


def css_for(theme: str) -> str:
    primary, accent, marker, link, ink, body_size, body_line = THEMES[theme]
    return (BASE_CSS.replace("PRIMARY", primary).replace("ACCENT", accent).replace("MARKER", marker)
            .replace("LINK", link).replace("INK", ink).replace("BODY_SIZE", body_size).replace("BODY_LINE", body_line))


def document(title: str, fragment: str, theme: str, meta: str, cover_url: str = "", back_href: str = "") -> str:
    safe_title = escape(title)
    safe_meta = escape(meta)
    cover = f'<img class="cover" src="{escape(cover_url, quote=True)}" alt="{safe_title}">' if cover_url else ""
    back = f'<a class="preview-nav" href="{escape(back_href, quote=True)}">← 返回文章目录</a>' if back_href else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="color-scheme" content="light"><title>{safe_title}</title><style>{css_for(theme)}</style></head>
<body class="theme-{theme}"><main class="page">{back}<header><h1 class="article-title">{safe_title}</h1>{f'<p class="article-meta">{safe_meta}</p>' if safe_meta else ''}{cover}</header><article id="article-content" class="article-body">{fragment}</article></main></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fragment-output", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--meta", default="")
    parser.add_argument("--cover", default="")
    parser.add_argument("--back-href", default="")
    parser.add_argument("--theme", choices=["auto", *THEMES], default="auto")
    parser.add_argument("--seed", default="wechat-article-skill-v1")
    args = parser.parse_args()

    title, source = extract_source(args.input.read_text(encoding="utf-8", errors="ignore"), args.title)
    profile = content_profile(title, source)
    theme = select_theme(title, source, args.seed) if args.theme == "auto" else args.theme
    fragment, report = sanitize(source, title, args.input.parent, args.output.parent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document(title, fragment, theme, args.meta, args.cover, args.back_href), encoding="utf-8")
    if args.fragment_output:
        args.fragment_output.parent.mkdir(parents=True, exist_ok=True)
        args.fragment_output.write_text(fragment + "\n", encoding="utf-8")
    report.update({
        "title": title,
        "theme": theme,
        "category": profile["category"],
        "category_label": profile["category_label"],
        "classification_confidence": profile["confidence"],
        "style_reasons": profile["reasons"],
        "theme_scores": profile["theme_scores"],
        "output": str(args.output.resolve()),
    })
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
