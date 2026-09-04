#!/usr/bin/env python3
"""Contracts and deterministic planning for an end-to-end WeChat article package."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

import style_article_html as engine


SCHEMA_VERSION = "1.0"
ARTICLE_TYPES = {*engine.CATEGORY_LABELS, "tutorial"}
TONES = {"auto", "professional", "academic", "accessible", "sharp", "narrative"}
RESEARCH_MODES = {"none", "light", "standard", "deep"}
IMAGE_POLICIES = {"none", "provided-only", "search", "generate", "hybrid"}
IMAGE_DENSITIES = {"sparse", "balanced", "rich"}
SOURCE_TYPES = {"provided", "searched", "generated", "chart", "diagram"}
VISUAL_ROLES = {"cover", "section", "diagram", "chart", "portrait", "product", "decorative"}
VISUAL_STATUSES = {"planned", "candidate", "approved", "ready", "rejected"}

THEME_LABELS = {
    "blueprint": "工程蓝图",
    "teal-editorial": "青绿评论",
    "cobalt-journal": "钴蓝期刊",
    "violet-dialogue": "紫色访谈",
    "orange-launch": "橙色发布",
    "cyan-research": "青蓝科研",
}

ROLE_BY_CATEGORY = {
    "technical-paper": ("diagram", "方法或系统架构关系"),
    "data-report": ("chart", "核心数据与对比关系"),
    "interview-profile": ("portrait", "受访者或访谈现场"),
    "launch-news": ("product", "正式产品或发布场景"),
    "editorial-analysis": ("section", "支撑核心观点的概念场景"),
    "event-promo": ("section", "活动议题或参与场景"),
    "tutorial": ("diagram", "步骤流程或操作关系"),
}


def _is_web_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_source_reference(value: str) -> bool:
    # Private/local papers have a content identity, not an invented public URL.
    return _is_web_url(value) or bool(re.fullmatch(r"urn:sha256:[a-f0-9]{64}", value))


def _path_exists(value: str, base_dir: Path | None) -> bool:
    if not value:
        return False
    path = Path(value).expanduser()
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path.is_file()


def validate_package(data: dict, base_dir: Path | None = None, require_ready: bool = False) -> dict:
    """Return machine-readable errors and warnings without mutating input."""
    errors: list[str] = []
    warnings: list[str] = []

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    article = data.get("article")
    if not isinstance(article, dict):
        errors.append("article must be an object")
        article = {}
    for key in ("title", "topic", "content_html"):
        if not isinstance(article.get(key), str) or not article.get(key, "").strip():
            errors.append(f"article.{key} must be a non-empty string")

    article_type = article.get("article_type", "auto")
    if article_type != "auto" and article_type not in ARTICLE_TYPES:
        errors.append(f"article.article_type must be auto or one of {sorted(ARTICLE_TYPES)}")
    if article.get("tone", "auto") not in TONES:
        errors.append(f"article.tone must be one of {sorted(TONES)}")
    theme = article.get("visual_theme", "auto")
    if theme != "auto" and theme not in engine.THEMES:
        errors.append(f"article.visual_theme must be auto or one of {sorted(engine.THEMES)}")
    if article.get("background", "white") != "white":
        errors.append("article.background must be white in this skill")

    research = data.get("research", {})
    if not isinstance(research, dict):
        errors.append("research must be an object")
        research = {}
    if research.get("mode", "none") not in RESEARCH_MODES:
        errors.append(f"research.mode must be one of {sorted(RESEARCH_MODES)}")
    sources = research.get("sources", [])
    if not isinstance(sources, list):
        errors.append("research.sources must be an array")
        sources = []
    source_urls = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(f"research.sources[{index}] must be an object")
            continue
        url = str(source.get("url") or "")
        if not _is_source_reference(url):
            errors.append(f"research.sources[{index}].url must be http(s) or a local paper SHA-256 URN")
        else:
            source_urls.add(url)
        for key in ("title", "publisher"):
            if not str(source.get(key) or "").strip():
                errors.append(f"research.sources[{index}].{key} is required")

    claims = research.get("claims", [])
    if not isinstance(claims, list):
        errors.append("research.claims must be an array")
        claims = []
    seen_claim_ids = set()
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            errors.append(f"research.claims[{index}] must be an object")
            continue
        claim_id = str(claim.get("id") or "")
        if not claim_id or claim_id in seen_claim_ids:
            errors.append(f"research.claims[{index}].id must be unique and non-empty")
        seen_claim_ids.add(claim_id)
        if not str(claim.get("claim") or "").strip():
            errors.append(f"research.claims[{index}].claim is required")
        status = claim.get("status")
        if status not in {"verified", "inference", "unverified"}:
            errors.append(f"research.claims[{index}].status is invalid")
        links = claim.get("source_urls", [])
        if status == "verified" and not links:
            errors.append(f"research.claims[{index}] is verified but has no source_urls")
        if status == "inference" and not links:
            errors.append(f"research.claims[{index}] is an inference but has no source_urls")
        if status == "inference" and not str(claim.get("notes") or "").strip():
            errors.append(f"research.claims[{index}].notes must explain the inference")
        for url in links or []:
            if url not in source_urls:
                errors.append(f"research.claims[{index}] references an undeclared source URL")
        if status == "unverified":
            warnings.append(f"research claim {claim_id or index} remains unverified")
            if require_ready:
                errors.append(f"research claim {claim_id or index} must be verified or removed")

    if require_ready and research.get("mode", "none") != "none":
        if not sources:
            errors.append("researched final package must declare at least one source")
        if not claims:
            errors.append("researched final package must declare at least one claim")

    visuals = data.get("visuals", {})
    if not isinstance(visuals, dict):
        errors.append("visuals must be an object")
        visuals = {}
    policy = visuals.get("policy", "none")
    if policy not in IMAGE_POLICIES:
        errors.append(f"visuals.policy must be one of {sorted(IMAGE_POLICIES)}")
    if visuals.get("density", "balanced") not in IMAGE_DENSITIES:
        errors.append(f"visuals.density must be one of {sorted(IMAGE_DENSITIES)}")
    items = visuals.get("items", [])
    if not isinstance(items, list):
        errors.append("visuals.items must be an array")
        items = []
    visual_ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"visuals.items[{index}] must be an object")
            continue
        prefix = f"visuals.items[{index}]"
        visual_id = str(item.get("id") or "")
        if not visual_id or visual_id in visual_ids:
            errors.append(f"{prefix}.id must be unique and non-empty")
        visual_ids.add(visual_id)
        if item.get("role") not in VISUAL_ROLES:
            errors.append(f"{prefix}.role is invalid")
        if item.get("source_type") not in SOURCE_TYPES:
            errors.append(f"{prefix}.source_type is invalid")
        if item.get("status") not in VISUAL_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        if not str(item.get("alt") or "").strip():
            errors.append(f"{prefix}.alt is required")
        if not str(item.get("placement") or "").strip():
            errors.append(f"{prefix}.placement is required")

        status = item.get("status")
        source_type = item.get("source_type")
        local_path = str(item.get("local_path") or "")
        source_url = str(item.get("source_url") or "")
        if status in {"approved", "ready"}:
            has_local = _path_exists(local_path, base_dir)
            has_remote = _is_web_url(source_url)
            if not has_local and not has_remote:
                errors.append(f"{prefix} is {status} but has no usable local_path or source_url")
            if source_type == "searched" and not str(item.get("credit") or "").strip():
                errors.append(f"{prefix}.credit is required for searched images")
            if source_type == "searched" and not _is_web_url(str(item.get("source_page_url") or "")):
                errors.append(f"{prefix}.source_page_url is required for searched images")
            if source_type == "searched" and not str(item.get("license") or "").strip():
                warnings.append(f"{prefix}.license is not documented")
                if require_ready:
                    errors.append(f"{prefix}.license is required before final rendering")
        if source_type == "generated" and not str(item.get("generation_prompt") or "").strip():
            errors.append(f"{prefix}.generation_prompt is required for generated images")
        if status == "ready" and source_type == "generated" and item.get("generated_disclosure") is not True:
            errors.append(f"{prefix}.generated_disclosure must be true for a ready generated image")
        if source_type == "searched" and not str(item.get("search_query") or "").strip():
            errors.append(f"{prefix}.search_query is required for searched images")
        if require_ready and status not in {"ready", "rejected"}:
            errors.append(f"{prefix} must be ready or rejected before final rendering")

    if policy == "none" and items:
        errors.append("visuals.items must be empty when visuals.policy is none")

    qa = data.get("qa", {})
    if not isinstance(qa, dict):
        errors.append("qa must be an object")
        qa = {}
    if require_ready:
        if qa.get("content_reviewed") is not True:
            errors.append("qa.content_reviewed must be true before final rendering")
        if research.get("mode", "none") != "none" and qa.get("sources_reviewed") is not True:
            errors.append("qa.sources_reviewed must be true before final rendering")
        if items and qa.get("visuals_reviewed") is not True:
            errors.append("qa.visuals_reviewed must be true before final rendering")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _visual_count(text_length: int, density: str) -> int:
    if density == "sparse":
        return min(2, 1 + int(text_length >= 3500))
    if density == "rich":
        return min(8, max(2, 1 + text_length // 1000))
    return min(5, max(2, 1 + text_length // 1800))


def _section_titles(content_html: str) -> list[str]:
    soup = BeautifulSoup(content_html, "html.parser")
    result = []
    for heading in soup.find_all(re.compile(r"^h[1-4]$")):
        text = engine.normalize_text(heading.get_text(" ", strip=True))
        if text and text not in result:
            result.append(text[:60])
    return result


def plan_visuals(
    title: str,
    content_html: str,
    policy: str = "hybrid",
    density: str = "balanced",
    theme: str = "auto",
    tone: str = "auto",
) -> dict:
    """Create image slots and both search/generation briefs; never fetch or fabricate assets."""
    if policy not in IMAGE_POLICIES:
        raise ValueError(f"invalid policy: {policy}")
    if density not in IMAGE_DENSITIES:
        raise ValueError(f"invalid density: {density}")
    if theme != "auto" and theme not in engine.THEMES:
        raise ValueError(f"invalid theme: {theme}")
    if tone not in TONES:
        raise ValueError(f"invalid tone: {tone}")
    if policy == "none":
        return {"policy": policy, "density": density, "items": [], "reason": "用户选择无配图"}

    profile = engine.content_profile(title, content_html)
    selected_theme = engine.select_theme(title, content_html, "visual-plan-v1") if theme == "auto" else theme
    category = profile["category"]
    text_length = profile["features"]["text_characters"]
    count = _visual_count(text_length, density)
    section_titles = _section_titles(content_html)
    primary_role, editorial_need = ROLE_BY_CATEGORY.get(category, ROLE_BY_CATEGORY["editorial-analysis"])
    theme_label = THEME_LABELS[selected_theme]

    items = []
    roles = ["cover", primary_role]
    while len(roles) < count:
        roles.append("section")
    for index, role in enumerate(roles[:count], 1):
        if index == 1:
            placement = "cover"
            ratio = "2:1"
            focus = f"概括《{title}》的核心矛盾或主角"
        else:
            section_index = min(index - 1, max(1, len(section_titles)))
            section = section_titles[section_index - 1] if section_titles else editorial_need
            placement = f"before-section:{section_index}"
            ratio = "16:9"
            focus = f"服务于「{section}」，表达{editorial_need}"

        if policy == "generate":
            source_type = "generated"
        elif policy in {"search", "provided-only"}:
            source_type = "searched" if policy == "search" else "provided"
        else:
            source_type = "searched"

        search_query = f"{title} {focus} 官方 原图 可授权"
        generation_prompt = (
            f"为微信公众号文章《{title}》创作{role}配图。"
            f"信息目标：{focus}。画面比例 {ratio}，{theme_label}视觉语言，"
            f"风格精准、克制、可编辑，白色或浅色画面基底，单一主色与少量辅色。"
            "不要水印、Logo、边框和无法识别的中文；不伪造数据、人物、产品或新闻现场。"
        )
        items.append({
            "id": f"visual-{index:02d}",
            "role": role,
            "placement": placement,
            "aspect_ratio": ratio,
            "source_type": source_type,
            "status": "planned",
            "alt": focus,
            "caption": "",
            "search_query": search_query if source_type == "searched" else "",
            "generation_prompt": generation_prompt if policy in {"generate", "hybrid"} else "",
            "source_url": "",
            "source_page_url": "",
            "local_path": "",
            "credit": "",
            "license": "",
            "generated_disclosure": source_type == "generated",
        })

    return {
        "policy": policy,
        "density": density,
        "items": items,
        "reason": f"{profile['category_label']}；{text_length}字；{density}密度；计划 {len(items)} 个有编辑作用的图片槽位",
        "category": category,
        "selected_theme": selected_theme,
    }


def package_template(
    title: str,
    topic: str,
    content_html: str,
    article_type: str = "auto",
    tone: str = "auto",
    visual_theme: str = "auto",
    research_mode: str = "none",
    image_policy: str = "hybrid",
    image_density: str = "balanced",
) -> dict:
    visuals = plan_visuals(title, content_html, image_policy, image_density, visual_theme, tone)
    return {
        "schema_version": SCHEMA_VERSION,
        "article": {
            "id": "",
            "title": title,
            "subtitle": "",
            "topic": topic,
            "audience": "",
            "goal": "",
            "article_type": article_type,
            "tone": tone,
            "visual_theme": visual_theme,
            "background": "white",
            "summary": "",
            "content_html": content_html,
            "metadata": {"author": "", "date": "", "source_label": ""},
        },
        "research": {"mode": research_mode, "query": topic, "claims": [], "sources": []},
        "visuals": {key: copy.deepcopy(value) for key, value in visuals.items() if key in {"policy", "density", "items"}},
        "layout": {"theme": visual_theme, "theme_reason": "", "seed": "wechat-studio-v1"},
        "qa": {"content_reviewed": False, "sources_reviewed": False, "visuals_reviewed": False, "browser_reviewed": False},
    }
