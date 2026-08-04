from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

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

    def _service_with_enforcement(self, *, strict_isolation: bool) -> NovelOSService:
        root = Path(self.temporary.name) / ("strict-config" if strict_isolation else "lenient-config")
        config_dir = root / "config"
        shutil.copytree(Path(__file__).resolve().parents[3] / "config" / "schemas", config_dir / "schemas")
        config = yaml.safe_load((Path(__file__).resolve().parents[3] / "config" / "agents.yaml").read_text(encoding="utf-8"))
        config["runtime"]["enforcement"]["strict_isolation_evidence"] = strict_isolation
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / "agents.yaml"
        config_path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
        return NovelOSService(root / "novelos.db", agent_contract_path=config_path)

    def _missing_evidence_review(self, service: NovelOSService) -> tuple[dict, dict, dict]:
        project = service.create_project("缺失隔离凭据测试")
        trace = service.start_trace("missing-isolation", project["id"])
        bindings = {
            name: f"test:{name}"
            for name in service.agent_contracts.get("direction_agent")["minimum_inputs"]
        }
        producer = service.start_agent_run(trace["id"], "direction_agent", bindings)
        service.finish_agent_run(producer["id"], "completed", "planning_candidate", "方向")
        candidate = service.create_planning_candidate(
            project["id"], "direction", project["id"], "方向", [], producer_run_id=producer["id"]
        )
        reviewer = service.start_agent_run(
            trace["id"],
            "review_agent",
            {
                "immutable_subject_ref": candidate["id"],
                "subject_hash": candidate["subject_hash"],
                "review_profile": "planning-direction",
                "authority_context_refs": candidate["resource_ref"],
            },
        )
        output = {
            "subject_type": "planning_asset",
            "subject_ref": candidate["id"],
            "subject_hash": candidate["subject_hash"],
            "verdict": "approved",
            "findings": [],
            "reviewer_profile": "planning-direction",
            "evidence_refs": [candidate["resource_ref"]],
        }
        service.finish_agent_run(reviewer["id"], "completed", "review_receipt_candidate", output)
        review = service.record_review(
            "planning_asset", candidate["id"], candidate["subject_hash"], "approved", [],
            "planning-direction", [candidate["resource_ref"]], reviewer["id"],
        )
        return candidate, review, trace

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
            self.project["id"], "direction", "base", "既有方向", [], "方向智能体"
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
                "被 主控智能体 改写的内容",
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
        self.assertEqual("方向智能体", candidate["producer_role"])
        self.assertEqual(run["id"], candidate["producer_run_id"])

    def test_planning_candidate_is_validated_and_registered_from_run(self) -> None:
        invalid = self.service.start_agent_run(
            self.trace["id"], "direction_agent", self._bindings("direction_agent")
        )
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            self.service.finish_agent_run(
                invalid["id"],
                "completed",
                "planning_candidate",
                {"content": "不允许的 typed result 外壳"},
            )
        self.assertEqual("running", self.service.get_agent_run(invalid["id"])["status"])
        self.service.finish_agent_run(invalid["id"], "failed", error="输出格式错误")

        run = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "直接登记的故事方向",
        )
        candidate = self.service.create_planning_candidate_from_run(
            self.project["id"],
            "direction",
            self.project["id"],
            [],
            run["id"],
        )
        self.assertEqual(run["id"], candidate["producer_run_id"])
        self.assertEqual("直接登记的故事方向", self.service.get_resource(candidate["resource_ref"].rsplit("/", 1)[-1]))

    def test_change_proposal_must_target_transitive_upstream(self) -> None:
        direction = self.service.create_planning_candidate(
            self.project["id"], "direction", self.project["id"], "上游方向", [], "方向智能体"
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

    def test_review_output_is_validated_and_recorded_from_run(self) -> None:
        producer = complete_agent_run(
            self.service,
            self.trace["id"],
            "direction_agent",
            "planning_candidate",
            "方向",
        )
        candidate = self.service.create_planning_candidate_from_run(
            self.project["id"],
            "direction",
            self.project["id"],
            [],
            producer["id"],
        )
        reviewer = self.service.start_agent_run(
            self.trace["id"],
            "review_agent",
            {
                "immutable_subject_ref": candidate["id"],
                "subject_hash": candidate["subject_hash"],
                "review_profile": "planning-direction",
                "authority_context_refs": [candidate["resource_ref"]],
            },
            isolation_evidence={"source": "test_harness"},
        )
        base_output = {
            "subject_type": "planning_asset",
            "subject_ref": candidate["id"],
            "subject_hash": candidate["subject_hash"],
            "verdict": "approved",
            "findings": [
                {
                    "severity": "note",
                    "code": "direction.coherent",
                    "message": "方向一致",
                    "evidence_refs": [candidate["resource_ref"]],
                }
            ],
            "reviewer_profile": "planning-direction",
            "evidence_refs": [candidate["resource_ref"]],
        }
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            self.service.finish_agent_run(
                reviewer["id"],
                "completed",
                "review_receipt_candidate",
                dict(base_output, reviewer_run_id=reviewer["id"]),
            )
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            self.service.finish_agent_run(
                reviewer["id"],
                "completed",
                "review_receipt_candidate",
                dict(base_output, assessment={"summary": "不允许"}),
            )
        completed = self.service.finish_agent_run(
            reviewer["id"], "completed", "review_receipt_candidate", base_output
        )
        review = self.service.record_review_from_run(completed["id"])
        self.assertEqual(completed["id"], review["reviewer_run_id"])
        self.assertEqual("direction.coherent", review["findings"][0]["code"])

    def test_lock_rejected_without_isolation_evidence(self) -> None:
        lenient_service = self._service_with_enforcement(strict_isolation=False)
        candidate, review, trace = self._missing_evidence_review(lenient_service)
        locked = lenient_service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], trace["id"]
        )
        self.assertEqual("locked", locked["status"])
        warnings = [
            step for step in lenient_service.get_trace(trace["id"])["steps"]
            if step["step_type"] == "isolation.evidence.missing"
        ]
        self.assertEqual({"reviewer", "producer"}, {step["details"]["role"] for step in warnings})
        self.assertTrue(all(step["status"] == "completed" and step["details"]["severity"] == "warning" for step in warnings))

        strict_service = self._service_with_enforcement(strict_isolation=True)
        strict_candidate, strict_review, strict_trace = self._missing_evidence_review(strict_service)
        with self.assertRaisesRegex(NovelOSError, "missing_isolation_evidence"):
            strict_service.lock_planning_asset(
                strict_candidate["id"], strict_review["id"], strict_candidate["version"], strict_trace["id"]
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
