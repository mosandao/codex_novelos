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
    SIGNATURE_FIELDS,
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


class CreatorsMixin:

    def create_creator_profile(
        self,
        display_name: str,
        signature: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = self.creative_contracts.validate_signature(signature)
        with self.database.transaction() as connection:
            profile, version = self._create_creator_profile_in_transaction(
                connection,
                display_name,
                normalized,
            )
            return {"profile": profile, "version": version}

    def derive_creator_profile(
        self,
        parent_version_id: str,
        parent_subject_hash: str,
        display_name: str,
        overrides: dict[str, Any],
    ) -> dict[str, Any]:
        with self.database.transaction() as connection:
            parent = self._get(connection, "creator_profile_versions", parent_version_id)
            if parent["subject_hash"] != _require_sha256(parent_subject_hash, "parent_subject_hash"):
                raise NovelOSError("hash_mismatch", "父作者签名版本 Hash 不一致")
            base = self._creator_profile_version(connection, parent_version_id)["signature"]
            signature, normalized_overrides = self.creative_contracts.derive_signature(base, overrides)
            profile, version = self._create_creator_profile_in_transaction(
                connection,
                display_name,
                signature,
                parent_version_id=parent_version_id,
                derivation=normalized_overrides,
            )
            return {"profile": profile, "version": version}

    def revise_creator_profile(
        self,
        profile_id: str,
        expected_version: int,
        signature: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = self.creative_contracts.validate_signature(signature)
        with self.database.transaction() as connection:
            profile = self._get(connection, "creator_profiles", profile_id)
            self._check_version(profile, expected_version)
            if profile["ownership"] == "system_archetype":
                raise NovelOSError("invalid_state", "系统叙事原型为只读资源，无法直接修改或修订")
            if profile["status"] != "active":
                raise NovelOSError("invalid_state", "已归档作者 Profile 不能修订")

            parent = connection.execute(
                "SELECT * FROM creator_profile_versions WHERE profile_id=? ORDER BY revision DESC LIMIT 1",
                (profile_id,),
            ).fetchone()
            if parent is None:
                raise NovelOSError("invalid_state", "作者 Profile 缺少历史版本")
            revision = int(parent["revision"]) + 1
            version = self._insert_creator_profile_version(
                connection,
                profile_id,
                revision,
                normalized,
                parent_version_id=str(parent["id"]),
            )
            connection.execute(
                "UPDATE creator_profiles SET version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (profile_id,),
            )
            return {
                "profile": self._creator_profile(connection, profile_id),
                "version": version,
            }

    def archive_creator_profile(self, profile_id: str, expected_version: int) -> dict[str, Any]:
        with self.database.transaction() as connection:
            profile = self._get(connection, "creator_profiles", profile_id)
            self._check_version(profile, expected_version)
            if profile["ownership"] == "system_archetype":
                raise NovelOSError("invalid_state", "系统叙事原型为只读资源，无法归档")
            if profile["status"] == "archived":
                raise NovelOSError("invalid_state", "作者 Profile 已归档")

            connection.execute(
                "UPDATE creator_profiles SET status='archived', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (profile_id,),
            )
            return self._creator_profile(connection, profile_id)

    def get_creator_profile(self, profile_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._creator_profile(connection, profile_id)

    def get_creator_profile_version(self, profile_version_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            return self._creator_profile_version(connection, profile_version_id)

    def list_system_archetypes(self) -> list[dict[str, Any]]:
        with self.database.read() as connection:
            rows = connection.execute(
                "SELECT id FROM creator_profiles WHERE ownership='system_archetype' ORDER BY id"
            ).fetchall()
            return [self._creator_profile(connection, str(row["id"])) for row in rows]

    def list_creator_profiles(
        self,
        status: str = "active",
        ownership: str = "user",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if status not in {"active", "archived", "all"}:
            raise NovelOSError("invalid_argument", "作者 Profile status 非法")
        if ownership not in {"user", "system_archetype", "all"}:
            raise NovelOSError("invalid_argument", "作者 Profile ownership 非法")
        self._validate_page(limit, offset)

        conditions: list[str] = []
        params: list[Any] = []
        if status != "all":
            conditions.append("status=?")
            params.append(status)
        if ownership != "all":
            conditions.append("ownership=?")
            params.append(ownership)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with self.database.read() as connection:
            rows = connection.execute(
                f"SELECT id FROM creator_profiles {where_clause} ORDER BY created_at, id LIMIT ? OFFSET ?",
                tuple(params),
            ).fetchall()
            return [self._creator_profile(connection, str(row["id"])) for row in rows]

    def get_project_creator_binding(self, project_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            return self._project_creator_binding(connection, project_id)

    def get_project_style_refs(self, project_id: str) -> dict[str, Any]:
        with self.database.read() as connection:
            self._get(connection, "projects", project_id)
            refs = self._project_style_refs(connection, project_id)
            return {"project_id": project_id, "style_refs": refs}

    def create_project_with_creator(
        self,
        name: str,
        description: str,
        metadata: dict[str, Any],
        creator: dict[str, Any],
    ) -> dict[str, Any]:
        project_id = _id("project")
        with self.database.transaction() as connection:
            version, mode = self._resolve_creator_request(connection, creator)
            connection.execute(
                "INSERT INTO projects(id, name, description, metadata_json) VALUES (?, ?, ?, ?)",
                (project_id, _require_text(name, "name"), description, _json(metadata)),
            )
            binding = self._insert_project_creator_binding(connection, project_id, version, mode)
            return {
                "project": self._row(self._get(connection, "projects", project_id)),
                "creator_binding": binding,
            }

    def reconcile_project_wizard_archetypes(
        self,
        selected_archetypes: list[dict[str, Any]],
        project_setup: dict[str, Any],
        display_name: str,
        fused_parent_version_id: str | None = None,
        fused_signature: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        把项目向导产出的多原型选择融合成合规的单 parent derive 结构。

        本方法纯读不写。两条路径：

        - 单原型 / 默认（``fused_parent_version_id`` 与 ``fused_signature`` 均缺省）：
          用 ``recommend_archetypes`` 在用户选中子集内打分确定 parent，用
          ``generate_derivation_draft`` 生成基础 overrides，再把其余选中原型的
          ``reader_promise`` 追加到 ``recurring_attention`` 作为辅风格融合。
        - 多原型 LLM 融合（二者同传）：parent 由 onboarding_agent 判定，通过
          ``fused_parent_version_id`` 传入，``fused_signature`` 是 Agent 深度融合后的
          完整签名（含 schema_version）。本方法跳过打分，直接把完整签名折算成相对
          parent 的 overrides diff（自动剔除 schema_version 与等于父原值的字段），
          把「完整签名→diff」的脆弱转换从主控手工挪进 MCP 确定性收口。

        两条路径最后都用 ``derive_signature`` 预校验合并签名合法。返回值可直接作为
        ``project.wizard.submit`` 的 ``creator`` 字段，并带 ``parent_source`` 标记
        （``"scored"`` 或 ``"fused"``）供主控/审查区分 parent 来源。
        """
        normalized_name = _require_text(display_name, "display_name")
        if not isinstance(selected_archetypes, list) or not selected_archetypes:
            raise NovelOSError(
                "invalid_project_setup",
                "selected_archetypes 必须是非空数组",
            )

        # fused 入参必须同传同缺：只给一个会被拒。
        if (fused_parent_version_id is None) != (fused_signature is None):
            raise NovelOSError(
                "invalid_project_setup",
                "fused_parent_version_id 与 fused_signature 必须同时提供或同时缺省",
            )

        # 1. 反查每个选中原型并校验 subject_hash 与 config 一致。
        resolved: list[dict[str, Any]] = []
        for entry in selected_archetypes:
            if not isinstance(entry, dict):
                raise NovelOSError("invalid_project_setup", "selected_archetypes 项必须是对象")
            version_id = _require_text(entry.get("profile_version_id"), "profile_version_id")
            parts = version_id.split(":")
            # 期望格式 creator-profile-version:{archetype_id}:{revision}
            if len(parts) < 3 or parts[0] != "creator-profile-version":
                raise NovelOSError(
                    "invalid_project_setup",
                    "profile_version_id 格式非法",
                    {"value": version_id},
                )
            archetype_id = ":".join(parts[1:-1])
            revision = parts[-1]
            match = next((a for a in self.system_archetypes if a["id"] == archetype_id), None)
            if match is None:
                raise NovelOSError(
                    "invalid_project_setup",
                    "找不到选中的系统叙事原型",
                    {"profile_version_id": version_id},
                )
            subject_hash = _require_sha256(entry.get("subject_hash"), "subject_hash")
            if subject_hash != match["subject_hash"]:
                raise NovelOSError(
                    "hash_mismatch",
                    "选中原型的 subject_hash 与配置不一致",
                    {"profile_version_id": version_id},
                )
            resolved.append(
                {
                    **match,
                    "profile_version_id": f"creator-profile-version:{archetype_id}:{revision}",
                    "user_display_name": _require_text(entry.get("display_name"), "display_name"),
                }
            )

        # 2. 确定 parent 与 overrides。
        if fused_parent_version_id is not None and fused_signature is not None:
            parent, overrides, parent_source = self._reconcile_fused(
                resolved, fused_parent_version_id, fused_signature
            )
        else:
            parent, overrides, parent_source = self._reconcile_scored(resolved, project_setup)

        if not overrides:
            raise NovelOSError(
                "invalid_creator_signature",
                "融合后未产生任何作者签名差异",
            )

        # 3. 预校验合并签名合法（overrides 是相对 parent 的真实 diff 且字段合法）。
        self.creative_contracts.derive_signature(parent["signature"], overrides)

        secondary_names = [a["display_name"] for a in resolved if a["id"] != parent["id"]]
        return {
            "creator": {
                "mode": "derive",
                "parent_version_id": parent["profile_version_id"],
                "parent_subject_hash": parent["subject_hash"],
                "display_name": normalized_name,
                "overrides": overrides,
            },
            "parent_archetype": {
                "id": parent["id"],
                "display_name": parent["display_name"],
                "reader_promise": parent.get("reader_promise", ""),
            },
            "merged_secondary_archetypes": secondary_names,
            "parent_source": parent_source,
        }

    @staticmethod
    def _reconcile_scored(
        resolved: list[dict[str, Any]],
        project_setup: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, list[str]], str]:
        """单原型路径：打分选 parent + generate_derivation_draft + 辅风格融合。"""
        creation_context = project_setup.get("creation_context", {}) if isinstance(project_setup, dict) else {}
        taxonomy = project_setup.get("taxonomy", {}) if isinstance(project_setup, dict) else {}
        primary_genre = creation_context.get("primary_genre", "")
        secondary_directions = creation_context.get("secondary_directions", [])
        emotional_tones = taxonomy.get("emotional_tones", [])
        aesthetic_styles = taxonomy.get("aesthetic_styles", [])
        ranked_ids = recommend_archetypes(
            primary_genre,
            secondary_directions,
            emotional_tones,
            aesthetic_styles,
            resolved,
        )
        parent = next(a for a in resolved if a["id"] == ranked_ids[0])
        overrides = generate_derivation_draft(parent, project_setup)

        merged_promises: list[str] = []
        for archetype in resolved:
            if archetype["id"] == parent["id"]:
                continue
            promise = archetype.get("reader_promise", "").strip()
            if promise:
                merged_promises.append(f"参考《{archetype['display_name']}》的辅风格：{promise}")
        if merged_promises:
            existing = list(
                overrides.get(
                    "recurring_attention",
                    list(parent["signature"].get("recurring_attention", [])),
                )
            )
            for item in merged_promises:
                if item not in existing:
                    existing.append(item)
            overrides["recurring_attention"] = existing
        return parent, overrides, "scored"

    def _reconcile_fused(
        self,
        resolved: list[dict[str, Any]],
        fused_parent_version_id: str,
        fused_signature: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, list[str]], str]:
        """多原型路径：用 Agent 判定的 parent，把完整融合签名折算成 overrides diff。"""
        parent = next(
            (a for a in resolved if a["profile_version_id"] == fused_parent_version_id),
            None,
        )
        if parent is None:
            raise NovelOSError(
                "invalid_project_setup",
                "fused_parent_version_id 必须是已选中的原型之一",
                {"fused_parent_version_id": fused_parent_version_id},
            )
        if not isinstance(fused_signature, dict):
            raise NovelOSError(
                "invalid_project_setup",
                "fused_signature 必须是对象",
            )
        base_signature = parent["signature"]

        # 先校验融合签名本身合法（含 schema_version 等 8 字段），再折算 diff。
        self.creative_contracts.validate_signature(fused_signature)

        # 折算 overrides：只取 7 个签名字段，剔除等于父原值的字段；schema_version
        # 不在 SIGNATURE_FIELDS 内，天然被排除。
        overrides: dict[str, list[str]] = {}
        for field in SIGNATURE_FIELDS:
            fused_value = fused_signature.get(field)
            if fused_value is None:
                continue
            if fused_value != base_signature.get(field):
                overrides[field] = fused_value
        return parent, overrides, "fused"

    def rebind_project_creator(
        self,
        project_id: str,
        expected_version: int,
        profile_version_id: str,
        subject_hash: str,
        trace_id: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized_reason = _require_text(reason, "reason")
        with self.database.transaction() as connection:
            project = self._get(connection, "projects", project_id)
            self._check_version(project, expected_version)
            trace = self._get(connection, "traces", _require_text(trace_id, "trace_id"))
            if trace["status"] != "running" or trace["project_id"] != project_id:
                raise NovelOSError("invalid_trace", "作者重绑定必须属于当前项目的运行中 Trace")
            target = self._get(connection, "creator_profile_versions", profile_version_id)
            if target["subject_hash"] != _require_sha256(subject_hash, "subject_hash"):
                raise NovelOSError("hash_mismatch", "目标作者签名版本 Hash 不一致")
            target_profile = self._get(connection, "creator_profiles", str(target["profile_id"]))
            if target_profile["status"] != "active":
                raise NovelOSError("invalid_state", "不能绑定已归档作者 Profile")
            current_row = connection.execute(
                "SELECT * FROM project_creator_bindings WHERE project_id=?", (project_id,)
            ).fetchone()
            old_ref = self._binding_constraint_ref(current_row) if current_row is not None else None
            new_ref = creator_signature_ref(
                str(target["profile_id"]),
                int(target["revision"]),
                str(target["id"]),
                str(target["subject_hash"]),
            )
            if old_ref == new_ref:
                raise NovelOSError("conflict", "项目已经绑定该作者签名版本")

            affected = self._creative_rebind_affected_assets(connection, project_id)
            if affected:
                placeholders = ",".join("?" for _ in affected)
                connection.execute(
                    f"UPDATE planning_assets SET status='stale', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                    affected,
                )
            if current_row is None:
                binding = self._insert_project_creator_binding(connection, project_id, target, "reuse")
            else:
                connection.execute(
                    "UPDATE project_creator_bindings SET profile_id=?, profile_version_id=?, profile_revision=?, subject_hash=?, binding_mode='reuse', version=version+1, updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                    (
                        target["profile_id"],
                        target["id"],
                        target["revision"],
                        target["subject_hash"],
                        project_id,
                    ),
                )
                binding = self._project_creator_binding(connection, project_id)
            connection.execute(
                "UPDATE projects SET version=version+1, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (project_id,),
            )
            self._record_trace_step_in_transaction(
                connection,
                trace_id,
                "project.creator.rebind",
                "主控智能体",
                "completed",
                [old_ref] if old_ref else [project_id],
                [new_ref],
                {
                    "reason": normalized_reason,
                    "old_creator_signature_ref": old_ref,
                    "new_creator_signature_ref": new_ref,
                    "old_creator_profile_id": str(current_row["profile_id"]) if current_row is not None else None,
                    "old_profile_revision": int(current_row["profile_revision"]) if current_row is not None else None,
                    "old_subject_hash": str(current_row["subject_hash"]) if current_row is not None else None,
                    "new_creator_profile_id": str(target["profile_id"]),
                    "new_profile_revision": int(target["revision"]),
                    "new_subject_hash": str(target["subject_hash"]),
                    "affected_asset_ids": affected,
                },
            )
            return {
                "project": self._row(self._get(connection, "projects", project_id)),
                "creator_binding": binding,
                "stale_asset_ids": affected,
            }
