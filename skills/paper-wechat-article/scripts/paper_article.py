"""Bridge paper evidence to the bundled WeChat renderer; no network or AI calls."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import math
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from article_package import package_template, validate_package
from paper_workspace import SCHEMA as WORKSPACE_SCHEMA, sha256, validate as validate_workspace

LABELS = {"original": "论文原图", "redraw": "依据原文重绘示意", "generated": "AI 生成概念配图，非论文原图", "project": "项目网站素材，非论文原图"}
SCOPES = {"full-text", "partial", "abstract", "notes-only"}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def paper_errors(paper):
    if not isinstance(paper, dict):
        return ["paper must be an object"]
    errors = ["paper." + key + " is required" for key in ("title", "version", "source_url")
              if not nonempty(paper.get(key))]
    url = urlparse(str(paper.get("source_url", "")))
    local = re.fullmatch(r"urn:sha256:[a-f0-9]{64}", str(paper.get("source_url", "")))
    if not local and (url.scheme not in {"https", "http"} or not url.netloc):
        errors.append("paper.source_url must be http(s) or a local paper SHA-256 URN; never invent a URL")
    if local and paper.get("source_url") != "urn:sha256:" + str(paper.get("sha256", "")):
        errors.append("Local source identity does not match paper.sha256")
    if paper.get("read_scope") not in SCOPES:
        errors.append("paper.read_scope is invalid")
    return errors


def prepare(handoff, draft, title, base, project_images=None):
    if not isinstance(handoff, dict):
        raise ValueError("handoff must be an object")
    if handoff.get("schema_version") == WORKSPACE_SCHEMA:
        validate_workspace(handoff, base)
    paper = handoff.get("paper")
    errors = paper_errors(paper)
    if errors:
        raise ValueError("; ".join(errors))
    data = package_template(title, paper["title"], draft, article_type="technical-paper",
                            tone="accessible", visual_theme="cyan-research", research_mode="standard",
                            image_policy="none")
    data["paper"] = copy.deepcopy(paper)
    if paper.get("local_pdf"):
        data["paper"]["local_pdf"] = str((base / paper["local_pdf"]).resolve())
    authors = paper.get("authors")
    credit = ", ".join(map(str, authors)) if isinstance(authors, list) else str(authors or "论文原文")
    data["research"]["sources"] = [{"url": paper["source_url"], "title": paper["title"],
                                    "publisher": credit or "论文原文"}]
    claims = handoff.get("claims", [])
    figures = copy.deepcopy(handoff.get("figures", []))
    if not isinstance(claims, list) or not isinstance(figures, list):
        raise ValueError("claims and figures must be arrays")
    data["project_assets"] = copy.deepcopy(handoff.get("project_assets", []))
    if not isinstance(data["project_assets"], list):
        raise ValueError("project_assets must be an array")
    for asset in data["project_assets"]:
        if asset.get("local_path"):
            asset["local_path"] = str((base / asset["local_path"]).resolve())
    for ident, reason in project_images or []:
        asset = next((a for a in data["project_assets"] if a.get("id") == ident), None)
        if not asset or asset.get("status") != "saved" or asset.get("media_type") != "image" or not reason.strip():
            raise ValueError("Selected project image must be saved; provide why it complements available paper figures")
        frame = asset.get("origin") == "video-frame"
        locator = asset["source_page_url"] + ("，视频 %.3f 秒" % asset["timestamp_seconds"] if frame else "")
        figures.append(dict(asset, id="project-" + ident, kind="project", label="项目演示视频截图" if frame else "项目网站图片",
                            locator=locator, caption=asset["title"], use_as_evidence=False, fallback_reason=reason,
                            project_asset_id=ident))
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("each claim must be an object")
        locator = claim.get("locator", "")
        data["research"]["claims"].append({
            "id": claim.get("id"), "claim": claim.get("claim"),
            "status": claim.get("status", "unverified"), "source_urls": [paper["source_url"]],
            "locator": locator, "notes": str(locator) + "；" + str(claim.get("notes", ""))})
    for figure in figures:
        if not isinstance(figure, dict) or figure.get("kind") not in LABELS:
            raise ValueError("each figure needs kind original, redraw, or generated")
        kind = figure["kind"]
        local = figure.get("local_path", "")
        if local and not isinstance(local, str):
            raise ValueError("figure.local_path must be a string")
        resolved = str((base / local).resolve()) if local else ""
        caption = " · ".join(str(figure.get(key) or "") for key in ("caption", "label", "locator", "credit"))
        item = {"id": figure.get("id"), "role": "section", "placement": "after-intro",
                "source_type": {"original": "provided", "redraw": "diagram", "generated": "generated", "project": "provided"}[kind],
                "status": "candidate", "alt": figure.get("alt", ""),
                "caption": LABELS[kind] + " · " + caption + " · " + (figure["source_page_url"] if kind == "project" else paper["source_url"]),
                "local_path": resolved, "source_page_url": figure["source_page_url"] if kind == "project" else paper["source_url"],
                "credit": figure.get("credit", ""), "license": figure.get("rights_note", ""),
                "paper_figure": copy.deepcopy(figure)}
        if kind == "generated":
            item.update(generation_prompt=figure.get("generation_prompt", ""), generated_disclosure=True)
        data["visuals"]["items"].append(item)
    if figures:
        data["visuals"]["policy"] = "hybrid"
    return data


def check(data, base, ready=False):
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["package must be an object"], "warnings": []}
    # The inherited validator assumes well-shaped nested collections. Turn malformed
    # imported data into a failed check rather than a successful partial validation.
    try:
        report = validate_package(data, base, ready)
    except (TypeError, AttributeError, ValueError):
        return {"valid": False, "errors": ["malformed article package"], "warnings": []}
    errors = report["errors"]
    paper = data.get("paper", {})
    errors.extend(paper_errors(paper))
    if not isinstance(paper, dict):
        paper = {}
    if paper.get("read_scope") != "full-text":
        report["warnings"].append("Limited reading scope: disclose it in the article; do not claim full-text review")
    if str(paper.get("source_url", "")).startswith("urn:"):
        report["warnings"].append("Local/private paper: no public source URL; disclose provenance and publication permission")
    if paper.get("sha256"):
        pdf_path = paper.get("local_pdf")
        pdf = (base / pdf_path).resolve() if isinstance(pdf_path, str) and pdf_path else None
        if not pdf or not pdf.is_file() or sha256(pdf) != paper["sha256"]:
            errors.append("Paper PDF is missing or changed; restore matching source before continuing")
    project_assets = data.get("project_assets", [])
    if not isinstance(project_assets, list):
        errors.append("project_assets must be an array")
        project_assets = []
    for asset in project_assets:
        if not isinstance(asset, dict):
            errors.append("Invalid project asset record")
            continue
        if asset.get("paper_sha256") != paper.get("sha256") or asset.get("paper_version") != paper.get("version"):
            errors.append("Project asset is bound to another paper record")
        if asset.get("status") == "saved":
            path = asset.get("local_path")
            path = (base / path).resolve() if isinstance(path, str) and path else None
            if not path or not path.is_file() or sha256(path) != asset.get("sha256"):
                errors.append("Archived project material is missing or changed")
        if asset.get("parent_id"):
            parent = next((p for p in project_assets if isinstance(p, dict) and p.get("id") == asset["parent_id"]), None)
            if not parent or parent.get("media_type") != "video" or parent.get("sha256") != asset.get("parent_sha256"):
                errors.append("Project video frame has no matching parent video")
            timestamp = asset.get("timestamp_seconds")
            if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp < 0:
                errors.append("Project video frame timestamp is invalid")
    article = data.get("article", {})
    if not isinstance(article, dict):
        article = {}
    soup = BeautifulSoup(str(article.get("content_html", "")), "html.parser")
    if soup.find(["img", "svg", "video", "iframe", "object", "embed", "picture"]):
        errors.append("Put all images in visuals.items for provenance checks, not content_html")
    research = data.get("research", {})
    if not isinstance(research, dict):
        research = {}
    if research.get("mode") == "none":
        errors.append("paper articles cannot disable evidence review")
    claims = research.get("claims", [])
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, dict):
            continue
        if not nonempty(claim.get("locator")):
            errors.append("Every claim needs its original locator")
        if claim.get("status") in {"verified", "inference"}:
            if paper.get("source_url") not in (claim.get("source_urls") or []):
                errors.append("Paper claims must retain the declared paper source")
    visuals = data.get("visuals", {})
    if not isinstance(visuals, dict):
        visuals = {}
    items = visuals.get("items", [])
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("status") == "rejected":
            continue
        figure = item.get("paper_figure", {})
        if not isinstance(figure, dict):
            figure = {}
        kind = figure.get("kind")
        prefix = str(item.get("id", "figure")) + ": "
        if kind not in LABELS:
            errors.append(prefix + "missing paper_figure.kind")
            continue
        if figure.get("project_asset_id") and kind != "project":
            errors.append(prefix + "archived website material must not be relabeled as a paper original")
        if kind in ("original", "project") and figure.get("paper_sha256"):
            if figure["paper_sha256"] != paper.get("sha256") or figure.get("paper_version") != paper.get("version"):
                errors.append(prefix + "figure provenance disagrees with this paper/version")
            asset_path = item.get("local_path")
            asset = (base / asset_path).resolve() if isinstance(asset_path, str) and asset_path else None
            if not asset or not asset.is_file() or sha256(asset) != figure.get("sha256"):
                errors.append(prefix + "saved original figure missing or modified; do not silently regenerate")
        if kind == "project":
            source = next((a for a in project_assets if isinstance(a, dict) and a.get("id") == figure.get("project_asset_id")), None)
            if not source or source.get("media_type") != "image" or source.get("sha256") != figure.get("sha256"):
                errors.append(prefix + "project image has no matching archived source")
            elif source.get("source_page_url") != item.get("source_page_url") or source["source_page_url"] not in str(item.get("caption", "")):
                errors.append(prefix + "project source page must remain in the visible caption")
        expected = {"original": "provided", "redraw": "diagram", "generated": "generated", "project": "provided"}[kind]
        if item.get("source_type") != expected:
            errors.append(prefix + "source_type disagrees with paper_figure.kind")
        if figure.get("rights_status") not in {"cleared", "unknown"}:
            errors.append(prefix + "rights_status must be cleared or unknown")
        if not isinstance(figure.get("use_as_evidence"), bool):
            errors.append(prefix + "use_as_evidence must be boolean")
        if kind != "original":
            if not nonempty(figure.get("fallback_reason")):
                errors.append(prefix + "record why inspected original figures cannot serve this slot")
            if figure.get("use_as_evidence") is not False:
                errors.append(prefix + "supplementary illustrations cannot be experimental evidence")
        if kind == "original" and (item.get("role") == "cover" or item.get("placement") == "cover"):
            errors.append(prefix + "keep original figures in the body with visible captions")
        if LABELS[kind] not in str(item.get("caption", "")):
            errors.append(prefix + "caption must disclose the image kind")
        if ready or item.get("status") == "ready":
            for key in ("caption", "credit", "alt"):
                if not nonempty(item.get(key)):
                    errors.append(prefix + key + " is required")
            for key in ("label", "locator") if kind == "original" else ():
                if not nonempty(figure.get(key)) or figure[key] not in str(item.get("caption", "")):
                    errors.append(prefix + key + " must appear in the visible caption")
            if item.get("credit") and item["credit"] not in str(item.get("caption", "")):
                errors.append(prefix + "credit must remain in the visible caption")
            if figure.get("checked") is not True:
                errors.append(prefix + "image has not been visually checked")
            if figure.get("rights_status") != "cleared" or not nonempty(figure.get("rights_note")):
                errors.append(prefix + "image reuse basis is unresolved")
            local = item.get("local_path")
            asset = (base / local).resolve() if isinstance(local, str) and local else None
            if not asset or not asset.is_file() or asset.stat().st_size == 0:
                errors.append(prefix + "a non-empty local asset is required; remote URL is not proof of availability")
    report["valid"] = not errors
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    prep = subs.add_parser("prepare")
    prep.add_argument("handoff", type=Path)
    prep.add_argument("draft", type=Path)
    prep.add_argument("output", type=Path)
    prep.add_argument("--title", required=True)
    prep.add_argument("--project-image", nargs=2, action="append", metavar=("ASSET_ID", "REASON"), help="Explicitly reuse a saved project image with a reason; never converts videos to images")
    for command in ("check", "render"):
        sub = subs.add_parser(command)
        sub.add_argument("package", type=Path)
        sub.add_argument("--require-ready", action="store_true")
        if command == "render":
            sub.add_argument("output", type=Path)
            sub.add_argument("--draft-images", action="store_true", help="Show candidate images with a visible draft warning, without approving them")
    args = parser.parse_args()
    if getattr(args, "draft_images", False) and args.require_ready:
        parser.error("--draft-images cannot be combined with --require-ready")
    try:
        if hasattr(args, "output") and args.output.exists():
            raise FileExistsError("Output already exists; choose a new path: " + str(args.output))
        if args.command == "prepare":
            data = prepare(json.loads(args.handoff.read_text(encoding="utf-8")),
                           args.draft.read_text(encoding="utf-8"), args.title, args.handoff.parent, args.project_image)
            # Keep the article package portable when the complete workspace moves.
            for container, key in [(data["paper"], "local_pdf")] + [(item, "local_path") for item in data["visuals"]["items"] + data["project_assets"]]:
                if container.get(key):
                    container[key] = os.path.relpath(container[key], args.output.parent.resolve()).replace(os.sep, "/")
            report = check(data, args.output.parent)
            if report["valid"]:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(data, stream, ensure_ascii=False, indent=2)
        else:
            data = json.loads(args.package.read_text(encoding="utf-8"))
            report = check(data, args.package.parent, args.require_ready)
            if report["valid"] and args.command == "render":
                cmd = [sys.executable, str(Path(__file__).with_name("render_article_package.py")),
                       str(args.package), str(args.output)]
                if args.require_ready:
                    cmd.append("--require-ready")
                if args.draft_images:
                    cmd.append("--include-candidates")
                subprocess.run(cmd, check=True)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
