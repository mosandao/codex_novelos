from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_repository_hygiene import DEFAULT_OUTPUT, HygieneError, build, render


ROOT = Path(__file__).resolve().parents[1]


class RepositoryHygieneTest(unittest.TestCase):
    def test_current_prospective_git_surface_is_clean(self) -> None:
        report = build()
        self.assertEqual("passed", report["status"])
        self.assertTrue(report["git_baseline_available"])
        self.assertGreater(report["tracked_file_count"], 0)
        self.assertEqual(0, report["prohibited_file_count"])
        self.assertEqual(render(report), DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    def test_forced_tracked_secret_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "private.key").write_text("not-a-real-key", encoding="utf-8")
            subprocess.run(["git", "add", "-f", "private.key"], cwd=root, check=True)
            with self.assertRaisesRegex(HygieneError, "禁止产物"):
                build(root)

    def test_missing_ignore_rule_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = (ROOT / ".gitignore").read_text(encoding="utf-8").replace("novels/\n", "")
            (root / ".gitignore").write_text(content, encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            with self.assertRaisesRegex(HygieneError, "缺少规则"):
                build(root)


if __name__ == "__main__":
    unittest.main()
