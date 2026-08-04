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


class _ServiceInternals:

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

    @staticmethod
    def _normalize_isolation_evidence(evidence: dict[str, Any] | None) -> str | None:
        """归一化隔离执行凭据。

        凭据用于在权威提交（lock/accept/promote）路径证明 producer/reviewer run
        来自独立的 sub-agent 而非 主控智能体 自审。这是声明性证明（非密码学证明）：
        真实隔离仍由 主控智能体 用独立 Codex Task 创建 sub-agent 兑现。存为 JSON 文本。
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
        allowed = required | {"code", "excerpt"}
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                raise NovelOSError("invalid_review", "finding 必须是对象", {"index": index})
            missing = sorted(required - finding.keys())
            unknown = sorted(finding.keys() - allowed)
            if missing or unknown:
                raise NovelOSError(
                    "invalid_review",
                    f"finding 字段不合法：index={index}，missing={missing}，unknown={unknown}",
                    {"index": index, "missing": missing, "unknown": unknown},
                )
            if finding["severity"] not in {"blocking", "warning", "note"}:
                raise NovelOSError("invalid_review", "finding severity 非法", {"index": index})
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise NovelOSError("invalid_review", "finding message 不能为空", {"index": index})
            if "code" in finding and (
                not isinstance(finding["code"], str) or not finding["code"].strip()
            ):
                raise NovelOSError("invalid_review", "finding code 不能为空", {"index": index})
            refs = finding["evidence_refs"]
            if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(
                not isinstance(ref, str) or not ref.strip() for ref in refs
            ):
                raise NovelOSError("invalid_review", "finding evidence_refs 非法", {"index": index})
            if "excerpt" in finding and not isinstance(finding["excerpt"], str):
                raise NovelOSError("invalid_review", "finding excerpt 必须是字符串", {"index": index})

    def _validate_review_receipt_candidate(
        self, run: sqlite3.Row, output: Any
    ) -> None:
        self.agent_contracts.validate_output("review_receipt_candidate", output)
        assert isinstance(output, dict)
        self._validate_review_findings(output["findings"])
        if any(item["severity"] == "blocking" for item in output["findings"]):
            if output["verdict"] == "approved":
                raise NovelOSError(
                    "invalid_agent_result",
                    "存在 blocking finding 时 Reviewer verdict 不能为 approved",
                )
        bindings = json.loads(run["input_bindings_json"])
        expected_bindings = {
            "immutable_subject_ref": output["subject_ref"],
            "subject_hash": output["subject_hash"],
            "review_profile": output["reviewer_profile"],
        }
        mismatched = {
            field: {"expected": expected, "actual": bindings.get(field)}
            for field, expected in expected_bindings.items()
            if bindings.get(field) != expected
        }
        if mismatched:
            raise NovelOSError(
                "invalid_agent_result",
                "Reviewer output 与 run 输入绑定不一致",
                {"mismatched": mismatched},
            )

    def _completed_agent_output(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        expected_output_type: str,
    ) -> tuple[sqlite3.Row, Any]:
        run = self._get(connection, "agent_runs", run_id)
        if run["status"] != "completed" or run["output_type"] != expected_output_type:
            raise NovelOSError(
                "invalid_agent_result",
                "Agent run 未完成或 output_type 不匹配",
                {
                    "run_id": run_id,
                    "status": run["status"],
                    "expected_output_type": expected_output_type,
                    "actual_output_type": run["output_type"],
                },
            )
        resource = self._get(connection, "resources", str(run["output_resource_id"]))
        raw = bytes(resource["content"]).decode("utf-8")
        if resource["media_type"] != "application/json":
            return run, raw
        try:
            return run, json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NovelOSError(
                "invalid_agent_result",
                "Agent output Resource 不是合法 JSON",
                {"run_id": run_id},
            ) from exc

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
        project_id: str,
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
        trace = self._get(connection, "traces", str(run["trace_id"]))
        if trace["project_id"] != project_id:
            raise NovelOSError("invalid_producer_run", "规划 Agent run 不属于当前项目 Trace")
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
        project_id: str,
    ) -> None:
        run = self._get(connection, "agent_runs", run_id)
        if (
            run["status"] != "completed"
            or run["role_id"] != "writer_agent"
            or run["output_type"] != "chapter_draft_candidate"
        ):
            raise NovelOSError("invalid_producer_run", "章节草稿必须来自已完成的 写作智能体 run")
        resource = self._get(connection, "resources", str(run["output_resource_id"]))
        if bytes(resource["content"]).decode("utf-8") != content:
            raise NovelOSError("hash_mismatch", "章节正文与 写作智能体 run 输出不一致")
        trace = self._get(connection, "traces", str(run["trace_id"]))
        if trace["project_id"] != project_id:
            raise NovelOSError("invalid_producer_run", "写作智能体 run 不属于章节所在项目")
        binding = connection.execute(
            "SELECT project_id FROM project_creator_bindings WHERE project_id=?", (project_id,)
        ).fetchone()
        if binding is not None:
            expected = set(self._project_style_refs(connection, project_id))
            actual_bindings = json.loads(run["input_bindings_json"])
            actual_value = actual_bindings.get("style_refs")
            actual = set(actual_value if isinstance(actual_value, list) else [actual_value])
            if not expected.issubset(actual):
                raise NovelOSError("stale_creator_binding", "Writer run 的作者约束已失效")

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
            raise NovelOSError("invalid_reviewer_run", "Review 必须来自已完成的 审查智能体 run")
        if run["output_type"] != "review_receipt_candidate":
            raise NovelOSError("invalid_reviewer_run", "审查智能体 output_type 非法")
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
                        "review_context_not_isolated", "评测 Producer 与 审查智能体 必须使用隔离上下文"
                    )
        producer_run_id: str | None = None
        if subject_type == "planning_asset":
            producer_run_id = self._get(connection, "planning_assets", subject_ref)["producer_run_id"]
        elif subject_type == "chapter":
            producer_run_id = self._get(connection, "chapters", subject_ref)["producer_run_id"]
        if producer_run_id:
            producer = self._get(connection, "agent_runs", str(producer_run_id))
            if producer["context_id"] == run["context_id"] or producer["id"] == run["id"]:
                raise NovelOSError("review_context_not_isolated", "生产 Agent 与 审查智能体 必须使用隔离上下文")

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

    def _validate_or_warn_story_arc_cross_check(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        asset_id: str,
        trace_id: str,
    ) -> None:
        asset = self._get(connection, "planning_assets", asset_id)
        cross_check_id = asset["cross_check_id"]
        if cross_check_id:
            check = self._get(connection, "planning_cross_checks", str(cross_check_id))
            upstream_rows = connection.execute(
                "SELECT planning_assets.* FROM planning_assets "
                "JOIN planning_asset_dependencies ON planning_asset_dependencies.upstream_asset_id=planning_assets.id "
                "WHERE planning_asset_dependencies.asset_id=?",
                (asset_id,),
            ).fetchall()
            self._validate_story_arc_cross_check(connection, project_id, list(upstream_rows), check)
            return
        if self.agent_contracts.is_strict("cross_consistency"):
            raise NovelOSError("cross_check_required", "Story Arc 必须绑定 Character/World 交叉审查")
        self._record_trace_step_in_transaction(
            connection,
            trace_id,
            "cross_check.missing",
            "NovelOSService",
            "completed",
            [asset_id],
            [],
            {
                "severity": "warning",
                "enforcement_mode": "lenient",
                "asset_id": asset_id,
                "asset_type": "story_arc",
            },
        )

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
            raise NovelOSError("reviewer_run_required", "权威提交必须绑定独立 审查智能体 run")
        reviewer = self._get(connection, "agent_runs", str(reviewer_run_id))
        if (
            reviewer["trace_id"] != trace_id
            or reviewer["role_id"] != "review_agent"
            or reviewer["status"] != "completed"
        ):
            raise NovelOSError("trace_review_mismatch", "审查智能体 run 必须在同一 Trace 中完成")
        if not self._decode_isolation_evidence(reviewer["isolation_evidence"]):
            if self.agent_contracts.is_strict("isolation_evidence"):
                raise NovelOSError(
                    "missing_isolation_evidence",
                    "权威提交的 审查智能体 run 缺少隔离执行凭据",
                    {"run_id": str(reviewer_run_id), "role": "reviewer"},
                )
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "isolation.evidence.missing",
                "NovelOSService",
                "completed",
                [str(reviewer_run_id)],
                [],
                {
                    "severity": "warning",
                    "enforcement_mode": "lenient",
                    "run_id": str(reviewer_run_id),
                    "role": "reviewer",
                },
            )
        if producer_run_id is not None:
            producer = self._get(connection, "agent_runs", producer_run_id)
            if producer["trace_id"] != trace_id or producer["status"] != "completed":
                raise NovelOSError("trace_producer_mismatch", "生产 Agent run 必须在同一 Trace 中完成")
            if not self._decode_isolation_evidence(producer["isolation_evidence"]):
                if self.agent_contracts.is_strict("isolation_evidence"):
                    raise NovelOSError(
                        "missing_isolation_evidence",
                        "权威提交的生产 Agent run 缺少隔离执行凭据",
                        {"run_id": producer_run_id, "role": "producer"},
                    )
                self._record_trace_step_in_transaction(
                    connection,
                    trace_id,
                    "isolation.evidence.missing",
                    "NovelOSService",
                    "completed",
                    [producer_run_id],
                    [],
                    {
                        "severity": "warning",
                        "enforcement_mode": "lenient",
                        "run_id": producer_run_id,
                        "role": "producer",
                    },
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
            "主控智能体",
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

    def _create_creator_profile_in_transaction(
        self,
        connection: sqlite3.Connection,
        display_name: str,
        signature: dict[str, Any],
        *,
        parent_version_id: str | None = None,
        derivation: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        profile_id = _id("creator-profile")
        connection.execute(
            "INSERT INTO creator_profiles(id, display_name) VALUES (?, ?)",
            (profile_id, _require_text(display_name, "display_name")),
        )
        version = self._insert_creator_profile_version(
            connection,
            profile_id,
            1,
            self.creative_contracts.validate_signature(signature),
            parent_version_id=parent_version_id,
            derivation=derivation,
        )
        return self._creator_profile(connection, profile_id), version

    def _insert_creator_profile_version(
        self,
        connection: sqlite3.Connection,
        profile_id: str,
        revision: int,
        signature: dict[str, Any],
        *,
        parent_version_id: str | None = None,
        derivation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if parent_version_id is not None:
            self._get(connection, "creator_profile_versions", parent_version_id)
        content_resource_id, digest = self._resource(connection, _json(signature), "application/json")
        derivation_resource_id: str | None = None
        if derivation is not None:
            derivation_resource_id, _ = self._resource(connection, _json(derivation), "application/json")
        version_id = _id("creator-profile-version")
        connection.execute(
            "INSERT INTO creator_profile_versions(id, profile_id, revision, content_resource_id, subject_hash, parent_version_id, derivation_resource_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                version_id,
                profile_id,
                revision,
                content_resource_id,
                digest,
                parent_version_id,
                derivation_resource_id,
            ),
        )
        return self._creator_profile_version(connection, version_id)

    def _creator_profile(self, connection: sqlite3.Connection, profile_id: str) -> dict[str, Any]:
        profile = self._row(self._get(connection, "creator_profiles", profile_id))
        rows = connection.execute(
            "SELECT id FROM creator_profile_versions WHERE profile_id=? ORDER BY revision, id",
            (profile_id,),
        ).fetchall()
        if not rows:
            raise NovelOSError("invalid_state", "作者 Profile 缺少版本", {"profile_id": profile_id})
        versions = [self._creator_profile_version(connection, str(row["id"])) for row in rows]
        profile["versions"] = versions
        profile["latest_version"] = versions[-1]
        return profile

    def _creator_profile_version(
        self,
        connection: sqlite3.Connection,
        profile_version_id: str,
    ) -> dict[str, Any]:
        row = self._get(connection, "creator_profile_versions", profile_version_id)
        result = self._row(row)
        resource = self._get(connection, "resources", str(row["content_resource_id"]))
        try:
            signature = json.loads(bytes(resource["content"]).decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise NovelOSError("invalid_state", "作者签名 Resource 已损坏") from exc
        result["signature"] = self.creative_contracts.validate_signature(signature)
        derivation_id = row["derivation_resource_id"]
        if derivation_id:
            derivation_resource = self._get(connection, "resources", str(derivation_id))
            result["derivation"] = json.loads(bytes(derivation_resource["content"]).decode("utf-8"))
            result["derivation_ref"] = f"novelos://resource/{derivation_id}"
        else:
            result["derivation"] = None
            result["derivation_ref"] = None
        result.pop("derivation_resource_id", None)
        result["constraint_ref"] = creator_signature_ref(
            str(row["profile_id"]),
            int(row["revision"]),
            str(row["id"]),
            str(row["subject_hash"]),
        )
        return result

    def _resolve_creator_request(
        self,
        connection: sqlite3.Connection,
        creator: dict[str, Any],
    ) -> tuple[sqlite3.Row, str]:
        if not isinstance(creator, dict):
            raise NovelOSError("invalid_creator_binding", "creator 必须是对象")
        mode = creator.get("mode")
        expected_fields = {
            "reuse": {"mode", "profile_version_id", "subject_hash"},
            "create": {"mode", "display_name", "signature"},
            "derive": {"mode", "parent_version_id", "parent_subject_hash", "display_name", "overrides"},
        }
        if mode not in expected_fields or set(creator) != expected_fields[mode]:
            raise NovelOSError(
                "invalid_creator_binding",
                "作者绑定模式或字段非法",
                {"mode": mode, "actual": sorted(creator)},
            )
        if mode != "derive":
            raise NovelOSError(
                "invalid_creator_binding",
                "项目创建向导只支持从系统原型派生 (mode='derive')",
                {"mode": mode},
            )

        parent = self._get(connection, "creator_profile_versions", str(creator["parent_version_id"]))
        if parent["subject_hash"] != _require_sha256(creator["parent_subject_hash"], "parent_subject_hash"):
            raise NovelOSError("hash_mismatch", "派生父作者签名版本 Hash 不一致")

        parent_profile = self._get(connection, "creator_profiles", str(parent["profile_id"]))
        if parent_profile["status"] != "active":
            raise NovelOSError("invalid_state", "不能从已归档作者 Profile 派生")
        if parent_profile["ownership"] != "system_archetype":
            raise NovelOSError(
                "invalid_creator_binding",
                "新项目派生必须以系统叙事原型为父版本",
                {"parent_profile_id": parent["profile_id"]},
            )



        base = self._creator_profile_version(connection, str(parent["id"]))["signature"]
        signature, overrides = self.creative_contracts.derive_signature(base, creator["overrides"])
        _, created = self._create_creator_profile_in_transaction(
            connection,
            creator["display_name"],
            signature,
            parent_version_id=str(parent["id"]),
            derivation=overrides,
        )
        return self._get(connection, "creator_profile_versions", str(created["id"])), mode

    def _insert_project_creator_binding(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        profile_version: sqlite3.Row,
        mode: str,
    ) -> dict[str, Any]:
        connection.execute(
            "INSERT INTO project_creator_bindings(project_id, profile_id, profile_version_id, profile_revision, subject_hash, binding_mode) VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                profile_version["profile_id"],
                profile_version["id"],
                profile_version["revision"],
                profile_version["subject_hash"],
                mode,
            ),
        )
        return self._project_creator_binding(connection, project_id)

    @staticmethod
    def _binding_constraint_ref(binding: sqlite3.Row) -> str:
        return creator_signature_ref(
            str(binding["profile_id"]),
            int(binding["profile_revision"]),
            str(binding["profile_version_id"]),
            str(binding["subject_hash"]),
        )

    def _project_creator_binding(
        self,
        connection: sqlite3.Connection,
        project_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM project_creator_bindings WHERE project_id=?", (project_id,)
        ).fetchone()
        if row is None:
            raise NovelOSError("creator_binding_required", "项目尚未绑定作者签名", {"project_id": project_id})
        result = self._row(row)
        result["constraint_ref"] = self._binding_constraint_ref(row)
        profile = self._get(connection, "creator_profiles", str(row["profile_id"]))
        result["profile_display_name"] = profile["display_name"]
        result["profile_status"] = profile["status"]
        result["profile_version"] = self._creator_profile_version(connection, str(row["profile_version_id"]))
        return result

    def _project_style_refs(self, connection: sqlite3.Connection, project_id: str) -> list[str]:
        binding = self._project_creator_binding(connection, project_id)
        direction = connection.execute(
            "SELECT * FROM planning_assets WHERE project_id=? AND asset_type='direction' AND status='locked' ORDER BY revision DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if direction is None:
            raise NovelOSError("locked_direction_required", "作者约束写作需要已锁定 Story Direction")
        return [
            str(binding["constraint_ref"]),
            planning_constraint_ref(str(direction["id"]), int(direction["version"]), str(direction["subject_hash"])),
        ]

    def _validate_creative_agent_inputs(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        role_id: str,
        input_bindings: dict[str, Any],
    ) -> None:
        binding_row = connection.execute(
            "SELECT * FROM project_creator_bindings WHERE project_id=?", (project_id,)
        ).fetchone()
        if binding_row is None:
            return
        creator_ref = self._binding_constraint_ref(binding_row)
        if role_id == "direction_agent":
            if input_bindings.get("creator_signature_ref") != creator_ref:
                raise NovelOSError(
                    "creator_binding_mismatch",
                    "方向智能体必须绑定项目当前作者签名版本",
                    {"expected": creator_ref},
                )
            return
        if role_id == "writer_agent":
            actual_value = input_bindings.get("style_refs")
            actual = set(actual_value if isinstance(actual_value, list) else [actual_value])
            expected = set(self._project_style_refs(connection, project_id))
            if not expected.issubset(actual):
                raise NovelOSError(
                    "creator_binding_mismatch",
                    "写作智能体 style_refs 缺少当前作者签名或锁定 Direction",
                    {"expected": sorted(expected)},
                )

    def _validate_direction_author_contract(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        producer_run_id: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise NovelOSError("invalid_argument", "规划 metadata 必须是对象")
        binding_row = connection.execute(
            "SELECT * FROM project_creator_bindings WHERE project_id=?", (project_id,)
        ).fetchone()
        if binding_row is None:
            if "book_soul" in metadata:
                normalized = dict(metadata)
                normalized["book_soul"] = self.creative_contracts.validate_book_soul(metadata["book_soul"])
                return normalized
            return dict(metadata)
        if producer_run_id is None:
            raise NovelOSError("producer_run_required", "绑定作者签名的 Direction 必须来自方向智能体 run")
        creator_ref = self._binding_constraint_ref(binding_row)
        if metadata.get("creator_signature_ref") != creator_ref:
            raise NovelOSError(
                "creator_binding_mismatch",
                "Direction metadata 未绑定项目当前作者签名",
                {"expected": creator_ref},
            )
        if "book_soul" not in metadata:
            raise NovelOSError("invalid_book_soul", "Direction 缺少 book_soul")
        run = self._get(connection, "agent_runs", producer_run_id)
        bindings = json.loads(run["input_bindings_json"])
        if bindings.get("creator_signature_ref") != creator_ref:
            raise NovelOSError("creator_binding_mismatch", "方向智能体 run 使用了过期作者签名")
        normalized = dict(metadata)
        normalized["book_soul"] = self.creative_contracts.validate_book_soul(metadata["book_soul"])
        return normalized

    def _validate_chapter_soul_contract(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(metadata, dict):
            raise NovelOSError("invalid_argument", "规划 metadata 必须是对象")
        binding = connection.execute(
            "SELECT 1 FROM project_creator_bindings WHERE project_id=?",
            (project_id,),
        ).fetchone()
        has_contract = "soul_pressure" in metadata or "moral_residue" in metadata
        if binding is None and not has_contract:
            return dict(metadata)
        if "soul_pressure" not in metadata or "moral_residue" not in metadata:
            raise NovelOSError(
                "invalid_chapter_soul_contract",
                "绑定作者签名的 Chapter Plan 必须同时包含 soul_pressure 与 moral_residue",
            )
        direction = connection.execute(
            "SELECT * FROM planning_assets WHERE project_id=? AND asset_type='direction' AND status='locked' ORDER BY revision DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if direction is None:
            raise NovelOSError("locked_direction_required", "Chapter Plan 思想压力契约需要 locked Direction")
        expected_ref = planning_constraint_ref(
            str(direction["id"]),
            int(direction["version"]),
            str(direction["subject_hash"]),
        )
        contract = self.creative_contracts.validate_chapter_soul(
            {
                "soul_pressure": metadata["soul_pressure"],
                "moral_residue": metadata["moral_residue"],
            }
        )
        if contract["soul_pressure"]["direction_ref"] != expected_ref:
            raise NovelOSError(
                "creator_binding_mismatch",
                "Chapter Plan soul_pressure 未绑定当前 locked Direction",
                {"expected": expected_ref},
            )
        normalized = dict(metadata)
        normalized.update(contract)
        return normalized

    @staticmethod
    def _creative_rebind_affected_assets(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> list[str]:
        rows = connection.execute(
            """
            WITH RECURSIVE affected(id) AS (
                SELECT id FROM planning_assets
                WHERE project_id=? AND asset_type='direction' AND status IN ('candidate', 'locked')
                UNION
                SELECT dependencies.asset_id
                FROM planning_asset_dependencies dependencies
                JOIN affected parent ON dependencies.upstream_asset_id=parent.id
            )
            SELECT assets.id
            FROM planning_assets assets
            JOIN affected ON affected.id=assets.id
            WHERE assets.status IN ('candidate', 'locked')
            ORDER BY assets.id
            """,
            (project_id,),
        ).fetchall()
        return [str(row["id"]) for row in rows]

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

    @staticmethod
    def _assert_project_deletable(connection: sqlite3.Connection, project_id: str) -> None:
        running_traces = connection.execute(
            "SELECT id FROM traces WHERE project_id=? AND status='running' ORDER BY id",
            (project_id,),
        ).fetchall()
        if running_traces:
            raise NovelOSError(
                "project_delete_blocked",
                "项目存在运行中的 Trace，不能删除",
                {"project_id": project_id, "trace_ids": [row["id"] for row in running_traces]},
            )
        authority_commits = connection.execute(
            "SELECT id FROM authority_commits WHERE project_id=? ORDER BY id",
            (project_id,),
        ).fetchall()
        if authority_commits:
            raise NovelOSError(
                "project_delete_blocked",
                "项目已有权威提交，不能物理删除",
                {"project_id": project_id, "authority_commit_ids": [row["id"] for row in authority_commits]},
            )

    @staticmethod
    def _project_delete_counts(connection: sqlite3.Connection, project_id: str) -> dict[str, int]:
        direct_tables = (
            "planning_assets",
            "planning_cross_checks",
            "characters",
            "worlds",
            "factions",
            "rules",
            "timelines",
            "chapter_facts",
            "continuity_candidate_sets",
            "narrative_promises",
            "expectation_ledgers",
            "relationship_states",
            "arc_states",
            "entity_mutations",
            "project_creator_bindings",
        )
        counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE project_id=?", (project_id,)).fetchone()[0])
            for table in direct_tables
        }
        counts["books"] = int(connection.execute("SELECT COUNT(*) FROM books WHERE project_id=?", (project_id,)).fetchone()[0])
        counts["volumes"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM volumes JOIN books ON books.id=volumes.book_id WHERE books.project_id=?",
                (project_id,),
            ).fetchone()[0]
        )
        counts["chapters"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM chapters JOIN volumes ON volumes.id=chapters.volume_id "
                "JOIN books ON books.id=volumes.book_id WHERE books.project_id=?",
                (project_id,),
            ).fetchone()[0]
        )
        counts["traces_detached"] = int(connection.execute("SELECT COUNT(*) FROM traces WHERE project_id=?", (project_id,)).fetchone()[0])
        counts["agent_runs_retained"] = int(
            connection.execute(
                "SELECT COUNT(*) FROM agent_runs JOIN traces ON traces.id=agent_runs.trace_id WHERE traces.project_id=?",
                (project_id,),
            ).fetchone()[0]
        )
        return counts

    @classmethod
    def _require_expected_version(cls, row: sqlite3.Row, expected_version: int | None) -> None:
        if expected_version is None:
            raise NovelOSError("expected_version_required", "更新已有资产必须提供 expected_version")
        cls._check_version(row, expected_version)

    @staticmethod
    def _validate_page(limit: int, offset: int) -> None:
        if not 1 <= limit <= 200 or offset < 0:
            raise NovelOSError("invalid_pagination", "limit 必须为 1..200 且 offset >= 0")

    def _read_projection_snapshot(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        include_candidates: bool = True,
        include_all_outputs: bool = True,
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

        binding_row = connection.execute(
            "SELECT * FROM project_creator_bindings WHERE project_id=?",
            (project_id,),
        ).fetchone()
        creator_signature = None
        if binding_row is not None:
            version = self._creator_profile_version(connection, str(binding_row["profile_version_id"]))
            profile = self._get(connection, "creator_profiles", str(binding_row["profile_id"]))
            creator_signature = {
                "profile_id": str(binding_row["profile_id"]),
                "profile_display_name": str(profile["display_name"]),
                "profile_version_id": str(binding_row["profile_version_id"]),
                "profile_revision": int(binding_row["profile_revision"]),
                "subject_hash": str(binding_row["subject_hash"]),
                "binding_mode": str(binding_row["binding_mode"]),
                "constraint_ref": self._binding_constraint_ref(binding_row),
                "signature": version["signature"],
            }

        locked_direction = planning_assets.get("direction")
        book_soul = None
        if locked_direction is not None:
            direction_metadata = locked_direction.get("metadata") or {}
            if "book_soul" in direction_metadata:
                book_soul = {
                    "direction_id": locked_direction["id"],
                    "direction_version": locked_direction["version"],
                    "direction_subject_hash": locked_direction["subject_hash"],
                    "direction_constraint_ref": planning_constraint_ref(
                        str(locked_direction["id"]),
                        int(locked_direction["version"]),
                        str(locked_direction["subject_hash"]),
                    ),
                    "book_soul": self.creative_contracts.validate_book_soul(
                        direction_metadata["book_soul"]
                    ),
                }

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
            "creator_signature": creator_signature,
            "book_soul": book_soul,
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
        if include_all_outputs:
            # 展示目录的“产出/”保留所有状态，供用户查看工作过程；它不参与
            # authority_snapshot_hash，也不改变“规划/”“正文/”中的当前权威语义。
            planning_output_rows = connection.execute(
                "SELECT * FROM planning_assets WHERE project_id=? AND status!='locked' ORDER BY asset_type, revision, id",
                (project_id,),
            ).fetchall()
            planning_outputs = []
            for row in planning_output_rows:
                item = self._row(row)
                res_id = item["resource_ref"].replace("novelos://resource/", "")
                item["content"] = self.get_resource(res_id)
                planning_outputs.append(item)

            chapter_output_rows = connection.execute(
                """
                SELECT c.*, v.number AS volume_number, v.title AS volume_title
                FROM chapters c
                JOIN volumes v ON c.volume_id = v.id
                JOIN books b ON v.book_id = b.id
                WHERE b.project_id=? AND c.status!='accepted'
                ORDER BY v.number, c.number, c.id
                """,
                (project_id,),
            ).fetchall()
            chapter_outputs = []
            for row in chapter_output_rows:
                item = self._row(row)
                res_id = item["resource_ref"].replace("novelos://resource/", "")
                item["content"] = self.get_resource(res_id)
                chapter_outputs.append(item)

            agent_output_rows = connection.execute(
                """
                SELECT agent_runs.* FROM agent_runs
                JOIN traces ON traces.id=agent_runs.trace_id
                WHERE traces.project_id=? AND agent_runs.status='completed'
                  AND agent_runs.output_resource_id IS NOT NULL
                ORDER BY agent_runs.created_at, agent_runs.id
                """,
                (project_id,),
            ).fetchall()
            agent_outputs = []
            for row in agent_output_rows:
                item = self._row(row)
                output_ref = item.get("output_ref")
                if not output_ref:
                    continue
                item["content"] = self.get_resource(output_ref.replace("novelos://resource/", ""))
                agent_outputs.append(item)
            snapshot_payload["planning_output_assets"] = planning_outputs
            snapshot_payload["chapter_output_drafts"] = chapter_outputs
            snapshot_payload["agent_outputs"] = agent_outputs
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
