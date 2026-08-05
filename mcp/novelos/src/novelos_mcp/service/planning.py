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


class PlanningMixin:

    def prepare_entity_mutation(
        self,
        project_id: str,
        entity_type: str,
        payload: dict[str, Any],
        authority_source_ref: str,
        authority_source_hash: str,
        target_expected_version: int | None = None,
    ) -> dict[str, Any]:
        self._validate_entity_payload(entity_type, payload)
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            source_version = self._validate_entity_authority_source(
                connection,
                project_id,
                entity_type,
                authority_source_ref,
                authority_source_hash,
            )
            existing = self._find_entity_target(connection, project_id, entity_type, payload)
            if existing is None and target_expected_version is not None:
                raise NovelOSError("not_found", "指定版本的目标实体不存在")
            if existing is not None:
                if target_expected_version is None:
                    raise NovelOSError("expected_version_required", "更新已有实体必须提供 target_expected_version")
                self._check_version(existing, target_expected_version)
            envelope = {
                "project_id": project_id,
                "entity_type": entity_type,
                "payload": payload,
                "authority_source_ref": authority_source_ref,
                "authority_source_hash": authority_source_hash,
                "authority_source_version": source_version,
                "target_id": str(existing["id"]) if existing is not None else None,
                "target_expected_version": target_expected_version,
            }
            resource_id, digest = self._resource(connection, _json(envelope), "application/json")
            mutation_id = _id("entity-mutation")
            connection.execute(
                "INSERT INTO entity_mutations(id, project_id, entity_type, mutation_resource_id, subject_hash, authority_source_ref, authority_source_hash, authority_source_version, target_id, target_expected_version) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    mutation_id,
                    project_id,
                    entity_type,
                    resource_id,
                    digest,
                    authority_source_ref,
                    authority_source_hash,
                    source_version,
                    envelope["target_id"],
                    target_expected_version,
                ),
            )
            return self._row(self._get(connection, "entity_mutations", mutation_id))

    def commit_entity_mutation(
        self,
        mutation_id: str,
        review_id: str,
        expected_version: int,
        trace_id: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            mutation = self._get(connection, "entity_mutations", mutation_id)
            self._check_version(mutation, expected_version)
            if mutation["status"] != "candidate":
                raise NovelOSError("invalid_state", "Entity mutation 已提交")
            review = self._get(connection, "reviews", review_id)
            if review["subject_type"] != "entity_mutation" or review["subject_ref"] != mutation_id:
                raise NovelOSError("invalid_review", "Review 不属于当前 entity mutation")
            if review["subject_hash"] != mutation["subject_hash"]:
                raise NovelOSError("hash_mismatch", "Review Hash 与 entity mutation 不一致")
            expected_profile = self.agent_contracts.review_profile_for_entity(str(mutation["entity_type"]))
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError("invalid_review_profile", "Entity Review Profile 不匹配", {"expected": expected_profile})
            if review["verdict"] != "approved" or any(
                item.get("severity") == "blocking" for item in json.loads(review["findings_json"])
            ):
                raise NovelOSError("review_rejected", "Review 未批准 entity mutation")
            self._validate_authority_trace(
                connection, trace_id, str(mutation["project_id"]), review
            )
            source_version = self._validate_entity_authority_source(
                connection,
                mutation["project_id"],
                mutation["entity_type"],
                mutation["authority_source_ref"],
                mutation["authority_source_hash"],
            )
            if source_version != mutation["authority_source_version"]:
                raise NovelOSError("stale_authority", "Entity mutation 的来源版本已变化")
            resource = self._get(connection, "resources", mutation["mutation_resource_id"])
            envelope = json.loads(bytes(resource["content"]).decode("utf-8"))
            current = self._find_entity_target(
                connection,
                mutation["project_id"],
                mutation["entity_type"],
                envelope["payload"],
            )
            if mutation["target_id"] is None:
                if current is not None:
                    raise NovelOSError("conflict", "Entity mutation 目标已由其他写入创建")
            else:
                if current is None or current["id"] != mutation["target_id"]:
                    raise NovelOSError("stale_version", "Entity mutation 目标已变化")
                self._check_version(current, int(mutation["target_expected_version"]))
            entity = self._apply_entity_mutation(
                connection,
                mutation["project_id"],
                mutation["entity_type"],
                envelope["payload"],
                current,
            )
            connection.execute(
                "UPDATE entity_mutations SET status='applied', applied_review_id=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (review_id, mutation_id),
            )
            result = {
                "mutation": self._row(self._get(connection, "entity_mutations", mutation_id)),
                "entity": self._row(entity),
            }
            self._record_authority_commit(
                connection,
                trace_id,
                str(mutation["project_id"]),
                "entity.commit",
                "entity_mutation",
                mutation_id,
                str(mutation["subject_hash"]),
                review_id,
                str(entity["id"]),
            )
            return result

    def prepare_planning_cross_check(
        self,
        project_id: str,
        character_asset_id: str,
        world_asset_id: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            character = self._get(connection, "planning_assets", character_asset_id)
            world = self._get(connection, "planning_assets", world_asset_id)
            for row, expected in ((character, "character_contract"), (world, "world_contract")):
                if row["project_id"] != project_id or row["asset_type"] != expected:
                    raise NovelOSError("authority_mismatch", "交叉审查资产类型或项目不匹配")
                if row["status"] != "locked":
                    raise NovelOSError("stale_upstream", "交叉审查只接受有效 locked 资产")
            payload = {
                "project_id": project_id,
                "character": {
                    "asset_id": character_asset_id,
                    "version": int(character["version"]),
                    "subject_hash": character["subject_hash"],
                },
                "world": {
                    "asset_id": world_asset_id,
                    "version": int(world["version"]),
                    "subject_hash": world["subject_hash"],
                },
            }
            resource_id, digest = self._resource(connection, _json(payload), "application/json")
            check_id = _id("planning-cross-check")
            try:
                connection.execute(
                    "INSERT INTO planning_cross_checks(id, project_id, character_asset_id, character_version, character_hash, world_asset_id, world_version, world_hash, content_resource_id, subject_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        check_id,
                        project_id,
                        character_asset_id,
                        character["version"],
                        character["subject_hash"],
                        world_asset_id,
                        world["version"],
                        world["subject_hash"],
                        resource_id,
                        digest,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise NovelOSError("conflict", "该 Character/World 版本已存在交叉审查") from exc
            return self._row(self._get(connection, "planning_cross_checks", check_id))

    def approve_planning_cross_check(
        self,
        check_id: str,
        review_id: str,
        expected_version: int,
        trace_id: str,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            check = self._get(connection, "planning_cross_checks", check_id)
            self._check_version(check, expected_version)
            if check["status"] != "pending":
                raise NovelOSError("invalid_state", "交叉审查已结束")
            self._validate_cross_check_sources(connection, check)
            review = self._get(connection, "reviews", review_id)
            if review["subject_type"] != "planning_cross_check" or review["subject_ref"] != check_id:
                raise NovelOSError("invalid_review", "Review 不属于该交叉审查")
            if review["subject_hash"] != check["subject_hash"]:
                raise NovelOSError("hash_mismatch", "交叉审查 Review Hash 不一致")
            expected_profile = self.agent_contracts.cross_consistency_profile()
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError("invalid_review_profile", "交叉审查 Profile 不匹配", {"expected": expected_profile})
            if not review["reviewer_run_id"]:
                raise NovelOSError("reviewer_run_required", "交叉审查必须绑定独立 审查智能体 run")
            if review["verdict"] != "approved" or any(
                item.get("severity") == "blocking" for item in json.loads(review["findings_json"])
            ):
                raise NovelOSError("review_rejected", "Character/World 交叉审查未通过")
            self._validate_authority_trace(
                connection, trace_id, str(check["project_id"]), review
            )
            connection.execute(
                "UPDATE planning_cross_checks SET status='approved', review_id=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (review_id, check_id),
            )
            approved = self._row(self._get(connection, "planning_cross_checks", check_id))
            self._record_authority_commit(
                connection,
                trace_id,
                str(check["project_id"]),
                "planning.cross_check.approve",
                "planning_cross_check",
                check_id,
                str(check["subject_hash"]),
                review_id,
                check_id,
            )
            return approved

    def get_planning_cross_check(self, check_id: str) -> dict[str, Any]:
        return self._get_public("planning_cross_checks", check_id)

    def create_planning_candidate(
        self,
        project_id: str,
        asset_type: str,
        scope_ref: str,
        content: str,
        upstream_refs: list[dict[str, Any]],
        producer_role: str | None = None,
        metadata: dict[str, Any] | None = None,
        producer_run_id: str | None = None,
        cross_check_id: str | None = None,
    ) -> dict[str, Any]:
        expected_upstream_types = PLANNING_UPSTREAM_TYPES.get(asset_type)
        if expected_upstream_types is None:
            raise NovelOSError("invalid_argument", "未知 planning asset_type", {"asset_type": asset_type})
        if producer_role is not None and producer_role != PLANNING_PRODUCERS[asset_type]:
            raise NovelOSError(
                "invalid_producer",
                "规划资产只能由唯一负责 Agent 生产",
                {"expected": PLANNING_PRODUCERS[asset_type], "actual": producer_role},
            )
        normalized_scope = _require_text(scope_ref, "scope_ref")
        if not isinstance(upstream_refs, list) or any(
            not isinstance(ref, dict) or set(ref) != {"asset_id", "version"} for ref in upstream_refs
        ):
            raise NovelOSError("invalid_upstream", "upstream_refs 必须只包含 asset_id 和 version")
        upstream_ids = [ref["asset_id"] for ref in upstream_refs]
        if len(upstream_ids) != len(set(upstream_ids)):
            raise NovelOSError("invalid_upstream", "upstream_refs 不能重复")

        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            upstream_rows: list[sqlite3.Row] = []
            for ref in upstream_refs:
                if not isinstance(ref["asset_id"], str) or not isinstance(ref["version"], int):
                    raise NovelOSError("invalid_upstream", "upstream ref 类型非法")
                row = self._get(connection, "planning_assets", ref["asset_id"])
                if row["project_id"] != project_id:
                    raise NovelOSError("invalid_upstream", "上游资产不属于当前项目")
                if row["status"] != "locked" or int(row["version"]) != ref["version"]:
                    raise NovelOSError(
                        "stale_upstream",
                        "上游资产不是指定的有效锁定版本",
                        {"asset_id": row["id"], "status": row["status"], "actual_version": row["version"]},
                    )
                upstream_rows.append(row)
            actual_upstream_types = {str(row["asset_type"]) for row in upstream_rows}
            if actual_upstream_types != set(expected_upstream_types):
                raise NovelOSError(
                    "invalid_upstream",
                    "规划资产的上游类型不完整或越界",
                    {"expected": sorted(expected_upstream_types), "actual": sorted(actual_upstream_types)},
                )

            if producer_run_id is not None:
                producer_role = self._validate_planning_producer_run(
                    connection, producer_run_id, asset_type, content, project_id
                )
            if producer_role is None:
                raise NovelOSError("producer_run_required", "规划候选必须绑定生产 Agent run")
            if asset_type == "story_arc":
                if cross_check_id is None:
                    if self.agent_contracts.is_strict("cross_consistency"):
                        raise NovelOSError("cross_check_required", "Story Arc 必须绑定 Character/World 交叉审查")
                else:
                    check = self._get(connection, "planning_cross_checks", cross_check_id)
                    self._validate_story_arc_cross_check(connection, project_id, upstream_rows, check)
            elif cross_check_id is not None:
                raise NovelOSError("invalid_cross_check", "只有 Story Arc 可以绑定交叉审查")

            normalized_metadata = metadata or {}
            if asset_type == "direction":
                normalized_metadata = self._validate_direction_author_contract(
                    connection,
                    project_id,
                    producer_run_id,
                    normalized_metadata,
                )
            elif asset_type == "chapter_plan":
                normalized_metadata = self._validate_chapter_soul_contract(
                    connection,
                    project_id,
                    normalized_metadata,
                )
            resource_id, content_digest = self._resource(connection, _require_text(content, "content"))
            normalized_refs = sorted(
                ({"asset_id": str(ref["asset_id"]), "version": int(ref["version"])} for ref in upstream_refs),
                key=lambda ref: ref["asset_id"],
            )
            subject_hash = content_hash(
                _json(
                    {
                        "asset_type": asset_type,
                        "content_hash": content_digest,
                        "metadata": normalized_metadata,
                        "project_id": project_id,
                        "scope_ref": normalized_scope,
                        "upstream_refs": normalized_refs,
                    }
                )
            )
            revision = int(
                connection.execute(
                    "SELECT COALESCE(MAX(revision), 0) + 1 FROM planning_assets WHERE project_id=? AND asset_type=? AND scope_ref=?",
                    (project_id, asset_type, normalized_scope),
                ).fetchone()[0]
            )
            asset_id = _id("planning")
            connection.execute(
                "INSERT INTO planning_assets(id, project_id, asset_type, scope_ref, revision, content_resource_id, subject_hash, producer_role, metadata_json, producer_run_id, cross_check_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (asset_id, project_id, asset_type, normalized_scope, revision, resource_id, subject_hash, producer_role, _json(normalized_metadata), producer_run_id, cross_check_id),
            )
            connection.executemany(
                "INSERT INTO planning_asset_dependencies(asset_id, upstream_asset_id, upstream_version) VALUES (?, ?, ?)",
                [(asset_id, ref["asset_id"], ref["version"]) for ref in normalized_refs],
            )
            return self._planning_asset(connection, asset_id)

    def create_planning_candidate_from_run(
        self,
        project_id: str,
        asset_type: str,
        scope_ref: str,
        upstream_refs: list[dict[str, Any]],
        producer_run_id: str,
        metadata: dict[str, Any] | None = None,
        cross_check_id: str | None = None,
    ) -> dict[str, Any]:
        with self.database.read() as connection:
            _, output = self._completed_agent_output(
                connection, producer_run_id, "planning_candidate"
            )
        if not isinstance(output, str):
            raise NovelOSError(
                "invalid_producer_run",
                "规划 Agent run 输出不是文本候选",
                {"run_id": producer_run_id},
            )
        return self.create_planning_candidate(
            project_id,
            asset_type,
            scope_ref,
            output,
            upstream_refs,
            metadata=metadata,
            producer_run_id=producer_run_id,
            cross_check_id=cross_check_id,
        )

    def get_planning_asset(self, asset_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._planning_asset(connection, asset_id)

    def list_planning_assets(
        self,
        project_id: str,
        asset_type: str | None = None,
        scope_ref: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if asset_type is not None and asset_type not in PLANNING_UPSTREAM_TYPES:
            raise NovelOSError("invalid_argument", "未知 planning asset_type", {"asset_type": asset_type})
        if status is not None and status not in {"candidate", "locked", "stale", "superseded"}:
            raise NovelOSError("invalid_argument", "未知 planning status", {"status": status})
        clauses = ["project_id=?"]
        values: list[Any] = [project_id]
        for column, value in (("asset_type", asset_type), ("scope_ref", scope_ref), ("status", status)):
            if value is not None:
                clauses.append(f"{column}=?")
                values.append(value)
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            rows = connection.execute(
                f"SELECT id FROM planning_assets WHERE {' AND '.join(clauses)} ORDER BY asset_type, scope_ref, revision DESC",
                values,
            ).fetchall()
            return [self._planning_asset(connection, str(row["id"])) for row in rows]

    def lock_planning_asset(
        self, asset_id: str, review_id: str, expected_version: int, trace_id: str
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            asset = self._get(connection, "planning_assets", asset_id)
            self._check_version(asset, expected_version)
            if asset["status"] != "candidate":
                raise NovelOSError("invalid_state", "只有 candidate 规划资产可以锁定", {"status": asset["status"]})
            self._validate_planning_dependencies(connection, asset_id)
            review = self._get(connection, "reviews", review_id)
            if review["subject_type"] != "planning_asset" or review["subject_ref"] != asset_id:
                raise NovelOSError("invalid_review", "Review 不属于当前规划资产")
            if review["subject_hash"] != asset["subject_hash"]:
                raise NovelOSError("hash_mismatch", "Review Hash 与当前规划资产不一致")
            expected_profile = self.agent_contracts.review_profile_for_asset(str(asset["asset_type"]))
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError(
                    "invalid_review_profile",
                    "Review Profile 与规划资产类型不匹配",
                    {"expected": expected_profile},
                )
            if review["verdict"] != "approved" or any(
                item.get("severity") == "blocking" for item in json.loads(review["findings_json"])
            ):
                raise NovelOSError("review_rejected", "Review 未批准规划资产")
            self._validate_authority_trace(
                connection,
                trace_id,
                str(asset["project_id"]),
                review,
                str(asset["producer_run_id"]) if asset["producer_run_id"] else None,
            )
            if asset["asset_type"] == "story_arc":
                self._validate_or_warn_story_arc_cross_check(
                    connection,
                    str(asset["project_id"]),
                    asset_id,
                    trace_id,
                )

            previous = connection.execute(
                "SELECT id FROM planning_assets WHERE project_id=? AND asset_type=? AND scope_ref=? AND status='locked'",
                (asset["project_id"], asset["asset_type"], asset["scope_ref"]),
            ).fetchone()
            if previous is not None:
                previous_id = str(previous["id"])
                connection.execute(
                    "UPDATE planning_assets SET status='superseded', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (previous_id,),
                )
                self._mark_planning_descendants_stale(connection, previous_id)
            connection.execute(
                "UPDATE planning_assets SET status='locked', locked_review_id=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (review_id, asset_id),
            )
            locked = self._planning_asset(connection, asset_id)
            self._record_authority_commit(
                connection,
                trace_id,
                str(asset["project_id"]),
                "planning.lock",
                "planning_asset",
                asset_id,
                str(asset["subject_hash"]),
                review_id,
                asset_id,
            )
            return locked

    def withdraw_planning_candidate(
        self, asset_id: str, trace_id: str, reason: str
    ) -> dict[str, Any]:
        """废弃一个 candidate 规划资产，使其退出诊断视图。

        candidate 没有"被取代"的生命周期终点：锁定只会把旧的 locked 标 superseded，
        探索过程中的中间候选会永久挂着 status='candidate'，污染诊断模式渲染。
        本方法补上这个终点：把 candidate 标 superseded（复用现有状态，不重建表），
        并记 trace step 留痕。只能废弃 candidate，不能动 locked/stale/superseded。
        """
        with self.database.transaction() as connection:
            asset = self._get(connection, "planning_assets", asset_id)
            if asset["status"] != "candidate":
                raise NovelOSError(
                    "invalid_state",
                    "只有 candidate 规划资产可以废弃",
                    {"status": asset["status"]},
                )
            trace = self._get(connection, "traces", _require_text(trace_id, "trace_id"))
            if trace["status"] != "running":
                raise NovelOSError("invalid_state", "已结束的 Trace 不能废弃候选")
            if trace["project_id"] != str(asset["project_id"]):
                raise NovelOSError(
                    "trace_project_mismatch",
                    "废弃候选 Trace 与目标项目不一致",
                )
            connection.execute(
                "UPDATE planning_assets SET status='superseded', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (asset_id,),
            )
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "planning.withdraw",
                "主控智能体",
                "completed",
                [asset_id],
                [],
                {"asset_type": str(asset["asset_type"]), "revision": int(asset["revision"]), "reason": _require_text(reason, "reason")},
            )
            return self._planning_asset(connection, asset_id)

    def extract_decision_points(self, asset_id: str) -> dict[str, Any]:
        """机械读取 candidate 的 metadata.decision_points，供检查点选项呈现。

        本方法不调用 LLM，只做结构化搬运：从 candidate 的 metadata_json 读取
        ``decision_points`` 字段（由生成 Agent 在产出 candidate 时写入），原样返回。
        决策点的内容设计是 strategy/character Agent 的 prompt 职责，不是本方法的职责。
        """
        with self.database.read() as connection:
            asset = self._planning_asset(connection, asset_id)
        if asset["status"] != "candidate":
            raise NovelOSError(
                "invalid_state",
                "只有 candidate 规划资产可提取决策点",
                {"status": asset["status"]},
            )
        metadata = asset.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        decision_points = metadata.get("decision_points")
        if decision_points is None:
            decision_points = []
        if not isinstance(decision_points, list):
            raise NovelOSError(
                "invalid_candidate",
                "decision_points 必须是数组",
                {"actual_type": type(decision_points).__name__},
            )
        return {"asset_id": asset_id, "decision_points": decision_points}

    def create_revision_candidate(
        self,
        project_id: str,
        asset_type: str,
        scope_ref: str,
        content: str,
        upstream_refs: list[dict[str, Any]],
        producer_role: str | None,
        supersedes_candidate_id: str,
        producer_run_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """创建一个修订 candidate 并把指定的旧 candidate 标 superseded。

        用于检查点选项呈现流程：用户在 candidate→lock 之间做完爽点选择题后，
        主控把选择融合进新 candidate，由本方法顶替旧 candidate。
        旧 candidate 必须仍是 candidate 状态（未被 lock/supersede）。
        """
        supersedes_id = _require_text(supersedes_candidate_id, "supersedes_candidate_id")
        with self.database.transaction() as connection:
            old = self._get(connection, "planning_assets", supersedes_id)
            if str(old["project_id"]) != _require_text(project_id, "project_id"):
                raise NovelOSError("invalid_argument", "旧 candidate 不属于当前项目")
            if old["status"] != "candidate":
                raise NovelOSError(
                    "invalid_state",
                    "被顶替的旧 candidate 必须仍是 candidate 状态",
                    {"status": old["status"]},
                )
            if old["asset_type"] != _require_text(asset_type, "asset_type"):
                raise NovelOSError(
                    "invalid_argument",
                    "修订 candidate 必须与旧 candidate 同 asset_type",
                    {"expected": str(old["asset_type"]), "actual": asset_type},
                )
        revision = self.create_planning_candidate(
            project_id,
            asset_type,
            scope_ref,
            content,
            upstream_refs,
            producer_role,
            metadata=metadata,
            producer_run_id=producer_run_id,
        )
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE planning_assets SET status='superseded', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (supersedes_id,),
            )
            if trace_id is not None:
                self._record_trace_step_in_transaction(
                    connection,
                    trace_id,
                    "planning.create_revision",
                    "主控智能体",
                    "completed",
                    [revision["id"]],
                    [supersedes_id],
                    {
                        "asset_type": asset_type,
                        "revision_id": revision["id"],
                        "superseded_id": supersedes_id,
                    },
                )
            return self._planning_asset(connection, revision["id"])

    def upsert_character(
        self,
        project_id: str,
        name: str,
        description: str = "",
        state: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        return self._upsert_described("characters", "character", project_id, name, description, state or {}, expected_version)

    def get_character(self, character_id: str) -> dict[str, Any]:
        return self._get_public("characters", character_id)

    def list_characters(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("characters", "project_id", project_id, "name")

    def upsert_world(
        self,
        project_id: str,
        name: str,
        description: str = "",
        state: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        return self._upsert_described("worlds", "world", project_id, name, description, state or {}, expected_version)

    def get_world(self, world_id: str) -> dict[str, Any]:
        return self._get_public("worlds", world_id)

    def list_worlds(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("worlds", "project_id", project_id, "name")

    def upsert_faction(
        self,
        project_id: str,
        name: str,
        description: str = "",
        state: dict[str, Any] | None = None,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        return self._upsert_described("factions", "faction", project_id, name, description, state or {}, expected_version)

    def get_faction(self, faction_id: str) -> dict[str, Any]:
        return self._get_public("factions", faction_id)

    def list_factions(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("factions", "project_id", project_id, "name")

    def upsert_rule(
        self,
        project_id: str,
        name: str,
        description: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            resource_id, _ = self._resource(connection, _require_text(description, "description"))
            normalized_name = _require_text(name, "name")
            existing = connection.execute(
                "SELECT * FROM rules WHERE project_id=? AND name=?", (project_id, normalized_name)
            ).fetchone()
            if existing:
                self._require_expected_version(existing, expected_version)
                connection.execute(
                    "UPDATE rules SET description_resource_id=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, existing["id"]),
                )
                rule_id = str(existing["id"])
            else:
                rule_id = _id("rule")
                connection.execute(
                    "INSERT INTO rules(id, project_id, name, description_resource_id) VALUES (?, ?, ?, ?)",
                    (rule_id, project_id, normalized_name, resource_id),
                )
            return self._row(self._get(connection, "rules", rule_id))

    def get_rule(self, rule_id: str) -> dict[str, Any]:
        return self._get_public("rules", rule_id)

    def list_rules(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("rules", "project_id", project_id, "name")

    def upsert_timeline(
        self,
        project_id: str,
        label: str,
        sequence: int,
        description: str,
        source_ref: str,
        expected_version: int | None = None,
    ) -> dict[str, Any]:
        if sequence < 0:
            raise NovelOSError("invalid_argument", "sequence 不能小于 0", {"field": "sequence"})
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            resource_id, _ = self._resource(connection, _require_text(description, "description"))
            normalized_label = _require_text(label, "label")
            existing = connection.execute(
                "SELECT * FROM timelines WHERE project_id=? AND sequence=? AND label=?",
                (project_id, sequence, normalized_label),
            ).fetchone()
            if existing:
                self._require_expected_version(existing, expected_version)
                connection.execute(
                    "UPDATE timelines SET description_resource_id=?, source_ref=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, _require_text(source_ref, "source_ref"), existing["id"]),
                )
                timeline_id = str(existing["id"])
            else:
                timeline_id = _id("timeline")
                connection.execute(
                    "INSERT INTO timelines(id, project_id, label, sequence, description_resource_id, source_ref) VALUES (?, ?, ?, ?, ?, ?)",
                    (timeline_id, project_id, normalized_label, sequence, resource_id, _require_text(source_ref, "source_ref")),
                )
            return self._row(self._get(connection, "timelines", timeline_id))

    def get_timeline(self, timeline_id: str) -> dict[str, Any]:
        return self._get_public("timelines", timeline_id)

    def list_timelines(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("timelines", "project_id", project_id, "sequence")
