from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from novelos_mcp import NovelOSError, NovelOSService
from agent_test_support import complete_review_run


class PlanningAssetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("规划测试")
        self.scope = self.project["id"]
        self.trace = self.service.start_trace("planning-test", self.project["id"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _candidate(
        self,
        asset_type: str,
        content: str,
        upstream: list[dict[str, Any]] | None = None,
        cross_check_id: str | None = None,
    ) -> dict[str, Any]:
        producers = {
            "direction": "方向智能体",
            "architecture": "架构智能体",
            "strategy": "策略智能体",
            "character_contract": "人物智能体",
            "world_contract": "世界观智能体",
            "story_arc": "故事弧智能体",
            "volume_outline": "卷规划智能体",
            "chapter_plan": "章节规划智能体",
        }
        return self.service.create_planning_candidate(
            self.project["id"],
            asset_type,
            self.scope,
            content,
            upstream or [],
            producers[asset_type],
            cross_check_id=cross_check_id,
        )

    def _lock(self, candidate: dict[str, Any]) -> dict[str, Any]:
        profile = f"planning-{candidate['asset_type'].replace('_', '-')}"
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            profile,
        )
        return self.service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], self.trace["id"]
        )

    def test_candidate_content_is_resource_and_lock_requires_exact_review(self) -> None:
        candidate = self._candidate("direction", "# 故事方向\n\n守城者必须决定是否开门。")

        self.assertEqual("candidate", candidate["status"])
        self.assertEqual([], candidate["upstream_refs"])
        self.assertEqual("# 故事方向\n\n守城者必须决定是否开门。", self.service.get_resource(candidate["resource_ref"].rsplit("/", 1)[-1]))

        wrong_profile = self.service.record_review(
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "approved",
            [],
            "planning-architecture",
        )
        with self.assertRaisesRegex(NovelOSError, "invalid_review_profile"):
            self.service.lock_planning_asset(candidate["id"], wrong_profile["id"], 1, self.trace["id"])

        locked = self._lock(candidate)
        self.assertEqual("locked", locked["status"])
        self.assertEqual(2, locked["version"])

    def test_asset_type_has_unique_producer_and_exact_upstream_types(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "invalid_producer"):
            self.service.create_planning_candidate(
                self.project["id"], "direction", self.scope, "内容", [], "架构智能体"
            )
        with self.assertRaisesRegex(NovelOSError, "invalid_upstream"):
            self._candidate("architecture", "缺少方向", [])

        direction = self._lock(self._candidate("direction", "方向一"))
        architecture = self._candidate(
            "architecture",
            "架构一",
            [{"asset_id": direction["id"], "version": direction["version"]}],
        )
        self.assertEqual("direction", self.service.get_planning_asset(architecture["upstream_refs"][0]["asset_id"])["asset_type"])

    def test_new_upstream_revision_recursively_marks_descendants_stale(self) -> None:
        direction_v1 = self._lock(self._candidate("direction", "方向一"))
        architecture = self._lock(
            self._candidate(
                "architecture",
                "架构一",
                [{"asset_id": direction_v1["id"], "version": direction_v1["version"]}],
            )
        )
        strategy = self._candidate(
            "strategy",
            "战略一",
            [
                {"asset_id": direction_v1["id"], "version": direction_v1["version"]},
                {"asset_id": architecture["id"], "version": architecture["version"]},
            ],
        )

        direction_v2 = self._lock(self._candidate("direction", "方向二"))

        self.assertEqual(2, direction_v2["revision"])
        self.assertEqual("superseded", self.service.get_planning_asset(direction_v1["id"])["status"])
        self.assertEqual("stale", self.service.get_planning_asset(architecture["id"])["status"])
        self.assertEqual("stale", self.service.get_planning_asset(strategy["id"])["status"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            review = self.service.record_review(
                "planning_asset", strategy["id"], strategy["subject_hash"], "approved", [], "planning-strategy"
            )
            self.service.lock_planning_asset(strategy["id"], review["id"], 2, self.trace["id"])

    def test_review_rejects_unregistered_subject_type(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "invalid_review"):
            self.service.record_review("arbitrary", "x", "sha256:" + "a" * 64, "approved", [], "unknown")

    def test_all_eight_asset_types_form_a_lockable_chain(self) -> None:
        direction = self._lock(self._candidate("direction", "方向"))
        architecture = self._lock(
            self._candidate("architecture", "架构", [{"asset_id": direction["id"], "version": 2}])
        )
        strategy = self._lock(
            self._candidate(
                "strategy",
                "战略",
                [
                    {"asset_id": direction["id"], "version": 2},
                    {"asset_id": architecture["id"], "version": 2},
                ],
            )
        )
        shared = [
            {"asset_id": architecture["id"], "version": 2},
            {"asset_id": strategy["id"], "version": 2},
        ]
        characters = self._lock(self._candidate("character_contract", "人物契约", shared))
        world = self._lock(self._candidate("world_contract", "世界契约", shared))
        story_upstream = [
            {"asset_id": strategy["id"], "version": 2},
            {"asset_id": characters["id"], "version": 2},
            {"asset_id": world["id"], "version": 2},
        ]
        with self.assertRaisesRegex(NovelOSError, "cross_check_required"):
            self._candidate("story_arc", "缺少交叉审查", story_upstream)
        cross_check = self.service.prepare_planning_cross_check(
            self.project["id"], characters["id"], world["id"]
        )
        unbound_review = self.service.record_review(
            "planning_cross_check",
            cross_check["id"],
            cross_check["subject_hash"],
            "approved",
            [],
            "planning-character-world-cross-consistency",
        )
        with self.assertRaisesRegex(NovelOSError, "reviewer_run_required"):
            self.service.approve_planning_cross_check(
                cross_check["id"], unbound_review["id"], cross_check["version"], self.trace["id"]
            )
        _, cross_review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_cross_check",
            cross_check["id"],
            cross_check["subject_hash"],
            "planning-character-world-cross-consistency",
            evidence_refs=[characters["resource_ref"], world["resource_ref"]],
        )
        approved_cross_check = self.service.approve_planning_cross_check(
            cross_check["id"], cross_review["id"], cross_check["version"], self.trace["id"]
        )
        story_arc = self._lock(
            self._candidate(
                "story_arc",
                "跨卷故事弧",
                story_upstream,
                approved_cross_check["id"],
            )
        )
        volume = self._lock(
            self._candidate("volume_outline", "卷纲", [{"asset_id": story_arc["id"], "version": 2}])
        )
        chapter = self._lock(
            self._candidate("chapter_plan", "章节执行卡", [{"asset_id": volume["id"], "version": 2}])
        )

        assets = self.service.list_planning_assets(self.project["id"], status="locked")
        self.assertEqual(8, len(assets))
        self.assertEqual("chapter_plan", chapter["asset_type"])


if __name__ == "__main__":
    unittest.main()
