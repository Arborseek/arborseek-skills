from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_workbuddy_package as workbuddy  # noqa: E402


class WorkBuddyPackageTests(unittest.TestCase):
    def test_package_has_expected_root_metadata_and_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "wechat-article-skill-workbuddy.zip"
            workbuddy.build_package(ROOT, output)

            with ZipFile(output) as archive:
                names = set(archive.namelist())
                expected = {
                    "SKILL.md",
                    "requirements.txt",
                    "references/style-system.md",
                    "scripts/style_article_html.py",
                    "schemas/article-package.schema.json",
                }
                self.assertFalse(expected - names)
                self.assertFalse(any(name.startswith("skills/") for name in names))
                manifest = archive.read("SKILL.md").decode("utf-8")

            for field in (
                "description_zh:",
                "description_en:",
                "version:",
                "author:",
                "user-invocable: true",
                "version: 1.1.2",
            ):
                self.assertIn(field, manifest)
            self.assertEqual(manifest.count("# WeChat Article Skill"), 1)


if __name__ == "__main__":
    unittest.main()
