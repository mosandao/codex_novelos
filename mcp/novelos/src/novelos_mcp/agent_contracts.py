from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource

from novelos_mcp.errors import NovelOSError


def _default_contract_path() -> Path:
    candidates = (
        Path.cwd() / "config" / "agents.yaml",
        Path(__file__).resolve().parents[4] / "config" / "agents.yaml",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise NovelOSError(
        "configuration_error",
        "找不到 Agent 契约配置",
        {"candidates": [str(candidate) for candidate in candidates]},
    )


class AgentContractStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else _default_contract_path()
        try:
            payload = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise NovelOSError("configuration_error", "Agent 契约配置无法读取", {"path": str(self.path)}) from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise NovelOSError("configuration_error", "Agent 契约 schema_version 非法")
        roles = payload.get("roles")
        if not isinstance(roles, dict) or not roles:
            raise NovelOSError("configuration_error", "Agent 契约缺少 roles")
        self.config = payload
        self.roles: dict[str, dict[str, Any]] = roles
        self.routes: dict[str, list[str]] = payload.get("review_profile_routes", {})
        self._validate_roles()
        self._validate_routes()
        root = self.path.parents[1]
        result_path = root / payload["runtime"]["result_schema"]
        proposal_path = root / payload["runtime"]["change_proposal_schema"]
        self.result_schema = json.loads(result_path.read_text(encoding="utf-8"))
        self.proposal_schema = json.loads(proposal_path.read_text(encoding="utf-8"))
        registry = Registry().with_resource(
            self.proposal_schema["$id"], Resource.from_contents(self.proposal_schema)
        )
        self.result_validator = jsonschema.Draft202012Validator(self.result_schema, registry=registry)
        self.proposal_validator = jsonschema.Draft202012Validator(self.proposal_schema)

    def get(self, role_id: str) -> dict[str, Any]:
        try:
            return self.roles[role_id]
        except KeyError as exc:
            raise NovelOSError("invalid_agent_role", "未知 Agent role", {"role_id": role_id}) from exc

    def review_packages(self, profile: str) -> list[str]:
        if not isinstance(self.routes, dict) or profile not in self.routes:
            raise NovelOSError("invalid_review_profile", "未知 Review Profile", {"profile": profile})
        packages = self.routes[profile]
        if not isinstance(packages, list) or not packages:
            raise NovelOSError("invalid_review_profile", "Review Profile 未关联有效 Catalog 包", {"profile": profile})
        return list(packages)

    def validate_inputs(self, role_id: str, bindings: dict[str, Any]) -> list[str]:
        role = self.get(role_id)
        if not isinstance(bindings, dict):
            raise NovelOSError("invalid_agent_input", "input_bindings 必须是对象")
        required = set(role["minimum_inputs"])
        actual = set(bindings)
        if actual != required:
            raise NovelOSError(
                "invalid_agent_input",
                "Agent 最小输入不完整或包含越界字段",
                {"required": sorted(required), "actual": sorted(actual)},
            )
        refs: list[str] = []
        for name, value in bindings.items():
            values = value if isinstance(value, list) else [value]
            if not values or any(not isinstance(item, str) or not item.strip() for item in values):
                raise NovelOSError("invalid_agent_input", "Agent 输入必须是非空字符串或非空字符串数组", {"field": name})
            refs.extend(values)
        return list(dict.fromkeys(refs))

    def validate_spawn(self, role_id: str, bindings: dict[str, Any]) -> None:
        gate = self.config.get("spawn_gates", {}).get(role_id)
        if gate is None:
            return
        field = gate["evidence_field"]
        values = bindings.get(field)
        normalized = values if isinstance(values, list) else [values]
        allowed = set(gate["allowed_values"])
        if not normalized or not set(normalized).issubset(allowed):
            raise NovelOSError(
                "spawn_condition_not_met",
                "Agent 创建条件未满足",
                {"role_id": role_id, "required_any_of": sorted(allowed)},
            )

    def validate_result(self, result: dict[str, Any]) -> None:
        try:
            self.result_validator.validate(result)
        except jsonschema.ValidationError as exc:
            raise NovelOSError("invalid_agent_result", "Agent result 不符合 Schema", {"path": list(exc.path)}) from exc

    def validate_change_proposals(self, proposals: list[dict[str, Any]]) -> None:
        if not isinstance(proposals, list):
            raise NovelOSError("invalid_change_proposal", "change_proposals 必须是数组")
        for index, proposal in enumerate(proposals):
            try:
                self.proposal_validator.validate(proposal)
            except jsonschema.ValidationError as exc:
                raise NovelOSError(
                    "invalid_change_proposal",
                    "change proposal 不符合 Schema",
                    {"index": index, "path": list(exc.path)},
                ) from exc

    def validate_change_proposals_for_role(
        self,
        role_id: str,
        proposals: list[dict[str, Any]],
    ) -> None:
        self.validate_change_proposals(proposals)
        role = self.get(role_id)
        if not proposals or role["kind"] != "planning_asset":
            return
        upstream_by_asset = {
            item["owned_asset_type"]: set(item["required_upstream_types"])
            for item in self.roles.values()
            if item["kind"] == "planning_asset"
        }
        allowed: set[str] = set()
        pending = list(role["required_upstream_types"])
        while pending:
            asset_type = pending.pop()
            if asset_type in allowed:
                continue
            allowed.add(asset_type)
            pending.extend(upstream_by_asset.get(asset_type, set()))
        invalid = sorted(
            {proposal["target_asset_type"] for proposal in proposals} - allowed
        )
        if invalid:
            raise NovelOSError(
                "invalid_change_proposal",
                "规划 Agent 只能向自己的上游资产提交变更提案",
                {"role_id": role_id, "allowed": sorted(allowed), "invalid": invalid},
            )
        owned_asset = role["owned_asset_type"]
        for proposal in proposals:
            target = proposal["target_asset_type"]
            downstream = {target}
            changed = True
            while changed:
                before = len(downstream)
                downstream.update(
                    asset_type
                    for asset_type, dependencies in upstream_by_asset.items()
                    if dependencies & downstream
                )
                changed = len(downstream) != before
            affected = set(proposal["affected_asset_types"])
            if owned_asset not in affected or not affected.issubset(downstream - {target}):
                raise NovelOSError(
                    "invalid_change_proposal",
                    "影响范围必须包含当前资产且只能引用目标上游的下游资产",
                    {
                        "role_id": role_id,
                        "required": owned_asset,
                        "allowed": sorted(downstream - {target}),
                        "actual": sorted(affected),
                    },
                )

    def _validate_roles(self) -> None:
        persistent = [role_id for role_id, role in self.roles.items() if role.get("lifecycle") == "persistent"]
        if persistent != [self.config["runtime"]["persistent_role"]]:
            raise NovelOSError("configuration_error", "必须且只能有一个常驻 主控智能体")
        planning_assets: set[str] = set()
        for role_id, role in self.roles.items():
            required = {
                "display_name", "kind", "lifecycle", "owned_asset_type", "required_upstream_types",
                "minimum_inputs", "allowed_tools", "output_types", "review_profile", "catalog_package",
                "spawn_condition", "must_destroy",
            }
            if set(role) != required:
                raise NovelOSError("configuration_error", "Agent role 字段不合法", {"role_id": role_id})
            if role_id == "review_agent" and role["catalog_package"] is not None:
                raise NovelOSError("configuration_error", "review_agent catalog_package 必须为 null")
            if role["kind"] == "planning_asset":
                asset_type = role["owned_asset_type"]
                if not isinstance(asset_type, str) or asset_type in planning_assets:
                    raise NovelOSError("configuration_error", "规划资产必须有唯一 Agent owner", {"role_id": role_id})
                planning_assets.add(asset_type)

    def _validate_routes(self) -> None:
        routes = self.config.get("review_profile_routes")
        if not isinstance(routes, dict) or not routes:
            raise NovelOSError("configuration_error", "Agent 契约缺少 review_profile_routes")
        expected_profiles = {
            "planning-direction", "planning-architecture", "planning-strategy",
            "planning-character-contract", "planning-world-contract", "planning-story-arc",
            "planning-volume-outline", "planning-chapter-plan",
            "planning-character-world-cross-consistency", "entity-character",
            "entity-world", "entity-faction", "entity-rule", "entity-timeline",
            "prose-v1", "continuity-v1",
        }
        if not expected_profiles.issubset(routes.keys()):
            missing = sorted(expected_profiles - routes.keys())
            raise NovelOSError("configuration_error", "review_profile_routes 缺失权威 Profile", {"missing": missing})
        for profile, packages in routes.items():
            if not isinstance(packages, list) or not packages:
                raise NovelOSError("configuration_error", "review_profile_routes 列表不能为空", {"profile": profile})
            if any(not isinstance(pkg, str) or not pkg.strip() for pkg in packages):
                raise NovelOSError("configuration_error", "review_profile_routes 必须是非空字符串列表", {"profile": profile})
            if len(packages) != len(set(packages)):
                raise NovelOSError("configuration_error", "review_profile_routes 包含重复包名", {"profile": profile})
