from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

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

    def _service_with_cross_enforcement(self, *, strict: bool) -> NovelOSService:
        root = Path(self.temporary.name) / ("strict-cross" if strict else "lenient-cross")
        config_dir = root / "config"
        shutil.copytree(Path(__file__).resolve().parents[3] / "config" / "schemas", config_dir / "schemas")
        config = yaml.safe_load(
            (Path(__file__).resolve().parents[3] / "config" / "agents.yaml").read_text(encoding="utf-8")
        )
        config["runtime"]["enforcement"]["strict_cross_consistency"] = strict
        config_path = config_dir / "agents.yaml"
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        service = NovelOSService(root / "novelos.db", agent_contract_path=config_path)
        project = service.create_project(f"cross-check-{strict}")
        service._test_project = project
        service._test_trace = service.start_trace("planning-test", project["id"])
        return service

    def _candidate(
        self,
        asset_type: str,
        content: str,
        upstream: list[dict[str, Any]] | None = None,
        cross_check_id: str | None = None,
        *,
        service: NovelOSService | None = None,
        project_id: str | None = None,
        scope_ref: str | None = None,
    ) -> dict[str, Any]:
        service = service or self.service
        project_id = project_id or self.project["id"]
        scope_ref = scope_ref or self.scope
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
        return service.create_planning_candidate(
            project_id,
            asset_type,
            scope_ref,
            content,
            upstream or [],
            producers[asset_type],
            cross_check_id=cross_check_id,
        )

    def _lock(
        self,
        candidate: dict[str, Any],
        *,
        service: NovelOSService | None = None,
        review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = service or self.service
        trace_id = getattr(service, "_test_trace", self.trace)["id"]
        profile = f"planning-{candidate['asset_type'].replace('_', '-')}"
        if review is None:
            _, review = complete_review_run(
                service,
                trace_id,
                "planning_asset",
                candidate["id"],
                candidate["subject_hash"],
                profile,
            )
        return service.lock_planning_asset(candidate["id"], review["id"], candidate["version"], trace_id)

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
        lenient_candidate = self._candidate("story_arc", "缺少交叉审查", story_upstream)
        self.assertEqual("candidate", lenient_candidate["status"])
        lenient_locked = self._lock(lenient_candidate)
        self.assertEqual("locked", lenient_locked["status"])
        self.assertTrue(
            any(
                step["step_type"] == "cross_check.missing"
                and step["status"] == "completed"
                and step["details"]["severity"] == "warning"
                for step in self.service.get_trace(self.trace["id"])["steps"]
            )
        )
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

    def _story_prerequisites(self, service: NovelOSService) -> tuple[dict, dict, dict, dict, dict]:
        project = service._test_project
        direction = self._lock(
            self._candidate("direction", "方向", service=service, project_id=project["id"]),
            service=service,
        )
        architecture = self._lock(
            self._candidate(
                "architecture",
                "架构",
                [{"asset_id": direction["id"], "version": direction["version"]}],
                service=service,
                project_id=project["id"],
            ),
            service=service,
        )
        strategy = self._lock(
            self._candidate(
                "strategy",
                "战略",
                [
                    {"asset_id": direction["id"], "version": direction["version"]},
                    {"asset_id": architecture["id"], "version": architecture["version"]},
                ],
                service=service,
                project_id=project["id"],
            ),
            service=service,
        )
        shared = [
            {"asset_id": architecture["id"], "version": architecture["version"]},
            {"asset_id": strategy["id"], "version": strategy["version"]},
        ]
        characters = self._lock(
            self._candidate("character_contract", "人物", shared, service=service, project_id=project["id"]),
            service=service,
        )
        world = self._lock(
            self._candidate("world_contract", "世界", shared, service=service, project_id=project["id"]),
            service=service,
        )
        return project, strategy, characters, world, shared

    def test_missing_cross_check_enforcement_is_loaded_from_config(self) -> None:
        for strict in (False, True):
            with self.subTest(strict=strict):
                service = self._service_with_cross_enforcement(strict=strict)
                project, strategy, characters, world, _ = self._story_prerequisites(service)
                upstream = [
                    {"asset_id": strategy["id"], "version": strategy["version"]},
                    {"asset_id": characters["id"], "version": characters["version"]},
                    {"asset_id": world["id"], "version": world["version"]},
                ]
                if strict:
                    with self.assertRaisesRegex(NovelOSError, "cross_check_required"):
                        self._candidate("story_arc", "strict 缺少交叉审查", upstream, service=service, project_id=project["id"])
                else:
                    candidate = self._candidate(
                        "story_arc", "lenient 缺少交叉审查", upstream, service=service, project_id=project["id"]
                    )
                    locked = self._lock(candidate, service=service)
                    self.assertEqual("locked", locked["status"])
                    self.assertTrue(
                        any(
                            step["step_type"] == "cross_check.missing"
                            and step["details"]["severity"] == "warning"
                            for step in service.get_trace(service._test_trace["id"])["steps"]
                        )
                    )

    def test_invalid_mismatched_and_stale_cross_checks_are_rejected_in_both_modes(self) -> None:
        for strict in (False, True):
            with self.subTest(strict=strict):
                service = self._service_with_cross_enforcement(strict=strict)
                project, strategy, characters, world, shared = self._story_prerequisites(service)
                check = service.prepare_planning_cross_check(project["id"], characters["id"], world["id"])
                base_upstream = [
                    {"asset_id": strategy["id"], "version": strategy["version"]},
                    {"asset_id": characters["id"], "version": characters["version"]},
                    {"asset_id": world["id"], "version": world["version"]},
                ]
                with self.assertRaisesRegex(NovelOSError, "cross_check_required"):
                    self._candidate(
                        "story_arc", "pending cross-check", base_upstream,
                        service=service, project_id=project["id"], cross_check_id=check["id"],
                    )
                _, review = complete_review_run(
                    service,
                    service._test_trace["id"],
                    "planning_cross_check",
                    check["id"],
                    check["subject_hash"],
                    "planning-character-world-cross-consistency",
                    evidence_refs=[characters["resource_ref"], world["resource_ref"]],
                )
                approved = service.approve_planning_cross_check(
                    check["id"], review["id"], check["version"], service._test_trace["id"]
                )

                alternate = self._lock(
                    self._candidate(
                        "character_contract", "另一人物", shared,
                        service=service, project_id=project["id"], scope_ref="alternate-character",
                    ),
                    service=service,
                )
                mismatched_upstream = [
                    {"asset_id": strategy["id"], "version": strategy["version"]},
                    {"asset_id": alternate["id"], "version": alternate["version"]},
                    {"asset_id": world["id"], "version": world["version"]},
                ]
                with self.assertRaisesRegex(NovelOSError, "cross_check_mismatch"):
                    self._candidate(
                        "story_arc", "mismatched cross-check", mismatched_upstream,
                        service=service, project_id=project["id"], cross_check_id=approved["id"],
                    )

                candidate = self._candidate(
                    "story_arc", "will become stale", base_upstream,
                    service=service, project_id=project["id"], cross_check_id=approved["id"],
                )
                newer_characters = self._lock(
                    self._candidate(
                        "character_contract", "新版人物", shared,
                        service=service, project_id=project["id"],
                    ),
                    service=service,
                )
                stale_upstream = [
                    {"asset_id": strategy["id"], "version": strategy["version"]},
                    {"asset_id": newer_characters["id"], "version": newer_characters["version"]},
                    {"asset_id": world["id"], "version": world["version"]},
                ]
                with self.assertRaisesRegex(NovelOSError, "stale_cross_check"):
                    self._candidate(
                        "story_arc", "stale cross-check", stale_upstream,
                        service=service, project_id=project["id"], cross_check_id=approved["id"],
                    )
                _, candidate_review = complete_review_run(
                    service,
                    service._test_trace["id"],
                    "planning_asset",
                    candidate["id"],
                    candidate["subject_hash"],
                    "planning-story-arc",
                )
                stale_candidate = service.get_planning_asset(candidate["id"])
                self.assertEqual("stale", stale_candidate["status"])
                with self.assertRaisesRegex(NovelOSError, "invalid_state"):
                    self._lock(stale_candidate, service=service, review=candidate_review)

    def test_bound_cross_check_is_revalidated_at_lock(self) -> None:
        service = self._service_with_cross_enforcement(strict=False)
        project, strategy, characters, world, _ = self._story_prerequisites(service)
        check = service.prepare_planning_cross_check(project["id"], characters["id"], world["id"])
        _, check_review = complete_review_run(
            service,
            service._test_trace["id"],
            "planning_cross_check",
            check["id"],
            check["subject_hash"],
            "planning-character-world-cross-consistency",
        )
        approved = service.approve_planning_cross_check(
            check["id"], check_review["id"], check["version"], service._test_trace["id"]
        )
        upstream = [
            {"asset_id": strategy["id"], "version": strategy["version"]},
            {"asset_id": characters["id"], "version": characters["version"]},
            {"asset_id": world["id"], "version": world["version"]},
        ]
        candidate = self._candidate(
            "story_arc", "锁定前交叉审查失效", upstream,
            service=service, project_id=project["id"], cross_check_id=approved["id"],
        )
        _, candidate_review = complete_review_run(
            service,
            service._test_trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "planning-story-arc",
        )
        with service.database.transaction() as connection:
            connection.execute(
                "UPDATE planning_cross_checks SET status='pending' WHERE id=?",
                (approved["id"],),
            )
        with self.assertRaisesRegex(NovelOSError, "cross_check_required"):
            self._lock(candidate, service=service, review=candidate_review)
        self.assertEqual("candidate", service.get_planning_asset(candidate["id"])["status"])


class DecisionPointAndRevisionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("决策点测试")
        self.scope = self.project["id"]
        self.trace = self.service.start_trace("decision-test", self.project["id"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _candidate(self, asset_type: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        producers = {
            "direction": "方向智能体",
            "strategy": "策略智能体",
            "character_contract": "人物智能体",
        }
        return self.service.create_planning_candidate(
            self.project["id"],
            asset_type,
            self.scope,
            content,
            [],
            producers[asset_type],
            metadata=metadata,
        )

    def test_extract_decision_points_returns_metadata_field(self) -> None:
        decision_points = [
            {
                "question": "主角觉醒节奏",
                "options": [
                    {"label": "A. 快爽", "detail": "第3章觉醒", "tradeoff": "中段需续"},
                    {"label": "B. 成长", "detail": "缓慢觉醒", "tradeoff": "开局不抓人"},
                ],
                "source_excerpt": "觉醒阶段...",
            }
        ]
        candidate = self._candidate("direction", "# 方向\n觉醒阶段...", metadata={"decision_points": decision_points})
        result = self.service.extract_decision_points(candidate["id"])
        self.assertEqual(candidate["id"], result["asset_id"])
        self.assertEqual(decision_points, result["decision_points"])

    def test_extract_decision_points_returns_empty_when_missing(self) -> None:
        candidate = self._candidate("direction", "# 方向")
        result = self.service.extract_decision_points(candidate["id"])
        self.assertEqual([], result["decision_points"])

    def test_extract_decision_points_rejects_non_candidate(self) -> None:
        candidate = self._candidate("direction", "# 方向")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "planning-direction",
        )
        self.service.lock_planning_asset(candidate["id"], review["id"], candidate["version"], self.trace["id"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.extract_decision_points(candidate["id"])

    def test_extract_decision_points_rejects_non_list(self) -> None:
        candidate = self._candidate("direction", "# 方向", metadata={"decision_points": "不是数组"})
        with self.assertRaisesRegex(NovelOSError, "invalid_candidate"):
            self.service.extract_decision_points(candidate["id"])

    def test_create_revision_candidate_supersedes_old(self) -> None:
        old = self._candidate("direction", "# 方向一", metadata={"decision_points": []})
        revision = self.service.create_revision_candidate(
            self.project["id"],
            "direction",
            self.scope,
            "# 方向二（融合用户选择）",
            [],
            "方向智能体",
            old["id"],
        )
        self.assertEqual("candidate", revision["status"])
        self.assertEqual("superseded", self.service.get_planning_asset(old["id"])["status"])

    def test_create_revision_candidate_rejects_locked_old(self) -> None:
        old = self._candidate("direction", "# 方向一")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            old["id"],
            old["subject_hash"],
            "planning-direction",
        )
        self.service.lock_planning_asset(old["id"], review["id"], old["version"], self.trace["id"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.create_revision_candidate(
                self.project["id"],
                "direction",
                self.scope,
                "# 方向二",
                [],
                "方向智能体",
                old["id"],
            )

    def test_create_revision_candidate_rejects_asset_type_mismatch(self) -> None:
        old = self._candidate("direction", "# 方向一")
        with self.assertRaisesRegex(NovelOSError, "invalid_argument"):
            self.service.create_revision_candidate(
                self.project["id"],
                "strategy",
                self.scope,
                "# 战略（错误类型）",
                [],
                "策略智能体",
                old["id"],
            )

    def test_create_revision_candidate_rejects_wrong_project(self) -> None:
        old = self._candidate("direction", "# 方向一")
        other = self.service.create_project("其他项目")
        with self.assertRaisesRegex(NovelOSError, "invalid_argument"):
            self.service.create_revision_candidate(
                other["id"],
                "direction",
                self.scope,
                "# 方向二",
                [],
                "方向智能体",
                old["id"],
            )


if __name__ == "__main__":
    unittest.main()
