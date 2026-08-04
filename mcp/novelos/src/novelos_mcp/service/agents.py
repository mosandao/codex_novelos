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


class AgentsMixin:

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
            if trace["project_id"] is not None:
                self._validate_creative_agent_inputs(
                    connection,
                    str(trace["project_id"]),
                    role_id,
                    input_bindings,
                )
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
                "主控智能体",
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
                assert output_type is not None
                self.agent_contracts.validate_output(output_type, output)
                if output_type == "review_receipt_candidate":
                    self._validate_review_receipt_candidate(run, output)
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
                "主控智能体",
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
