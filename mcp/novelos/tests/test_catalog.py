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
        package = self.root / "writing" / "scene-dialogue"
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

    def _make_atlas(self) -> Path:
        """搭一个带 clusters/ 目录的临时 atlas 包，供 cluster 读取测试复用。"""
        package = self.root / "expansions" / "scenario-atlas"
        package.mkdir(parents=True)
        (package / "metadata.yaml").write_text(
            """name: scenario-atlas
description: 桥段图集
stage: plan
asset: world_contract
capability: compose
lifecycle: active
version: 0.3.1
output_contract: document
genres: []
priority: 30
""",
            encoding="utf-8",
        )
        (package / "prompt.md").write_text("索引文件。", encoding="utf-8")
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
        clusters = package / "clusters"
        clusters.mkdir()
        (clusters / "xiuxian.md").write_text("# 修仙桥段\n灵根觉醒。", encoding="utf-8")
        (clusters / "system.md").write_text("# 系统流桥段\n面板激活。", encoding="utf-8")
        return package

    def test_cluster_files_are_listed_in_resources(self) -> None:
        self._make_atlas()
        info = self.store.get("scenario-atlas")
        self.assertEqual(["system.md", "xiuxian.md"], info["resources"]["clusters"])
        listing = self.store.list_cluster_files("scenario-atlas")
        self.assertEqual(["system.md", "xiuxian.md"], listing["clusters"])

    def test_get_cluster_file_returns_content(self) -> None:
        self._make_atlas()
        content = self.store.get_cluster_file("scenario-atlas", "xiuxian.md")
        self.assertIn("灵根觉醒", content)

    def test_get_cluster_file_rejects_path_traversal(self) -> None:
        self._make_atlas()
        for malicious in ("../etc/passwd.md", "a/b.md", ".env.md", "xiuxian.txt", "", "xiuxian.md/"):
            with self.subTest(filename=malicious):
                with self.assertRaisesRegex(NovelOSError, "invalid_argument"):
                    self.store.get_cluster_file("scenario-atlas", malicious)

    def test_get_cluster_file_missing_file_raises(self) -> None:
        self._make_atlas()
        with self.assertRaisesRegex(NovelOSError, "not_found"):
            self.store.get_cluster_file("scenario-atlas", "wuxia.md")

    def test_unknown_metadata_field_is_rejected(self) -> None:
        metadata = self.root / "writing" / "scene-dialogue" / "metadata.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8") + "semantic_router: true\n", encoding="utf-8")
        with self.assertRaisesRegex(NovelOSError, "invalid_catalog"):
            self.store.search()

    def test_changed_package_invalidates_snapshot(self) -> None:
        result = self.store.search()
        prompt = self.root / "writing" / "scene-dialogue" / "prompt.md"
        prompt.write_text("新的方法。", encoding="utf-8")
        with self.assertRaisesRegex(NovelOSError, "stale_catalog"):
            self.store.validate_selection(
                ["scene-dialogue"], ["scene-dialogue"], result["snapshot_hash"]
            )

    def test_missing_provenance_is_rejected(self) -> None:
        (self.root / "writing" / "scene-dialogue" / "provenance.yaml").unlink()
        with self.assertRaisesRegex(NovelOSError, "invalid_catalog"):
            self.store.search()

    def test_free_text_output_validation_rejects_empty_content(self) -> None:
        self.assertTrue(self.store.validate_output("scene-dialogue", "有效正文")["valid"])
        self.assertFalse(self.store.validate_output("scene-dialogue", "  ")["valid"])

    def test_non_active_package_requires_explicit_lifecycle(self) -> None:
        metadata = self.root / "writing" / "scene-dialogue" / "metadata.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8").replace("lifecycle: active", "lifecycle: experiment"), encoding="utf-8")
        self.assertEqual([], self.store.search()["candidates"])
        self.assertEqual(["scene-dialogue"], [item["name"] for item in self.store.search(lifecycle="experiment")["candidates"]])

    def test_duplicate_name_across_tiers_is_rejected(self) -> None:
        source = self.root / "writing" / "scene-dialogue"
        duplicate = self.root / "planning" / "scene-dialogue"
        shutil.copytree(source, duplicate)
        with self.assertRaisesRegex(NovelOSError, "名称重复"):
            self.store.search()

    def test_exact_scope_precedes_global_candidate(self) -> None:
        package = self.root / "writing" / "scene-dialogue-project"
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
        shutil.copy(self.root / "writing" / "scene-dialogue" / "provenance.yaml", package / "provenance.yaml")
        result = self.store.search(stage="write", asset="scene", scope="project:1")
        self.assertEqual(["scene-dialogue-project", "scene-dialogue"], [item["name"] for item in result["candidates"]])
        self.assertTrue(
            self.store.validate_selection(
                ["scene-dialogue-project"],
                [item["name"] for item in result["candidates"]],
                result["snapshot_hash"],
            )["valid"]
        )

    def test_contract_yaml_loading_and_lightweight_search(self) -> None:
        package_dir = self.root / "writing" / "scene-dialogue"
        (package_dir / "contract.yaml").write_text(
            """contract_version: 1
inputs:
  - contract: fundamental_rules
    cardinality: one
outputs:
  - growth_and_resource_system
invariants:
  - 不得创建主角免费例外
forbidden_actions:
  - commit_authority
""",
            encoding="utf-8",
        )
        search_res = self.store.search(stage="write", asset="scene")
        self.assertNotIn("contract", search_res["candidates"][0])
        self.assertNotIn("inputs", search_res["candidates"][0])

        pkg_info = self.store.get("scene-dialogue")
        self.assertEqual("novelos://catalog/scene-dialogue/contract", pkg_info["resources"]["contract"])
        content = self.store.get_resource("scene-dialogue", "contract")
        self.assertIn("fundamental_rules", content)

    def test_invalid_contract_yaml_rejected(self) -> None:
        package_dir = self.root / "writing" / "scene-dialogue"
        (package_dir / "contract.yaml").write_text("contract_version: 1\nunknown_field: true\n", encoding="utf-8")
        with self.assertRaisesRegex(NovelOSError, "contract 字段不合法"):
            self.store.search()

    def test_invalid_contract_cardinality_rejected(self) -> None:
        package_dir = self.root / "writing" / "scene-dialogue"
        (package_dir / "contract.yaml").write_text(
            """contract_version: 1
inputs:
  - contract: test
    cardinality: invalid_cardinality
outputs: []
invariants: []
forbidden_actions: []
""",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(NovelOSError, "contract input cardinality 非法"):
            self.store.search()

    def test_duplicate_string_in_contract_rejected(self) -> None:
        package_dir = self.root / "writing" / "scene-dialogue"
        (package_dir / "contract.yaml").write_text(
            """contract_version: 1
inputs: []
outputs:
  - dup
  - dup
invariants: []
forbidden_actions: []
""",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(NovelOSError, "outputs 存在重复字符串"):
            self.store.search()

    def test_contract_yaml_change_invalidates_snapshot(self) -> None:
        package_dir = self.root / "writing" / "scene-dialogue"
        (package_dir / "contract.yaml").write_text(
            """contract_version: 1
inputs: []
outputs: [a]
invariants: []
forbidden_actions: []
""",
            encoding="utf-8",
        )
        snap1 = self.store.search()["snapshot_hash"]
        (package_dir / "contract.yaml").write_text(
            """contract_version: 1
inputs: []
outputs: [b]
invariants: []
forbidden_actions: []
""",
            encoding="utf-8",
        )
        snap2 = self.store.search()["snapshot_hash"]
        self.assertNotEqual(snap1, snap2)


if __name__ == "__main__":
    unittest.main()
