from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class AdaptersConsistency(unittest.TestCase):
    """P4-1：adapters README 与事实源同步；一致性校验器对仓库现状全绿。"""

    def test_check_passes_on_repo(self):
        import subprocess
        import sys
        r = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/novelos_build_adapters.py"), "--check"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(r.returncode, 0, f"adapters check FAIL:\n{r.stderr}")

    def test_readme_covers_three_harnesses(self):
        readme = (REPO_ROOT / "adapters/README.md").read_text(encoding="utf-8")
        for h in ("codex", "zcode", "deepseek"):
            self.assertIn(h, readme)
        self.assertIn("零变体", readme)  # sub agent ABI 单源原则


if __name__ == "__main__":
    unittest.main()
