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


class ChaptersMixin:

    def prepare_review_subject(
        self,
        trace_id: str,
        subject_kind: str,
        content: dict[str, Any],
        reviewer_profile: str,
        evidence_refs: list[str],
        producer_run_ids: list[str],
    ) -> dict[str, Any]:
        if subject_kind != "agent_quality_evaluation":
            raise NovelOSError(
                "invalid_argument", "review subject_kind 非法", {"subject_kind": subject_kind}
            )
        if not isinstance(content, dict) or not content:
            raise NovelOSError("invalid_argument", "review subject content 必须是非空对象")
        if (
            not isinstance(evidence_refs, list)
            or not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
            or any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs)
        ):
            raise NovelOSError("invalid_argument", "review subject evidence_refs 必须是唯一非空引用")
        if (
            not isinstance(producer_run_ids, list)
            or len(producer_run_ids) != len(set(producer_run_ids))
            or any(not isinstance(run_id, str) or not run_id.strip() for run_id in producer_run_ids)
        ):
            raise NovelOSError("invalid_argument", "review subject producer_run_ids 非法")
        with self.database.transaction() as connection:
            trace = self._get(connection, "traces", _require_text(trace_id, "trace_id"))
            if trace["status"] != "running":
                raise NovelOSError("invalid_state", "已结束的 Trace 不能准备 Review subject")
            self._validate_agent_quality_subject(connection, content, reviewer_profile, evidence_refs)
            for producer_run_id in producer_run_ids:
                producer = self._get(connection, "agent_runs", producer_run_id)
                output_ref = (
                    f"novelos://resource/{producer['output_resource_id']}"
                    if producer["output_resource_id"]
                    else None
                )
                if (
                    producer["trace_id"] != trace_id
                    or producer["status"] != "completed"
                    or producer["role_id"] == "review_agent"
                    or output_ref not in evidence_refs
                ):
                    raise NovelOSError(
                        "invalid_producer_run",
                        "评测 Producer run 必须已完成、属于同一 Trace 且输出包含在 evidence 中",
                        {"producer_run_id": producer_run_id},
                    )
            resource_id, digest = self._resource(connection, _json(content), "application/json")
            subject_id = _id("review-subject")
            connection.execute(
                "INSERT INTO review_subjects(id, trace_id, subject_kind, reviewer_profile, content_resource_id, subject_hash, evidence_refs_json, producer_run_ids_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    subject_id,
                    trace_id,
                    subject_kind,
                    _require_text(reviewer_profile, "reviewer_profile"),
                    resource_id,
                    digest,
                    _json(evidence_refs),
                    _json(producer_run_ids),
                ),
            )
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "review.subject.prepare",
                "主控智能体",
                "completed",
                evidence_refs,
                [subject_id, f"novelos://resource/{resource_id}"],
                {
                    "subject_kind": subject_kind,
                    "reviewer_profile": reviewer_profile,
                    "producer_run_ids": producer_run_ids,
                },
            )
            return self._row(self._get(connection, "review_subjects", subject_id))

    def get_review_subject(self, subject_id: str) -> dict[str, Any]:
        return self._get_public("review_subjects", subject_id)

    def create_chapter_draft(
        self,
        volume_id: str,
        number: int,
        title: str,
        content: str,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
        producer_run_id: str | None = None,
    ) -> dict[str, Any]:
        if number < 1:
            raise NovelOSError("invalid_argument", "number 必须大于 0", {"field": "number"})
        if metadata and metadata.get("chapter_plan_ref") and producer_run_id is None:
            raise NovelOSError("producer_run_required", "绑定 Chapter Plan 的完整章节必须来自 写作智能体 run")
        with self.database.transaction() as connection:
            self._get(connection, "volumes", volume_id)
            project_row = connection.execute(
                "SELECT books.project_id FROM volumes JOIN books ON books.id=volumes.book_id WHERE volumes.id=?",
                (volume_id,),
            ).fetchone()
            if project_row is None:
                raise NovelOSError("not_found", "章节所属项目不存在")
            if producer_run_id is not None:
                self._validate_chapter_producer_run(
                    connection,
                    producer_run_id,
                    content,
                    str(project_row["project_id"]),
                )
            resource_id, digest = self._resource(connection, _require_text(content, "content"))
            chapter_id = _id("chapter")
            try:
                connection.execute(
                    "INSERT INTO chapters(id, volume_id, number, title, content_resource_id, subject_hash, summary, metadata_json, producer_run_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (chapter_id, volume_id, number, _require_text(title, "title"), resource_id, digest, summary, _json(metadata or {}), producer_run_id),
                )
            except sqlite3.IntegrityError as exc:
                raise NovelOSError("conflict", "卷内章节号已存在", {"volume_id": volume_id, "number": number}) from exc
            return self._row(self._get(connection, "chapters", chapter_id))

    def update_chapter_draft(
        self,
        chapter_id: str,
        expected_version: int,
        content: str,
        title: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            current = self._get(connection, "chapters", chapter_id)
            self._check_version(current, expected_version)
            if current["status"] != "draft":
                raise NovelOSError("invalid_state", "只有 draft 可以修改", {"status": current["status"]})
            resource_id, digest = self._resource(connection, _require_text(content, "content"))
            connection.execute(
                "UPDATE chapters SET title=?, summary=?, content_resource_id=?, subject_hash=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (title if title is not None else current["title"], summary if summary is not None else current["summary"], resource_id, digest, chapter_id),
            )
            return self._row(self._get(connection, "chapters", chapter_id))

    def get_chapter(self, chapter_id: str) -> dict[str, Any]:
        return self._get_public("chapters", chapter_id)

    def list_chapters(self, volume_id: str) -> list[dict[str, Any]]:
        return self._list_children("chapters", "volume_id", volume_id, "number")

    def accept_chapter(
        self, chapter_id: str, review_id: str, expected_version: int, trace_id: str
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            chapter = self._get(connection, "chapters", chapter_id)
            review = self._get(connection, "reviews", review_id)
            self._check_version(chapter, expected_version)
            if chapter["status"] != "draft":
                raise NovelOSError("invalid_state", "只有 draft 可以接受", {"status": chapter["status"]})
            if review["subject_type"] != "chapter" or review["subject_ref"] != chapter_id:
                raise NovelOSError("invalid_review", "Review 不属于当前章节")
            expected_profile = self.agent_contracts.review_profile_for_binding("chapter_acceptance")
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError("invalid_review_profile", "接受章节 Review Profile 不匹配", {"expected": expected_profile, "actual": review["reviewer_profile"]})
            if review["subject_hash"] != chapter["subject_hash"]:
                raise NovelOSError("hash_mismatch", "Review Hash 与当前章节不一致")
            if review["verdict"] != "approved":
                raise NovelOSError("review_rejected", "Review 未批准章节")
            findings = json.loads(review["findings_json"])
            if any(item.get("severity") == "blocking" for item in findings):
                raise NovelOSError("review_blocking", "Review 存在 blocking finding")
            project_id = str(
                connection.execute(
                    "SELECT books.project_id FROM volumes JOIN books ON books.id=volumes.book_id WHERE volumes.id=?",
                    (chapter["volume_id"],),
                ).fetchone()["project_id"]
            )
            self._validate_authority_trace(
                connection,
                trace_id,
                project_id,
                review,
                str(chapter["producer_run_id"]) if chapter["producer_run_id"] else None,
            )
            connection.execute(
                "UPDATE chapters SET status='accepted', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (chapter_id,),
            )
            accepted = self._row(self._get(connection, "chapters", chapter_id))
            self._record_authority_commit(
                connection,
                trace_id,
                project_id,
                "chapter.accept",
                "chapter",
                chapter_id,
                str(chapter["subject_hash"]),
                review_id,
                chapter_id,
            )
            return accepted

    def supersede_chapter(self, chapter_id: str, expected_version: int) -> dict[str, Any]:
        with self.database.transaction() as connection:
            chapter = self._get(connection, "chapters", chapter_id)
            self._check_version(chapter, expected_version)
            if chapter["status"] != "accepted":
                raise NovelOSError("invalid_state", "只有 accepted 可以 supersede", {"status": chapter["status"]})
            connection.execute("UPDATE chapters SET status='superseded', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?", (chapter_id,))
            return self._row(self._get(connection, "chapters", chapter_id))
