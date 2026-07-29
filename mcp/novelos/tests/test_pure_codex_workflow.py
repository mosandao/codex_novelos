from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from novelos_mcp import NovelOSService
from agent_test_support import complete_agent_run, complete_review_run


ROOT = Path(__file__).resolve().parents[3]
CATALOG_ROOT = ROOT / "catalog" / "skills"
PRODUCERS = {
    "direction": "Direction Agent",
    "architecture": "Architecture Agent",
    "strategy": "Strategy Agent",
    "character_contract": "Character Agent",
    "world_contract": "World Agent",
    "story_arc": "Story Arc Agent",
    "volume_outline": "Volume Planner",
    "chapter_plan": "Chapter Planner",
}
PACKAGES = {
    "direction": "story-direction",
    "architecture": "story-architecture",
    "strategy": "story-strategy",
    "character_contract": "character-contract",
    "world_contract": "world-contract",
    "story_arc": "story-arc",
    "volume_outline": "volume-outline",
    "chapter_plan": "chapter-plan-execution-card",
}
ROLE_IDS = {
    "direction": "direction_agent",
    "architecture": "architecture_agent",
    "strategy": "strategy_agent",
    "character_contract": "character_agent",
    "world_contract": "world_agent",
    "story_arc": "story_arc_agent",
    "volume_outline": "volume_planner",
    "chapter_plan": "chapter_planner",
}


class PureCodexWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(
            Path(self.temporary.name) / "novelos.db",
            catalog_path=CATALOG_ROOT,
        )
        self.project = self.service.create_project("端到端测试")
        self.book = self.service.create_book(self.project["id"], "测试书")
        self.volume = self.service.create_volume(self.book["id"], 1, "测试卷")
        self.trace = self.service.start_trace("pure-codex-chapter", self.project["id"])

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _select(self, stage: str, asset: str, capability: str, name: str) -> str:
        result = self.service.search_skill_catalog(stage=stage, asset=asset, capability=capability)
        candidates = [item["name"] for item in result["candidates"]]
        self.assertIn(name, candidates)
        self.service.validate_skill_selection([name], candidates, result["snapshot_hash"])
        prompt_ref = self.service.get_skill_catalog(name)["resources"]["prompt"]
        self.service.record_trace_step(
            self.trace["id"],
            "catalog.select",
            "Main Agent",
            "completed",
            output_refs=[prompt_ref],
            details={"selected": name},
        )
        return prompt_ref

    def _planning_asset(
        self,
        asset_type: str,
        upstream_assets: list[dict[str, Any]],
        cross_check_id: str | None = None,
    ) -> dict[str, Any]:
        self._select("plan", asset_type, "generate", PACKAGES[asset_type])
        content = f"# {asset_type}\n\n端到端候选。"
        producer_run = complete_agent_run(
            self.service,
            self.trace["id"],
            ROLE_IDS[asset_type],
            "planning_candidate",
            content,
        )
        candidate = self.service.create_planning_candidate(
            self.project["id"],
            asset_type,
            self.project["id"],
            content,
            [{"asset_id": item["id"], "version": item["version"]} for item in upstream_assets],
            producer_run_id=producer_run["id"],
            cross_check_id=cross_check_id,
        )
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            f"planning-{asset_type.replace('_', '-')}",
            evidence_refs=[candidate["resource_ref"]],
        )
        locked = self.service.lock_planning_asset(
            candidate["id"], review["id"], candidate["version"], self.trace["id"]
        )
        return locked

    def test_planning_draft_review_accept_and_continuity_share_one_production_path(self) -> None:
        direction = self._planning_asset("direction", [])
        architecture = self._planning_asset("architecture", [direction])
        strategy = self._planning_asset("strategy", [direction, architecture])
        characters = self._planning_asset("character_contract", [architecture, strategy])
        world = self._planning_asset("world_contract", [architecture, strategy])
        cross_check = self.service.prepare_planning_cross_check(
            self.project["id"], characters["id"], world["id"]
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
        story_arc = self._planning_asset(
            "story_arc", [strategy, characters, world], approved_cross_check["id"]
        )
        volume_outline = self._planning_asset("volume_outline", [story_arc])
        chapter_plan = self._planning_asset("chapter_plan", [volume_outline])
        self.assertEqual("locked", chapter_plan["status"])

        self._select("write", "chapter", "generate", "chapter-draft-generation")
        content = "林舟穿过城门，确认封印仍未修复。"
        self.assertTrue(self.service.validate_skill_output("chapter-draft-generation", content)["valid"])
        writer_run = complete_agent_run(
            self.service,
            self.trace["id"],
            "writer_agent",
            "chapter_draft_candidate",
            content,
            {"locked_chapter_plan_ref": chapter_plan["id"]},
        )
        draft = self.service.create_chapter_draft(
            self.volume["id"],
            1,
            "入城",
            content,
            metadata={"chapter_plan_ref": chapter_plan["id"], "chapter_plan_version": chapter_plan["version"]},
            producer_run_id=writer_run["id"],
        )

        self._select("review", "chapter", "review", "prose-quality-review")
        review_input = {
            "subject_ref": draft["id"],
            "subject_hash": draft["subject_hash"],
            "reviewer_profile": "prose-v1",
            "context_refs": [chapter_plan["resource_ref"]],
        }
        self.assertTrue(self.service.validate_skill_input("prose-quality-review", review_input)["valid"])
        review_output = {
            "subject_hash": draft["subject_hash"],
            "verdict": "approved",
            "findings": [],
            "evidence_refs": [draft["resource_ref"]],
            "reviewer_profile": "prose-v1",
        }
        self.assertTrue(self.service.validate_skill_output("prose-quality-review", review_output)["valid"])
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
            evidence_refs=review_output["evidence_refs"],
        )
        chapter = self.service.accept_chapter(
            draft["id"], review["id"], draft["version"], self.trace["id"]
        )

        self._select("meta", "continuity", "extract", "continuity-candidate-extraction")
        snapshot = self.service.get_authority_snapshot(self.project["id"])
        continuity_input = {
            "project_id": self.project["id"],
            "chapter_id": chapter["id"],
            "source_content_hash": chapter["subject_hash"],
            "authority_snapshot": snapshot,
        }
        self.assertTrue(
            self.service.validate_skill_input("continuity-candidate-extraction", continuity_input)["valid"]
        )
        continuity_output = {
            "owners": ["canon"],
            "candidates": [
                {
                    "type": "fact",
                    "fact_type": "plot",
                    "subject": "封印",
                    "description": "林舟确认封印仍未修复。",
                }
            ],
        }
        self.assertTrue(
            self.service.validate_skill_output("continuity-candidate-extraction", continuity_output)["valid"]
        )
        candidate_set = self.service.record_continuity_candidates(
            self.project["id"],
            chapter["id"],
            chapter["subject_hash"],
            snapshot,
            continuity_output["owners"],
            continuity_output["candidates"],
        )
        _, continuity_review = complete_review_run(
            self.service,
            self.trace["id"],
            "continuity_candidate_set",
            candidate_set["id"],
            candidate_set["subject_hash"],
            "continuity-v1",
            evidence_refs=[candidate_set["candidate_ref"]],
        )
        self.service.promote_reviewed_continuity(
            candidate_set["id"], continuity_review["id"], 1, self.trace["id"]
        )
        audit = self.service.audit_authority_trace(self.project["id"])
        finished = self.service.finish_trace(self.trace["id"], "completed")

        self.assertEqual("accepted", chapter["status"])
        self.assertEqual("封印", self.service.search_facts(self.project["id"], "封印")[0]["subject"])
        self.assertEqual("completed", finished["status"])
        self.assertTrue(audit["verified"], audit["issues"])
        self.assertEqual(11, audit["authority_count"])
        self.assertGreaterEqual(len(self.service.get_trace(self.trace["id"])["steps"]), 12)
        self.assertTrue(
            all(run["status"] == "completed" for run in self.service.list_agent_runs(self.trace["id"]))
        )


if __name__ == "__main__":
    unittest.main()
