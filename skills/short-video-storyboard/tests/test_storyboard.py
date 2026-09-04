import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import storyboard


class StoryboardTests(unittest.TestCase):
    def plan(self):
        return json.loads((ROOT / "examples/work-feedback.json").read_text(encoding="utf-8"))

    def test_example_and_all_types(self):
        for kind in storyboard.TYPES:
            plan = self.plan()
            plan["type"] = kind
            self.assertTrue(storyboard.check(plan)["valid"])
            self.assertEqual(storyboard.check(plan)["duration_seconds"], 45)

    def test_time_mismatch(self):
        plan = self.plan()
        plan["shots"][0]["duration_seconds"] += 1
        self.assertFalse(storyboard.check(plan)["valid"])

    def test_invalid_durations(self):
        for duration in (0, -1, True, float("nan"), float("inf"), "5"):
            plan = self.plan()
            plan["shots"][0]["duration_seconds"] = duration
            self.assertFalse(storyboard.check(plan)["valid"])

    def test_missing_or_duplicate_assets(self):
        plan = self.plan()
        plan["shots"][0]["assets"] = ["not-found"]
        self.assertFalse(storyboard.check(plan)["valid"])
        plan = self.plan()
        plan["assets"].append(copy.deepcopy(plan["assets"][0]))
        self.assertFalse(storyboard.check(plan)["valid"])

    def test_placeholder_and_density(self):
        plan = self.plan()
        for placeholder in ("待补数据", "效果提升{{数值}}", "提升【待确认数据】"):
            plan["shots"][0]["voiceover"] = placeholder
            self.assertFalse(storyboard.check(plan)["valid"])
        plan["shots"][0]["voiceover"] = "待确认的配图，记在待办中。"
        self.assertTrue(storyboard.check(plan)["valid"])
        plan["shots"][0]["voiceover"] = "这是非常长的口播" * 30
        self.assertTrue(storyboard.check(plan)["valid"])
        self.assertTrue(storyboard.check(plan)["warnings"])

    def test_exports_no_overwrite_and_no_input_mutation(self):
        plan = self.plan()
        original = copy.deepcopy(plan)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "脚本"
            storyboard.export(plan, output)
            self.assertEqual(len(list(output.iterdir())), 5)
            self.assertIn("00:00:40,000 --> 00:00:45,000", (output / "rough-subtitles.srt").read_text())
            self.assertNotIn("单人手机拍摄假设", (output / "script.md").read_text())
            self.assertIn("单人手机拍摄假设", (output / "production.md").read_text())
            with self.assertRaises(FileExistsError):
                storyboard.export(plan, output)
        self.assertEqual(plan, original)

    def test_blank_subtitle_and_csv_injection(self):
        plan = self.plan()
        plan["shots"][0]["subtitle"] = ""
        plan["shots"][0]["voiceover"] = "=1+1"
        plan["shots"][0]["visual"] = "画面 | 换行\n新行"
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            storyboard.export(plan, output)
            self.assertTrue((output / "rough-subtitles.srt").read_text().startswith("1\n00:00:05,000"))
            with (output / "shots.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[1][6], "'=1+1")
            self.assertIn("画面 \\| 换行<br>新行", (output / "script.md").read_text())

    def test_malformed_input(self):
        for plan in (None, [], {}, {"shots": [None], "assets": [None]}):
            self.assertFalse(storyboard.check(plan)["valid"])

    def test_timecodes(self):
        self.assertEqual(storyboard.timecode(3661002), "01:01:01,002")
        rows = list(storyboard.timeline([{"duration_seconds": .333}, {"duration_seconds": .667}]))
        self.assertEqual(rows[0][2], rows[1][1])
        self.assertEqual(rows[1][2], 1000)

    def test_cli_from_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/storyboard.py"), "export", str(ROOT / "examples/work-feedback.json"), str(Path(tmp) / "out")], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])
