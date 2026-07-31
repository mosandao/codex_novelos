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
    def _setup(self) -> dict:
        return {
            "title": "向导测试项目",
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
        title, description, metadata = normalize_project_setup(self._setup())
        self.assertEqual("向导测试项目", title)
        self.assertIn("男频", description)
        self.assertEqual("起点", metadata["project_setup"]["creation_context"]["platform"])
        self.assertEqual("主角从边境小镇出发，避免无敌开局。", metadata["project_setup"]["creation_context"]["reference_material"])
        self.assertEqual(["史诗厚重", "黑暗压抑"], metadata["project_setup"]["taxonomy"]["emotional_tones"])
        self.assertEqual(["西幻史诗", "黑暗哥特"], metadata["project_setup"]["taxonomy"]["aesthetic_styles"])

        with tempfile.TemporaryDirectory() as directory:
            service = NovelOSService(Path(directory) / "wizard.db")
            project = service.create_project(title, description, metadata)
            stored = service.get_project(project["id"])
            self.assertEqual(metadata, stored["metadata"])

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
        self.assertIn("本地预览页不能创建项目", html)


if __name__ == "__main__":
    unittest.main()
