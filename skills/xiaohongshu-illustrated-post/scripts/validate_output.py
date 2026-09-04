#!/usr/bin/env python3
"""Validate backgrounds and final rendered pages against a normalized plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required. Install it with: python3 -m pip install Pillow") from exc


def read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_image(path: Path, expected_size: tuple[int, int], label: str, errors: List[str]) -> str | None:
    if not path.is_file():
        errors.append(f"missing {label}: {path}")
        return None
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.size != expected_size:
                errors.append(f"wrong size for {label}: {path} is {image.size}, expected {expected_size}")
    except Exception as exc:
        errors.append(f"invalid image for {label}: {path}: {exc}")
        return None
    return sha256(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path, help="normalized plan.json")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=("backgrounds", "final", "all"), default="all")
    parser.add_argument("--strict", action="store_true", help="treat duplicate images and extra PNGs as errors")
    args = parser.parse_args()

    errors: List[str] = []
    warnings: List[str] = []
    try:
        plan_path = args.plan.resolve()
        plan = read_json(plan_path)
        if plan.get("version") != 1 or not isinstance(plan.get("pages"), list):
            raise ValueError("plan must be normalized by prepare_plan.py")
        expected_size = (int(plan["canvas"]["width"]), int(plan["canvas"]["height"]))
        run_dir = args.run_dir.resolve()
        backgrounds_dir = run_dir / "backgrounds"
        final_dir = run_dir / "final"
        digest_locations: Dict[str, List[str]] = defaultdict(list)

        if args.stage in {"backgrounds", "all"}:
            expected_backgrounds = set()
            for page in plan["pages"]:
                filename = page["background_file"]
                expected_backgrounds.add(filename)
                digest = check_image(backgrounds_dir / filename, expected_size, f"page {page['number']} background", errors)
                if digest:
                    digest_locations[f"backgrounds:{digest}"].append(f"backgrounds/{filename}")
            if backgrounds_dir.is_dir():
                extras = sorted(path.name for path in backgrounds_dir.glob("*.png") if path.name not in expected_backgrounds)
                if extras:
                    (errors if args.strict else warnings).append(f"extra background PNGs: {extras}")

        report_by_page: Dict[int, Dict[str, Any]] = {}
        if args.stage in {"final", "all"}:
            report_path = final_dir / "render-report.json"
            if not report_path.is_file():
                errors.append(f"missing render report: {report_path}")
            else:
                report = read_json(report_path)
                if report.get("plan_sha256") != sha256(plan_path):
                    errors.append("render report was produced from a different plan.json")
                report_by_page = {int(item["number"]): item for item in report.get("pages", []) if isinstance(item, dict)}
            expected_outputs = set()
            for page in plan["pages"]:
                filename = page["output_file"]
                expected_outputs.add(filename)
                output_path = final_dir / filename
                digest = check_image(output_path, expected_size, f"page {page['number']} final", errors)
                if digest:
                    digest_locations[f"final:{digest}"].append(f"final/{filename}")
                rendered = report_by_page.get(int(page["number"]))
                if not rendered:
                    errors.append(f"page {page['number']} is absent from render-report.json")
                    continue
                if digest and rendered.get("output_sha256") != digest:
                    errors.append(f"page {page['number']} final image changed after text rendering")
                planned_text = {block["id"]: block["text"] for block in page.get("text_blocks", [])}
                rendered_text = {block["id"]: block["text"] for block in rendered.get("text_blocks", [])}
                if rendered_text != planned_text:
                    errors.append(f"page {page['number']} rendered text contract does not match plan")
            if final_dir.is_dir():
                extras = sorted(path.name for path in final_dir.glob("*.png") if path.name not in expected_outputs)
                if extras:
                    (errors if args.strict else warnings).append(f"extra final PNGs: {extras}")

        duplicates = [locations for locations in digest_locations.values() if len(locations) > 1]
        if duplicates:
            message = "duplicate images detected: " + "; ".join(", ".join(group) for group in duplicates)
            (errors if args.strict else warnings).append(message)

        for warning in warnings:
            print(f"WARNING: {warning}")
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print(f"Validation failed with {len(errors)} error(s) and {len(warnings)} warning(s).", file=sys.stderr)
            return 2
        print(f"Validation passed for {len(plan['pages'])} page(s) with {len(warnings)} warning(s).")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
