from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.check_repository_hygiene import DEFAULT_OUTPUT, HygieneError, build, render, snapshot


ROOT = Path(__file__).resolve().parents[2]


class RepositoryHygieneTest(unittest.TestCase):
    def test_current_prospective_git_surface_is_clean(self) -> None:
        report = build()
        self.assertEqual("passed", report["status"])
        self.assertTrue(report["git_baseline_available"])
        self.assertGreater(report["tracked_file_count"], 0)
        self.assertEqual(0, report["prohibited_file_count"])
        # 黄金文件只锁定结构性字段：剥离随工作树波动的瞬时文件计数，
        # 避免 developer 临时文件触发假阳性；禁止产物检测仍由 build() 即时 fail-closed。
        self.assertEqual(render(snapshot(report)), DEFAULT_OUTPUT.read_text(encoding="utf-8"))

    def test_golden_snapshot_ignores_instantaneous_untracked_files(self) -> None:
        # 工作树出现合法未跟踪文件时，结构性快照必须保持稳定（回归：曾因 .bak 假阳性失败）。
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "tracked.md").write_text("a", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.md"], cwd=root, check=True)
            baseline = render(snapshot(build(root)))
            # 加入一个合法但未跟踪的临时文件
            (root / "scratch.bak").write_text("transient", encoding="utf-8")
            self.assertEqual(baseline, render(snapshot(build(root))))

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
