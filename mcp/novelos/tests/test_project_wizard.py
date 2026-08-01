from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSService
from novelos_mcp.errors import NovelOSError
from novelos_mcp.project_wizard import (
    SECONDARY_DIRECTION_SUGGESTIONS,
    WIZARD_OPTIONS,
    normalize_project_setup,
    project_wizard_html,
)


class ProjectWizardTest(unittest.TestCase):
    @staticmethod
    def _signature(label: str = "制度") -> dict[str, object]:
        return {
            "schema_version": 1,
            "sympathies": [f"维护{label}中的普通人尊严"],
            "distrusts": [f"警惕{label}中不承担代价的权力"],
            "recurring_attention": [f"观察{label}如何进入日常关系"],
            "narrative_principles": ["通过选择和后果表达判断"],
            "forbidden_conveniences": ["不得用一句道歉抹平长期伤害"],
            "expression_preferences": ["保持克制叙述并允许留白"],
            "negative_constraints": ["不模仿具体作者，不根据人口属性推导文风"],
        }

    def _setup(self) -> dict:
        return {
            "title": "向导测试项目",
            "creator": {
                "mode": "create",
                "display_name": "向导测试作者",
                "signature": self._signature(),
            },
            "channel": "男频",
            "platform": "起点",
            "scale": "超长篇（500万字以上）",
            "primary_genre": "奇幻",
            "secondary_directions": ["西方玄幻", "领主战争"],
            "emotional_tones": ["史诗厚重", "黑暗压抑"],
            "aesthetic_styles": ["西幻史诗", "黑暗哥特"],
            "reference_material": "主角从边境小镇出发，避免无敌开局。",
        }

    def test_normalizes_structured_constraints_for_project_metadata(self) -> None:
        title, description, metadata, creator = normalize_project_setup(self._setup())
        self.assertEqual("向导测试项目", title)
        self.assertIn("男频", description)
        self.assertEqual("create", creator["mode"])
        self.assertEqual(3, metadata["project_setup"]["version"])
        self.assertEqual("create", metadata["project_setup"]["creator_selection"]["mode"])
        self.assertEqual("起点", metadata["project_setup"]["creation_context"]["platform"])
        self.assertEqual("主角从边境小镇出发，避免无敌开局。", metadata["project_setup"]["creation_context"]["reference_material"])
        self.assertEqual(["史诗厚重", "黑暗压抑"], metadata["project_setup"]["taxonomy"]["emotional_tones"])
        self.assertEqual(["西幻史诗", "黑暗哥特"], metadata["project_setup"]["taxonomy"]["aesthetic_styles"])

        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            created = service.create_project_with_creator(title, description, metadata, creator)
            stored = service.get_project(created["project"]["id"])
            self.assertEqual(metadata, stored["metadata"])
            self.assertEqual(
                created["creator_binding"]["subject_hash"],
                service.get_project_creator_binding(stored["id"])["subject_hash"],
            )

    def test_normalizes_and_creates_reuse_and_derive_modes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            base = service.create_creator_profile("基础作者", self._signature("城市"))["version"]
            reuse_setup = self._setup() | {
                "title": "复用作者项目",
                "creator": {
                    "mode": "reuse",
                    "profile_version_id": base["id"],
                    "subject_hash": base["subject_hash"],
                },
            }
            name, description, metadata, creator = normalize_project_setup(reuse_setup)
            reused = service.create_project_with_creator(name, description, metadata, creator)
            self.assertEqual("reuse", reused["creator_binding"]["binding_mode"])
            self.assertEqual(base["id"], reused["creator_binding"]["profile_version_id"])

            derive_setup = self._setup() | {
                "title": "派生作者项目",
                "creator": {
                    "mode": "derive",
                    "parent_version_id": base["id"],
                    "parent_subject_hash": base["subject_hash"],
                    "display_name": "城市冷峻分支",
                    "overrides": {"expression_preferences": ["短句、低议论、保留事实空白"]},
                },
            }
            name, description, metadata, creator = normalize_project_setup(derive_setup)
            derived = service.create_project_with_creator(name, description, metadata, creator)
            derived_version = derived["creator_binding"]["profile_version"]
            self.assertEqual("derive", derived["creator_binding"]["binding_mode"])
            self.assertEqual(base["id"], derived_version["parent_version_id"])
            self.assertEqual(creator["overrides"], derived_version["derivation"])

    def test_rejects_removed_options_and_invalid_choices(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "最多选择两项"):
            normalize_project_setup(self._setup() | {"aesthetic_styles": ["西幻史诗", "黑暗哥特", "蒸汽幻想"]})
        with self.assertRaisesRegex(NovelOSError, "未支持字段"):
            normalize_project_setup(self._setup() | {"custom_word_count": 680_000})
        with self.assertRaisesRegex(NovelOSError, "二级方向"):
            normalize_project_setup(self._setup() | {"secondary_directions": ["古典仙侠"]})
        with self.assertRaisesRegex(NovelOSError, "主情绪基调"):
            normalize_project_setup(self._setup() | {"emotional_tones": ["不存在的情绪"]})

    def test_local_preview_contains_all_choices_without_javascript(self) -> None:
        html = project_wizard_html()

        for key in ("channels", "platforms", "scales", "primary_genres", "emotional_tones", "aesthetic_styles"):
            for value in WIZARD_OPTIONS[key]:
                self.assertIn(f">{value}</label>", html)
        for genre, suggestions in SECONDARY_DIRECTION_SUGGESTIONS.items():
            self.assertIn(f'"{genre}"', html)
            for value in suggestions:
                self.assertIn(f'"{value}"', html)
        self.assertNotIn("知乎盐选", html)
        self.assertNotIn("自定义字数", html)
        self.assertNotIn('value="自定义"', html)
        self.assertIn("reference_material", html)
        self.assertIn("emotional_tones", html)
        self.assertIn('name="creator_mode" value="reuse"', html)
        self.assertIn('name="creator_mode" value="derive"', html)
        self.assertIn('name="creator_mode" value="create"', html)
        for field in self._signature():
            self.assertIn(field, html)
        self.assertIn('appInfo: { name: "novelos-project-wizard", version: "3.0.0" }', html)
        self.assertNotIn("clientInfo:", html)
        self.assertIn("if (!standalone) void initializeBridge().then(loadCreatorProfiles).catch(() => {});", html)
        self.assertIn("bridgePromise = undefined;", html)
        self.assertIn("本地预览页不能创建项目", html)


if __name__ == "__main__":
    unittest.main()
