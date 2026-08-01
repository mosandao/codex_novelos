from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novelos_mcp import NovelOSError, NovelOSService

from agent_test_support import complete_agent_run, complete_review_run


def signature(label: str) -> dict[str, object]:
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


def book_soul(label: str = "权力") -> dict[str, object]:
    return {
        "schema_version": 1,
        "unresolved_claims": [f"{label}能否在不腐化人的情况下被使用"],
        "central_contradiction": "个人自由与共同体责任都不可放弃，但无法同时完整满足",
        "costly_commitments": ["宁愿让主角失败，也不让无辜者替其承担代价"],
        "protected_dignity": ["不羞辱失败者，也不免除其行为后果"],
        "forbidden_resolutions": ["制度问题不得归罪于一个坏人后自动消失"],
        "recurring_tests": ["每次以大局为名的牺牲都检查决策者是否承担同等风险"],
        "narrative_mercy": "理解人物为何作恶，但不替其取消后果",
        "narrative_cruelty": "让人物亲手承受其信念的反面结果",
        "deliberate_silences": ["不由叙述者宣布人物是否获得原谅"],
    }


class CreatorProfileTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _lock_asset(
        self,
        project: dict[str, object],
        trace: dict[str, object],
        asset_type: str,
        upstreams: list[dict[str, object]],
        *,
        metadata: dict[str, object] | None = None,
        cross_check_id: str | None = None,
    ) -> dict[str, object]:
        role_ids = {
            "architecture": "architecture_agent",
            "strategy": "strategy_agent",
            "character_contract": "character_agent",
            "world_contract": "world_agent",
            "story_arc": "story_arc_agent",
            "volume_outline": "volume_planner",
            "chapter_plan": "chapter_planner",
        }
        content = f"{asset_type} 候选"
        run = complete_agent_run(
            self.service,
            str(trace["id"]),
            role_ids[asset_type],
            "planning_candidate",
            content,
        )
        candidate = self.service.create_planning_candidate(
            str(project["id"]),
            asset_type,
            str(project["id"]),
            content,
            [{"asset_id": item["id"], "version": item["version"]} for item in upstreams],
            metadata=metadata,
            producer_run_id=run["id"],
            cross_check_id=cross_check_id,
        )
        _, review = complete_review_run(
            self.service,
            str(trace["id"]),
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            f"planning-{asset_type.replace('_', '-')}",
        )
        return self.service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], str(trace["id"])
        )

    def test_signature_and_book_soul_schemas_fail_closed(self) -> None:
        valid = self.service.creative_contracts.validate_signature(signature("制度"))
        self.assertEqual(1, valid["schema_version"])
        with self.assertRaisesRegex(NovelOSError, "作者签名不符合 Schema"):
            self.service.creative_contracts.validate_signature({"schema_version": 1})
        invalid = signature("制度") | {"author_age": 35}
        with self.assertRaisesRegex(NovelOSError, "作者签名不符合 Schema"):
            self.service.creative_contracts.validate_signature(invalid)
        with self.assertRaisesRegex(NovelOSError, "不得保存具体作者模仿指令"):
            self.service.creative_contracts.validate_signature(
                signature("制度") | {"expression_preferences": ["模仿某位具体作者的句法"]}
            )
        self.assertEqual(
            signature("制度")["negative_constraints"],
            self.service.creative_contracts.validate_signature(signature("制度"))["negative_constraints"],
        )
        with self.assertRaisesRegex(NovelOSError, "书级创作灵魂不符合 Schema"):
            self.service.creative_contracts.validate_book_soul(book_soul() | {"central_contradiction": ""})
        chapter_contract = {
            "soul_pressure": {
                "foreground": False,
                "direction_ref": "novelos://planning-constraint/test/1/sha256:test",
                "manifestation": "纯过渡场景，承接既有关系压力而不前景化母题",
            },
            "moral_residue": {
                "kind": "carried",
                "consequence": "没有新增道德后果",
                "unresolved_aftereffect": "前章的不信任仍未解除",
            },
        }
        self.assertEqual(
            chapter_contract,
            self.service.creative_contracts.validate_chapter_soul(chapter_contract),
        )
        with self.assertRaisesRegex(NovelOSError, "章节思想压力契约不符合 Schema"):
            self.service.creative_contracts.validate_chapter_soul(
                chapter_contract | {"moral_residue": {"kind": "none"}}
            )

    def test_reused_profile_versions_do_not_drift_after_revision(self) -> None:
        created = self.service.create_creator_profile("克制现实主义", signature("制度"))
        first = created["version"]
        creator_request = {
            "mode": "reuse",
            "profile_version_id": first["id"],
            "subject_hash": first["subject_hash"],
        }
        project_a = self.service.create_project_with_creator("甲", "", {}, creator_request)
        project_b = self.service.create_project_with_creator("乙", "", {}, creator_request)
        revised_signature = signature("家庭")
        revised = self.service.revise_creator_profile(
            created["profile"]["id"],
            created["profile"]["version"],
            revised_signature,
        )
        self.assertEqual(2, revised["version"]["revision"])
        history = self.service.get_creator_profile(created["profile"]["id"])["versions"]
        self.assertEqual([1, 2], [item["revision"] for item in history])
        self.assertEqual([first["subject_hash"], revised["version"]["subject_hash"]], [item["subject_hash"] for item in history])
        for project in (project_a, project_b):
            binding = self.service.get_project_creator_binding(project["project"]["id"])
            self.assertEqual(first["id"], binding["profile_version_id"])
            self.assertEqual(first["subject_hash"], binding["subject_hash"])
            self.assertEqual(1, binding["profile_revision"])

    def test_same_signature_can_form_distinct_project_book_souls(self) -> None:
        profile = self.service.create_creator_profile("同一作者", signature("制度"))["version"]
        creator_request = {
            "mode": "reuse",
            "profile_version_id": profile["id"],
            "subject_hash": profile["subject_hash"],
        }
        candidates = []
        for title, label in (("甲书", "权力"), ("乙书", "亲情")):
            created = self.service.create_project_with_creator(title, "", {}, creator_request)
            project = created["project"]
            binding = created["creator_binding"]
            trace = self.service.start_trace(f"direction-{title}", project["id"])
            content = f"{title}的独有故事方向"
            run = complete_agent_run(
                self.service,
                trace["id"],
                "direction_agent",
                "planning_candidate",
                content,
                {"creator_signature_ref": binding["constraint_ref"]},
            )
            candidates.append(
                self.service.create_planning_candidate(
                    project["id"],
                    "direction",
                    project["id"],
                    content,
                    [],
                    metadata={
                        "creator_signature_ref": binding["constraint_ref"],
                        "book_soul": book_soul(label),
                    },
                    producer_run_id=run["id"],
                )
            )
        self.assertNotEqual(candidates[0]["subject_hash"], candidates[1]["subject_hash"])
        self.assertNotEqual(
            candidates[0]["metadata"]["book_soul"]["unresolved_claims"],
            candidates[1]["metadata"]["book_soul"]["unresolved_claims"],
        )

    def test_create_derive_and_atomic_failure(self) -> None:
        base_project = self.service.create_project_with_creator(
            "原作者项目",
            "",
            {},
            {"mode": "create", "display_name": "原作者", "signature": signature("城市")},
        )
        base = base_project["creator_binding"]["profile_version"]
        derived = self.service.create_project_with_creator(
            "派生作者项目",
            "",
            {},
            {
                "mode": "derive",
                "parent_version_id": base["id"],
                "parent_subject_hash": base["subject_hash"],
                "display_name": "冷峻分支",
                "overrides": {"expression_preferences": ["短句、低议论、保留事实空白"]},
            },
        )
        derived_version = derived["creator_binding"]["profile_version"]
        self.assertEqual(base["id"], derived_version["parent_version_id"])
        self.assertEqual(
            {"expression_preferences": ["短句、低议论、保留事实空白"]},
            derived_version["derivation"],
        )
        counts_before = (len(self.service.list_projects()), len(self.service.list_creator_profiles()))
        with self.assertRaisesRegex(NovelOSError, "Hash"):
            self.service.create_project_with_creator(
                "不应创建",
                "",
                {},
                {
                    "mode": "reuse",
                    "profile_version_id": base["id"],
                    "subject_hash": "sha256:" + "0" * 64,
                },
            )
        self.assertEqual(counts_before, (len(self.service.list_projects()), len(self.service.list_creator_profiles())))

    def test_archived_profile_remains_readable_but_cannot_be_reused(self) -> None:
        created = self.service.create_creator_profile("待归档", signature("旧城"))
        archived = self.service.archive_creator_profile(
            created["profile"]["id"], created["profile"]["version"]
        )
        self.assertEqual("archived", archived["status"])
        self.assertEqual(created["version"]["subject_hash"], self.service.get_creator_profile_version(created["version"]["id"])["subject_hash"])
        with self.assertRaisesRegex(NovelOSError, "归档"):
            self.service.create_project_with_creator(
                "拒绝归档作者",
                "",
                {},
                {
                    "mode": "reuse",
                    "profile_version_id": created["version"]["id"],
                    "subject_hash": created["version"]["subject_hash"],
                },
            )

    def test_project_deletion_does_not_delete_reusable_profile_history(self) -> None:
        created = self.service.create_creator_profile("共享作者", signature("社区"))
        project_result = self.service.create_project_with_creator(
            "可删除项目",
            "",
            {},
            {
                "mode": "reuse",
                "profile_version_id": created["version"]["id"],
                "subject_hash": created["version"]["subject_hash"],
            },
        )
        project = project_result["project"]
        deleted = self.service.delete_project(
            project["id"],
            project["version"],
            output_root=str(Path(self.temporary.name) / "novels"),
        )
        self.assertEqual(project["id"], deleted["id"])
        self.assertEqual(
            created["version"]["subject_hash"],
            self.service.get_creator_profile_version(created["version"]["id"])["subject_hash"],
        )

    def _bound_project_with_locked_direction(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        profile = self.service.create_creator_profile("作者", signature("宗门"))
        project_result = self.service.create_project_with_creator(
            "绑定项目",
            "",
            {},
            {
                "mode": "reuse",
                "profile_version_id": profile["version"]["id"],
                "subject_hash": profile["version"]["subject_hash"],
            },
        )
        project = project_result["project"]
        binding = project_result["creator_binding"]
        trace = self.service.start_trace("creator-direction", project["id"])
        content = "方向候选与 book_soul 正文"
        run = complete_agent_run(
            self.service,
            trace["id"],
            "direction_agent",
            "planning_candidate",
            content,
            {"creator_signature_ref": binding["constraint_ref"]},
        )
        direction = self.service.create_planning_candidate(
            project["id"],
            "direction",
            project["id"],
            content,
            [],
            metadata={
                "creator_signature_ref": binding["constraint_ref"],
                "book_soul": book_soul(),
            },
            producer_run_id=run["id"],
        )
        _, review = complete_review_run(
            self.service,
            trace["id"],
            "planning_asset",
            direction["id"],
            direction["subject_hash"],
            "planning-direction",
        )
        locked = self.service.lock_planning_asset(
            direction["id"], review["id"], direction["version"], trace["id"]
        )
        return project, trace, locked

    def test_bound_direction_and_writer_inputs_fail_closed(self) -> None:
        profile = self.service.create_creator_profile("作者", signature("宗门"))
        project_result = self.service.create_project_with_creator(
            "失败关闭项目",
            "",
            {},
            {
                "mode": "reuse",
                "profile_version_id": profile["version"]["id"],
                "subject_hash": profile["version"]["subject_hash"],
            },
        )
        project = project_result["project"]
        trace = self.service.start_trace("direction", project["id"])
        role = self.service.agent_contracts.get("direction_agent")
        bindings = {name: f"test:{name}" for name in role["minimum_inputs"]}
        with self.assertRaisesRegex(NovelOSError, "当前作者签名"):
            self.service.start_agent_run(trace["id"], "direction_agent", bindings)

        project, trace, _ = self._bound_project_with_locked_direction()
        role = self.service.agent_contracts.get("writer_agent")
        writer_bindings = {name: f"test:{name}" for name in role["minimum_inputs"]}
        with self.assertRaisesRegex(NovelOSError, "style_refs"):
            self.service.start_agent_run(trace["id"], "writer_agent", writer_bindings)
        refs = self.service.get_project_style_refs(project["id"])["style_refs"]
        writer_bindings["style_refs"] = [*refs, "novelos://pov-voice/limited-third-person"]
        run = self.service.start_agent_run(trace["id"], "writer_agent", writer_bindings)
        self.assertEqual(writer_bindings["style_refs"], run["input_bindings"]["style_refs"])

    def test_bound_chapter_plan_requires_exact_soul_pressure_and_residue(self) -> None:
        project, trace, direction = self._bound_project_with_locked_direction()
        architecture = self._lock_asset(project, trace, "architecture", [direction])
        strategy = self._lock_asset(project, trace, "strategy", [direction, architecture])
        character = self._lock_asset(project, trace, "character_contract", [architecture, strategy])
        world = self._lock_asset(project, trace, "world_contract", [architecture, strategy])
        check = self.service.prepare_planning_cross_check(
            project["id"], character["id"], world["id"]
        )
        _, check_review = complete_review_run(
            self.service,
            trace["id"],
            "planning_cross_check",
            check["id"],
            check["subject_hash"],
            "planning-character-world-cross-consistency",
        )
        approved = self.service.approve_planning_cross_check(
            check["id"], check_review["id"], check["version"], trace["id"]
        )
        arc = self._lock_asset(
            project,
            trace,
            "story_arc",
            [strategy, character, world],
            cross_check_id=approved["id"],
        )
        volume = self._lock_asset(project, trace, "volume_outline", [arc])
        content = "chapter_plan 候选"
        run = complete_agent_run(
            self.service,
            trace["id"],
            "chapter_planner",
            "planning_candidate",
            content,
        )
        upstream = [{"asset_id": volume["id"], "version": volume["version"]}]
        with self.assertRaisesRegex(NovelOSError, "soul_pressure"):
            self.service.create_planning_candidate(
                project["id"],
                "chapter_plan",
                project["id"],
                content,
                upstream,
                producer_run_id=run["id"],
            )
        contract = {
            "soul_pressure": {
                "foreground": False,
                "direction_ref": "novelos://planning-constraint/wrong/1/sha256%3Awrong",
                "manifestation": "纯过渡场景不前景化母题",
            },
            "moral_residue": {
                "kind": "carried",
                "consequence": "没有新增道德后果",
                "unresolved_aftereffect": "既有关系裂痕仍未解除",
            },
        }
        with self.assertRaisesRegex(NovelOSError, "当前 locked Direction"):
            self.service.create_planning_candidate(
                project["id"],
                "chapter_plan",
                project["id"],
                content,
                upstream,
                metadata=contract,
                producer_run_id=run["id"],
            )
        contract["soul_pressure"]["direction_ref"] = self.service.get_project_style_refs(project["id"])["style_refs"][1]
        candidate = self.service.create_planning_candidate(
            project["id"],
            "chapter_plan",
            project["id"],
            content,
            upstream,
            metadata=contract,
            producer_run_id=run["id"],
        )
        self.assertEqual(contract, candidate["metadata"])

    def test_rebind_stales_direction_and_descendants(self) -> None:
        project, trace, direction = self._bound_project_with_locked_direction()
        architecture_content = "架构候选"
        architecture_run = complete_agent_run(
            self.service,
            trace["id"],
            "architecture_agent",
            "planning_candidate",
            architecture_content,
        )
        architecture = self.service.create_planning_candidate(
            project["id"],
            "architecture",
            project["id"],
            architecture_content,
            [{"asset_id": direction["id"], "version": direction["version"]}],
            producer_run_id=architecture_run["id"],
        )
        _, review = complete_review_run(
            self.service,
            trace["id"],
            "planning_asset",
            architecture["id"],
            architecture["subject_hash"],
            "planning-architecture",
        )
        architecture = self.service.lock_planning_asset(
            architecture["id"], review["id"], architecture["version"], trace["id"]
        )
        replacement = self.service.create_creator_profile("新作者", signature("边城"))["version"]
        current_project = self.service.get_project(project["id"])
        with self.assertRaisesRegex(NovelOSError, "Hash"):
            self.service.rebind_project_creator(
                project["id"],
                current_project["version"],
                replacement["id"],
                "sha256:" + "0" * 64,
                trace["id"],
                "错误目标 Hash",
            )
        other_project = self.service.create_project("其他项目")
        other_trace = self.service.start_trace("cross-project-rebind", other_project["id"])
        with self.assertRaisesRegex(NovelOSError, "当前项目"):
            self.service.rebind_project_creator(
                project["id"],
                current_project["version"],
                replacement["id"],
                replacement["subject_hash"],
                other_trace["id"],
                "跨项目 Trace",
            )
        result = self.service.rebind_project_creator(
            project["id"],
            current_project["version"],
            replacement["id"],
            replacement["subject_hash"],
            trace["id"],
            "切换创作立场",
        )
        self.assertEqual({direction["id"], architecture["id"]}, set(result["stale_asset_ids"]))
        self.assertEqual("stale", self.service.get_planning_asset(direction["id"])["status"])
        self.assertEqual("stale", self.service.get_planning_asset(architecture["id"])["status"])
        steps = self.service.get_trace(trace["id"])["steps"]
        self.assertEqual("project.creator.rebind", steps[-1]["step_type"])
        self.assertEqual("切换创作立场", steps[-1]["details"]["reason"])
        self.assertEqual(1, steps[-1]["details"]["old_profile_revision"])
        self.assertEqual(replacement["revision"], steps[-1]["details"]["new_profile_revision"])
        self.assertEqual(replacement["subject_hash"], steps[-1]["details"]["new_subject_hash"])
        with self.assertRaisesRegex(NovelOSError, "已锁定 Story Direction"):
            self.service.get_project_style_refs(project["id"])
        with self.assertRaisesRegex(NovelOSError, "版本"):
            self.service.rebind_project_creator(
                project["id"],
                current_project["version"],
                replacement["id"],
                replacement["subject_hash"],
                trace["id"],
                "错误并发版本",
            )
        current_after_rebind = self.service.get_project(project["id"])
        third = self.service.create_creator_profile("第三作者", signature("旧港"))["version"]
        self.service.finish_trace(trace["id"], "completed")
        with self.assertRaisesRegex(NovelOSError, "运行中 Trace"):
            self.service.rebind_project_creator(
                project["id"],
                current_after_rebind["version"],
                third["id"],
                third["subject_hash"],
                trace["id"],
                "已结束 Trace",
            )


if __name__ == "__main__":
    unittest.main()
