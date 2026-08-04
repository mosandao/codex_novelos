from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import shutil
import sqlite3
import uuid
import yaml
from pathlib import Path
from typing import Any, Iterable

from novelos_mcp.agent_contracts import AgentContractStore
from novelos_mcp.errors import NovelOSError
from novelos_mcp.catalog import CatalogStore
from novelos_mcp.creative_contracts import (
    CreativeContractStore,
    creator_signature_ref,
    planning_constraint_ref,
)
from novelos_mcp.hashing import content_hash
from novelos_mcp.knowledge import KnowledgeStore
from novelos_mcp.storage import Database
from novelos_mcp.system_archetypes import (
    load_system_archetypes_config,
    sync_system_archetypes_to_db,
)
from novelos_mcp.archetype_recommendation import (
    recommend_archetypes,
    generate_derivation_draft,
)

from ._constants import (
    CONTINUITY_OWNERS,
    ENTITY_AUTHORITY_ASSETS,
    PLANNING_PRODUCERS,
    PLANNING_UPSTREAM_TYPES,
)
from ._helpers import _id, _json, _require_sha256, _require_text


class MemoryMixin:

    def get_resource(self, resource_id: str) -> str:
        with self.database.read() as connection:
            row = self._get(connection, "resources", resource_id)
        return bytes(row["content"]).decode("utf-8")

    def create_resource(
        self,
        trace_id: str,
        content: str | dict[str, Any] | list[Any],
        media_type: str = "text/markdown",
    ) -> dict[str, str]:
        if media_type not in {"text/markdown", "application/json"}:
            raise NovelOSError("invalid_argument", "resource media_type 非法")
        if isinstance(content, str):
            normalized = _require_text(content, "content")
        elif isinstance(content, (dict, list)) and content:
            normalized = _json(content)
            if media_type != "application/json":
                raise NovelOSError("invalid_argument", "结构化 Resource 必须使用 application/json")
        else:
            raise NovelOSError("invalid_argument", "resource content 必须是非空文本、对象或数组")
        with self.database.transaction() as connection:
            trace = self._get(connection, "traces", _require_text(trace_id, "trace_id"))
            if trace["status"] != "running":
                raise NovelOSError("invalid_state", "已结束的 Trace 不能创建 Resource")
            resource_id, digest = self._resource(connection, normalized, media_type)
            resource_ref = f"novelos://resource/{resource_id}"
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "resource.create",
                "主控智能体",
                "completed",
                [],
                [resource_ref],
                {"media_type": media_type, "content_hash": digest},
            )
            return {
                "resource_ref": resource_ref,
                "content_hash": digest,
                "media_type": media_type,
            }

    def search_knowledge(self, query: str, tables: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return self.knowledge.search(query, tables, limit)

    def get_knowledge(self, table: str, record_id: str) -> dict[str, str]:
        self.knowledge.get(table, record_id)
        return {"resource_ref": f"novelos://knowledge/{table}/{record_id}"}

    def recent_chapters(self, project_id: str, limit: int = 5) -> list[dict[str, Any]]:
        self._validate_page(limit, 0)
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            rows = connection.execute(
                """
                SELECT chapters.* FROM chapters
                JOIN volumes ON volumes.id = chapters.volume_id
                JOIN books ON books.id = volumes.book_id
                WHERE books.project_id=? AND chapters.status='accepted'
                ORDER BY volumes.number DESC, chapters.number DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [self._row(row) for row in reversed(rows)]

    def search_facts(self, project_id: str, query: str, limit: int = 20) -> list[dict[str, Any]]:
        self._validate_page(limit, 0)
        pattern = f"%{query.strip()}%"
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            rows = connection.execute(
                """
                SELECT chapter_facts.*, resources.id AS description_resource_id
                FROM chapter_facts
                JOIN resources ON resources.id = chapter_facts.description_resource_id
                WHERE chapter_facts.project_id=? AND chapter_facts.status='accepted'
                  AND (?='' OR chapter_facts.subject LIKE ? OR chapter_facts.fact_type LIKE ?
                       OR CAST(resources.content AS TEXT) LIKE ?)
                ORDER BY chapter_facts.created_at DESC, chapter_facts.id
                LIMIT ?
                """,
                (project_id, query.strip(), pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._row(row) for row in rows]

    def get_entity_states(self, project_id: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "characters": self.list_characters(project_id),
            "worlds": self.list_worlds(project_id),
            "factions": self.list_factions(project_id),
        }

    def get_authority_snapshot(self, project_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            project = self._get(connection, "projects", project_id)
            tables = ("characters", "worlds", "factions", "rules", "timelines", "narrative_promises", "expectation_ledgers", "relationship_states", "arc_states")
            versions = {}
            for table in tables:
                rows = connection.execute(
                    f"SELECT id, version FROM {table} WHERE project_id=? ORDER BY id", (project_id,)
                ).fetchall()
                versions[table] = {row["id"]: row["version"] for row in rows}
        snapshot = {"project_id": project_id, "project_version": project["version"], "assets": versions}
        snapshot["snapshot_hash"] = content_hash(_json(snapshot))
        return snapshot

    def record_continuity_candidates(
        self,
        project_id: str,
        chapter_id: str,
        source_content_hash: str,
        authority_snapshot: dict[str, Any],
        owners: list[str],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not owners or not candidates:
            raise NovelOSError("invalid_argument", "owners 和 candidates 不能为空")
        if len(owners) != len(set(owners)) or not set(owners).issubset(CONTINUITY_OWNERS):
            raise NovelOSError(
                "invalid_argument",
                "owners 必须是 canon、expectation、relationship、arc 的非空唯一集合",
            )
        self._validate_continuity_candidates(candidates)
        payload = {
            "project_id": project_id,
            "chapter_id": chapter_id,
            "source_content_hash": source_content_hash,
            "authority_snapshot": authority_snapshot,
            "owners": owners,
            "candidates": candidates,
        }
        serialized = _json(payload)
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            chapter = self._get(connection, "chapters", chapter_id)
            if chapter["status"] != "accepted":
                raise NovelOSError("invalid_state", "只有 accepted 章节可以提取连续性")
            if chapter["subject_hash"] != source_content_hash:
                raise NovelOSError("hash_mismatch", "连续性来源 Hash 与接受正文不一致")
            actual_project = connection.execute(
                "SELECT books.project_id FROM chapters JOIN volumes ON volumes.id=chapters.volume_id JOIN books ON books.id=volumes.book_id WHERE chapters.id=?",
                (chapter_id,),
            ).fetchone()["project_id"]
            if actual_project != project_id:
                raise NovelOSError("authority_mismatch", "章节不属于指定项目")
            current_snapshot = self._authority_snapshot_in_transaction(connection, project_id)
            if authority_snapshot != current_snapshot:
                raise NovelOSError("stale_authority", "Authority Snapshot 已过期")
            resource_id, digest = self._resource(connection, serialized, "application/json")
            candidate_set_id = _id("continuity-set")
            try:
                connection.execute(
                    "INSERT INTO continuity_candidate_sets(id, project_id, chapter_id, source_content_hash, authority_snapshot_json, candidate_resource_id, subject_hash, owners_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (candidate_set_id, project_id, chapter_id, source_content_hash, _json(authority_snapshot), resource_id, digest, _json(owners)),
                )
            except sqlite3.IntegrityError as exc:
                raise NovelOSError("conflict", "该章节版本已有连续性候选集") from exc
            return self._row(self._get(connection, "continuity_candidate_sets", candidate_set_id))

    def get_continuity_candidates(self, candidate_set_id: str) -> dict[str, Any]:
        return self._get_public("continuity_candidate_sets", candidate_set_id)

    def promote_reviewed_continuity(
        self,
        candidate_set_id: str,
        review_id: str,
        expected_version: int,
        trace_id: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            candidate_set = self._get(connection, "continuity_candidate_sets", candidate_set_id)
            review = self._get(connection, "reviews", review_id)
            self._check_version(candidate_set, expected_version)
            if candidate_set["status"] != "working":
                raise NovelOSError("invalid_state", "只有 working 候选集可以晋升")
            if review["subject_type"] != "continuity_candidate_set" or review["subject_ref"] != candidate_set_id:
                raise NovelOSError("invalid_review", "Review 不属于当前连续性候选集")
            expected_profile = self.agent_contracts.review_profile_for_binding("continuity_promotion")
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError("invalid_review_profile", "晋升连续性 Review Profile 不匹配", {"expected": expected_profile, "actual": review["reviewer_profile"]})
            if review["subject_hash"] != candidate_set["subject_hash"]:
                raise NovelOSError("hash_mismatch", "Review Hash 与候选集不一致")
            if review["verdict"] != "approved":
                raise NovelOSError("review_rejected", "Review 未批准连续性候选集")
            if any(item.get("severity") == "blocking" for item in json.loads(review["findings_json"])):
                raise NovelOSError("review_blocking", "Review 存在 blocking finding")
            self._validate_authority_trace(
                connection, trace_id, str(candidate_set["project_id"]), review
            )
            current_snapshot = self._authority_snapshot_in_transaction(connection, candidate_set["project_id"])
            stored_snapshot = json.loads(candidate_set["authority_snapshot_json"])
            if stored_snapshot != current_snapshot:
                raise NovelOSError("stale_authority", "Authority Snapshot 已过期")
            resource = self._get(connection, "resources", candidate_set["candidate_resource_id"])
            payload = json.loads(bytes(resource["content"]).decode("utf-8"))
            candidates = payload["candidates"]
            self._validate_continuity_candidates(candidates)
            counts: dict[str, int] = {}
            for candidate in candidates:
                candidate_type = candidate["type"]
                counts[candidate_type] = counts.get(candidate_type, 0) + 1
                self._apply_continuity_candidate(connection, candidate_set, candidate)
            result_payload = {"candidate_set_id": candidate_set_id, "subject_hash": candidate_set["subject_hash"], "applied": counts}
            result_resource_id, _ = self._resource(connection, _json(result_payload), "application/json")
            result_id = _id("continuity-result")
            connection.execute(
                "INSERT INTO continuity_update_results(id, candidate_set_id, subject_hash, result_resource_id) VALUES (?, ?, ?, ?)",
                (result_id, candidate_set_id, candidate_set["subject_hash"], result_resource_id),
            )
            connection.execute(
                "UPDATE continuity_candidate_sets SET status='promoted', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (candidate_set_id,),
            )
            connection.execute(
                "INSERT INTO chapter_completion_checkpoints(id, chapter_id, source_content_hash, candidate_set_id, review_id, status) VALUES (?, ?, ?, ?, ?, 'continuity_promoted')",
                (_id("checkpoint"), candidate_set["chapter_id"], candidate_set["source_content_hash"], candidate_set_id, review_id),
            )
            result = self._row(self._get(connection, "continuity_update_results", result_id))
            self._record_authority_commit(
                connection,
                trace_id,
                str(candidate_set["project_id"]),
                "continuity.promote",
                "continuity_candidate_set",
                candidate_set_id,
                str(candidate_set["subject_hash"]),
                review_id,
                result_id,
            )
            return result
