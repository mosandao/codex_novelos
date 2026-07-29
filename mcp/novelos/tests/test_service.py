from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from novelos_mcp import NovelOSError, NovelOSService
from novelos_mcp.seed_inventory import build_seed_inventory
from agent_test_support import complete_review_run


class NovelOSServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("测试项目")
        self.trace = self.service.start_trace("service-test", self.project["id"])
        self.book = self.service.create_book(self.project["id"], "第一部")
        self.volume = self.service.create_volume(self.book["id"], 1, "第一卷")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_project_version_is_optimistic(self) -> None:
        updated = self.service.update_project(self.project["id"], 1, description="新说明")
        self.assertEqual(2, updated["version"])
        with self.assertRaisesRegex(NovelOSError, "stale_version"):
            self.service.update_project(self.project["id"], 1, description="过期修改")

    def test_chapter_accept_requires_review_for_exact_hash(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "开端", "正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
        )
        accepted = self.service.accept_chapter(draft["id"], review["id"], 1, self.trace["id"])
        self.assertEqual("accepted", accepted["status"])
        self.assertEqual(2, accepted["version"])

    def test_changed_draft_invalidates_old_review(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "开端", "第一版")
        review = self.service.record_review(
            "chapter", draft["id"], draft["subject_hash"], "approved", [], "prose-v1"
        )
        changed = self.service.update_chapter_draft(draft["id"], 1, "第二版")
        with self.assertRaisesRegex(NovelOSError, "hash_mismatch"):
            self.service.accept_chapter(changed["id"], review["id"], 2, self.trace["id"])

    def test_blocking_review_cannot_be_approved(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "开端", "正文")
        with self.assertRaisesRegex(NovelOSError, "invalid_review"):
            self.service.record_review(
                "chapter",
                draft["id"],
                draft["subject_hash"],
                "approved",
                [{"severity": "blocking", "message": "冲突", "evidence_refs": ["chapter:1"]}],
                "prose-v1",
            )

    def test_long_content_is_returned_by_resource(self) -> None:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "开端", "较长正文")
        resource_id = draft["resource_ref"].rsplit("/", 1)[-1]
        self.assertEqual("较长正文", self.service.get_resource(resource_id))
        with self.assertRaisesRegex(NovelOSError, "not_found"):
            self.service.get_resource("resource:not-found")

    def test_entity_update_requires_expected_version(self) -> None:
        character = self.service.upsert_character(self.project["id"], "林舟", "信使")
        with self.assertRaisesRegex(NovelOSError, "expected_version_required"):
            self.service.upsert_character(self.project["id"], "林舟", "新的描述")
        updated = self.service.upsert_character(
            self.project["id"], "林舟", "新的描述", expected_version=character["version"]
        )
        self.assertEqual(2, updated["version"])

    def test_faction_rule_and_timeline_are_versioned_resources(self) -> None:
        faction = self.service.upsert_faction(self.project["id"], "巡夜司", "夜间执法机构")
        rule = self.service.upsert_rule(self.project["id"], "夜禁", "子时后不得通行")
        timeline = self.service.upsert_timeline(
            self.project["id"], "城门关闭", 10, "城门在子时关闭", "chapter:1"
        )
        self.assertTrue(faction["id"].startswith("faction:"))
        self.assertTrue(rule["description_ref"].startswith("novelos://resource/"))
        self.assertEqual("chapter:1", timeline["source_ref"])

    def _accepted_chapter(self) -> dict[str, object]:
        draft = self.service.create_chapter_draft(self.volume["id"], 1, "开端", "正文")
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "chapter",
            draft["id"],
            draft["subject_hash"],
            "prose-v1",
        )
        return self.service.accept_chapter(draft["id"], review["id"], 1, self.trace["id"])

    def test_continuity_candidates_promote_atomically_after_review(self) -> None:
        chapter = self._accepted_chapter()
        snapshot = self.service.get_authority_snapshot(self.project["id"])
        candidate_set = self.service.record_continuity_candidates(
            self.project["id"],
            chapter["id"],
            chapter["subject_hash"],
            snapshot,
            ["canon", "expectation", "relationship", "arc"],
            [
                {"type": "fact", "fact_type": "location", "subject": "林舟", "description": "林舟进入城内"},
                {"type": "narrative_promise", "key": "broken-seal", "description": "封印仍待解决", "status": "open"},
                {"type": "expectation", "key": "gate-truth", "description": "城门真相需要揭示", "status": "open"},
                {"type": "relationship", "subject_ref": "林舟", "object_ref": "巡夜司", "state": "互相戒备"},
                {"type": "arc", "arc_ref": "arrival", "state": "主角已进入城内"},
            ],
        )
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "continuity_candidate_set",
            candidate_set["id"],
            candidate_set["subject_hash"],
            "continuity-v1",
        )
        result = self.service.promote_reviewed_continuity(
            candidate_set["id"], review["id"], 1, self.trace["id"]
        )
        facts = self.service.search_facts(self.project["id"], "林舟")
        self.assertEqual("林舟", facts[0]["subject"])
        self.assertTrue(result["result_ref"].startswith("novelos://resource/"))

    def test_stale_authority_blocks_continuity_promotion_without_partial_writes(self) -> None:
        chapter = self._accepted_chapter()
        snapshot = self.service.get_authority_snapshot(self.project["id"])
        candidate_set = self.service.record_continuity_candidates(
            self.project["id"],
            chapter["id"],
            chapter["subject_hash"],
            snapshot,
            ["canon"],
            [{"type": "fact", "fact_type": "location", "subject": "林舟", "description": "进入城内"}],
        )
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "continuity_candidate_set",
            candidate_set["id"],
            candidate_set["subject_hash"],
            "continuity-v1",
        )
        self.service.upsert_character(self.project["id"], "林舟", "信使")
        with self.assertRaisesRegex(NovelOSError, "stale_authority"):
            self.service.promote_reviewed_continuity(
                candidate_set["id"], review["id"], 1, self.trace["id"]
            )
        self.assertEqual([], self.service.search_facts(self.project["id"], "林舟"))

    def test_continuity_candidate_rejects_unknown_fields(self) -> None:
        chapter = self._accepted_chapter()
        snapshot = self.service.get_authority_snapshot(self.project["id"])
        with self.assertRaisesRegex(NovelOSError, "invalid_candidate"):
            self.service.record_continuity_candidates(
                self.project["id"],
                chapter["id"],
                chapter["subject_hash"],
                snapshot,
                ["canon"],
                [{
                    "type": "fact",
                    "fact_type": "location",
                    "subject": "林舟",
                    "description": "进入城内",
                    "unexpected": "不允许",
                }],
            )

    def test_trace_is_ordered_append_only_and_cannot_reopen(self) -> None:
        trace = self.service.start_trace("chapter-continuation", self.project["id"])
        first = self.service.record_trace_step(
            trace["id"], "agent.spawn", "Main Agent", "completed", output_refs=["agent:writer"]
        )
        second = self.service.record_trace_step(
            trace["id"], "tool.call", "Writer Agent", "completed", input_refs=["chapter-plan:1"]
        )
        self.assertEqual((1, 2), (first["sequence"], second["sequence"]))
        finished = self.service.finish_trace(trace["id"], "completed")
        self.assertEqual("completed", finished["status"])
        with self.assertRaisesRegex(NovelOSError, "invalid_state"):
            self.service.record_trace_step(trace["id"], "agent.destroy", "Main Agent", "completed")
        self.assertEqual(2, len(self.service.get_trace(trace["id"])["steps"]))


