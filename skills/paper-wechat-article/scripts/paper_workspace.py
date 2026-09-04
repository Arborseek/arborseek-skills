"""Portable paper/PDF/figure workspace. Standard library; capture needs pdftoppm."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

SCHEMA = "paper-workspace/1"
MANIFEST = "paper-workspace.json"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inside(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Workspace paths must be non-empty relative paths")
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError("Workspace path escapes its directory: " + relative)
    return target


def load(path):
    path = Path(path)
    if path.is_dir():
        path = path / MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data, path.parent)
    return data, path


def validate(data, root):
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA:
        raise ValueError("Not a paper-workspace/1 manifest")
    paper = data.get("paper", {})
    for key in ("title", "version", "source_url", "sha256", "local_pdf"):
        if not isinstance(paper.get(key), str) or not paper[key].strip():
            raise ValueError("Missing paper." + key)
    pdf = inside(root, paper["local_pdf"])
    if not pdf.is_file() or sha256(pdf) != paper["sha256"]:
        raise ValueError("PDF missing or hash changed; do not mix versions")
    if paper.get("read_scope") not in {"full-text", "partial", "abstract", "notes-only"}:
        raise ValueError("Invalid reading scope")
    if not isinstance(data.get("claims"), list) or not isinstance(data.get("figures"), list):
        raise ValueError("claims and figures must be arrays")
    seen = set()
    for figure in data["figures"]:
        if not isinstance(figure, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(figure.get("id", ""))):
            raise ValueError("Invalid figure id")
        if figure["id"] in seen:
            raise ValueError("Duplicate figure id")
        seen.add(figure["id"])
        if figure.get("kind") != "original":
            raise ValueError("Source workspace stores original figures only; supplement in article package")
        if figure.get("paper_sha256") != paper["sha256"] or figure.get("paper_version") != paper["version"]:
            raise ValueError("Figure belongs to a different PDF/version")
        asset = inside(root, figure.get("local_path"))
        if not asset.is_file() or sha256(asset) != figure.get("sha256"):
            raise ValueError("Figure missing or hash changed: " + figure["id"])
    if data.get("notes_path"):
        if not inside(root, data["notes_path"]).is_file():
            raise ValueError("Reading notes path does not exist")
    return data


def init_workspace(pdf, output, metadata=None, title=None, version=None, source_url=None, selection=None, selected_id=None):
    pdf, output = Path(pdf), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError("Workspace exists; run check/reuse it or choose a new directory")
    with pdf.open("rb") as stream:
        if not stream.read(1024).lstrip().startswith(b"%PDF-"):
            raise ValueError("Input is not a PDF")
    digest = sha256(pdf)
    meta = json.loads(Path(metadata).read_text(encoding="utf-8")) if metadata else {}
    if metadata and (meta.get("kind") != "pdf" or meta.get("sha256") != digest or meta.get("bytes") != pdf.stat().st_size):
        raise ValueError("Download metadata does not match this PDF")
    ident = meta.get("id", "")
    if selected_id and selected_id != ident:
        raise ValueError("Selected ID does not match download metadata")
    if version and ident and version != ident:
        raise ValueError("Requested version disagrees with metadata ID")
    search = None
    if selection:
        search = json.loads(Path(selection).read_text(encoding="utf-8"))
        if not ident or ident not in [p.get("id") for p in search.get("papers", []) if isinstance(p, dict)]:
            raise ValueError("Downloaded version is not in the supplied search results")
    title = title or meta.get("title")
    if not title:
        raise ValueError("Standalone PDF needs a title read from the paper (--title)")
    paper = {"id": ident or "local-" + digest[:12], "title": title,
             "version": version or ident or "local-" + digest[:12],
             "source_url": source_url or meta.get("url") or "urn:sha256:" + digest,
             "authors": meta.get("authors", []), "sha256": digest, "local_pdf": "paper.pdf",
             "read_scope": "notes-only"}
    data = {"schema_version": SCHEMA, "paper": paper, "claims": [], "figures": [], "notes_path": None}
    output.mkdir(parents=True)
    shutil.copyfile(pdf, output / "paper.pdf")
    if sha256(output / "paper.pdf") != digest:
        raise ValueError("PDF changed while copying; incomplete workspace retained for inspection")
    if metadata:
        shutil.copyfile(metadata, output / "download.json")
    if selection:
        shutil.copyfile(selection, output / "search-results.json")
        data["selection"] = {"selected_id": ident, "search_result": "search-results.json"}
    with (output / MANIFEST).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return data


def png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
        raise ValueError("Renderer did not produce a PNG")
    return struct.unpack(">II", data[16:24])


def render_pdf(pdf, page, box, scale, renderer):
    executable = shutil.which(renderer)
    if not executable:
        raise RuntimeError("pdftoppm unavailable; use an existing host PDF renderer then import-figure; no automatic install")
    with tempfile.TemporaryDirectory(prefix="paper-render-") as tmp:
        prefix = Path(tmp) / "page"
        cmd = [executable, "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", str(scale), "-png"]
        subprocess.run(cmd + [str(pdf), str(prefix)], check=True, capture_output=True, timeout=45)
        full = prefix.with_suffix(".png").read_bytes()
        if box == [0.0, 0.0, 1.0, 1.0]:
            return full
        width, height = png_size(full)
        x, y = math.floor(box[0] * width), math.floor(box[1] * height)
        w, h = math.ceil(box[2] * width) - x, math.ceil(box[3] * height) - y
        crop = Path(tmp) / "crop"
        subprocess.run(cmd + ["-x", str(x), "-y", str(y), "-W", str(w), "-H", str(h), str(pdf), str(crop)],
                       check=True, capture_output=True, timeout=45)
        return crop.with_suffix(".png").read_bytes()


def save_figure(manifest, ident, page, label, caption, box=None, image=None, scale=2400, renderer="pdftoppm"):
    data, manifest = load(manifest)
    root = manifest.parent
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", ident):
        raise ValueError("Figure id must be lowercase letters/digits/hyphens, max 64 characters")
    box = list(box or [0.0, 0.0, 1.0, 1.0])
    if page < 1 or not 600 <= scale <= 6000 or len(box) != 4 or not all(math.isfinite(v) for v in box):
        raise ValueError("Invalid page, scale, or crop")
    if not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1:
        raise ValueError("Crop must be normalized x0 y0 x1 y1 within the rendered page")
    if not label.strip() or not caption.strip():
        raise ValueError("Actual figure label and original caption are required")
    imported = Path(image).read_bytes() if image else None
    request = {"page": page, "box": box, "scale": scale, "label": label, "caption": caption,
               "import_sha256": hashlib.sha256(imported).hexdigest() if imported else None}
    for figure in data["figures"]:
        if figure["id"] == ident:
            if figure.get("extraction") == request:
                return {"status": "cached", "figure": figure}
            raise FileExistsError("Figure ID exists with different crop/content; use a new ID")
    # A lock prevents competing updates from silently losing an indexed figure.
    lock = root / ".figure-write.lock"
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.close(fd)
        current, _ = load(manifest)
        if current != data:
            raise RuntimeError("Workspace changed; reload before retrying")
        content = imported if imported is not None else render_pdf(inside(root, data["paper"]["local_pdf"]), page, box, scale, renderer)
        if content[:8] == b"\x89PNG\r\n\x1a\n":
            png_size(content)
            ext = ".png"
        elif content.startswith(b"\xff\xd8\xff"):
            ext = ".jpg"
        else:
            raise ValueError("Only actual PNG/JPEG figure files are accepted")
        relative = "figures/" + ident + ext
        target = inside(root, relative)
        target.parent.mkdir(exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        figure = {"id": ident, "kind": "original", "label": label, "locator": "PDF 第 %s 页，%s" % (page, label),
                  "pdf_page": page, "caption": caption, "alt": label + "（待补中文说明）", "credit": "",
                  "local_path": relative, "sha256": sha256(target), "paper_sha256": data["paper"]["sha256"],
                  "paper_version": data["paper"]["version"], "rights_status": "unknown", "rights_note": "",
                  "checked": False, "use_as_evidence": True, "extraction": request}
        data["figures"].append(figure)
        validate(data, root)
        # Atomically replace only the manifest we loaded; never overwrite an image.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root, prefix=".manifest-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
        try:
            os.replace(temporary, manifest)
        finally:
            temporary.unlink(missing_ok=True)
        return {"status": "saved", "figure": figure}
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("--pdf", type=Path, required=True)
    init.add_argument("--output-dir", type=Path, required=True)
    for field in ("metadata", "title", "version", "source-url", "selection", "selected-id"):
        init.add_argument("--" + field)
    check = subs.add_parser("check")
    check.add_argument("manifest", type=Path)
    for mode in ("capture", "import-figure"):
        item = subs.add_parser(mode)
        item.add_argument("manifest", type=Path)
        item.add_argument("--id", required=True)
        item.add_argument("--page", type=int, required=True)
        item.add_argument("--label", required=True)
        item.add_argument("--caption", required=True)
        if mode == "capture":
            item.add_argument("--box", type=float, nargs=4)
            item.add_argument("--scale", type=int, default=2400)
            item.add_argument("--renderer", default="pdftoppm")
        else:
            item.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            init_workspace(args.pdf, args.output_dir, args.metadata, args.title, args.version,
                           args.source_url, args.selection, args.selected_id)
            result = {"manifest": str((args.output_dir / MANIFEST).resolve()), "status": "initialized"}
        elif args.command == "check":
            data, path = load(args.manifest)
            result = {"status": "valid", "manifest": str(path.resolve()), "figures": len(data["figures"]),
                      "note": "Checks files/hashes/version only, not scientific truth or visual review"}
        else:
            result = save_figure(args.manifest, args.id, args.page, args.label, args.caption,
                                 getattr(args, "box", None), getattr(args, "image", None),
                                 getattr(args, "scale", 2400), getattr(args, "renderer", "pdftoppm"))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
