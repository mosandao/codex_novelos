from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSError
from novelos_mcp.projection import ProjectionEngine, sanitize_filename
from novelos_mcp.service import NovelOSService


from agent_test_support import complete_agent_run, complete_review_run

ROLE_IDS = {
    "direction": "direction_agent",
    "architecture": "architecture_agent",
    "strategy": "strategy_agent",
    "character_contract": "character_agent",
    "world_contract": "world_agent",
    "story_arc": "story_arc_agent",
    "volume_outline": "volume_planner",
    "chapter_plan": "chapter_planner",
    "chapter": "writer_agent",
}


class ProjectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "projection_test.db"
        self.service = NovelOSService(self.db_path, catalog_path=Path(__file__).resolve().parents[3] / "catalog" / "skills")

        self.project = self.service.create_project("测试全结构小说", "测试用的完整全结构小说投影")
        self.book = self.service.create_book(self.project["id"], "第一部")
        self.volume = self.service.create_volume(self.book["id"], 1, "第一卷")
        self.trace = self.service.start_trace("trace-projection-test", self.project["id"])

        # 1. 创建并锁定全套 6 大规划资产
        def _lock_asset(asset_type: str, upstreams: list[dict], cross_check_id: str | None = None) -> dict:
            content = f"{asset_type} 规划内容正文"
            p_run = complete_agent_run(self.service, self.trace["id"], ROLE_IDS[asset_type], "planning_candidate", content)
            cand = self.service.create_planning_candidate(
                self.project["id"],
                asset_type,
                self.project["id"],
                content,
                [{"asset_id": u["id"], "version": u["version"]} for u in upstreams],
                producer_run_id=p_run["id"],
                cross_check_id=cross_check_id,
            )
            _, rec = complete_review_run(self.service, self.trace["id"], "planning_asset", cand["id"], cand["subject_hash"], f"planning-{asset_type.replace('_', '-')}")
            return self.service.lock_planning_asset(cand["id"], rec["id"], cand["version"], self.trace["id"])

        direction = _lock_asset("direction", [])
        architecture = _lock_asset("architecture", [direction])
        strategy = _lock_asset("strategy", [direction, architecture])
        char_contract = _lock_asset("character_contract", [architecture, strategy])
        world_contract = _lock_asset("world_contract", [architecture, strategy])

        # Story Arc 需要交叉检查
        cross_check_cand = self.service.prepare_planning_cross_check(
            self.project["id"], char_contract["id"], world_contract["id"]
        )
        _, cross_review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_cross_check",
            cross_check_cand["id"],
            cross_check_cand["subject_hash"],
            "planning-character-world-cross-consistency",
        )
        approved_cross_check = self.service.approve_planning_cross_check(
            cross_check_cand["id"], cross_review["id"], cross_check_cand["version"], self.trace["id"]
        )
        story_arc = _lock_asset("story_arc", [strategy, char_contract, world_contract], cross_check_id=approved_cross_check["id"])

        volume_outline = _lock_asset("volume_outline", [story_arc])
        self.volume_outline = volume_outline

        chapter_plan = _lock_asset("chapter_plan", [volume_outline])
        self.chapter_plan = chapter_plan

        # 3. 创建并接受正文
        chap_content = "寒山绝顶，风雪交加。主角立于试剑石前，拔剑出鞘。"
        writer_run = complete_agent_run(
            self.service,
            self.trace["id"],
            ROLE_IDS["chapter"],
            "chapter_draft_candidate",
            chap_content,
            {"locked_chapter_plan_ref": self.chapter_plan["id"]},
        )
        chap_draft = self.service.create_chapter_draft(
            self.volume["id"],
            1,
            "第一章 试剑石前",
            chap_content,
            metadata={"chapter_plan_ref": self.chapter_plan["id"], "chapter_plan_version": self.chapter_plan["version"]},
            producer_run_id=writer_run["id"],
        )
        _, chap_rec = complete_review_run(self.service, self.trace["id"], "chapter", chap_draft["id"], chap_draft["subject_hash"], "prose-v1")
        self.chapter = self.service.accept_chapter(chap_draft["id"], chap_rec["id"], chap_draft["version"], self.trace["id"])

        # 4. 创建实体与连续性
        char_mut = self.service.prepare_entity_mutation(
            self.project["id"],
            "character",
            {"name": "陆沉", "description": "寒山剑宗弟子", "state": {"location": "寒山"}},
            char_contract["id"],
            char_contract["subject_hash"],
            None,
        )
        _, char_rev = complete_review_run(self.service, self.trace["id"], "entity_mutation", char_mut["id"], char_mut["subject_hash"], "entity-character", evidence_refs=[char_mut["mutation_ref"]])
        self.char = self.service.commit_entity_mutation(char_mut["id"], char_rev["id"], char_mut["version"], self.trace["id"])

        world_mut = self.service.prepare_entity_mutation(
            self.project["id"],
            "world",
            {"name": "寒山剑宗", "description": "宗门所在地与规则边界", "state": {"season": "冬"}},
            world_contract["id"],
            world_contract["subject_hash"],
            None,
        )
        _, world_rev = complete_review_run(self.service, self.trace["id"], "entity_mutation", world_mut["id"], world_mut["subject_hash"], "entity-world", evidence_refs=[world_mut["mutation_ref"]])
        self.world = self.service.commit_entity_mutation(world_mut["id"], world_rev["id"], world_mut["version"], self.trace["id"])

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_sanitize_filename(self) -> None:
        self.assertEqual("test_file", sanitize_filename("test/file"))
        self.assertEqual("hello_world_", sanitize_filename("hello:world?"))
        self.assertEqual("untitled", sanitize_filename(".."))
        self.assertEqual("untitled", sanitize_filename(""))

    def test_full_project_projection_rendering(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))

        target_dir = Path(res["output_directory"])
        self.assertTrue(target_dir.is_dir())
        self.assertTrue((target_dir / "README.md").is_file())
        self.assertTrue((target_dir / "manifest.json").is_file())

        # 校验 规划/ 目录
        self.assertTrue((target_dir / "规划" / "01-故事方向.md").is_file())
        self.assertTrue((target_dir / "规划" / "02-故事架构.md").is_file())

        # 校验 大纲/ 目录
        self.assertTrue((target_dir / "大纲" / "第01卷-卷纲.md").is_file())

        # 校验 正文/ 目录
        chap_file = target_dir / "正文" / "第01卷" / "第001章-第一章 试剑石前.md"
        self.assertTrue(chap_file.is_file())
        self.assertIn("寒山绝顶", chap_file.read_text(encoding="utf-8"))

        # 校验 人物/ & 世界/
        self.assertTrue((target_dir / "人物" / "陆沉.md").is_file())
        self.assertTrue((target_dir / "世界" / "寒山剑宗.md").is_file())

        # 校验 manifest.json
        manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(self.project["id"], manifest["project_id"])
        self.assertEqual(res["authority_snapshot_hash"], manifest["authority_snapshot_hash"])
        self.assertTrue(len(manifest["files"]) >= 10)

    def test_non_authoritative_content_excluded(self) -> None:
        # 创建未锁定的 candidate 规划资产，确保不会进入投影
        cand_run = complete_agent_run(self.service, self.trace["id"], "direction_agent", "planning_candidate", "未锁定的草稿方向")
        cand_draft = self.service.create_planning_candidate(
            self.project["id"],
            "direction",
            self.project["id"],
            "未锁定的草稿方向",
            [],
            producer_run_id=cand_run["id"],
        )
        out_root = Path(self.tmp_dir.name) / "novels"
        self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = out_root / "测试全结构小说"

        dir_content = (target_dir / "规划" / "01-故事方向.md").read_text(encoding="utf-8")
        self.assertNotIn("未锁定的草稿方向", dir_content)
        self.assertIn("direction 规划内容正文", dir_content)

    def test_deterministic_rendering(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res1 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        manifest1 = (Path(res1["output_directory"]) / "manifest.json").read_text(encoding="utf-8")

        res2 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        manifest2 = (Path(res2["output_directory"]) / "manifest.json").read_text(encoding="utf-8")

        self.assertEqual(res1["authority_snapshot_hash"], res2["authority_snapshot_hash"])
        self.assertEqual(manifest1, manifest2)

    def test_rebuild_from_sqlite_without_db_mutation(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res1 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res1["output_directory"])

        # 手动删除投影目录
        shutil.rmtree(target_dir)
        self.assertFalse(target_dir.exists())

        # 重新生成可完整恢复
        res2 = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        self.assertTrue(target_dir.exists())
        self.assertEqual(res1["authority_snapshot_hash"], res2["authority_snapshot_hash"])

    def test_project_id_mismatch_security_rejection(self) -> None:
        out_root = Path(self.tmp_dir.name) / "novels"
        res = self.service.render_project_projection(self.project["id"], output_root=str(out_root))
        target_dir = Path(res["output_directory"])

        # 创建第二个不同 ID 的项目
        proj2 = self.service.create_project("测试全结构小说", "同名但不同ID的项目")

        # 尝试覆盖已属于 proj1 的同名目录，必须抛出拒绝
        with self.assertRaisesRegex(NovelOSError, "拒绝非授权覆盖"):
            self.service.render_project_projection(proj2["id"], output_root=str(out_root))


if __name__ == "__main__":
    unittest.main()
