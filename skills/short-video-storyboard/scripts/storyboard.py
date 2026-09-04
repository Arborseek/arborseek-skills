"""Validate and export shooting plans offline; never generates or publishes video."""
import argparse
import csv
import json
import math
import re
from pathlib import Path

TYPES = {"product-demo", "explainer", "talking-head", "tutorial", "event-recap", "customer-case", "company-story", "team-culture"}


def text(value):
    return isinstance(value, str) and bool(value.strip())


def seconds(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= .001


def check(data):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["plan must be an object"], "warnings": []}
    for key in ("title", "audience", "objective", "platform"):
        if not text(data.get(key)):
            errors.append(key + " is required")
    if not isinstance(data.get("type"), str) or data.get("type") not in TYPES:
        errors.append("unknown video type")
    if data.get("aspect_ratio") not in ("9:16", "16:9", "1:1", "4:5"):
        errors.append("unsupported aspect_ratio")
    if not seconds(data.get("duration_seconds")):
        errors.append("duration_seconds must be positive and finite")
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        errors.append("assets must be an array")
        assets = []
    ids = set()
    for asset in assets:
        if not isinstance(asset, dict):
            errors.append("asset must be an object")
            continue
        ident = asset.get("id")
        if not text(ident) or ident in ids:
            errors.append("asset id must be a unique string")
        else:
            ids.add(ident)
        if asset.get("status") not in ("existing", "to-shoot", "to-create"):
            errors.append("invalid asset status")
        for key in ("description", "source"):
            if not text(asset.get(key)):
                errors.append("asset " + key + " is required")
    notes = data.get("production_notes", [])
    if not isinstance(notes, list) or any(not text(n) for n in notes):
        errors.append("production_notes must be an array of nonempty strings")
    shots = data.get("shots")
    if not isinstance(shots, list) or not shots:
        errors.append("shots must be a nonempty array")
        shots = []
    total = 0
    for index, shot in enumerate(shots, 1):
        prefix = f"shot {index}: "
        if not isinstance(shot, dict):
            errors.append(prefix + "must be an object")
            continue
        duration = shot.get("duration_seconds")
        if not seconds(duration):
            errors.append(prefix + "duration must be positive and finite")
        else:
            total += duration
        for key in ("framing", "movement", "visual", "audio"):
            if not text(shot.get(key)):
                errors.append(prefix + key + " is required")
        for key in ("voiceover", "subtitle"):
            value = shot.get(key)
            if not isinstance(value, str):
                errors.append(prefix + key + " must be a string (empty is allowed)")
            elif (re.search(r"\{\{.+?\}\}|【(?:待补|待确认|TODO)[^】]*】", value, re.I)
                  or value.strip().lower() in ("todo", "待补", "待补数据", "待确认")):
                errors.append(prefix + "move editorial placeholders out of spoken text/subtitles")
        spoken = shot.get("voiceover", "")
        if isinstance(spoken, str) and seconds(duration):
            units = len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+", spoken))
            if units / duration > 4:
                warnings.append(prefix + "voiceover may be too dense; time an actual read")
        refs = shot.get("assets")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in ids for ref in refs):
            errors.append(prefix + "assets must reference known asset IDs")
    if seconds(data.get("duration_seconds")) and abs(total - data["duration_seconds"]) > .01:
        errors.append("shot durations do not match target duration")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "duration_seconds": total, "shots": len(shots)}


def timecode(milliseconds):
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, millis = divmod(rest, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def timeline(shots):
    elapsed = 0.0
    for i, shot in enumerate(shots, 1):
        start = round(elapsed * 1000)
        elapsed += shot["duration_seconds"]
        yield i, start, round(elapsed * 1000), shot


def md(value):
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def cell(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r")) else value


def export(data, output):
    report = check(data)
    if not report["valid"]:
        raise ValueError("; ".join(report["errors"]))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows, subtitles = [], []
    header = ["镜号", "起始", "结束", "景别/机位", "运动", "画面动作", "口播/旁白", "屏幕字幕", "声音", "素材ID"]
    for i, start, end, shot in timeline(data["shots"]):
        rows.append([str(i), timecode(start), timecode(end), shot["framing"], shot["movement"], shot["visual"], shot["voiceover"], shot["subtitle"], shot["audio"], ", ".join(shot["assets"])])
        if shot["subtitle"].strip():
            subtitle = "\n".join(line.strip() for line in shot["subtitle"].splitlines() if line.strip())
            subtitles.append(f"{len(subtitles)+1}\n{timecode(start)} --> {timecode(end)}\n{subtitle}\n")
    script = f"# {data['title']}\n\n受众：{data['audience']}\n\n目标：{data['objective']}\n\n类型：{data['type']} · 渠道：{data['platform']} · 画幅：{data['aspect_ratio']} · 计划时长：{data['duration_seconds']} 秒\n\n## 口播 / 旁白\n\n"
    script += "\n\n".join(s["voiceover"] for s in data["shots"] if s["voiceover"].strip()) or "无口播。"
    script += "\n\n## 分镜表\n\n| " + " | ".join(header) + " |\n| " + " | ".join(["---"] * len(header)) + " |\n"
    script += "\n".join("| " + " | ".join(md(c) for c in row) + " |" for row in rows) + "\n"
    with (output / "shots.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows([[cell(c) for c in row] for row in rows])
    (output / "script.md").write_text(script, encoding="utf-8")
    (output / "rough-subtitles.srt").write_text("\n".join(subtitles), encoding="utf-8")
    production = "# 制作执行单\n\n字幕时间仅按计划镜头估算，需在实际录音/剪辑后重新对齐。尚未生成或发布视频。\n\n## 素材\n\n"
    production += "\n".join(f"- {a['id']}｜{a['status']}｜{a['description']}｜{a['source']}" for a in data.get("assets", [])) or "无额外素材。"
    production += "\n\n## 拍摄与剪辑安排\n\n" + ("\n".join("- " + n for n in data.get("production_notes", [])) or "按分镜安排。")
    if report["warnings"]:
        production += "\n\n## 需试读核对\n\n" + "\n".join("- " + w for w in report["warnings"])
    (output / "production.md").write_text(production + "\n", encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "export"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    args = parser.parse_args()
    if args.command == "export" and args.output is None:
        parser.error("export needs a new output directory")
    try:
        data = json.loads(args.plan.read_text(encoding="utf-8"))
        report = export(data, args.output) if args.command == "export" else check(data)
    except (ValueError, OSError) as exc:
        report = {"valid": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
