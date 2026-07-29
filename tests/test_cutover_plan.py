from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_cutover_plan import CutoverPlanError, DEFAULT_MANIFEST, REQUIRED_DELETE_PATHS, ROOT, load_and_validate


class CutoverPlanTest(unittest.TestCase):
    def test_cutover_manifest_covers_the_complete_removed_legacy_surface(self) -> None:
        manifest = load_and_validate()
        self.assertEqual("cutover", manifest["phase"])
        self.assertEqual(REQUIRED_DELETE_PATHS, {entry["path"] for entry in manifest["delete_paths"]})
        self.assertIn("mcp/novelos", manifest["preserve_paths"])
        self.assertIn(".agents/skills", manifest["preserve_paths"])

    def test_missing_delete_target_fails_closed(self) -> None:
        payload = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        payload["delete_paths"] = payload["delete_paths"][:-1]
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(CutoverPlanError, "删除范围不完整"):
                load_and_validate(ROOT, manifest)


if __name__ == "__main__":
    unittest.main()
