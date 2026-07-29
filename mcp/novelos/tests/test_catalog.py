from __future__ import annotations

import tempfile
import unittest
import shutil
from pathlib import Path

from novelos_mcp import NovelOSError
from novelos_mcp.catalog import CatalogStore


class CatalogStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        package = self.root / "wave-a" / "scene-dialogue"
        package.mkdir(parents=True)
        (package / "metadata.yaml").write_text(
            """name: scene-dialogue
description: 对话场景方法
stage: write
asset: scene
capability: generate
lifecycle: active
version: 1.0.0
output_contract: free_text
genres: []
priority: 10
""",
            encoding="utf-8",
        )
        (package / "prompt.md").write_text("保持人物声音一致。", encoding="utf-8")
        (package / "provenance.yaml").write_text(
            """origin: target-native
source_repository: null
source_path: null
source_commit: null
source_hash: null
license: test
migration_note: 测试夹具
""",
            encoding="utf-8",
        )
        self.store = CatalogStore(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_search_is_lightweight_and_selection_is_snapshot_bound(self) -> None:
        result = self.store.search(stage="write", asset="scene", capability="generate")
        self.assertEqual("scene-dialogue", result["candidates"][0]["name"])
        self.assertNotIn("prompt", result["candidates"][0])
        validated = self.store.validate_selection(
            ["scene-dialogue"], ["scene-dialogue"], result["snapshot_hash"]
        )
        self.assertTrue(validated["valid"])

    def test_prompt_is_loaded_only_by_resource(self) -> None:
        package = self.store.get("scene-dialogue")
        self.assertEqual(
            "novelos://catalog/scene-dialogue/prompt",
            package["resources"]["prompt"],
        )
        self.assertEqual("保持人物声音一致。", self.store.get_resource("scene-dialogue", "prompt"))
        self.assertEqual("target-native", package["provenance"]["origin"])

    def test_unknown_metadata_field_is_rejected(self) -> None:
        metadata = self.root / "wave-a" / "scene-dialogue" / "metadata.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8") + "semantic_router: true\n", encoding="utf-8")
        with self.assertRaisesRegex(NovelOSError, "invalid_catalog"):
            self.store.search()

    def test_changed_package_invalidates_snapshot(self) -> None:
        result = self.store.search()
        prompt = self.root / "wave-a" / "scene-dialogue" / "prompt.md"
        prompt.write_text("新的方法。", encoding="utf-8")
        with self.assertRaisesRegex(NovelOSError, "stale_catalog"):
            self.store.validate_selection(
                ["scene-dialogue"], ["scene-dialogue"], result["snapshot_hash"]
            )

    def test_missing_provenance_is_rejected(self) -> None:
        (self.root / "wave-a" / "scene-dialogue" / "provenance.yaml").unlink()
        with self.assertRaisesRegex(NovelOSError, "invalid_catalog"):
            self.store.search()

    def test_free_text_output_validation_rejects_empty_content(self) -> None:
        self.assertTrue(self.store.validate_output("scene-dialogue", "有效正文")["valid"])
        self.assertFalse(self.store.validate_output("scene-dialogue", "  ")["valid"])

    def test_non_active_package_requires_explicit_lifecycle(self) -> None:
        metadata = self.root / "wave-a" / "scene-dialogue" / "metadata.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8").replace("lifecycle: active", "lifecycle: experiment"), encoding="utf-8")
        self.assertEqual([], self.store.search()["candidates"])
        self.assertEqual(["scene-dialogue"], [item["name"] for item in self.store.search(lifecycle="experiment")["candidates"]])

    def test_duplicate_name_across_tiers_is_rejected(self) -> None:
        source = self.root / "wave-a" / "scene-dialogue"
        duplicate = self.root / "wave-b" / "scene-dialogue"
        shutil.copytree(source, duplicate)
        with self.assertRaisesRegex(NovelOSError, "名称重复"):
            self.store.search()

    def test_exact_scope_precedes_global_candidate(self) -> None:
        package = self.root / "wave-a" / "scene-dialogue-project"
        package.mkdir(parents=True)
        (package / "metadata.yaml").write_text(
            """name: scene-dialogue-project
description: 项目专用对话方法
stage: write
asset: scene
capability: generate
lifecycle: active
version: 1.0.0
output_contract: free_text
scope: project:1
priority: 100
""",
            encoding="utf-8",
        )
        shutil.copy(self.root / "wave-a" / "scene-dialogue" / "provenance.yaml", package / "provenance.yaml")
        result = self.store.search(stage="write", asset="scene", scope="project:1")
        self.assertEqual(["scene-dialogue-project", "scene-dialogue"], [item["name"] for item in result["candidates"]])
        self.assertTrue(
            self.store.validate_selection(
                ["scene-dialogue-project"],
                [item["name"] for item in result["candidates"]],
                result["snapshot_hash"],
            )["valid"]
        )


if __name__ == "__main__":
    unittest.main()
