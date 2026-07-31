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
from novelos_mcp.hashing import content_hash
from novelos_mcp.knowledge import KnowledgeStore
from novelos_mcp.storage import Database


def _id(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _json(value: dict[str, Any] | list[Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _require_text(value: str, field: str) -> str:
    if not isinstance(value, str):
        raise NovelOSError("invalid_argument", f"{field} 必须是字符串", {"field": field})
    normalized = value.strip()
    if not normalized:
        raise NovelOSError("invalid_argument", f"{field} 不能为空", {"field": field})
    return normalized


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise NovelOSError("invalid_argument", f"{field} 必须是 sha256 Hash")
    return value


PLANNING_UPSTREAM_TYPES: dict[str, frozenset[str]] = {
    "direction": frozenset(),
    "architecture": frozenset({"direction"}),
    "strategy": frozenset({"direction", "architecture"}),
    "character_contract": frozenset({"architecture", "strategy"}),
    "world_contract": frozenset({"architecture", "strategy"}),
    "story_arc": frozenset({"strategy", "character_contract", "world_contract"}),
    "volume_outline": frozenset({"story_arc"}),
    "chapter_plan": frozenset({"volume_outline"}),
}

PLANNING_PRODUCERS = {
    "direction": "Direction Agent",
    "architecture": "Architecture Agent",
    "strategy": "Strategy Agent",
    "character_contract": "Character Agent",
    "world_contract": "World Agent",
    "story_arc": "Story Arc Agent",
    "volume_outline": "Volume Planner",
    "chapter_plan": "Chapter Planner",
}

PLANNING_REVIEW_PROFILES = {
    asset_type: f"planning-{asset_type.replace('_', '-')}" for asset_type in PLANNING_UPSTREAM_TYPES
}

CONTINUITY_OWNERS = {"canon", "expectation", "relationship", "arc"}
ENTITY_AUTHORITY_ASSETS = {
    "character": {"character_contract"},
    "world": {"world_contract"},
    "faction": {"world_contract"},
    "rule": {"world_contract"},
    "timeline": {"world_contract", "story_arc"},
}


class NovelOSService:
    def __init__(
        self,
        database_path: str | Path,
        seed_database_path: str | Path | None = None,
        catalog_path: str | Path | None = None,
        agent_contract_path: str | Path | None = None,
        seed_inventory_path: str | Path | None = None,
    ) -> None:
        self.database = Database(database_path)
        self.database.initialize()
        self.knowledge = KnowledgeStore(seed_database_path, seed_inventory_path)
        self.catalog = CatalogStore(catalog_path)
        self.agent_contracts = AgentContractStore(agent_contract_path)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        for key in tuple(result):
            if key.endswith("_json"):
                result[key[:-5]] = json.loads(result.pop(key))
        if "content_resource_id" in result:
            result["resource_ref"] = f"novelos://resource/{result.pop('content_resource_id')}"
        if "candidate_resource_id" in result:
            result["candidate_ref"] = f"novelos://resource/{result.pop('candidate_resource_id')}"
        if "result_resource_id" in result:
            result["result_ref"] = f"novelos://resource/{result.pop('result_resource_id')}"
        if "assessment_resource_id" in result:
            assessment_resource_id = result.pop("assessment_resource_id")
            result["assessment_ref"] = (
                f"novelos://resource/{assessment_resource_id}" if assessment_resource_id else None
            )
        if "output_resource_id" in result:
            output_resource_id = result.pop("output_resource_id")
            result["output_ref"] = f"novelos://resource/{output_resource_id}" if output_resource_id else None
        if "mutation_resource_id" in result:
            result["mutation_ref"] = f"novelos://resource/{result.pop('mutation_resource_id')}"
        if "description_resource_id" in result:
            description_resource_id = result.pop("description_resource_id")
            result["description_ref"] = (
                f"novelos://resource/{description_resource_id}" if description_resource_id else None
            )
        return result

    @staticmethod
    def _get(connection: sqlite3.Connection, table: str, item_id: str) -> sqlite3.Row:
        row = connection.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise NovelOSError("not_found", f"{table} 记录不存在", {"id": item_id})
        return row

    @staticmethod
    def _resource(connection: sqlite3.Connection, content: str, media_type: str = "text/markdown") -> tuple[str, str]:
        digest = content_hash(content)
        row = connection.execute(
            "SELECT id FROM resources WHERE content_hash = ? AND media_type = ?",
            (digest, media_type),
        ).fetchone()
        if row:
            return str(row["id"]), digest
        resource_id = _id("resource")
        connection.execute(
            "INSERT INTO resources(id, media_type, content, content_hash) VALUES (?, ?, ?, ?)",
            (resource_id, media_type, content.encode("utf-8"), digest),
        )
        return resource_id, digest

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
                "Main Agent",
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
                "Main Agent",
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

    def search_skill_catalog(
        self,
        stage: str | None = None,
        asset: str | None = None,
        capability: str | None = None,
        genres: list[str] | None = None,
        lifecycle: str = "active",
        scope: str | None = None,
    ) -> dict[str, Any]:
        return self.catalog.search(stage, asset, capability, genres, lifecycle, scope)

    def get_skill_catalog(self, name: str) -> dict[str, Any]:
        return self.catalog.get(name)

    def validate_skill_selection(
        self,
        selected_names: list[str],
        candidate_names: list[str],
        snapshot_hash: str,
    ) -> dict[str, Any]:
        return self.catalog.validate_selection(selected_names, candidate_names, snapshot_hash)

    def validate_skill_output(self, name: str, payload: Any) -> dict[str, Any]:
        return self.catalog.validate_output(name, payload)

    def validate_skill_input(self, name: str, payload: Any) -> dict[str, Any]:
        return self.catalog.validate_input(name, payload)

    def get_review_catalog_route(self, profile: str) -> dict[str, Any]:
        package_names = self.agent_contracts.review_packages(profile)
        packages: list[dict[str, Any]] = []
        for name in package_names:
            pkg_info = self.catalog.get(name)
            if pkg_info["metadata"].get("lifecycle") != "active":
                raise NovelOSError(
                    "invalid_review_profile",
                    "Review Profile 包含非 active Catalog 包",
                    {"profile": profile, "name": name},
                )
            packages.append({
                "name": name,
                "package_hash": pkg_info["package_hash"],
                "resources": pkg_info["resources"],
            })
        return {
            "profile": profile,
            "packages": packages,
        }

    def validate_contract_inputs(self, package_name: str, project_id: str, bindings: list[dict[str, Any]]) -> dict[str, Any]:
        if not project_id or not isinstance(project_id, str):
            raise NovelOSError("invalid_argument", "project_id 必须是非空字符串", {"project_id": project_id})

        package = self.catalog.get(package_name)
        resources = package.get("resources", {})
        if "contract" not in resources:
            raise NovelOSError("invalid_contract", "Catalog 包不包含 contract 资源", {"package_name": package_name})

        contract_text = self.catalog.get_resource(package_name, "contract")
        try:
            contract_data = yaml.safe_load(contract_text)
        except Exception as exc:
            raise NovelOSError("invalid_contract", "无法解析 contract.yaml", {"package_name": package_name}) from exc

        expected_inputs = contract_data.get("inputs", [])
        if not isinstance(expected_inputs, list):
            expected_inputs = []

        cardinality_map = {}
        for item in expected_inputs:
            c_name = item.get("contract")
            c_card = item.get("cardinality")
            if c_name and c_card:
                cardinality_map[c_name] = c_card

        if not isinstance(bindings, list):
            raise NovelOSError("invalid_argument", "bindings 必须是数组", {"package_name": package_name})

        verified_bindings = []
        counts_by_contract = Counter()
        seen_refs = set()

        with self.database.read() as connection:
            for b in bindings:
                if not isinstance(b, dict):
                    raise NovelOSError("invalid_argument", "binding 必须是对象", {"package_name": package_name})

                allowed_fields = {"contract", "subject_ref", "version", "subject_hash", "status"}
                if any(k not in allowed_fields for k in b):
                    raise NovelOSError("invalid_contract_binding", "binding 包含未知字段", {"binding": b})

                c_type = b.get("contract")
                ref = b.get("subject_ref")
                version = b.get("version")
                s_hash = b.get("subject_hash")
                status = b.get("status")

                if not c_type or not ref or version is None or not s_hash or not status:
                    raise NovelOSError("invalid_contract_binding", "binding 缺少必填字段", {"binding": b})

                if type(version) is bool or not isinstance(version, int):
                    raise NovelOSError("invalid_contract_binding", "version 必须是整数", {"binding": b})
                if type(s_hash) is not str or type(status) is not str or type(c_type) is not str or type(ref) is not str:
                    raise NovelOSError("invalid_contract_binding", "binding 字段类型错误", {"binding": b})

                if ref in seen_refs:
                    raise NovelOSError("contract_validation_failed", f"重复的引用: {ref}", {"subject_ref": ref})
                seen_refs.add(ref)

                if c_type in {"direction", "architecture", "strategy", "character_contract", "world_contract", "story_arc", "volume_outline", "chapter_plan"}:
                    row = connection.execute(
                        "SELECT id, asset_type, version, subject_hash, status, project_id FROM planning_assets WHERE id = ?",
                        (ref,),
                    ).fetchone()
                    if not row:
                        raise NovelOSError("contract_validation_failed", f"找不到规划资产: {ref}", {"subject_ref": ref})
                    if row["project_id"] != project_id:
                        raise NovelOSError("contract_validation_failed", "跨项目引用资产", {"expected_project": project_id, "actual_project": row["project_id"]})
                    if row["asset_type"] != c_type:
                        raise NovelOSError("contract_validation_failed", "资产类型不匹配", {"expected": c_type, "actual": row["asset_type"]})
                    if row["status"] in ("stale", "superseded") or status in ("stale", "superseded"):
                        raise NovelOSError("contract_validation_failed", f"引用的规划资产已失效 ({row['status']})，必须使用最新 locked 资产", {"subject_ref": ref, "status": row["status"]})
                    if row["status"] != "locked" or status != "locked":
                        raise NovelOSError("contract_validation_failed", "规划资产必须处于 locked 状态", {"subject_ref": ref, "status": row["status"]})
                    if row["version"] != version:
                        raise NovelOSError("contract_validation_failed", "资产版本漂移", {"expected": version, "actual": row["version"]})
                    if row["subject_hash"] != s_hash:
                        raise NovelOSError("contract_validation_failed", "资产 Hash 漂移", {"expected": s_hash, "actual": row["subject_hash"]})

                elif c_type == "chapter_draft":
                    row = connection.execute(
                        "SELECT chapters.id, chapters.version, chapters.subject_hash, chapters.status, books.project_id FROM chapters JOIN volumes ON chapters.volume_id = volumes.id JOIN books ON volumes.book_id = books.id WHERE chapters.id = ?",
                        (ref,),
                    ).fetchone()
                    if not row:
                        raise NovelOSError("contract_validation_failed", f"找不到章节: {ref}", {"subject_ref": ref})
                    if row["project_id"] != project_id:
                        raise NovelOSError("contract_validation_failed", "跨项目引用章节", {"expected_project": project_id, "actual_project": row["project_id"]})
                    if row["status"] != "draft" or status != "draft":
                        raise NovelOSError("contract_validation_failed", "章节必须处于 draft 状态", {"subject_ref": ref, "status": row["status"]})
                    if row["version"] != version:
                        raise NovelOSError("contract_validation_failed", "章节版本漂移", {"expected": version, "actual": row["version"]})
                    if row["subject_hash"] != s_hash:
                        raise NovelOSError("contract_validation_failed", "章节 Hash 漂移", {"expected": s_hash, "actual": row["subject_hash"]})
                else:
                    raise NovelOSError("invalid_contract", f"不支持的 contract 输入类型: {c_type}", {"contract": c_type})

                counts_by_contract[c_type] += 1
                verified_bindings.append({
                    "contract": c_type,
                    "subject_ref": ref,
                    "version": version,
                    "subject_hash": s_hash,
                    "status": row["status"],
                })

        for req_type, expr in cardinality_map.items():
            count = counts_by_contract[req_type]
            valid = False
            if expr == "one" and count == 1:
                valid = True
            elif expr == "zero_or_one" and count in (0, 1):
                valid = True
            elif expr == "one_or_more" and count >= 1:
                valid = True
            elif expr == "zero_or_more" and count >= 0:
                valid = True
            elif expr == "exactly_two" and count == 2:
                valid = True
            elif expr == "three_or_more" and count >= 3:
                valid = True

            if not valid:
                raise NovelOSError(
                    "contract_validation_failed",
                    f"输入数量不符合 cardinality 要求: {req_type} 要求 {expr}, 实际得到 {count}",
                    {"contract": req_type, "cardinality": expr, "actual_count": count},
                )

        for b_type in counts_by_contract:
            if b_type not in cardinality_map:
                raise NovelOSError("contract_validation_failed", f"未在 Contract 中声明的输入类型: {b_type}", {"contract": b_type})

        contract_hash = hashlib.sha256(contract_text.encode("utf-8")).hexdigest()
        package_hash = package.get("package_hash", "")

        verified_bindings_sorted = sorted(verified_bindings, key=lambda x: (x["contract"], x["subject_ref"]))
        snapshot_payload = {
            "package_name": package_name,
            "package_hash": package_hash,
            "contract_hash": f"sha256:{contract_hash}",
            "project_id": project_id,
            "verified_bindings": verified_bindings_sorted,
        }
        payload_bytes = json.dumps(snapshot_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        snapshot_hash = f"sha256:{hashlib.sha256(payload_bytes).hexdigest()}"

        return {
            "valid": True,
            "package_name": package_name,
            "project_id": project_id,
            "verified_bindings": verified_bindings_sorted,
            "contract_snapshot_hash": snapshot_hash,
        }

    def create_project(self, name: str, description: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        project_id = _id("project")
        with self.database.transaction() as connection:
            connection.execute(
                "INSERT INTO projects(id, name, description, metadata_json) VALUES (?, ?, ?, ?)",
                (project_id, _require_text(name, "name"), description, _json(metadata or {})),
            )
            return self._row(self._get(connection, "projects", project_id))

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._row(self._get(connection, "projects", project_id))

    def list_projects(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        self._validate_page(limit, offset)
        with self.database.read() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY created_at, id LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [self._row(row) for row in rows]

    def update_project(
        self,
        project_id: str,
        expected_version: int,
        name: str | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            current = self._get(connection, "projects", project_id)
            self._check_version(current, expected_version)
            connection.execute(
                "UPDATE projects SET name=?, description=?, metadata_json=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    _require_text(name, "name") if name is not None else current["name"],
                    description if description is not None else current["description"],
                    _json(metadata) if metadata is not None else current["metadata_json"],
                    project_id,
                ),
            )
            return self._row(self._get(connection, "projects", project_id))

    def create_book(self, project_id: str, title: str, description: str = "") -> dict[str, Any]:
        return self._create_child("books", "book", "project_id", project_id, {"title": _require_text(title, "title"), "description": description})

    def get_book(self, book_id: str) -> dict[str, Any]:
        return self._get_public("books", book_id)

    def list_books(self, project_id: str) -> list[dict[str, Any]]:
        return self._list_children("books", "project_id", project_id)

    def create_volume(self, book_id: str, number: int, title: str, summary: str = "") -> dict[str, Any]:
        if number < 1:
            raise NovelOSError("invalid_argument", "number 必须大于 0", {"field": "number"})
        return self._create_child("volumes", "volume", "book_id", book_id, {"number": number, "title": _require_text(title, "title"), "summary": summary})

    def get_volume(self, volume_id: str) -> dict[str, Any]:
        return self._get_public("volumes", volume_id)

    def list_volumes(self, book_id: str) -> list[dict[str, Any]]:
        return self._list_children("volumes", "book_id", book_id, "number")

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
            raise NovelOSError("producer_run_required", "绑定 Chapter Plan 的完整章节必须来自 Writer Agent run")
        with self.database.transaction() as connection:
            self._get(connection, "volumes", volume_id)
            if producer_run_id is not None:
                self._validate_chapter_producer_run(connection, producer_run_id, content)
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
            expected_profile = f"entity-{mutation['entity_type']}"
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
            expected_profile = self.agent_contracts.config["cross_consistency_gate"]["profile"]
            if review["reviewer_profile"] != expected_profile:
                raise NovelOSError("invalid_review_profile", "交叉审查 Profile 不匹配", {"expected": expected_profile})
            if not review["reviewer_run_id"]:
                raise NovelOSError("reviewer_run_required", "交叉审查必须绑定独立 Review Agent run")
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
                    connection, producer_run_id, asset_type, content
                )
            if producer_role is None:
                raise NovelOSError("producer_run_required", "规划候选必须绑定生产 Agent run")
            if asset_type == "story_arc":
                if cross_check_id is None:
                    raise NovelOSError("cross_check_required", "Story Arc 必须绑定 Character/World 交叉审查")
                check = self._get(connection, "planning_cross_checks", cross_check_id)
                self._validate_story_arc_cross_check(connection, project_id, upstream_rows, check)
            elif cross_check_id is not None:
                raise NovelOSError("invalid_cross_check", "只有 Story Arc 可以绑定交叉审查")

            resource_id, content_digest = self._resource(connection, _require_text(content, "content"))
            normalized_metadata = metadata or {}
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
            if review["reviewer_profile"] != PLANNING_REVIEW_PROFILES[asset["asset_type"]]:
                raise NovelOSError(
                    "invalid_review_profile",
                    "Review Profile 与规划资产类型不匹配",
                    {"expected": PLANNING_REVIEW_PROFILES[asset["asset_type"]]},
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
                "Main Agent",
                "completed",
                [asset_id],
                [],
                {"asset_type": str(asset["asset_type"]), "revision": int(asset["revision"]), "reason": _require_text(reason, "reason")},
            )
            return self._planning_asset(connection, asset_id)

    def record_review(
        self,
        subject_type: str,
        subject_ref: str,
        subject_hash: str,
        verdict: str,
        findings: list[dict[str, Any]],
        reviewer_profile: str,
        evidence_refs: list[str] | None = None,
        reviewer_run_id: str | None = None,
        assessment: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if verdict not in {"approved", "rejected"}:
            raise NovelOSError("invalid_argument", "verdict 非法", {"verdict": verdict})
        self._validate_review_findings(findings)
        normalized_evidence = evidence_refs or []
        if len(normalized_evidence) != len(set(normalized_evidence)) or any(
            not isinstance(ref, str) or not ref.strip() for ref in normalized_evidence
        ):
            raise NovelOSError("invalid_review", "Review evidence_refs 必须是唯一的非空字符串")
        blocking = any(item.get("severity") == "blocking" for item in findings)
        if blocking and verdict == "approved":
            raise NovelOSError("invalid_review", "存在 blocking finding 时不能 approved")
        if subject_type == "review_subject":
            if not isinstance(assessment, dict) or not assessment:
                raise NovelOSError("invalid_review", "评测 Review 必须包含非空 assessment")
        elif assessment is not None:
            raise NovelOSError("invalid_review", "普通权威 Review 不接受 assessment")
        review_id = _id("review")
        with self.database.transaction() as connection:
            if subject_type == "chapter":
                chapter = self._get(connection, "chapters", subject_ref)
                if chapter["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与当前章节不一致")
            elif subject_type == "continuity_candidate_set":
                candidate_set = self._get(connection, "continuity_candidate_sets", subject_ref)
                if candidate_set["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与连续性候选集不一致")
            elif subject_type == "planning_asset":
                asset = self._get(connection, "planning_assets", subject_ref)
                if asset["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与规划资产不一致")
            elif subject_type == "entity_mutation":
                mutation = self._get(connection, "entity_mutations", subject_ref)
                if mutation["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与 entity mutation 不一致")
            elif subject_type == "planning_cross_check":
                cross_check = self._get(connection, "planning_cross_checks", subject_ref)
                if cross_check["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与交叉审查不一致")
            elif subject_type == "review_subject":
                review_subject = self._get(connection, "review_subjects", subject_ref)
                if review_subject["subject_hash"] != subject_hash:
                    raise NovelOSError("hash_mismatch", "Review Hash 与不可变评测 subject 不一致")
                if review_subject["reviewer_profile"] != reviewer_profile:
                    raise NovelOSError("invalid_review_profile", "Review Profile 与评测 subject 不一致")
                if json.loads(review_subject["evidence_refs_json"]) != normalized_evidence:
                    raise NovelOSError("invalid_review", "Review evidence 与评测 subject 不一致")
            else:
                raise NovelOSError("invalid_review", "不支持的 Review subject_type", {"subject_type": subject_type})
            if reviewer_run_id is not None:
                self._validate_reviewer_run(
                    connection,
                    reviewer_run_id,
                    subject_type,
                    subject_ref,
                    subject_hash,
                    verdict,
                    findings,
                    reviewer_profile,
                    normalized_evidence,
                    assessment,
                )
            assessment_resource_id: str | None = None
            if assessment is not None:
                assessment_resource_id, _ = self._resource(
                    connection, _json(assessment), "application/json"
                )
            connection.execute(
                "INSERT INTO reviews(id, subject_type, subject_ref, subject_hash, verdict, findings_json, reviewer_profile, evidence_refs_json, reviewer_run_id, assessment_resource_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    review_id,
                    _require_text(subject_type, "subject_type"),
                    _require_text(subject_ref, "subject_ref"),
                    subject_hash,
                    verdict,
                    _json(findings),
                    _require_text(reviewer_profile, "reviewer_profile"),
                    _json(normalized_evidence),
                    reviewer_run_id,
                    assessment_resource_id,
                ),
            )
            return self._row(self._get(connection, "reviews", review_id))

    def get_review(self, review_id: str) -> dict[str, Any]:
        return self._get_public("reviews", review_id)

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
            if review["reviewer_profile"] != "prose-v1":
                raise NovelOSError("invalid_review_profile", "接受章节必须使用 prose-v1 Profile", {"reviewer_profile": review["reviewer_profile"]})
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
            if review["reviewer_profile"] != "continuity-v1":
                raise NovelOSError("invalid_review_profile", "晋升连续性候选必须使用 continuity-v1 Profile", {"reviewer_profile": review["reviewer_profile"]})
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

    def start_trace(
        self,
        operation: str,
        project_id: str | None = None,
        subject_ref: str | None = None,
    ) -> dict[str, Any]:
        trace_id = _id("trace")
        with self.database.transaction() as connection:
            if project_id is not None:
                self._get(connection, "projects", project_id)
            connection.execute(
                "INSERT INTO traces(id, project_id, operation, subject_ref) VALUES (?, ?, ?, ?)",
                (trace_id, project_id, _require_text(operation, "operation"), subject_ref),
            )
            return self._row(self._get(connection, "traces", trace_id))

    def start_agent_run(
        self,
        trace_id: str,
        role_id: str,
        input_bindings: dict[str, Any],
        isolation_evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        role = self.agent_contracts.get(role_id)
        if role["lifecycle"] != "temporary" or not role["must_destroy"]:
            raise NovelOSError("invalid_agent_role", "只有临时业务 Agent 可以创建 run", {"role_id": role_id})
        input_refs = self.agent_contracts.validate_inputs(role_id, input_bindings)
        self.agent_contracts.validate_spawn(role_id, input_bindings)
        normalized_evidence = self._normalize_isolation_evidence(isolation_evidence)
        with self.database.transaction() as connection:
            trace = self._get(connection, "traces", trace_id)
            if trace["status"] != "running":
                raise NovelOSError("invalid_state", "已结束的 Trace 不能创建 Agent run")
            run_id = _id("agent-run")
            context_id = _id("agent-context")
            connection.execute(
                "INSERT INTO agent_runs(id, trace_id, role_id, display_name, kind, context_id, input_bindings_json, input_refs_json, isolation_evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    trace_id,
                    role_id,
                    role["display_name"],
                    role["kind"],
                    context_id,
                    _json(input_bindings),
                    _json(input_refs),
                    normalized_evidence,
                ),
            )
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "agent.spawn",
                "Main Agent",
                "completed",
                input_refs,
                [run_id],
                {"role_id": role_id, "context_id": context_id},
            )
            return self._agent_run(connection, run_id)

    def finish_agent_run(
        self,
        run_id: str,
        status: str,
        output_type: str | None = None,
        output: Any | None = None,
        change_proposals: list[dict[str, Any]] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"completed", "failed", "timed_out"}:
            raise NovelOSError("invalid_argument", "Agent run 结束状态非法", {"status": status})
        proposals = change_proposals or []
        with self.database.transaction() as connection:
            run = self._get(connection, "agent_runs", run_id)
            if run["status"] != "running":
                raise NovelOSError("invalid_state", "Agent run 已结束", {"status": run["status"]})
            role = self.agent_contracts.get(str(run["role_id"]))
            self.agent_contracts.validate_change_proposals_for_role(str(run["role_id"]), proposals)
            self._validate_change_proposal_targets(connection, run, proposals)
            output_resource_id: str | None = None
            output_ref: str | None = None
            if status == "completed":
                if output_type not in role["output_types"]:
                    raise NovelOSError(
                        "invalid_agent_result",
                        "Agent output_type 不在角色契约内",
                        {"role_id": run["role_id"], "output_type": output_type},
                    )
                if isinstance(output, str):
                    output_resource_id, _ = self._resource(connection, _require_text(output, "output"))
                elif isinstance(output, (dict, list)):
                    output_resource_id, _ = self._resource(connection, _json(output), "application/json")
                else:
                    raise NovelOSError("invalid_agent_result", "完成的 Agent run 必须返回字符串、对象或数组")
                output_ref = f"novelos://resource/{output_resource_id}"
                normalized_error = None
            else:
                if output_type is not None or output is not None or proposals:
                    raise NovelOSError("invalid_agent_result", "失败或超时的 Agent run 不得返回部分结果")
                normalized_error = _require_text(error or "", "error")
                output_type = None
            input_refs = json.loads(run["input_refs_json"])
            result = {
                "role": run["role_id"],
                "run_id": run_id,
                "status": status,
                "input_refs": input_refs,
                "output_type": output_type,
                "output_ref": output_ref,
                "change_proposals": proposals,
                "error": normalized_error,
            }
            self.agent_contracts.validate_result(result)
            result_resource_id, _ = self._resource(connection, _json(result), "application/json")
            connection.execute(
                "UPDATE agent_runs SET status=?, output_type=?, output_resource_id=?, result_resource_id=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, output_type, output_resource_id, result_resource_id, normalized_error, run_id),
            )
            self._record_trace_step_in_transaction(
                connection,
                str(run["trace_id"]),
                "agent.destroy",
                "Main Agent",
                "completed" if status == "completed" else "failed",
                [run_id],
                [f"novelos://resource/{result_resource_id}"],
                {"role_id": run["role_id"], "outcome": status},
            )
            return self._agent_run(connection, run_id)

    def get_agent_run(self, run_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._agent_run(connection, run_id)

    def list_agent_runs(self, trace_id: str) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            self._get(connection, "traces", trace_id)
            rows = connection.execute(
                "SELECT id FROM agent_runs WHERE trace_id=? ORDER BY created_at, id", (trace_id,)
            ).fetchall()
            return [self._agent_run(connection, str(row["id"])) for row in rows]

    def record_trace_step(
        self,
        trace_id: str,
        step_type: str,
        actor: str,
        status: str,
        input_refs: list[str] | None = None,
        output_refs: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"started", "completed", "failed"}:
            raise NovelOSError("invalid_argument", "Trace step status 非法", {"status": status})
        inputs = input_refs or []
        outputs = output_refs or []
        if any(not isinstance(value, str) or not value.strip() for value in [*inputs, *outputs]):
            raise NovelOSError("invalid_argument", "Trace refs 必须是非空字符串")
        with self.database.transaction() as connection:
            return self._record_trace_step_in_transaction(
                connection, trace_id, step_type, actor, status, inputs, outputs, details or {}
            )

    def finish_trace(self, trace_id: str, status: str) -> dict[str, Any]:
        if status not in {"completed", "failed"}:
            raise NovelOSError("invalid_argument", "Trace 结束状态必须为 completed 或 failed")
        with self.database.transaction() as connection:
            trace = self._get(connection, "traces", trace_id)
            if trace["status"] != "running":
                raise NovelOSError("invalid_state", "Trace 已结束")
            active = connection.execute(
                "SELECT id FROM agent_runs WHERE trace_id=? AND status='running' ORDER BY id", (trace_id,)
            ).fetchall()
            if active:
                raise NovelOSError(
                    "active_agent_runs",
                    "存在未销毁的临时 Agent，不能结束 Trace",
                    {"run_ids": [row["id"] for row in active]},
                )
            connection.execute(
                "UPDATE traces SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, trace_id)
            )
            return self._row(self._get(connection, "traces", trace_id))

    def get_trace(self, trace_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            trace = self._row(self._get(connection, "traces", trace_id))
            steps = connection.execute(
                "SELECT * FROM trace_steps WHERE trace_id=? ORDER BY sequence", (trace_id,)
            ).fetchall()
            commits = connection.execute(
                "SELECT * FROM authority_commits WHERE trace_id=? ORDER BY created_at, id", (trace_id,)
            ).fetchall()
        trace["steps"] = [self._row(row) for row in steps]
        trace["authority_commits"] = [self._row(row) for row in commits]
        trace["agent_runs"] = self.list_agent_runs(trace_id)
        return trace

    def audit_authority_trace(self, project_id: str) -> dict[str, Any]:
        expected_queries = (
            (
                "planning.lock",
                "planning_asset",
                "SELECT id, subject_hash, locked_review_id AS review_id FROM planning_assets "
                "WHERE project_id=? AND locked_review_id IS NOT NULL",
            ),
            (
                "planning.cross_check.approve",
                "planning_cross_check",
                "SELECT id, subject_hash, review_id FROM planning_cross_checks "
                "WHERE project_id=? AND status='approved'",
            ),
            (
                "chapter.accept",
                "chapter",
                "SELECT chapters.id, chapters.subject_hash, authority_commits.review_id "
                "FROM chapters JOIN volumes ON volumes.id=chapters.volume_id "
                "JOIN books ON books.id=volumes.book_id "
                "LEFT JOIN authority_commits ON authority_commits.action='chapter.accept' "
                "AND authority_commits.subject_ref=chapters.id "
                "WHERE books.project_id=? AND chapters.status IN ('accepted','superseded')",
            ),
            (
                "entity.commit",
                "entity_mutation",
                "SELECT id, subject_hash, applied_review_id AS review_id FROM entity_mutations "
                "WHERE project_id=? AND status='applied'",
            ),
            (
                "continuity.promote",
                "continuity_candidate_set",
                "SELECT continuity_candidate_sets.id, continuity_candidate_sets.subject_hash, "
                "chapter_completion_checkpoints.review_id FROM continuity_candidate_sets "
                "JOIN chapter_completion_checkpoints "
                "ON chapter_completion_checkpoints.candidate_set_id=continuity_candidate_sets.id "
                "WHERE continuity_candidate_sets.project_id=? AND continuity_candidate_sets.status='promoted'",
            ),
        )
        issues: list[dict[str, Any]] = []
        expected: list[dict[str, str]] = []
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            for action, subject_type, query in expected_queries:
                for row in connection.execute(query, (project_id,)).fetchall():
                    expected.append(
                        {
                            "action": action,
                            "subject_type": subject_type,
                            "subject_ref": str(row["id"]),
                            "subject_hash": str(row["subject_hash"]),
                            "review_id": str(row["review_id"]) if row["review_id"] else "",
                        }
                    )
            commits = connection.execute(
                "SELECT * FROM authority_commits WHERE project_id=? ORDER BY action, subject_ref",
                (project_id,),
            ).fetchall()
            commit_index = {(str(row["action"]), str(row["subject_ref"])): row for row in commits}
            for item in expected:
                key = (item["action"], item["subject_ref"])
                commit = commit_index.get(key)
                if commit is None:
                    issues.append({"code": "missing_commit", **item})
                    continue
                for field in ("subject_type", "subject_hash", "review_id"):
                    if str(commit[field]) != item[field]:
                        issues.append(
                            {
                                "code": "commit_mismatch",
                                "action": item["action"],
                                "subject_ref": item["subject_ref"],
                                "field": field,
                                "expected": item[field],
                                "actual": str(commit[field]),
                            }
                        )
                trace = self._get(connection, "traces", str(commit["trace_id"]))
                review = self._get(connection, "reviews", str(commit["review_id"]))
                reviewer_run_id = review["reviewer_run_id"]
                reviewer = (
                    self._get(connection, "agent_runs", str(reviewer_run_id))
                    if reviewer_run_id
                    else None
                )
                if (
                    trace["project_id"] != project_id
                    or not reviewer_run_id
                    or review["subject_type"] != item["subject_type"]
                    or review["subject_ref"] != item["subject_ref"]
                    or review["subject_hash"] != item["subject_hash"]
                    or review["verdict"] != "approved"
                    or reviewer is None
                    or reviewer["trace_id"] != commit["trace_id"]
                    or reviewer["role_id"] != "review_agent"
                    or reviewer["status"] != "completed"
                ):
                    issues.append(
                        {
                            "code": "trace_review_mismatch",
                            "action": item["action"],
                            "subject_ref": item["subject_ref"],
                        }
                    )
                steps = connection.execute(
                    "SELECT details_json FROM trace_steps WHERE trace_id=? AND step_type=? AND status='completed'",
                    (commit["trace_id"], commit["action"]),
                ).fetchall()
                if not any(
                    json.loads(row["details_json"]).get("authority_commit_id") == commit["id"]
                    for row in steps
                ):
                    issues.append(
                        {
                            "code": "missing_trace_step",
                            "action": item["action"],
                            "subject_ref": item["subject_ref"],
                        }
                    )
            expected_keys = {(item["action"], item["subject_ref"]) for item in expected}
            for key, commit in commit_index.items():
                if key not in expected_keys:
                    issues.append(
                        {
                            "code": "orphan_commit",
                            "action": str(commit["action"]),
                            "subject_ref": str(commit["subject_ref"]),
                        }
                    )
        by_action: dict[str, int] = {}
        for item in expected:
            by_action[item["action"]] = by_action.get(item["action"], 0) + 1
        return {
            "project_id": project_id,
            "verified": not issues,
            "authority_count": len(expected),
            "commit_count": len(commits),
            "by_action": by_action,
            "issues": issues,
        }

    @staticmethod
    def _normalize_isolation_evidence(evidence: dict[str, Any] | None) -> str | None:
        """归一化隔离执行凭据。

        凭据用于在权威提交（lock/accept/promote）路径证明 producer/reviewer run
        来自独立的 sub-agent 而非 Main Agent 自审。这是声明性证明（非密码学证明）：
        真实隔离仍由 Main Agent 用独立 Codex Task 创建 sub-agent 兑现。存为 JSON 文本。
        """
        if evidence is None:
            return None
        if not isinstance(evidence, dict) or not evidence:
            raise NovelOSError(
                "invalid_isolation_evidence",
                "isolation_evidence 必须是非空对象",
            )
        normalized: dict[str, Any] = {}
        for key in sorted(evidence):
            value = evidence[key]
            if not isinstance(key, str) or not key.strip():
                raise NovelOSError("invalid_isolation_evidence", "isolation_evidence 键必须是非空字符串")
            if not isinstance(value, (str, int, float, bool)) or (isinstance(value, str) and not value.strip()):
                raise NovelOSError("invalid_isolation_evidence", "isolation_evidence 值必须是非空标量")
            normalized[key] = value
        if "source" not in normalized:
            raise NovelOSError("invalid_isolation_evidence", "isolation_evidence 必须包含 source 字段")
        return _json(normalized)

    @staticmethod
    def _decode_isolation_evidence(raw: str | None) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            value = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _validate_continuity_candidates(candidates: list[dict[str, Any]]) -> None:
        required = {
            "fact": {"fact_type", "subject", "description"},
            "narrative_promise": {"key", "description", "status"},
            "expectation": {"key", "description", "status"},
            "relationship": {"subject_ref", "object_ref", "state"},
            "arc": {"arc_ref", "state"},
        }
        allowed_status = {
            "narrative_promise": {"open", "resolved", "broken"},
            "expectation": {"open", "met", "abandoned"},
        }
        for index, candidate in enumerate(candidates):
            candidate_type = candidate.get("type")
            if candidate_type not in required:
                raise NovelOSError("invalid_candidate", "未知连续性候选类型", {"index": index, "type": candidate_type})
            missing = sorted(required[candidate_type] - candidate.keys())
            if missing:
                raise NovelOSError("invalid_candidate", "连续性候选缺少字段", {"index": index, "missing": missing})
            unknown = sorted(candidate.keys() - ({"type"} | required[candidate_type]))
            if unknown:
                raise NovelOSError("invalid_candidate", "连续性候选包含未知字段", {"index": index, "unknown": unknown})
            if candidate_type in allowed_status and candidate["status"] not in allowed_status[candidate_type]:
                raise NovelOSError("invalid_candidate", "连续性状态非法", {"index": index, "status": candidate["status"]})
            for field in required[candidate_type]:
                if not isinstance(candidate[field], str) or not candidate[field].strip():
                    raise NovelOSError("invalid_candidate", "连续性候选字段不能为空", {"index": index, "field": field})

    @staticmethod
    def _validate_review_findings(findings: list[dict[str, Any]]) -> None:
        if not isinstance(findings, list):
            raise NovelOSError("invalid_review", "findings 必须是数组")
        required = {"severity", "message", "evidence_refs"}
        allowed = required | {"excerpt"}
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                raise NovelOSError("invalid_review", "finding 必须是对象", {"index": index})
            missing = sorted(required - finding.keys())
            unknown = sorted(finding.keys() - allowed)
            if missing or unknown:
                raise NovelOSError(
                    "invalid_review",
                    "finding 字段不合法",
                    {"index": index, "missing": missing, "unknown": unknown},
                )
            if finding["severity"] not in {"blocking", "warning", "note"}:
                raise NovelOSError("invalid_review", "finding severity 非法", {"index": index})
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise NovelOSError("invalid_review", "finding message 不能为空", {"index": index})
            refs = finding["evidence_refs"]
            if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(
                not isinstance(ref, str) or not ref.strip() for ref in refs
            ):
                raise NovelOSError("invalid_review", "finding evidence_refs 非法", {"index": index})
            if "excerpt" in finding and not isinstance(finding["excerpt"], str):
                raise NovelOSError("invalid_review", "finding excerpt 必须是字符串", {"index": index})

    def _validate_agent_quality_subject(
        self,
        connection: sqlite3.Connection,
        content: dict[str, Any],
        reviewer_profile: str,
        evidence_refs: list[str],
    ) -> list[dict[str, Any]]:
        required = {"schema_version", "case_id", "input_hash", "outputs", "review_profile"}
        if set(content) != required:
            raise NovelOSError("invalid_argument", "评测 subject 字段不完整或包含未知字段")
        if content["schema_version"] != 1:
            raise NovelOSError("invalid_argument", "评测 subject Schema 版本不受支持")
        _require_text(content["case_id"], "case_id")
        _require_sha256(content["input_hash"], "input_hash")
        if content["review_profile"] != reviewer_profile:
            raise NovelOSError("invalid_review_profile", "评测 subject Review Profile 不匹配")
        outputs = content["outputs"]
        if not isinstance(outputs, list) or not outputs:
            raise NovelOSError("invalid_argument", "评测 subject outputs 不能为空")
        labels: list[str] = []
        refs: list[str] = []
        for index, output in enumerate(outputs):
            if not isinstance(output, dict) or set(output) != {
                "label",
                "output_ref",
                "output_hash",
                "media_type",
            }:
                raise NovelOSError(
                    "invalid_argument", "评测 subject output 字段非法", {"index": index}
                )
            label = _require_text(output["label"], "label")
            output_ref = _require_text(output["output_ref"], "output_ref")
            if not output_ref.startswith("novelos://resource/"):
                raise NovelOSError("invalid_argument", "评测输出必须是 NovelOS Resource")
            resource_id = output_ref.rsplit("/", 1)[-1]
            resource = self._get(connection, "resources", resource_id)
            if (
                resource["content_hash"] != _require_sha256(output["output_hash"], "output_hash")
                or resource["media_type"] != output["media_type"]
                or output["media_type"] not in {"text/markdown", "application/json"}
            ):
                raise NovelOSError(
                    "hash_mismatch", "评测输出 Resource、Hash 或媒体类型不匹配", {"label": label}
                )
            labels.append(label)
            refs.append(output_ref)
        if labels != sorted(set(labels)):
            raise NovelOSError("invalid_argument", "评测输出标签必须唯一且排序")
        if refs != evidence_refs:
            raise NovelOSError("invalid_review", "评测输出 refs 与 evidence_refs 不一致")
        return outputs

    def _authority_snapshot_in_transaction(self, connection: sqlite3.Connection, project_id: str) -> dict[str, Any]:
        project = self._get(connection, "projects", project_id)
        tables = ("characters", "worlds", "factions", "rules", "timelines", "narrative_promises", "expectation_ledgers", "relationship_states", "arc_states")
        versions = {}
        for table in tables:
            rows = connection.execute(f"SELECT id, version FROM {table} WHERE project_id=? ORDER BY id", (project_id,)).fetchall()
            versions[table] = {row["id"]: row["version"] for row in rows}
        snapshot = {"project_id": project_id, "project_version": project["version"], "assets": versions}
        snapshot["snapshot_hash"] = content_hash(_json(snapshot))
        return snapshot

    def _apply_continuity_candidate(self, connection: sqlite3.Connection, candidate_set: sqlite3.Row, candidate: dict[str, Any]) -> None:
        project_id = candidate_set["project_id"]
        chapter_id = candidate_set["chapter_id"]
        source_hash = candidate_set["source_content_hash"]
        candidate_type = candidate["type"]
        if candidate_type == "fact":
            resource_id, _ = self._resource(connection, candidate["description"])
            connection.execute(
                "INSERT INTO chapter_facts(id, project_id, source_chapter_id, source_content_hash, fact_type, subject, description_resource_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_id("fact"), project_id, chapter_id, source_hash, candidate["fact_type"], candidate["subject"], resource_id),
            )
            return
        if candidate_type in {"narrative_promise", "expectation"}:
            table = "narrative_promises" if candidate_type == "narrative_promise" else "expectation_ledgers"
            key_field = "promise_key" if candidate_type == "narrative_promise" else "expectation_key"
            prefix = "promise" if candidate_type == "narrative_promise" else "expectation"
            resource_id, _ = self._resource(connection, candidate["description"])
            existing = connection.execute(f"SELECT id FROM {table} WHERE project_id=? AND {key_field}=?", (project_id, candidate["key"])).fetchone()
            if existing:
                connection.execute(
                    f"UPDATE {table} SET description_resource_id=?, status=?, source_chapter_id=?, source_content_hash=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, candidate["status"], chapter_id, source_hash, existing["id"]),
                )
            else:
                connection.execute(
                    f"INSERT INTO {table}(id, project_id, {key_field}, description_resource_id, status, source_chapter_id, source_content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (_id(prefix), project_id, candidate["key"], resource_id, candidate["status"], chapter_id, source_hash),
                )
            return
        if candidate_type == "relationship":
            resource_id, _ = self._resource(connection, candidate["state"])
            existing = connection.execute(
                "SELECT id FROM relationship_states WHERE project_id=? AND subject_ref=? AND object_ref=?",
                (project_id, candidate["subject_ref"], candidate["object_ref"]),
            ).fetchone()
            if existing:
                connection.execute(
                    "UPDATE relationship_states SET state_resource_id=?, source_chapter_id=?, source_content_hash=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, chapter_id, source_hash, existing["id"]),
                )
            else:
                connection.execute(
                    "INSERT INTO relationship_states(id, project_id, subject_ref, object_ref, state_resource_id, source_chapter_id, source_content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (_id("relationship"), project_id, candidate["subject_ref"], candidate["object_ref"], resource_id, chapter_id, source_hash),
                )
            return
        resource_id, _ = self._resource(connection, candidate["state"])
        existing = connection.execute("SELECT id FROM arc_states WHERE project_id=? AND arc_ref=?", (project_id, candidate["arc_ref"])).fetchone()
        if existing:
            connection.execute(
                "UPDATE arc_states SET state_resource_id=?, source_chapter_id=?, source_content_hash=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (resource_id, chapter_id, source_hash, existing["id"]),
            )
        else:
            connection.execute(
                "INSERT INTO arc_states(id, project_id, arc_ref, state_resource_id, source_chapter_id, source_content_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (_id("arc"), project_id, candidate["arc_ref"], resource_id, chapter_id, source_hash),
            )

    def _upsert_described(
        self,
        table: str,
        prefix: str,
        project_id: str,
        name: str,
        description: str,
        state: dict[str, Any],
        expected_version: int | None,
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            self._get(connection, "projects", project_id)
            resource_id = None
            if description:
                resource_id, _ = self._resource(connection, description)
            existing = connection.execute(f"SELECT * FROM {table} WHERE project_id=? AND name=?", (project_id, _require_text(name, "name"))).fetchone()
            if existing:
                self._require_expected_version(existing, expected_version)
                connection.execute(
                    f"UPDATE {table} SET description_resource_id=?, state_json=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id or existing["description_resource_id"], _json(state), existing["id"]),
                )
                item_id = str(existing["id"])
            else:
                item_id = _id(prefix)
                connection.execute(
                    f"INSERT INTO {table}(id, project_id, name, description_resource_id, state_json) VALUES (?, ?, ?, ?, ?)",
                    (item_id, project_id, name.strip(), resource_id, _json(state)),
                )
            return self._row(self._get(connection, table, item_id))

    def _agent_run(self, connection: sqlite3.Connection, run_id: str) -> dict[str, Any]:
        return self._row(self._get(connection, "agent_runs", run_id))

    def _validate_planning_producer_run(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        asset_type: str,
        content: str,
    ) -> str:
        run = self._get(connection, "agent_runs", run_id)
        if run["status"] != "completed" or run["kind"] != "planning_asset":
            raise NovelOSError("invalid_producer_run", "规划候选必须来自已完成的规划 Agent run")
        role = self.agent_contracts.get(str(run["role_id"]))
        if role["owned_asset_type"] != asset_type or run["output_type"] != "planning_candidate":
            raise NovelOSError(
                "invalid_producer_run",
                "Agent run 不拥有该规划资产",
                {"role_id": run["role_id"], "asset_type": asset_type},
            )
        resource = self._get(connection, "resources", str(run["output_resource_id"]))
        actual = bytes(resource["content"]).decode("utf-8")
        if actual != content:
            raise NovelOSError("hash_mismatch", "规划候选与 Agent run 输出不一致")
        return str(run["display_name"])

    def _validate_chapter_producer_run(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        content: str,
    ) -> None:
        run = self._get(connection, "agent_runs", run_id)
        if (
            run["status"] != "completed"
            or run["role_id"] != "writer_agent"
            or run["output_type"] != "chapter_draft_candidate"
        ):
            raise NovelOSError("invalid_producer_run", "章节草稿必须来自已完成的 Writer Agent run")
        resource = self._get(connection, "resources", str(run["output_resource_id"]))
        if bytes(resource["content"]).decode("utf-8") != content:
            raise NovelOSError("hash_mismatch", "章节正文与 Writer Agent run 输出不一致")

    def _validate_change_proposal_targets(
        self,
        connection: sqlite3.Connection,
        run: sqlite3.Row,
        proposals: list[dict[str, Any]],
    ) -> None:
        if not proposals:
            return
        trace = self._get(connection, "traces", str(run["trace_id"]))
        if trace["project_id"] is None:
            raise NovelOSError("invalid_change_proposal", "变更提案必须属于项目 Trace")
        for proposal in proposals:
            target = self._get(connection, "planning_assets", proposal["target_asset_ref"])
            if (
                target["project_id"] != trace["project_id"]
                or target["asset_type"] != proposal["target_asset_type"]
                or target["status"] != "locked"
                or int(target["version"]) != proposal["target_asset_version"]
                or target["subject_hash"] != proposal["target_subject_hash"]
            ):
                raise NovelOSError(
                    "invalid_change_proposal",
                    "变更提案必须绑定当前项目中类型匹配的 locked 上游资产",
                    {"target_asset_ref": proposal["target_asset_ref"]},
                )

    def _validate_reviewer_run(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        subject_type: str,
        subject_ref: str,
        subject_hash: str,
        verdict: str,
        findings: list[dict[str, Any]],
        reviewer_profile: str,
        evidence_refs: list[str],
        assessment: dict[str, Any] | None,
    ) -> None:
        run = self._get(connection, "agent_runs", run_id)
        if run["status"] != "completed" or run["role_id"] != "review_agent":
            raise NovelOSError("invalid_reviewer_run", "Review 必须来自已完成的 Review Agent run")
        if run["output_type"] != "review_receipt_candidate":
            raise NovelOSError("invalid_reviewer_run", "Review Agent output_type 非法")
        bindings = json.loads(run["input_bindings_json"])
        if (
            bindings["immutable_subject_ref"] != subject_ref
            or bindings["subject_hash"] != subject_hash
            or bindings["review_profile"] != reviewer_profile
        ):
            raise NovelOSError("invalid_reviewer_run", "Reviewer run 输入与 Review subject 不一致")
        resource = self._get(connection, "resources", str(run["output_resource_id"]))
        try:
            output = json.loads(bytes(resource["content"]).decode("utf-8"))
        except (TypeError, json.JSONDecodeError) as exc:
            raise NovelOSError("invalid_reviewer_run", "Reviewer 输出不是 JSON 对象") from exc
        expected = {
            "subject_type": subject_type,
            "subject_ref": subject_ref,
            "subject_hash": subject_hash,
            "verdict": verdict,
            "findings": findings,
            "reviewer_profile": reviewer_profile,
            "evidence_refs": evidence_refs,
        }
        if subject_type == "review_subject":
            expected["assessment"] = assessment
        if output != expected:
            raise NovelOSError("invalid_reviewer_run", "Review 参数与 Reviewer run 输出不一致")
        if subject_type == "review_subject":
            subject = self._get(connection, "review_subjects", subject_ref)
            if subject["trace_id"] != run["trace_id"]:
                raise NovelOSError("trace_review_mismatch", "评测 subject 与 Reviewer run 必须属于同一 Trace")
            for producer_run_id in json.loads(subject["producer_run_ids_json"]):
                producer = self._get(connection, "agent_runs", producer_run_id)
                if producer["id"] == run["id"] or producer["context_id"] == run["context_id"]:
                    raise NovelOSError(
                        "review_context_not_isolated", "评测 Producer 与 Review Agent 必须使用隔离上下文"
                    )
        producer_run_id: str | None = None
        if subject_type == "planning_asset":
            producer_run_id = self._get(connection, "planning_assets", subject_ref)["producer_run_id"]
        elif subject_type == "chapter":
            producer_run_id = self._get(connection, "chapters", subject_ref)["producer_run_id"]
        if producer_run_id:
            producer = self._get(connection, "agent_runs", str(producer_run_id))
            if producer["context_id"] == run["context_id"] or producer["id"] == run["id"]:
                raise NovelOSError("review_context_not_isolated", "生产 Agent 与 Review Agent 必须使用隔离上下文")

    def _validate_cross_check_sources(self, connection: sqlite3.Connection, check: sqlite3.Row) -> None:
        for prefix, expected_type in (("character", "character_contract"), ("world", "world_contract")):
            asset = self._get(connection, "planning_assets", str(check[f"{prefix}_asset_id"]))
            if (
                asset["asset_type"] != expected_type
                or asset["status"] != "locked"
                or int(asset["version"]) != int(check[f"{prefix}_version"])
                or asset["subject_hash"] != check[f"{prefix}_hash"]
            ):
                raise NovelOSError("stale_cross_check", "Character/World 交叉审查来源已失效", {"asset_type": expected_type})

    def _validate_story_arc_cross_check(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        upstream_rows: list[sqlite3.Row],
        check: sqlite3.Row,
    ) -> None:
        if check["project_id"] != project_id or check["status"] != "approved":
            raise NovelOSError("cross_check_required", "Story Arc 需要当前项目已批准的交叉审查")
        self._validate_cross_check_sources(connection, check)
        upstream = {str(row["asset_type"]): str(row["id"]) for row in upstream_rows}
        if (
            upstream.get("character_contract") != check["character_asset_id"]
            or upstream.get("world_contract") != check["world_asset_id"]
        ):
            raise NovelOSError("cross_check_mismatch", "Story Arc 上游与交叉审查绑定版本不一致")

    def _validate_authority_trace(
        self,
        connection: sqlite3.Connection,
        trace_id: str,
        project_id: str,
        review: sqlite3.Row,
        producer_run_id: str | None = None,
    ) -> None:
        trace = self._get(connection, "traces", _require_text(trace_id, "trace_id"))
        if trace["status"] != "running":
            raise NovelOSError("invalid_state", "权威提交必须绑定运行中的 Trace")
        if trace["project_id"] != project_id:
            raise NovelOSError(
                "trace_project_mismatch",
                "权威提交 Trace 与目标项目不一致",
                {"trace_project_id": trace["project_id"], "project_id": project_id},
            )
        reviewer_run_id = review["reviewer_run_id"]
        if not reviewer_run_id:
            raise NovelOSError("reviewer_run_required", "权威提交必须绑定独立 Review Agent run")
        reviewer = self._get(connection, "agent_runs", str(reviewer_run_id))
        if (
            reviewer["trace_id"] != trace_id
            or reviewer["role_id"] != "review_agent"
            or reviewer["status"] != "completed"
        ):
            raise NovelOSError("trace_review_mismatch", "Review Agent run 必须在同一 Trace 中完成")
        if not self._decode_isolation_evidence(reviewer["isolation_evidence"]):
            raise NovelOSError(
                "missing_isolation_evidence",
                "权威提交的 Review Agent run 缺少隔离执行凭据",
                {"run_id": str(reviewer_run_id), "role": "reviewer"},
            )
        if producer_run_id is not None:
            producer = self._get(connection, "agent_runs", producer_run_id)
            if producer["trace_id"] != trace_id or producer["status"] != "completed":
                raise NovelOSError("trace_producer_mismatch", "生产 Agent run 必须在同一 Trace 中完成")
            if not self._decode_isolation_evidence(producer["isolation_evidence"]):
                raise NovelOSError(
                    "missing_isolation_evidence",
                    "权威提交的生产 Agent run 缺少隔离执行凭据",
                    {"run_id": producer_run_id, "role": "producer"},
                )

    def _record_authority_commit(
        self,
        connection: sqlite3.Connection,
        trace_id: str,
        project_id: str,
        action: str,
        subject_type: str,
        subject_ref: str,
        subject_hash: str,
        review_id: str,
        result_ref: str,
    ) -> dict[str, Any]:
        commit_id = _id("authority-commit")
        connection.execute(
            "INSERT INTO authority_commits(id, trace_id, project_id, action, subject_type, subject_ref, subject_hash, review_id, result_ref) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                commit_id,
                trace_id,
                project_id,
                action,
                subject_type,
                subject_ref,
                subject_hash,
                review_id,
                result_ref,
            ),
        )
        self._record_trace_step_in_transaction(
            connection,
            trace_id,
            action,
            "Main Agent",
            "completed",
            [subject_ref, review_id],
            [result_ref],
            {
                "authority_commit_id": commit_id,
                "subject_type": subject_type,
                "subject_hash": subject_hash,
            },
        )
        return self._row(self._get(connection, "authority_commits", commit_id))

    def _record_trace_step_in_transaction(
        self,
        connection: sqlite3.Connection,
        trace_id: str,
        step_type: str,
        actor: str,
        status: str,
        input_refs: list[str],
        output_refs: list[str],
        details: dict[str, Any],
    ) -> dict[str, Any]:
        trace = self._get(connection, "traces", trace_id)
        if trace["status"] != "running":
            raise NovelOSError("invalid_state", "已结束的 Trace 不能追加 step")
        sequence = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM trace_steps WHERE trace_id=?", (trace_id,)
            ).fetchone()[0]
        )
        step_id = _id("trace-step")
        connection.execute(
            "INSERT INTO trace_steps(id, trace_id, sequence, step_type, actor, input_refs_json, output_refs_json, status, details_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                step_id,
                trace_id,
                sequence,
                _require_text(step_type, "step_type"),
                _require_text(actor, "actor"),
                _json(input_refs),
                _json(output_refs),
                status,
                _json(details),
            ),
        )
        return self._row(self._get(connection, "trace_steps", step_id))

    def _planning_asset(self, connection: sqlite3.Connection, asset_id: str) -> dict[str, Any]:
        result = self._row(self._get(connection, "planning_assets", asset_id))
        dependencies = connection.execute(
            "SELECT upstream_asset_id, upstream_version FROM planning_asset_dependencies WHERE asset_id=? ORDER BY upstream_asset_id",
            (asset_id,),
        ).fetchall()
        result["upstream_refs"] = [
            {"asset_id": row["upstream_asset_id"], "version": row["upstream_version"]} for row in dependencies
        ]
        return result

    @staticmethod
    def _validate_entity_payload(entity_type: str, payload: dict[str, Any]) -> None:
        required = {
            "character": {"name", "description", "state"},
            "world": {"name", "description", "state"},
            "faction": {"name", "description", "state"},
            "rule": {"name", "description"},
            "timeline": {"label", "sequence", "description", "event_source_ref"},
        }
        fields = required.get(entity_type)
        if fields is None:
            raise NovelOSError("invalid_argument", "未知 entity_type", {"entity_type": entity_type})
        if not isinstance(payload, dict) or set(payload) != fields:
            raise NovelOSError(
                "invalid_candidate",
                "Entity mutation payload 字段不合法",
                {"expected": sorted(fields), "actual": sorted(payload) if isinstance(payload, dict) else []},
            )
        for field in fields - {"state", "sequence"}:
            if not isinstance(payload[field], str) or not payload[field].strip():
                raise NovelOSError("invalid_candidate", "Entity mutation 文本字段不能为空", {"field": field})
        if "state" in fields and not isinstance(payload["state"], dict):
            raise NovelOSError("invalid_candidate", "Entity mutation state 必须是对象")
        if "sequence" in fields and (
            isinstance(payload["sequence"], bool) or not isinstance(payload["sequence"], int) or payload["sequence"] < 0
        ):
            raise NovelOSError("invalid_candidate", "Entity mutation sequence 非法")

    def _validate_entity_authority_source(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        entity_type: str,
        source_ref: str,
        source_hash: str,
    ) -> int:
        if source_ref.startswith("planning:"):
            source = self._get(connection, "planning_assets", source_ref)
            if source["project_id"] != project_id or source["status"] != "locked":
                raise NovelOSError("stale_authority", "规划来源不是当前项目的锁定资产")
            if source["asset_type"] not in ENTITY_AUTHORITY_ASSETS[entity_type]:
                raise NovelOSError("authority_mismatch", "规划资产类型不能授权该实体写入")
            if source["subject_hash"] != source_hash:
                raise NovelOSError("hash_mismatch", "Entity authority source Hash 不一致")
            return int(source["version"])
        if source_ref.startswith("chapter:") and entity_type == "timeline":
            source = self._get(connection, "chapters", source_ref)
            actual_project = connection.execute(
                "SELECT books.project_id FROM chapters JOIN volumes ON volumes.id=chapters.volume_id JOIN books ON books.id=volumes.book_id WHERE chapters.id=?",
                (source_ref,),
            ).fetchone()["project_id"]
            if actual_project != project_id or source["status"] != "accepted":
                raise NovelOSError("stale_authority", "章节来源不是当前项目的已接受正文")
            if source["subject_hash"] != source_hash:
                raise NovelOSError("hash_mismatch", "Entity authority source Hash 不一致")
            return int(source["version"])
        raise NovelOSError("authority_mismatch", "Entity mutation 缺少允许的权威来源")

    @staticmethod
    def _find_entity_target(
        connection: sqlite3.Connection,
        project_id: str,
        entity_type: str,
        payload: dict[str, Any],
    ) -> sqlite3.Row | None:
        if entity_type in {"character", "world", "faction"}:
            table = {"character": "characters", "world": "worlds", "faction": "factions"}[entity_type]
            return connection.execute(
                f"SELECT * FROM {table} WHERE project_id=? AND name=?",
                (project_id, payload["name"].strip()),
            ).fetchone()
        if entity_type == "rule":
            return connection.execute(
                "SELECT * FROM rules WHERE project_id=? AND name=?",
                (project_id, payload["name"].strip()),
            ).fetchone()
        return connection.execute(
            "SELECT * FROM timelines WHERE project_id=? AND sequence=? AND label=?",
            (project_id, payload["sequence"], payload["label"].strip()),
        ).fetchone()

    def _apply_entity_mutation(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        entity_type: str,
        payload: dict[str, Any],
        current: sqlite3.Row | None,
    ) -> sqlite3.Row:
        resource_id, _ = self._resource(connection, payload["description"])
        if entity_type in {"character", "world", "faction"}:
            table = {"character": "characters", "world": "worlds", "faction": "factions"}[entity_type]
            if current is None:
                entity_id = _id(entity_type)
                connection.execute(
                    f"INSERT INTO {table}(id, project_id, name, description_resource_id, state_json) VALUES (?, ?, ?, ?, ?)",
                    (entity_id, project_id, payload["name"].strip(), resource_id, _json(payload["state"])),
                )
            else:
                entity_id = str(current["id"])
                connection.execute(
                    f"UPDATE {table} SET description_resource_id=?, state_json=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, _json(payload["state"]), entity_id),
                )
            return self._get(connection, table, entity_id)
        if entity_type == "rule":
            if current is None:
                entity_id = _id("rule")
                connection.execute(
                    "INSERT INTO rules(id, project_id, name, description_resource_id) VALUES (?, ?, ?, ?)",
                    (entity_id, project_id, payload["name"].strip(), resource_id),
                )
            else:
                entity_id = str(current["id"])
                connection.execute(
                    "UPDATE rules SET description_resource_id=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (resource_id, entity_id),
                )
            return self._get(connection, "rules", entity_id)
        if current is None:
            entity_id = _id("timeline")
            connection.execute(
                "INSERT INTO timelines(id, project_id, label, sequence, description_resource_id, source_ref) VALUES (?, ?, ?, ?, ?, ?)",
                (entity_id, project_id, payload["label"].strip(), payload["sequence"], resource_id, payload["event_source_ref"]),
            )
        else:
            entity_id = str(current["id"])
            connection.execute(
                "UPDATE timelines SET description_resource_id=?, source_ref=?, version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (resource_id, payload["event_source_ref"], entity_id),
            )
        return self._get(connection, "timelines", entity_id)

    def _validate_planning_dependencies(self, connection: sqlite3.Connection, asset_id: str) -> None:
        dependencies = connection.execute(
            "SELECT d.upstream_version, a.* FROM planning_asset_dependencies d JOIN planning_assets a ON a.id=d.upstream_asset_id WHERE d.asset_id=?",
            (asset_id,),
        ).fetchall()
        for upstream in dependencies:
            if upstream["status"] != "locked" or int(upstream["version"]) != int(upstream["upstream_version"]):
                raise NovelOSError(
                    "stale_upstream",
                    "规划资产的上游版本已失效",
                    {"asset_id": upstream["id"], "status": upstream["status"], "actual_version": upstream["version"]},
                )

    @staticmethod
    def _mark_planning_descendants_stale(connection: sqlite3.Connection, upstream_asset_id: str) -> None:
        connection.execute(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT asset_id FROM planning_asset_dependencies WHERE upstream_asset_id=?
                UNION
                SELECT d.asset_id
                FROM planning_asset_dependencies d
                JOIN descendants parent ON d.upstream_asset_id=parent.id
            )
            UPDATE planning_assets
            SET status='stale', version=version+1, updated_at=CURRENT_TIMESTAMP
            WHERE id IN (SELECT id FROM descendants) AND status IN ('candidate', 'locked')
            """,
            (upstream_asset_id,),
        )

    def _create_child(self, table: str, prefix: str, parent_field: str, parent_id: str, values: dict[str, Any]) -> dict[str, Any]:
        parent_table = {"project_id": "projects", "book_id": "books"}[parent_field]
        item_id = _id(prefix)
        fields = ["id", parent_field, *values]
        placeholders = ",".join("?" for _ in fields)
        with self.database.transaction() as connection:
            self._get(connection, parent_table, parent_id)
            try:
                connection.execute(
                    f"INSERT INTO {table}({','.join(fields)}) VALUES ({placeholders})",
                    (item_id, parent_id, *values.values()),
                )
            except sqlite3.IntegrityError as exc:
                raise NovelOSError("conflict", f"{table} 记录冲突") from exc
            return self._row(self._get(connection, table, item_id))

    def _get_public(self, table: str, item_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._row(self._get(connection, table, item_id))

    def _list_children(self, table: str, field: str, parent_id: str, order: str = "created_at") -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(f"SELECT * FROM {table} WHERE {field}=? ORDER BY {order}, id", (parent_id,)).fetchall()
        return [self._row(row) for row in rows]

    @staticmethod
    def _check_version(row: sqlite3.Row, expected_version: int) -> None:
        if int(row["version"]) != expected_version:
            raise NovelOSError("stale_version", "版本已变化", {"expected": expected_version, "actual": row["version"]})

    @classmethod
    def _require_expected_version(cls, row: sqlite3.Row, expected_version: int | None) -> None:
        if expected_version is None:
            raise NovelOSError("expected_version_required", "更新已有资产必须提供 expected_version")
        cls._check_version(row, expected_version)

    @staticmethod
    def _validate_page(limit: int, offset: int) -> None:
        if not 1 <= limit <= 200 or offset < 0:
            raise NovelOSError("invalid_pagination", "limit 必须为 1..200 且 offset >= 0")

    def get_projection_snapshot(self, project_id: str, include_candidates: bool = False) -> dict[str, Any]:
        with self.database.read() as connection:
            # 显式开启只读事务以获得快照隔离：整个读取期间所有 SELECT
            # 看到事务开始时的数据库快照，并发写不会穿插进来造成混合版本。
            connection.execute("BEGIN")
            try:
                return self._read_projection_snapshot(connection, project_id, include_candidates=include_candidates)
            finally:
                connection.rollback()

    def _read_projection_snapshot(
        self, connection: sqlite3.Connection, project_id: str, include_candidates: bool = False
    ) -> dict[str, Any]:
        project = self._get(connection, "projects", project_id)
        initial_version = project["version"]

        # 读取规划资产，同时统计被跳过的非权威状态（candidate/stale/superseded）。
        planning_rows = connection.execute(
            "SELECT * FROM planning_assets WHERE project_id=? AND status='locked' ORDER BY asset_type",
            (project_id,),
        ).fetchall()
        planning_assets = {}
        volume_outlines = []
        chapter_plans = []
        for row in planning_rows:
            r = self._row(row)
            res_id = r["resource_ref"].replace("novelos://resource/", "")
            r["content"] = self.get_resource(res_id)
            atype = r["asset_type"]
            planning_assets[atype] = r
            if atype == "volume_outline":
                volume_outlines.append(r)
            elif atype == "chapter_plan":
                chapter_plans.append(r)

        # 统计被过滤的非权威规划资产数量
        skipped_candidates = connection.execute(
            "SELECT COUNT(*) FROM planning_assets WHERE project_id=? AND status='candidate'",
            (project_id,),
        ).fetchone()[0]
        skipped_stale = connection.execute(
            "SELECT COUNT(*) FROM planning_assets WHERE project_id=? AND status='stale'",
            (project_id,),
        ).fetchone()[0]
        skipped_superseded = connection.execute(
            "SELECT COUNT(*) FROM planning_assets WHERE project_id=? AND status='superseded'",
            (project_id,),
        ).fetchone()[0]
        # 统计被过滤的非 accepted 正文（draft/superseded）
        skipped_draft_chapters = connection.execute(
            """
            SELECT COUNT(*) FROM chapters c
            JOIN volumes v ON c.volume_id = v.id
            JOIN books b ON v.book_id = b.id
            WHERE b.project_id=? AND c.status='draft'
            """,
            (project_id,),
        ).fetchone()[0]
        skipped_superseded_chapters = connection.execute(
            """
            SELECT COUNT(*) FROM chapters c
            JOIN volumes v ON c.volume_id = v.id
            JOIN books b ON v.book_id = b.id
            WHERE b.project_id=? AND c.status='superseded'
            """,
            (project_id,),
        ).fetchone()[0]

        # 读取仅 accepted 的正文
        chap_rows = connection.execute(
            """
            SELECT c.*, v.number AS volume_number, v.title AS volume_title
            FROM chapters c
            JOIN volumes v ON c.volume_id = v.id
            JOIN books b ON v.book_id = b.id
            WHERE b.project_id=? AND c.status='accepted'
            ORDER BY v.number, c.number
            """,
            (project_id,),
        ).fetchall()
        chapters = []
        for r in chap_rows:
            item = self._row(r)
            res_id = item["resource_ref"].replace("novelos://resource/", "")
            item["content"] = self.get_resource(res_id)
            chapters.append(item)

        # 读取实体
        char_rows = connection.execute(
            "SELECT * FROM characters WHERE project_id=? ORDER BY name",
            (project_id,),
        ).fetchall()
        characters = [self._row(r) for r in char_rows]

        world_rows = connection.execute(
            "SELECT * FROM worlds WHERE project_id=? ORDER BY name",
            (project_id,),
        ).fetchall()
        worlds = [self._row(r) for r in world_rows]

        # 读取时间线账本
        timeline_rows = connection.execute(
            "SELECT * FROM timelines WHERE project_id=? ORDER BY sequence, label", (project_id,)
        ).fetchall()
        timelines = []
        for r in timeline_rows:
            item = self._row(r)
            res_id = item["description_ref"].replace("novelos://resource/", "")
            item["description"] = self.get_resource(res_id)
            timelines.append(item)

        # 读取连续性账本
        np_rows = connection.execute(
            "SELECT * FROM narrative_promises WHERE project_id=? ORDER BY id", (project_id,)
        ).fetchall()
        el_rows = connection.execute(
            "SELECT * FROM expectation_ledgers WHERE project_id=? ORDER BY id", (project_id,)
        ).fetchall()
        rs_rows = connection.execute(
            "SELECT * FROM relationship_states WHERE project_id=? ORDER BY id", (project_id,)
        ).fetchall()
        as_rows = connection.execute(
            "SELECT * FROM arc_states WHERE project_id=? ORDER BY id", (project_id,)
        ).fetchall()
        # 读取正文事实账本
        fact_rows = connection.execute(
            "SELECT * FROM chapter_facts WHERE project_id=? AND status='accepted' ORDER BY id",
            (project_id,),
        ).fetchall()
        fact_records = []
        for r in fact_rows:
            item = self._row(r)
            res_id = item["description_ref"].replace("novelos://resource/", "")
            item["description"] = self.get_resource(res_id)
            fact_records.append(item)

        # 再次查验版本漂移（快照隔离下并发写已无法穿插，此处为防御性二次校验）
        current_project = self._get(connection, "projects", project_id)
        if current_project["version"] != initial_version:
            raise NovelOSError("version_drift", "在快照读取期间发现项目版本漂移，拒绝生成快照")

        skipped_non_authoritative_stats = {
            "candidates": skipped_candidates,
            "stale": skipped_stale,
            "superseded": skipped_superseded + skipped_superseded_chapters,
            "draft_chapters": skipped_draft_chapters,
        }
        # authority_snapshot_hash 只覆盖权威业务内容，不含运行时的跳过统计，
        # 否则非权威内容的增删会破坏两次投影之间的确定性 Hash。
        snapshot_payload = {
            "project": self._row(project),
            "planning_assets": planning_assets,
            "volume_outlines": volume_outlines,
            "chapter_plans": chapter_plans,
            "chapters": chapters,
            "characters": characters,
            "worlds": worlds,
            "timelines": timelines,
            "narrative_promises": [self._row(r) for r in np_rows],
            "expectation_ledgers": [self._row(r) for r in el_rows],
            "relationship_states": [self._row(r) for r in rs_rows],
            "arc_states": [self._row(r) for r in as_rows],
            "fact_records": fact_records,
        }
        snapshot_hash = content_hash(_json(snapshot_payload))
        snapshot_payload["authority_snapshot_hash"] = snapshot_hash
        snapshot_payload["skipped_non_authoritative_stats"] = skipped_non_authoritative_stats
        # 诊断模式：额外读取未锁定的 candidate 规划资产，供显式诊断视图渲染。
        # 与 skipped 统计、authority_snapshot_hash 一样走旁路 key，绝不纳入
        # snapshot_payload 哈希计算，以免候选增删破坏两次投影间的确定性 Hash。
        if include_candidates:
            cand_rows = connection.execute(
                "SELECT * FROM planning_assets WHERE project_id=? AND status='candidate' ORDER BY asset_type, revision",
                (project_id,),
            ).fetchall()
            planning_candidate_assets = []
            for row in cand_rows:
                item = self._row(row)
                res_id = item["resource_ref"].replace("novelos://resource/", "")
                item["content"] = self.get_resource(res_id)
                planning_candidate_assets.append(item)
            snapshot_payload["planning_candidate_assets"] = planning_candidate_assets
        # 创作全过程档案（旁路 key，不进 snapshot_payload 哈希）：为每个 locked 规划资产
        # 收集溯源链（producer run → review + findings → reviewer run → authority commit）。
        # 这些数据已存 DB，此处只是组装成对外可读视图，让用户追溯资产如何锁定。
        # 默认模式也收集——档案是已锁定资产的过程，属于权威视图的一部分，不是诊断。
        planning_provenance: list[dict[str, Any]] = []
        for asset in planning_assets.values():
            asset_id = asset["id"]
            entry: dict[str, Any] = {
                "asset_type": asset.get("asset_type"),
                "revision": asset.get("revision"),
                "version": asset.get("version"),
                "subject_hash": asset.get("subject_hash"),
                "producer_run": None,
                "review": None,
                "authority_commit": None,
            }
            producer_run_id = asset.get("producer_run_id")
            if producer_run_id:
                prow = self._get(connection, "agent_runs", producer_run_id)
                entry["producer_run"] = {
                    "role_id": prow["role_id"],
                    "status": prow["status"],
                    "isolation_evidence": self._decode_isolation_evidence(prow["isolation_evidence"]),
                    "output_ref": f"novelos://resource/{prow['output_resource_id']}" if prow["output_resource_id"] else None,
                }
            review_id = asset.get("locked_review_id")
            if review_id:
                rev = self._get(connection, "reviews", review_id)
                reviewer_entry: dict[str, Any] | None = None
                reviewer_run_id = rev["reviewer_run_id"]
                if reviewer_run_id:
                    rrun = self._get(connection, "agent_runs", str(reviewer_run_id))
                    reviewer_entry = {
                        "isolation_evidence": self._decode_isolation_evidence(rrun["isolation_evidence"]),
                    }
                entry["review"] = {
                    "id": rev["id"],
                    "verdict": rev["verdict"],
                    "findings": json.loads(rev["findings_json"]) if rev["findings_json"] else [],
                    "reviewer_profile": rev["reviewer_profile"],
                    "reviewer_run": reviewer_entry,
                }
            commit = connection.execute(
                "SELECT id, trace_id, action, subject_hash FROM authority_commits WHERE subject_ref=? AND subject_type='planning_asset' ORDER BY created_at DESC LIMIT 1",
                (asset_id,),
            ).fetchone()
            if commit:
                entry["authority_commit"] = {
                    "id": commit["id"],
                    "trace_id": commit["trace_id"],
                    "action": commit["action"],
                    "subject_hash": commit["subject_hash"],
                }
            planning_provenance.append(entry)
        snapshot_payload["planning_provenance"] = planning_provenance
        return snapshot_payload

    def render_project_projection(
        self, project_id: str, output_root: str = "novels", include_candidates: bool = False
    ) -> dict[str, Any]:
        from novelos_mcp.projection import ProjectionEngine

        engine = ProjectionEngine(root_dir=output_root)
        return engine.render(self, project_id, include_candidates=include_candidates)

    def verify_project_projection(self, project_directory: str) -> dict[str, Any]:
        """逐文件校验已生成的投影目录，校验其 manifest 中记录的内容 Hash 与来源 Hash。"""
        from novelos_mcp.projection import ProjectionEngine

        return ProjectionEngine.verify_manifest(project_directory)
