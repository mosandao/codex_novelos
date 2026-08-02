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

    def _setup(self, service: NovelOSService | None = None) -> dict:
        parent_id = "creator-profile-version:system-youthful-bonds:v1"
        parent_hash = "sha256:" + "0" * 64
        if service is not None:
            archetype = service.list_system_archetypes()[0]["latest_version"]
            parent_id = archetype["id"]
            parent_hash = archetype["subject_hash"]
        return {
            "title": "向导测试项目",
            "creator": {
                "mode": "derive",
                "parent_version_id": parent_id,
                "parent_subject_hash": parent_hash,
                "display_name": "向导测试作者",
                "overrides": {"recurring_attention": ["观察少年羁绊与日常矛盾"]},
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
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            title, description, metadata, creator = normalize_project_setup(self._setup(service))
            self.assertEqual("向导测试项目", title)
            self.assertIn("男频", description)
            self.assertEqual("derive", creator["mode"])
            self.assertEqual(3, metadata["project_setup"]["version"])
            self.assertEqual("derive", metadata["project_setup"]["creator_selection"]["mode"])
            self.assertEqual("起点", metadata["project_setup"]["creation_context"]["platform"])
            self.assertEqual("主角从边境小镇出发，避免无敌开局。", metadata["project_setup"]["creation_context"]["reference_material"])
            self.assertEqual(["史诗厚重", "黑暗压抑"], metadata["project_setup"]["taxonomy"]["emotional_tones"])
            self.assertEqual(["西幻史诗", "黑暗哥特"], metadata["project_setup"]["taxonomy"]["aesthetic_styles"])

            created = service.create_project_with_creator(title, description, metadata, creator)
            stored = service.get_project(created["project"]["id"])
            self.assertEqual(metadata, stored["metadata"])
            self.assertEqual(
                created["creator_binding"]["subject_hash"],
                service.get_project_creator_binding(stored["id"])["subject_hash"],
            )

    def test_normalizes_and_creates_derive_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            archetype = service.list_system_archetypes()[0]["latest_version"]
            derive_setup = self._setup(service) | {
                "title": "派生作者项目",
                "creator": {
                    "mode": "derive",
                    "parent_version_id": archetype["id"],
                    "parent_subject_hash": archetype["subject_hash"],
                    "display_name": "城市冷峻分支",
                    "overrides": {"expression_preferences": ["短句、低议论、保留事实空白"]},
                },
            }
            name, description, metadata, creator = normalize_project_setup(derive_setup)
            derived = service.create_project_with_creator(name, description, metadata, creator)
            derived_version = derived["creator_binding"]["profile_version"]
            self.assertEqual("derive", derived["creator_binding"]["binding_mode"])
            self.assertEqual(archetype["id"], derived_version["parent_version_id"])
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
        self.assertNotIn('name="creator_mode"', html)
        self.assertNotIn('id="creator_reuse"', html)
        self.assertNotIn('id="creator_create"', html)
        self.assertIn('id="archetype_recommendations"', html)
        self.assertIn("recommendationScore", html)
        self.assertIn("继承自原型（只读）", html)
        self.assertIn("提供给 Main Agent 的作者偏好原始输入", html)
        self.assertIn('id="creator_parent_options"', html)
        self.assertIn('name="creator_parents"', html)
        self.assertIn("selected_archetypes", html)
        self.assertIn("user_signature_inputs", html)
        self.assertIn("main_agent_processing", html)
        self.assertNotIn('id="generate_derived_signature"', html)
        self.assertNotIn('id="reset_derived_signature"', html)
        self.assertNotIn("已清空本书差异", html)
        self.assertNotIn("生成基础差异草稿", html)
        self.assertNotIn("fillGeneratedDerivation", html)
        self.assertIn('mode: "derive"', html)
        self.assertNotIn("fillGeneratedSignature", html)
        for field in ("recurring_attention", "narrative_principles", "forbidden_conveniences", "expression_preferences"):
            self.assertIn(field, html)
        self.assertIn('appInfo: { name: "novelos-project-wizard", version: "3.0.0" }', html)
        self.assertNotIn("clientInfo:", html)
        self.assertNotIn('name: "project.wizard.render"', html)
        self.assertIn("loadCreatorProfiles();", html)
        self.assertIn("bridgePromise = undefined;", html)
        self.assertIn("window.NOVELOS_WIZARD_DATA || {}", html)
        self.assertIn('get("mode") === "offline"', html)
        self.assertIn('request_type: "novelos.project.create.v1"', html)
        self.assertIn("generateStandaloneJson", html)
        self.assertIn('submit.textContent = "生成项目提交 JSON";', html)
        self.assertNotIn('name: "project.wizard.submit"', html)
        self.assertIn("JSON.stringify(request, null, 2)", html)
        self.assertIn("navigator.clipboard.writeText", html)
        self.assertIn('document.execCommand("copy")', html)
        self.assertIn('id="json_output"', html)
        self.assertIn('id="copy_json"', html)
        self.assertIn('script src="./project-wizard-data.js"', html)


if __name__ == "__main__":
    unittest.main()
