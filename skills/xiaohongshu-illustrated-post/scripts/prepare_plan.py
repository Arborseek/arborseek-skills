#!/usr/bin/env python3
"""Normalize a Xiaohongshu production plan and build text-free image prompts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


ALLOWED_BACKBONES = {
    "editorial-stack",
    "vertical-flow",
    "split-contrast",
    "center-out",
    "input-process-output",
    "matrix-grid",
    "layered-system",
    "narrative-panels",
}

DNA_KEYS = (
    "substrate",
    "type_voice",
    "palette_roles",
    "stroke_light",
    "graphic_language",
    "density",
    "motif",
)

DEFAULT_PAGE_COUNT = 6
MAX_PAGE_COUNT = 9


class PlanError(ValueError):
    pass


def read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanError(f"plan not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise PlanError("plan root must be a JSON object")
    return value


def require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{label} must be a non-empty string")
    return value.strip()


def text_list(value: Any, label: str, *, minimum: int = 0, maximum: int = 20) -> List[str]:
    if not isinstance(value, list):
        raise PlanError(f"{label} must be an array")
    result = [require_text(item, f"{label}[{index}]") for index, item in enumerate(value)]
    if not minimum <= len(result) <= maximum:
        raise PlanError(f"{label} must contain between {minimum} and {maximum} items")
    return result


def safe_slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or fallback)[:64]


def safe_filename(value: Any, fallback: str, label: str) -> str:
    if value is None:
        value = fallback
    value = require_text(value, label)
    if Path(value).name != value or "/" in value or "\\" in value or value in {".", ".."}:
        raise PlanError(f"{label} must be a plain filename without directories")
    if not value.lower().endswith(".png"):
        raise PlanError(f"{label} must end in .png")
    return value


def number(value: Any, label: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise PlanError(f"{label} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise PlanError(f"{label} must be between {minimum} and {maximum}")
    return result


def normalize_box(value: Any, label: str) -> List[float]:
    if not isinstance(value, list) or len(value) != 4:
        raise PlanError(f"{label} must be [x, y, width, height]")
    x, y, width, height = [number(item, label, 0.0, 1.0) for item in value]
    if width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise PlanError(f"{label} must describe a positive box fully inside the canvas")
    return [round(x, 6), round(y, 6), round(width, 6), round(height, 6)]


def normalize_text_block(raw: Any, page_number: int, index: int) -> Dict[str, Any]:
    label = f"pages[{page_number}].text_blocks[{index}]"
    if not isinstance(raw, dict):
        raise PlanError(f"{label} must be an object")
    font_size = int(number(raw.get("font_size", 64), f"{label}.font_size", 8, 320))
    min_font_size = int(number(raw.get("min_font_size", max(16, font_size // 2)), f"{label}.min_font_size", 8, 320))
    if min_font_size > font_size:
        raise PlanError(f"{label}.min_font_size cannot exceed font_size")
    align = raw.get("align", "left")
    valign = raw.get("valign", "top")
    weight = raw.get("weight", "regular")
    if align not in {"left", "center", "right"}:
        raise PlanError(f"{label}.align must be left, center, or right")
    if valign not in {"top", "center", "bottom"}:
        raise PlanError(f"{label}.valign must be top, center, or bottom")
    if weight not in {"regular", "bold"}:
        raise PlanError(f"{label}.weight must be regular or bold")
    result: Dict[str, Any] = {
        "id": safe_slug(require_text(raw.get("id"), f"{label}.id"), f"text-{index + 1}"),
        "text": require_text(raw.get("text"), f"{label}.text"),
        "box": normalize_box(raw.get("box"), f"{label}.box"),
        "font_size": font_size,
        "min_font_size": min_font_size,
        "color": require_text(raw.get("color", "#111111"), f"{label}.color"),
        "align": align,
        "valign": valign,
        "weight": weight,
        "line_spacing": number(raw.get("line_spacing", 1.15), f"{label}.line_spacing", 0.8, 2.5),
        "padding": int(number(raw.get("padding", 0), f"{label}.padding", 0, 160)),
        "stroke_width": int(number(raw.get("stroke_width", 0), f"{label}.stroke_width", 0, 20)),
        "stroke_fill": require_text(raw.get("stroke_fill", "#FFFFFF"), f"{label}.stroke_fill"),
    }
    if raw.get("background") is not None:
        result["background"] = require_text(raw["background"], f"{label}.background")
        result["radius"] = int(number(raw.get("radius", 0), f"{label}.radius", 0, 200))
    return result


def normalize_plan(raw: Dict[str, Any]) -> Dict[str, Any]:
    title = require_text(raw.get("title"), "title")
    canvas_raw = raw.get("canvas", {})
    if not isinstance(canvas_raw, dict):
        raise PlanError("canvas must be an object")
    width = int(number(canvas_raw.get("width", 1080), "canvas.width", 512, 4096))
    height = int(number(canvas_raw.get("height", 1440), "canvas.height", 512, 4096))

    theme_raw = raw.get("theme")
    if not isinstance(theme_raw, dict):
        raise PlanError("theme must be an object")
    dna_raw = theme_raw.get("dna")
    if not isinstance(dna_raw, dict):
        raise PlanError("theme.dna must be an object")
    dna = {key: require_text(dna_raw.get(key), f"theme.dna.{key}") for key in DNA_KEYS}
    references = text_list(theme_raw.get("reference_assets", []), "theme.reference_assets", maximum=4)
    for index, reference in enumerate(references):
        if Path(reference).is_absolute() or ".." in Path(reference).parts:
            raise PlanError(f"theme.reference_assets[{index}] must be a safe relative path")

    pages_raw = raw.get("pages")
    if not isinstance(pages_raw, list) or not pages_raw:
        raise PlanError("pages must be a non-empty array")
    if len(pages_raw) > MAX_PAGE_COUNT:
        raise PlanError(f"pages cannot exceed {MAX_PAGE_COUNT} entries, including the cover")

    pages: List[Dict[str, Any]] = []
    seen_numbers = set()
    seen_backgrounds = set()
    seen_outputs = set()
    for position, page_raw in enumerate(pages_raw, start=1):
        if not isinstance(page_raw, dict):
            raise PlanError(f"pages[{position}] must be an object")
        page_number = int(number(page_raw.get("number", position), f"pages[{position}].number", 1, 999))
        if page_number in seen_numbers:
            raise PlanError(f"duplicate page number: {page_number}")
        seen_numbers.add(page_number)
        role = safe_slug(require_text(page_raw.get("role", "content"), f"pages[{position}].role"), "content")
        layout_raw = page_raw.get("layout")
        if not isinstance(layout_raw, dict):
            raise PlanError(f"pages[{position}].layout must be an object")
        backbone = require_text(layout_raw.get("backbone"), f"pages[{position}].layout.backbone")
        if backbone not in ALLOWED_BACKBONES:
            raise PlanError(f"pages[{position}].layout.backbone is not supported: {backbone}")
        modules = text_list(layout_raw.get("modules", []), f"pages[{position}].layout.modules", maximum=3)
        text_blocks_raw = page_raw.get("text_blocks", [])
        if not isinstance(text_blocks_raw, list):
            raise PlanError(f"pages[{position}].text_blocks must be an array")
        text_blocks = [normalize_text_block(item, page_number, index) for index, item in enumerate(text_blocks_raw)]
        ids = [block["id"] for block in text_blocks]
        if len(ids) != len(set(ids)):
            raise PlanError(f"page {page_number} has duplicate text block ids")
        prefix = f"{page_number:02d}-{role}"
        background_file = safe_filename(page_raw.get("background_file"), f"{prefix}-bg.png", f"pages[{position}].background_file")
        output_file = safe_filename(page_raw.get("output_file"), f"{prefix}.png", f"pages[{position}].output_file")
        if background_file in seen_backgrounds:
            raise PlanError(f"duplicate background filename: {background_file}")
        if output_file in seen_outputs:
            raise PlanError(f"duplicate output filename: {output_file}")
        seen_backgrounds.add(background_file)
        seen_outputs.add(output_file)
        pages.append(
            {
                "number": page_number,
                "role": role,
                "purpose": require_text(page_raw.get("purpose"), f"pages[{position}].purpose"),
                "core_claim": require_text(page_raw.get("core_claim"), f"pages[{position}].core_claim"),
                "information_units": text_list(page_raw.get("information_units", []), f"pages[{position}].information_units", minimum=1, maximum=8),
                "layout": {
                    "backbone": backbone,
                    "modules": modules,
                    "reading_path": require_text(layout_raw.get("reading_path", "top-to-bottom"), f"pages[{position}].layout.reading_path"),
                    "emphasis": require_text(layout_raw.get("emphasis", "60/30/10"), f"pages[{position}].layout.emphasis"),
                },
                "image_prompt": str(page_raw.get("image_prompt", "")).strip(),
                "text_blocks": text_blocks,
                "background_file": background_file,
                "output_file": output_file,
            }
        )

    pages.sort(key=lambda item: item["number"])
    expected = list(range(1, len(pages) + 1))
    actual = [page["number"] for page in pages]
    if actual != expected:
        raise PlanError(f"page numbers must be contiguous starting at 1; got {actual}")

    return {
        "version": 1,
        "slug": safe_slug(str(raw.get("slug", "")), "xiaohongshu-post"),
        "title": title,
        "body": str(raw.get("body", "")).strip(),
        "tags": text_list(raw.get("tags", []), "tags", maximum=20),
        "visual_intent": require_text(raw.get("visual_intent"), "visual_intent"),
        "canvas": {"width": width, "height": height},
        "theme": {
            "id": safe_slug(require_text(theme_raw.get("id"), "theme.id"), "custom-theme"),
            "reason": require_text(theme_raw.get("reason"), "theme.reason"),
            "reference_assets": references,
            "dna": dna,
        },
        "pages": pages,
    }


def page_prompt(plan: Dict[str, Any], page: Dict[str, Any]) -> str:
    dna = plan["theme"]["dna"]
    regions = "; ".join(f'{block["id"]}={block["box"]}' for block in page["text_blocks"]) or "none"
    references = ", ".join(plan["theme"]["reference_assets"])
    reference_line = (
        f"Reference assets: {references}. Style reference only; never copy wording, signatures, watermarks, logos, or exact layout."
        if references
        else "Reference assets: none. Use the written Theme DNA as the complete style specification."
    )
    modules = ", ".join(page["layout"]["modules"]) or "none"
    units = "; ".join(page["information_units"])
    return "\n".join(
        [
            "Use case: infographic-diagram",
            f'Asset type: Xiaohongshu vertical illustrated post, page {page["number"]} of {len(plan["pages"])}',
            reference_line,
            f'Visual intent: {plan["visual_intent"]}',
            f'Theme: {plan["theme"]["id"]}',
            "Theme DNA: " + "; ".join(f"{key}={value}" for key, value in dna.items()),
            f'Page purpose: {page["purpose"]}',
            f'Core meaning to express visually: {page["core_claim"]}',
            f"Information units to represent with illustration, icons, shapes, or charts: {units}",
            f'Composition: backbone={page["layout"]["backbone"]}; modules={modules}; reading path={page["layout"]["reading_path"]}; emphasis={page["layout"]["emphasis"]}',
            f"Reserved text regions as normalized [x,y,w,h] boxes: {regions}",
            f'Additional imagery request: {page["image_prompt"] or "none"}',
            "Critical production rule: generate the complete visual background and illustration WITHOUT ANY TEXT. Leave reserved text regions calm and uncluttered for later deterministic typesetting.",
            "Constraints: exact portrait composition; phone-readable hierarchy; consistent series identity; no letters; no Chinese characters; no numbers; no pseudo-text; no logo; no QR code; no watermark; no signature.",
        ]
    ) + "\n"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="draft production-plan JSON")
    parser.add_argument("--output-dir", type=Path, required=True, help="run directory to create")
    parser.add_argument("--force", action="store_true", help="allow replacing generated plan/prompt files")
    args = parser.parse_args()

    try:
        plan = normalize_plan(read_json(args.plan))
        run_dir = args.output_dir.resolve()
        prompts_dir = run_dir / "prompts"
        backgrounds_dir = run_dir / "backgrounds"
        final_dir = run_dir / "final"
        plan_path = run_dir / "plan.json"
        manifest_path = run_dir / "manifest.json"
        if not args.force and (plan_path.exists() or manifest_path.exists()):
            raise PlanError(f"run already exists at {run_dir}; pass --force to refresh generated files")
        prompts_dir.mkdir(parents=True, exist_ok=True)
        backgrounds_dir.mkdir(parents=True, exist_ok=True)
        final_dir.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        manifest_pages = []
        for page in plan["pages"]:
            prompt_name = f'{page["number"]:02d}-{page["role"]}.txt'
            prompt_path = prompts_dir / prompt_name
            if prompt_path.exists() and not args.force:
                raise PlanError(f"prompt already exists: {prompt_path}")
            prompt_path.write_text(page_prompt(plan, page), encoding="utf-8")
            manifest_pages.append(
                {
                    "number": page["number"],
                    "prompt_file": f"prompts/{prompt_name}",
                    "background_file": f'backgrounds/{page["background_file"]}',
                    "output_file": f'final/{page["output_file"]}',
                    "required_text": [block["text"] for block in page["text_blocks"]],
                }
            )
        manifest = {
            "version": 1,
            "plan_file": "plan.json",
            "plan_sha256": sha256(plan_path),
            "canvas": plan["canvas"],
            "theme_id": plan["theme"]["id"],
            "page_policy": {
                "default": DEFAULT_PAGE_COUNT,
                "maximum": MAX_PAGE_COUNT,
                "includes_cover": True,
            },
            "pages": manifest_pages,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Prepared {len(plan['pages'])} pages in {run_dir}")
        print(f"Plan: {plan_path}")
        print(f"Prompts: {prompts_dir}")
        return 0
    except PlanError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
