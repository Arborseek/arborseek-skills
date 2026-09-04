"""Offline, deterministic math images. No TeX processes, network, or AI rendering."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from bs4 import BeautifulSoup


def unresolved_math(raw):
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup.select("pre, code, [data-formula-id]"):
        node.decompose()
    text = soup.get_text(" ")
    if re.search(r"\$\$|\\[\[\]()]|\\(?:frac|sqrt|sum|int|begin|mathbb)\b|(?<!\\)\$[^$\n]+\$", text):
        return True
    # Catch standalone probability equations like the reported screenshot, not
    # ordinary prose, code examples, or simple inline variable assignments.
    return any("=" in p.get_text() and len(p.get_text()) > 20
               and re.search(r"[pπ]\s*\([^)]*[|｜]", p.get_text())
               for p in soup.find_all("p"))


def validate_formulas(data, ready=False):
    errors = []
    formulas = data.get("formulas", [])
    if not isinstance(formulas, list):
        return ["formulas must be an array"]
    soup = BeautifulSoup(str(data.get("article", {}).get("content_html", "")), "html.parser")
    slots = soup.select("[data-formula-id]")
    ids = []
    for formula in formulas:
        if not isinstance(formula, dict):
            errors.append("formula must be an object")
            continue
        ident = formula.get("id")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", ident) or ident in ids:
            errors.append("formula id must be unique and alphanumeric")
        ids.append(ident)
        lines = formula.get("latex_lines")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 8 or any(
            not isinstance(line, str) or not line.strip() or len(line) > 1000
            or "$" in line or "\n" in line for line in (lines if isinstance(lines, list) else [])
        ):
            errors.append("formula latex_lines needs 1–8 nonempty expressions without dollar delimiters")
        for key in ("alt", "locator"):
            if not isinstance(formula.get(key), str) or not formula[key].strip():
                errors.append("formula " + key + " is required")
        if ready and formula.get("checked") is not True:
            errors.append("formula must be checked against source before final rendering")
        matches = [slot for slot in slots if slot.get("data-formula-id") == ident]
        if len(matches) != 1 or matches[0].name != "p" or matches[0].get_text(strip=True) or matches[0].find(True):
            errors.append("each formula needs exactly one empty p[data-formula-id] slot")
    if any(slot.get("data-formula-id") not in ids for slot in slots):
        errors.append("formula slot has no matching record")
    if ready and unresolved_math(str(soup)):
        errors.append("Unrendered math remains: register display formulas or write simple inline symbols as text")
    return errors


def render_png(lines):
    try:
        import matplotlib
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from PIL import Image
    except ImportError as exc:
        raise ValueError("Formula rendering needs optional requirements-math.txt in this Python environment") from exc
    # 3x raster pixels, 18 CSS-pixel mathematical text on an opaque white canvas.
    # Refuse excessive width rather than shrinking a long equation into illegibility.
    with matplotlib.rc_context({"text.usetex": False, "mathtext.fontset": "stix"}):
        fig = Figure(figsize=(4, 2), dpi=300, facecolor="white")
        canvas = FigureCanvasAgg(fig)
        artists = [fig.text(0, 0, "$" + line + "$", fontsize=13.5, color="#243746") for line in lines]
        try:
            canvas.draw()
            sizes = [a.get_window_extent(canvas.get_renderer()) for a in artists]
            width = max(s.width for s in sizes) + 48
            height = sum(s.height for s in sizes) + 24 * (len(lines) + 1)
            if width > 1026:
                raise ValueError("Formula is too wide for mobile; split latex_lines at a mathematically valid boundary")
            fig.set_size_inches(width / 300, height / 300)
            y = height - 24
            for artist, size in zip(artists, sizes):
                artist.set_ha("center")
                artist.set_va("top")
                artist.set_position((0.5, y / height))
                y -= size.height + 24
            buf = io.BytesIO()
            canvas.print_png(buf)
            img = Image.open(buf).convert("RGB")
            out = io.BytesIO()
            img.save(out, format="PNG")
            return out.getvalue(), round(img.width / 3)
        except (ValueError, RuntimeError) as exc:
            raise ValueError("Formula render failed; correct unsupported syntax or split lines: " + str(exc)) from exc


def materialize_formulas(source, formulas, output_dir):
    soup = BeautifulSoup(source, "html.parser")
    for formula in formulas:
        png, width = render_png(formula["latex_lines"])
        path = Path(output_dir) / "assets" / ("formula-" + hashlib.sha256(png).hexdigest()[:16] + ".png")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(png)
        slot = soup.find("p", attrs={"data-formula-id": formula["id"]})
        img = soup.new_tag("img", src=str(path.resolve()), alt=formula["alt"], width=str(width))
        slot.append(img)
    return str(soup)
