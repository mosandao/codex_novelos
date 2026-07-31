from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSError, NovelOSService
from novelos_mcp.hashing import content_hash

from agent_test_support import complete_agent_run, complete_review_run


class AgentWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("Agent 工作流测试")
        self.trace = self.service.start_trace("agent-workflow", self.project["id"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _bindings(self, role_id: str) -> dict[str, str]:
        return {
            name: f"test:{name}"
            for name in self.service.agent_contracts.get(role_id)["minimum_inputs"]
        }

    def test_simple_task_finishes_without_spawning_agent(self) -> None:
        self.assertEqual(self.project["id"], self.service.get_project(self.project["id"])["id"])
        finished = self.service.finish_trace(self.trace["id"], "completed")
        self.assertEqual("completed", finished["status"])
        self.assertEqual([], self.service.get_trace(self.trace["id"])["agent_runs"])

    def test_active_run_blocks_trace_finish_and_failure_rejects_partial_output(self) -> None:
        run = self.service.start_agent_run(
            self.trace["id"], "writer_agent", self._bindings("writer_agent")
        )
        with self.assertRaisesRegex(NovelOSError, "active_agent_runs"):
            self.service.finish_trace(self.trace["id"], "completed")
        with self.assertRaisesRegex(NovelOSError, "invalid_agent_result"):
            self.service.finish_agent_run(
                run["id"], "failed", "chapter_draft_candidate", "部分正文", error="模型失败"
            )
        self.assertEqual("running", self.service.get_agent_run(run["id"])["status"])
        failed = self.service.finish_agent_run(run["id"], "failed", error="模型失败")
        self.assertEqual("failed", failed["status"])
        self.assertIsNone(failed["output_ref"])
        self.service.finish_trace(self.trace["id"], "failed")
        steps = self.service.get_trace(self.trace["id"])["steps"]
        self.assertEqual(["agent.spawn", "agent.destroy"], [step["step_type"] for step in steps])

    def test_timed_out_run_cannot_create_authority_candidate(self) -> None:
        run = self.service.start_agent_run(
            self.trace["id"], "direction_agent", self._bindings("direction_agent")
        )
        timed_out = self.service.finish_agent_run(run["id"], "timed_out", error="超过 900 秒")
        self.assertEqual("timed_out", timed_out["status"])
        with self.assertRaisesRegex(NovelOSError, "invalid_producer_run"):
            self.service.create_planning_candidate(
                self.project["id"],
                "direction",
                self.project["id"],
                "不应写入",
                [],
                producer_run_id=run["id"],
            )
        self.assertEqual([], self.service.list_planning_assets(self.project["id"]))

    def test_character_and_world_runs_can_coexist_with_isolated_contexts(self) -> None:
        character = self.service.start_agent_run(
            self.trace["id"], "character_agent", self._bindings("character_agent")
        )
        world = self.service.start_agent_run(
            self.trace["id"], "world_agent", self._bindings("world_agent")
        )
        self.assertEqual({"running"}, {character["status"], world["status"]})
        self.assertNotEqual(character["context_id"], world["context_id"])
        self.service.finish_agent_run(
            character["id"], "completed", "planning_candidate", "人物契约候选"
        )
        self.service.finish_agent_run(
            world["id"], "completed", "planning_candidate", "世界契约候选"
        )
        self.assertEqual(
            ["completed", "completed"],
            [run["status"] for run in self.service.list_agent_runs(self.trace["id"])],
        )

    def test_context_builder_requires_explicit_complexity_evidence(self) -> None:
        bindings = self._bindings("context_builder")
        bindings["complexity_reasons"] = ["recent_single_thread"]
        with self.assertRaisesRegex(NovelOSError, "spawn_condition_not_met"):
            self.service.start_agent_run(self.trace["id"], "context_builder", bindings)
        bindings["complexity_reasons"] = ["cross_volume", "conflicting_facts"]
        run = self.service.start_agent_run(self.trace["id"], "context_builder", bindings)
        completed = self.service.finish_agent_run(
            run["id"], "completed", "context_package", {"resource_refs": ["novelos://resource/context"]}
        )
        self.assertEqual("completed", completed["status"])

    def test_planning_run_owns_exact_asset_and_output(self) -> None:
        base = self.service.create_planning_candidate(
            self.project["id"], "direction", "base", "既有方向", [], "Direction Agent"
        )
        _, base_review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            base["id"],
            base["subject_hash"],
            "planning-direction",
        )
        base = self.service.lock_planning_asset(
            base["id"], base_review["id"], base["version"], self.trace["id"]
        )
        run = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "故事方向候选",
        )
        with self.assertRaisesRegex(NovelOSError, "invalid_producer_run"):
            self.service.create_planning_candidate(
                self.project["id"],
                "architecture",
                self.project["id"],
                "故事方向候选",
                [{"asset_id": base["id"], "version": base["version"]}],
                producer_run_id=run["id"],
            )
        with self.assertRaisesRegex(NovelOSError, "hash_mismatch"):
            self.service.create_planning_candidate(
                self.project["id"],
                "direction",
                self.project["id"],
                "被 Main Agent 改写的内容",
                [],
                producer_run_id=run["id"],
            )
        candidate = self.service.create_planning_candidate(
            self.project["id"],
            "direction",
            self.project["id"],
            "故事方向候选",
            [],
            producer_run_id=run["id"],
        )
        self.assertEqual("Direction Agent", candidate["producer_role"])
        self.assertEqual(run["id"], candidate["producer_run_id"])

    def test_change_proposal_must_target_transitive_upstream(self) -> None:
        direction = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "上游方向", [], "Direction Agent"
        )
        _, direction_review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            direction["id"],
            direction["subject_hash"],
            "planning-direction",
        )
        direction = self.service.lock_planning_asset(
            direction["id"], direction_review["id"], direction["version"], self.trace["id"]
        )
        valid = {
            "target_asset_type": "direction",
            "target_asset_ref": direction["id"],
            "target_asset_version": direction["version"],
            "target_subject_hash": direction["subject_hash"],
            "reason": "架构约束无法支撑当前承诺",
            "evidence_refs": ["novelos://resource/evidence"],
            "affected_asset_types": ["architecture", "strategy"],
        }
        run = self.service.start_agent_run(
            self.trace["id"], "architecture_agent", self._bindings("architecture_agent")
        )
        completed = self.service.finish_agent_run(
            run["id"], "completed", "planning_candidate", "架构候选", [valid]
        )
        self.assertEqual("completed", completed["status"])

        stale_run = self.service.start_agent_run(
            self.trace["id"], "architecture_agent", self._bindings("architecture_agent")
        )
        stale = dict(valid, target_asset_version=direction["version"] - 1)
        with self.assertRaisesRegex(NovelOSError, "invalid_change_proposal"):
            self.service.finish_agent_run(
                stale_run["id"], "completed", "planning_candidate", "架构候选", [stale]
            )
        self.service.finish_agent_run(stale_run["id"], "failed", error="上游版本已变化")

        invalid_run = self.service.start_agent_run(
            self.trace["id"], "architecture_agent", self._bindings("architecture_agent")
        )
        invalid = dict(valid, target_asset_type="chapter_plan")
        with self.assertRaisesRegex(NovelOSError, "invalid_change_proposal"):
            self.service.finish_agent_run(
                invalid_run["id"], "completed", "planning_candidate", "架构候选", [invalid]
            )
        self.assertEqual("running", self.service.get_agent_run(invalid_run["id"])["status"])
        self.service.finish_agent_run(invalid_run["id"], "failed", error="越权提案已拒绝")

    def test_review_receipt_is_bound_to_reviewer_run_output(self) -> None:
        producer = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "方向",
        )
        candidate = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "方向", [], producer_run_id=producer["id"]
        )
        with self.assertRaisesRegex(NovelOSError, "invalid_reviewer_run"):
            self.service.record_review(
                "planning_asset",
                candidate["id"],
                candidate["subject_hash"],
                "approved",
                [],
                "planning-direction",
                [],
                producer["id"],
            )
        reviewer_run, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "planning-direction",
            evidence_refs=[candidate["resource_ref"]],
        )
        self.assertEqual(reviewer_run["id"], review["reviewer_run_id"])
        locked = self.service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], self.trace["id"]
        )
        self.assertEqual("locked", locked["status"])

    def test_lock_rejected_without_isolation_evidence(self) -> None:
        # 缺隔离凭据的 self-produced run 必须被 lock 拒绝（防御性校验）。
        # 复刻 Main Agent 自审的真实路径：直接 start_agent_run 不传 isolation_evidence。
        role = self.service.agent_contracts.get("direction_agent")
        producer_run = self.service.start_agent_run(
            self.trace["id"],
            "direction_agent",
            {name: f"test:{name}" for name in role["minimum_inputs"]},
        )
        self.service.finish_agent_run(producer_run["id"], "completed", "planning_candidate", "方向")
        candidate = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "方向", [], producer_run_id=producer_run["id"]
        )
        review_role = self.service.agent_contracts.get("review_agent")
        reviewer_run = self.service.start_agent_run(
            self.trace["id"],
            "review_agent",
            {
                "immutable_subject_ref": candidate["id"],
                "subject_hash": candidate["subject_hash"],
                "review_profile": "planning-direction",
                "authority_context_refs": candidate["resource_ref"],
            },
        )
        review_output = {
            "subject_type": "planning_asset",
            "subject_ref": candidate["id"],
            "subject_hash": candidate["subject_hash"],
            "verdict": "approved",
            "findings": [],
            "reviewer_profile": "planning-direction",
            "evidence_refs": [candidate["resource_ref"]],
        }
        self.service.finish_agent_run(
            reviewer_run["id"], "completed", "review_receipt_candidate", review_output
        )
        review = self.service.record_review(
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "approved",
            [],
            "planning-direction",
            [candidate["resource_ref"]],
            reviewer_run["id"],
        )
        with self.assertRaisesRegex(NovelOSError, "missing_isolation_evidence"):
            self.service.lock_planning_asset(
                candidate["id"], review["id"], candidate["version"], self.trace["id"]
            )

    def test_agent_quality_subject_has_a_real_isolated_review_receipt_path(self) -> None:
        producer = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "临时 Agent 匿名输出",
        )
        baseline = self.service.create_resource(self.trace["id"], "Main + Skill 匿名输出")
        evidence_refs = [baseline["resource_ref"], producer["output_ref"]]
        subject_content = {
            "schema_version": 1,
            "case_id": "writer-gate-seal-v1",
            "input_hash": "sha256:" + "1" * 64,
            "outputs": [
                {
                    "label": "A",
                    "output_ref": evidence_refs[0],
                    "output_hash": baseline["content_hash"],
                    "media_type": "text/markdown",
                },
                {
                    "label": "B",
                    "output_ref": evidence_refs[1],
                    "output_hash": content_hash("临时 Agent 匿名输出"),
                    "media_type": "text/markdown",
                },
            ],
            "review_profile": "agent-quality-blind-comparison",
        }
        subject = self.service.prepare_review_subject(
            self.trace["id"],
            "agent_quality_evaluation",
            subject_content,
            "agent-quality-blind-comparison",
            evidence_refs,
            [producer["id"]],
        )
        self.assertEqual(evidence_refs, subject["evidence_refs"])
        self.assertEqual(subject["id"], self.service.get_review_subject(subject["id"])["id"])

        assessment = {
            "schema_version": 1,
            "case_id": "writer-gate-seal-v1",
            "scores": {"A": {"canon_accuracy": 4}, "B": {"canon_accuracy": 3}},
            "winner": "A",
            "blocking": False,
            "regression_labels": [],
        }
        reviewer_run, review = complete_review_run(
            self.service,
            self.trace["id"],
            "review_subject",
            subject["id"],
            subject["subject_hash"],
            "agent-quality-blind-comparison",
            evidence_refs=evidence_refs,
            assessment=assessment,
        )
        self.assertEqual(reviewer_run["id"], review["reviewer_run_id"])
        self.assertEqual(subject["subject_hash"], review["subject_hash"])
        self.assertEqual(
            assessment,
            json.loads(self.service.get_resource(review["assessment_ref"].rsplit("/", 1)[-1])),
        )

        with self.assertRaisesRegex(NovelOSError, "字段不完整"):
            self.service.prepare_review_subject(
                self.trace["id"],
                "agent_quality_evaluation",
                dict(subject_content, execution_mode="isolated_writer_agent"),
                "agent-quality-blind-comparison",
                evidence_refs,
                [producer["id"]],
            )

        context_output = self.service.create_resource(self.trace["id"], "上下文包")
        other_subject = self.service.prepare_review_subject(
            self.trace["id"],
            "agent_quality_evaluation",
            {
                "schema_version": 1,
                "case_id": "context-gate-seal-v1",
                "input_hash": "sha256:" + "4" * 64,
                "outputs": [
                    {
                        "label": "A",
                        "output_ref": context_output["resource_ref"],
                        "output_hash": context_output["content_hash"],
                        "media_type": "text/markdown",
                    }
                ],
                "review_profile": "agent-quality-blind-comparison",
            },
            "agent-quality-blind-comparison",
            [context_output["resource_ref"]],
            [],
        )
        other_trace = self.service.start_trace("cross-trace-quality-review", self.project["id"])
        with self.assertRaisesRegex(NovelOSError, "trace_review_mismatch"):
            complete_review_run(
                self.service,
                other_trace["id"],
                "review_subject",
                other_subject["id"],
                other_subject["subject_hash"],
                "agent-quality-blind-comparison",
                evidence_refs=[context_output["resource_ref"]],
                assessment={"schema_version": 1, "case_id": "context-gate-seal-v1"},
            )

    def test_authority_commit_rejects_reviewer_from_another_trace_atomically(self) -> None:
        producer = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "跨 Trace 方向",
        )
        candidate = self.service.create_planning_candidate(
            self.project["id"],
            "direction",
            self.project["id"],
            "跨 Trace 方向",
            [],
            producer_run_id=producer["id"],
        )
        other_trace = self.service.start_trace("isolated-review", self.project["id"])
        _, review = complete_review_run(
            self.service,
            other_trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            "planning-direction",
        )
        with self.assertRaisesRegex(NovelOSError, "trace_review_mismatch"):
            self.service.lock_planning_asset(
                candidate["id"], review["id"], candidate["version"], self.trace["id"]
            )
        self.assertEqual("candidate", self.service.get_planning_asset(candidate["id"])["status"])
        self.assertEqual(0, self.service.audit_authority_trace(self.project["id"])["commit_count"])

    def test_chapter_plan_requires_writer_but_short_unplanned_draft_does_not(self) -> None:
        book = self.service.create_book(self.project["id"], "测试书")
        volume = self.service.create_volume(book["id"], 1, "测试卷")
        with self.assertRaisesRegex(NovelOSError, "producer_run_required"):
            self.service.create_chapter_draft(
                volume["id"], 1, "完整章", "正文", metadata={"chapter_plan_ref": "planning:chapter:1"}
            )
        short = self.service.create_chapter_draft(volume["id"], 1, "局部草稿", "一句修改")
        self.assertIsNone(short["producer_run_id"])


if __name__ == "__main__":
    unittest.main()