class KnowledgeStoreTest(unittest.TestCase):
    def test_search_returns_summary_and_resource_from_read_only_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed = root / "seed.db"
            with closing(sqlite3.connect(seed)) as connection:
                connection.execute(
                    "CREATE TABLE kb_writing_techniques(id INTEGER PRIMARY KEY, technique_name TEXT, category TEXT, description TEXT)"
                )
                connection.execute(
                    "INSERT INTO kb_writing_techniques VALUES (1, '递进冲突', '剧情', '逐步提高阻碍强度')"
                )
                connection.commit()
            inventory = root / "seed-inventory.json"
            inventory.write_text(
                json.dumps(build_seed_inventory(seed, "synthetic-test")), encoding="utf-8"
            )
            service = NovelOSService(
                root / "novelos.db", seed_database_path=seed, seed_inventory_path=inventory
            )
            results = service.search_knowledge("阻碍")
            self.assertEqual("递进冲突", results[0]["title"])
            reference = service.get_knowledge("kb_writing_techniques", "1")["resource_ref"]
            self.assertEqual("novelos://knowledge/kb_writing_techniques/1", reference)
            resource = service.knowledge.get_resource("kb_writing_techniques", "1")
            self.assertIn("逐步提高阻碍强度", resource)

            with self.assertRaises(sqlite3.OperationalError):
                with closing(service.knowledge._connect()) as connection:
                    connection.execute("DELETE FROM kb_writing_techniques")


if __name__ == "__main__":
    unittest.main()
