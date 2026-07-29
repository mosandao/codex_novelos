from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from novelos_mcp import NovelOSError, NovelOSService
from agent_test_support import complete_review_run


PRODUCERS = {
    "direction": "Direction Agent",
    "architecture": "Architecture Agent",
    "strategy": "Strategy Agent",
    "character_contract": "Character Agent",
    "world_contract": "World Agent",
}


class EntityMutationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.service = NovelOSService(Path(self.temporary.name) / "novelos.db")
        self.project = self.service.create_project("实体写入测试")
        self.trace = self.service.start_trace("entity-mutation-test", self.project["id"])
        direction = self._planning("direction", [])
        architecture = self._planning("architecture", [direction])
        strategy = self._planning("strategy", [direction, architecture])
        self.character_contract = self._planning("character_contract", [architecture, strategy])
        self.world_contract = self._planning("world_contract", [architecture, strategy])
        self.architecture = architecture
        self.strategy = strategy

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _planning(self, asset_type: str, upstream: list[dict[str, Any]]) -> dict[str, Any]:
        candidate = self.service.create_planning_candidate(
            self.project["id"],
            asset_type,
            self.project["id"],
            f"# {asset_type}",
            [{"asset_id": item["id"], "version": item["version"]} for item in upstream],
            PRODUCERS[asset_type],
        )
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "planning_asset",
            candidate["id"],
            candidate["subject_hash"],
            f"planning-{asset_type.replace('_', '-')}",
        )
        return self.service.lock_planning_asset(
            candidate["id"], review["id"], 1, self.trace["id"]
        )

    def _prepare(self, entity_type: str, payload: dict[str, Any], expected: int | None = None) -> dict[str, Any]:
        source = self.character_contract if entity_type == "character" else self.world_contract
        return self.service.prepare_entity_mutation(
            self.project["id"],
            entity_type,
            payload,
            source["id"],
            source["subject_hash"],
            expected,
        )

    def _commit(self, mutation: dict[str, Any], profile: str | None = None) -> dict[str, Any]:
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "entity_mutation",
            mutation["id"],
            mutation["subject_hash"],
            profile or f"entity-{mutation['entity_type']}",
            evidence_refs=[mutation["mutation_ref"]],
        )
        return self.service.commit_entity_mutation(
            mutation["id"], review["id"], mutation["version"], self.trace["id"]
        )

    def test_all_authority_entities_require_reviewed_mutation(self) -> None:
        cases = [
            ("character", {"name": "林舟", "description": "信使", "state": {"location": "城门"}}),
            ("world", {"name": "边城", "description": "边境城市", "state": {"season": "冬"}}),
            ("faction", {"name": "巡夜司", "description": "执法势力", "state": {"stance": "警戒"}}),
            ("rule", {"name": "夜禁", "description": "子时后禁止通行"}),
            (
                "timeline",
                {"label": "城门关闭", "sequence": 10, "description": "城门在子时关闭", "event_source_ref": "world-contract:event-1"},
            ),
        ]
        for entity_type, payload in cases:
            result = self._commit(self._prepare(entity_type, payload))
            self.assertEqual("applied", result["mutation"]["status"])
            self.assertEqual(1, result["entity"]["version"])

        self.assertEqual("林舟", self.service.list_characters(self.project["id"])[0]["name"])
        self.assertEqual("边城", self.service.list_worlds(self.project["id"])[0]["name"])
        self.assertEqual("巡夜司", self.service.list_factions(self.project["id"])[0]["name"])
        self.assertEqual("夜禁", self.service.list_rules(self.project["id"])[0]["name"])
        self.assertEqual("城门关闭", self.service.list_timelines(self.project["id"])[0]["label"])

    def test_concurrent_mutations_use_target_optimistic_version(self) -> None:
        created = self._commit(
            self._prepare("character", {"name": "林舟", "description": "第一版", "state": {}})
        )["entity"]
        first = self._prepare(
            "character", {"name": "林舟", "description": "第二版 A", "state": {}}, created["version"]
        )
        second = self._prepare(
            "character", {"name": "林舟", "description": "第二版 B", "state": {}}, created["version"]
        )
        self._commit(first)
        with self.assertRaisesRegex(NovelOSError, "stale_version"):
            self._commit(second)
        self.assertEqual("candidate", self.service._get_public("entity_mutations", second["id"])["status"])

    def test_superseded_authority_source_blocks_commit_without_partial_write(self) -> None:
        mutation = self._prepare("world", {"name": "边城", "description": "旧契约候选", "state": {}})
        self.world_contract = self._planning("world_contract", [self.architecture, self.strategy])
        _, review = complete_review_run(
            self.service,
            self.trace["id"],
            "entity_mutation",
            mutation["id"],
            mutation["subject_hash"],
            "entity-world",
        )
        with self.assertRaisesRegex(NovelOSError, "stale_authority"):
            self.service.commit_entity_mutation(mutation["id"], review["id"], 1, self.trace["id"])
        self.assertEqual([], self.service.list_worlds(self.project["id"]))

    def test_wrong_review_profile_does_not_apply_mutation(self) -> None:
        mutation = self._prepare("rule", {"name": "夜禁", "description": "子时后禁止通行"})
        with self.assertRaisesRegex(NovelOSError, "invalid_review_profile"):
            self._commit(mutation, "entity-world")
        self.assertEqual([], self.service.list_rules(self.project["id"]))

    def test_unknown_payload_fields_fail_before_resource_write(self) -> None:
        with self.assertRaisesRegex(NovelOSError, "invalid_candidate"):
            self._prepare(
                "character",
                {"name": "林舟", "description": "信使", "state": {}, "unexpected": True},
            )
        with self.service.database.read() as connection:
            self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM entity_mutations").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
