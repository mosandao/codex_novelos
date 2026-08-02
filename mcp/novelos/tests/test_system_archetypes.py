from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from novelos_mcp.archetype_recommendation import generate_derivation_draft, recommend_archetypes
from novelos_mcp.errors import NovelOSError
from novelos_mcp.service import NovelOSService
from novelos_mcp.system_archetypes import load_system_archetypes_config


class TestSystemArchetypes(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.db_path = self.root / "test.db"
        self.service = NovelOSService(self.db_path)


    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_load_all_18_archetypes(self) -> None:
        archetypes = load_system_archetypes_config()

        self.assertEqual(len(archetypes), 18)
        ids = {item["id"] for item in archetypes}
        self.assertIn("system-epic-framework", ids)
        self.assertIn("system-shadowed-choice", ids)
        self.assertIn("system-psychological-maze", ids)

    def test_standalone_wizard_bundle_matches_authoritative_archetypes(self) -> None:
        bundle = Path(__file__).resolve().parents[1] / "src" / "novelos_mcp" / "ui" / "project-wizard-data.js"
        payload_text = bundle.read_text(encoding="utf-8").split(" = ", 1)[1].rsplit(";\n", 1)[0]
        payload = json.loads(payload_text)
        configured = load_system_archetypes_config()
        self.assertEqual(18, len(payload["system_archetypes"]))
        self.assertEqual(
            [item["subject_hash"] for item in configured],
            [item["subject_hash"] for item in payload["system_archetypes"]],
        )
        self.assertEqual(18, len({item["profile_version_id"] for item in payload["system_archetypes"]}))

    def test_db_initialization_contains_18_system_archetypes(self) -> None:
        archetypes = self.service.list_system_archetypes()
        self.assertEqual(len(archetypes), 18)
        for profile in archetypes:
            self.assertEqual(profile["ownership"], "system_archetype")

    def test_system_archetypes_read_only_protection(self) -> None:
        archetypes = self.service.list_system_archetypes()
        target = archetypes[0]

        # 尝试修订只读原型，应当抛出 error
        with self.assertRaises(NovelOSError) as ctx:
            self.service.revise_creator_profile(
                target["id"],
                target["version"],
                target["latest_version"]["signature"],
            )
        self.assertIn("只读", str(ctx.exception.message))

        # 尝试归档只读原型，应当抛出 error
        with self.assertRaises(NovelOSError) as ctx:
            self.service.archive_creator_profile(target["id"], target["version"])
        self.assertIn("只读", str(ctx.exception.message))

    def test_recommendation_algorithm(self) -> None:
        archetypes = self.service.list_system_archetypes()
        arch_data = [item["latest_version"] for item in archetypes]

        top3 = recommend_archetypes(
            primary_genre="玄幻",
            secondary_directions=["东方玄幻"],
            emotional_tones=["史诗厚重"],
            aesthetic_styles=["东方古典"],
            archetypes=self.service.system_archetypes,
        )
        self.assertEqual(len(top3), 3)
        self.assertIn("system-epic-framework", top3)

    def test_wizard_only_allows_derive_from_system_archetype(self) -> None:
        archetypes = self.service.list_system_archetypes()
        target = archetypes[0]["latest_version"]

        # 1. 使用合法 derive 模式创建项目成功
        setup = {
            "title": "系统派生测试书",
            "channel": "男频",
            "platform": "起点",
            "scale": "长篇（300-500万字）",
            "primary_genre": "玄幻",
            "secondary_directions": ["东方玄幻"],
            "emotional_tones": ["爽快燃向"],
            "aesthetic_styles": ["东方古典"],
            "creator": {
                "mode": "derive",
                "parent_version_id": target["id"],
                "parent_subject_hash": target["subject_hash"],
                "display_name": "体系史诗·测试派生",
                "overrides": {"recurring_attention": ["关注主角的功法突破代价"]},
            },
        }

        created = self.service.create_project_with_creator(
            name="系统派生测试书",
            description="男频 · 玄幻",
            metadata={"project_setup": setup},
            creator=setup["creator"],
        )
        self.assertIsNotNone(created["project"]["id"])
        self.assertEqual(created["creator_binding"]["binding_mode"], "derive")

        # 2. 尝试使用 create 模式提交，应当报错
        illegal_setup = dict(setup)
        illegal_setup["creator"] = {
            "mode": "create",
            "display_name": "非法新建作者",
            "signature": target["signature"],
        }
        with self.assertRaises(NovelOSError) as ctx:
            self.service.create_project_with_creator(
                name="非法项目",
                description="desc",
                metadata={},
                creator=illegal_setup["creator"],
            )
        self.assertIn("只支持从系统原型派生", str(ctx.exception.message))


if __name__ == "__main__":
    unittest.main()
