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


class ReviewsMixin:

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

    def record_review_from_run(self, reviewer_run_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            run, output = self._completed_agent_output(
                connection, reviewer_run_id, "review_receipt_candidate"
            )
            self._validate_review_receipt_candidate(run, output)
        assert isinstance(output, dict)
        return self.record_review(
            output["subject_type"],
            output["subject_ref"],
            output["subject_hash"],
            output["verdict"],
            output["findings"],
            output["reviewer_profile"],
            output["evidence_refs"],
            reviewer_run_id,
            output.get("assessment"),
        )

    def get_review(self, review_id: str) -> dict[str, Any]:
        return self._get_public("reviews", review_id)
