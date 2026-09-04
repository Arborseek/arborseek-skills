#!/usr/bin/env python3
"""Overlay exact text from a normalized plan onto generated text-free backgrounds."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: python3 -m pip install Pillow") from exc


REGULAR_FONTS = (
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
)

BOLD_FONTS = (
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
)


class ComposeError(RuntimeError):
    pass


def load_plan(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComposeError(f"cannot read normalized plan {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("pages"), list):
        raise ComposeError("plan must be normalized by prepare_plan.py")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_font(weight: str, override: Path | None) -> Path:
    if override is not None:
        if not override.is_file():
            raise ComposeError(f"font not found: {override}")
        return override
    candidates = BOLD_FONTS if weight == "bold" else REGULAR_FONTS
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file():
            return path
    raise ComposeError("no CJK font found; pass --font /path/to/licensed-font.ttf")


def parse_color(value: str) -> Tuple[int, int, int, int]:
    try:
        color = ImageColor.getcolor(value, "RGBA")
    except ValueError as exc:
        raise ComposeError(f"invalid color: {value}") from exc
    return tuple(color)  # type: ignore[return-value]


def tokenize(paragraph: str) -> List[str]:
    return re.findall(r"[\u3400-\u9fff]|[^\u3400-\u9fff\s]+|\s+", paragraph)


def split_long_token(token: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    pieces: List[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if current and font.getlength(candidate) > max_width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def wrap_paragraph(paragraph: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    if not paragraph:
        return [""]
    lines: List[str] = []
    current = ""
    for token in tokenize(paragraph):
        if token.isspace() and not current:
            continue
        candidates = [token]
        if font.getlength(token) > max_width:
            candidates = split_long_token(token, font, max_width)
        for piece in candidates:
            candidate = current + piece
            if current and font.getlength(candidate.rstrip()) > max_width:
                lines.append(current.rstrip())
                current = piece.lstrip()
            else:
                current = candidate
    if current or not lines:
        lines.append(current.rstrip())
    return lines


def fit_text(
    text: str,
    font_path: Path,
    preferred_size: int,
    minimum_size: int,
    max_width: int,
    max_height: int,
    spacing_factor: float,
) -> Tuple[ImageFont.FreeTypeFont, List[str], int, int]:
    for size in range(preferred_size, minimum_size - 1, -1):
        font = ImageFont.truetype(str(font_path), size=size)
        lines: List[str] = []
        for paragraph in text.split("\n"):
            lines.extend(wrap_paragraph(paragraph, font, max_width))
        bbox = font.getbbox("国Ag")
        line_height = max(1, bbox[3] - bbox[1])
        spacing = max(0, int(line_height * (spacing_factor - 1.0)))
        total_height = line_height * len(lines) + spacing * max(0, len(lines) - 1)
        widest = max((int(font.getlength(line)) for line in lines), default=0)
        if widest <= max_width and total_height <= max_height:
            return font, lines, line_height, spacing
    raise ComposeError(
        f"text does not fit its box even at {minimum_size}px: {text!r}. Enlarge the box, shorten the text, or lower min_font_size."
    )


def pixel_box(box: Sequence[float], width: int, height: int) -> Tuple[int, int, int, int]:
    x, y, w, h = box
    left = round(x * width)
    top = round(y * height)
    right = round((x + w) * width)
    bottom = round((y + h) * height)
    return left, top, right, bottom


def draw_block(image: Image.Image, block: Dict[str, Any], font_override: Path | None) -> Dict[str, Any]:
    left, top, right, bottom = pixel_box(block["box"], image.width, image.height)
    padding = int(block.get("padding", 0))
    if block.get("background"):
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rounded_rectangle(
            (left, top, right, bottom),
            radius=int(block.get("radius", 0)),
            fill=parse_color(block["background"]),
        )
        image.alpha_composite(overlay)
    inner_width = right - left - 2 * padding
    inner_height = bottom - top - 2 * padding
    if inner_width <= 0 or inner_height <= 0:
        raise ComposeError(f'text block {block["id"]} has no drawable area after padding')
    font_path = choose_font(block.get("weight", "regular"), font_override)
    font, lines, line_height, spacing = fit_text(
        block["text"],
        font_path,
        int(block["font_size"]),
        int(block["min_font_size"]),
        inner_width,
        inner_height,
        float(block.get("line_spacing", 1.15)),
    )
    total_height = line_height * len(lines) + spacing * max(0, len(lines) - 1)
    valign = block.get("valign", "top")
    if valign == "center":
        y = top + padding + (inner_height - total_height) // 2
    elif valign == "bottom":
        y = bottom - padding - total_height
    else:
        y = top + padding
    draw = ImageDraw.Draw(image)
    fill = parse_color(block["color"])
    stroke_fill = parse_color(block.get("stroke_fill", "#FFFFFF"))
    for line in lines:
        line_width = int(font.getlength(line))
        align = block.get("align", "left")
        if align == "center":
            x = left + padding + (inner_width - line_width) // 2
        elif align == "right":
            x = right - padding - line_width
        else:
            x = left + padding
        draw.text(
            (x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=int(block.get("stroke_width", 0)),
            stroke_fill=stroke_fill,
        )
        y += line_height + spacing
    return {
        "id": block["id"],
        "text": block["text"],
        "text_sha256": hashlib.sha256(block["text"].encode("utf-8")).hexdigest(),
        "font": str(font_path),
        "font_size": font.size,
        "lines": lines,
        "box_pixels": [left, top, right, bottom],
    }


def selected_pages(pages: Iterable[Dict[str, Any]], numbers: Sequence[int] | None) -> List[Dict[str, Any]]:
    page_list = list(pages)
    if not numbers:
        return page_list
    wanted = set(numbers)
    result = [page for page in page_list if page["number"] in wanted]
    missing = wanted - {page["number"] for page in result}
    if missing:
        raise ComposeError(f"unknown page number(s): {sorted(missing)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="normalized plan.json")
    parser.add_argument("--background-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--font", type=Path, help="licensed CJK TTF/TTC/OTF font override")
    parser.add_argument("--page", type=int, action="append", help="render only this page; repeatable")
    parser.add_argument("--resize-background", action="store_true", help="resize backgrounds to the planned canvas")
    parser.add_argument("--force", action="store_true", help="replace existing final images/report")
    args = parser.parse_args()

    try:
        plan_path = args.plan.resolve()
        plan = load_plan(plan_path)
        width = int(plan["canvas"]["width"])
        height = int(plan["canvas"]["height"])
        output_dir = args.output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "render-report.json"
        if report_path.exists() and not args.force:
            raise ComposeError(f"render report exists: {report_path}; pass --force to replace")
        pages_to_render = selected_pages(plan["pages"], args.page)
        reports = []
        if report_path.exists() and args.page:
            previous = json.loads(report_path.read_text(encoding="utf-8"))
            if previous.get("plan_sha256") != file_sha256(plan_path):
                raise ComposeError("cannot merge a partial rerender into a report from a different plan")
            rerendered_numbers = {page["number"] for page in pages_to_render}
            reports = [item for item in previous.get("pages", []) if item.get("number") not in rerendered_numbers]
        for page in pages_to_render:
            background_path = args.background_dir.resolve() / page["background_file"]
            output_path = output_dir / page["output_file"]
            if not background_path.is_file():
                raise ComposeError(f"missing background for page {page['number']}: {background_path}")
            if output_path.exists() and not args.force:
                raise ComposeError(f"output exists: {output_path}; pass --force to replace")
            with Image.open(background_path) as source:
                image = source.convert("RGBA")
            if image.size != (width, height):
                if not args.resize_background:
                    raise ComposeError(
                        f"page {page['number']} background is {image.size}, expected {(width, height)}; pass --resize-background to allow resizing"
                    )
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            block_reports = [draw_block(image, block, args.font.resolve() if args.font else None) for block in page["text_blocks"]]
            rgb = Image.new("RGB", image.size, "white")
            rgb.paste(image, mask=image.getchannel("A"))
            rgb.save(output_path, format="PNG", optimize=True)
            reports.append(
                {
                    "number": page["number"],
                    "background_file": page["background_file"],
                    "background_sha256": file_sha256(background_path),
                    "output_file": page["output_file"],
                    "output_sha256": file_sha256(output_path),
                    "text_blocks": block_reports,
                }
            )
            print(f"Rendered page {page['number']}: {output_path}")
        reports.sort(key=lambda item: item["number"])
        report = {
            "version": 1,
            "plan_sha256": file_sha256(plan_path),
            "canvas": plan["canvas"],
            "pages": reports,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Report: {report_path}")
        return 0
    except ComposeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
