from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSService, NovelOSError


class CreationSeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("种子测试")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_get_seed_returns_none_when_absent(self) -> None:
        self.assertIsNone(self.service.get_creation_seed(self.project["id"]))

    def test_update_creates_v1_and_gets_active(self) -> None:
        seed = self.service.update_creation_seed(
            self.project["id"],
            protagonist_seed="外卖员觉醒古老血脉",
            world_seed="都市地下有古老势力",
            hook_seed="扮猪吃虎幕后流",
        )
        self.assertEqual(1, seed["version"])
        self.assertEqual(1, seed["is_active"])
        self.assertEqual("外卖员觉醒古老血脉", seed["protagonist_seed"])

        active = self.service.get_creation_seed(self.project["id"])
        self.assertIsNotNone(active)
        self.assertEqual(seed["id"], active["id"])

    def test_update_iterates_version_and_deactivates_old(self) -> None:
        first = self.service.update_creation_seed(self.project["id"], protagonist_seed="v1 主角")
        second = self.service.update_creation_seed(self.project["id"], protagonist_seed="v2 主角改了")

        self.assertEqual(1, first["version"])
        self.assertEqual(2, second["version"])

        history = self.service.list_creation_seeds(self.project["id"])
        self.assertEqual(2, len(history))
        # 倒序：v2 在前
        self.assertEqual(2, history[0]["version"])
        self.assertEqual(1, history[1]["version"])
        # 只有 v2 active
        active_count = sum(1 for s in history if s["is_active"])
        self.assertEqual(1, active_count)
        active = self.service.get_creation_seed(self.project["id"])
        self.assertEqual(2, active["version"])
        self.assertEqual("v2 主角改了", active["protagonist_seed"])

    def test_seed_does_not_trigger_stale(self) -> None:
        """种子更新不应触发任何 planning_assets stale 传播。"""
        trace = self.service.start_trace("seed-stale-test", self.project["id"])
        direction = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "# 方向", [], "方向智能体"
        )
        # 锁定 direction 使其成为可被 stale 的资产
        from agent_test_support import complete_review_run

        _, review = complete_review_run(
            self.service, trace["id"], "planning_asset", direction["id"],
            direction["subject_hash"], "planning-direction",
        )
        locked = self.service.lock_planning_asset(direction["id"], review["id"], direction["version"], trace["id"])
        self.assertEqual("locked", locked["status"])

        # 更新种子
        self.service.update_creation_seed(self.project["id"], protagonist_seed="新主角")

        # direction 应仍是 locked，未被标 stale
        self.assertEqual("locked", self.service.get_planning_asset(direction["id"])["status"])

    def test_seed_isolates_per_project(self) -> None:
        other = self.service.create_project("其他项目")
        self.service.update_creation_seed(self.project["id"], protagonist_seed="A 项目主角")
        self.service.update_creation_seed(other["id"], protagonist_seed="B 项目主角")

        self.assertEqual("A 项目主角", self.service.get_creation_seed(self.project["id"])["protagonist_seed"])
        self.assertEqual("B 项目主角", self.service.get_creation_seed(other["id"])["protagonist_seed"])

    def test_get_seed_rejects_unknown_project(self) -> None:
        with self.assertRaises(NovelOSError):
            self.service.get_creation_seed("project:nonexistent")

    def test_list_seed_empty_when_none(self) -> None:
        self.assertEqual([], self.service.list_creation_seeds(self.project["id"]))


if __name__ == "__main__":
    unittest.main()
