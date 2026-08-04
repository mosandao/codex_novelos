from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml
from referencing import Registry, Resource

from novelos_mcp.errors import NovelOSError


_REVIEW_PROFILE_BINDING_KEYS = {
    "chapter_acceptance",
    "continuity_promotion",
    "entity_authority",
}
_ENTITY_REVIEW_BINDING_KEYS = {"character", "world", "faction", "rule", "timeline"}


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
        runtime = payload.get("runtime")
        if not isinstance(runtime, dict):
            raise NovelOSError("configuration_error", "Agent 契约缺少 runtime 配置")
        self.config = payload
        self.roles: dict[str, dict[str, Any]] = roles
        self.routes: dict[str, list[str]] = payload.get("review_profile_routes", {})
        self.enforcement = self._validate_enforcement(runtime.get("enforcement"))
        self._validate_roles()
        self._validate_routes()
        self._asset_review_profile = self._derive_planning_review_profiles()
        root = self.path.parents[1]
        result_path = root / payload["runtime"]["result_schema"]
        proposal_path = root / payload["runtime"]["change_proposal_schema"]
        self.result_schema = json.loads(result_path.read_text(encoding="utf-8"))
        self.proposal_schema = json.loads(proposal_path.read_text(encoding="utf-8"))
        self.output_schemas = {
            output_type: json.loads((root / schema_path).read_text(encoding="utf-8"))
            for output_type, schema_path in payload["runtime"].get("output_schemas", {}).items()
        }
        registry = Registry().with_resource(
            self.proposal_schema["$id"], Resource.from_contents(self.proposal_schema)
        )
        self.result_validator = jsonschema.Draft202012Validator(self.result_schema, registry=registry)
        self.proposal_validator = jsonschema.Draft202012Validator(self.proposal_schema)
        self.output_validators = {
            output_type: jsonschema.Draft202012Validator(schema)
            for output_type, schema in self.output_schemas.items()
        }

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

    def review_profile_for_asset(self, asset_type: str) -> str:
        try:
            return self._asset_review_profile[asset_type]
        except KeyError as exc:
            raise NovelOSError(
                "invalid_review_profile",
                "未知或未绑定 Review Profile 的规划资产类型",
                {"asset_type": asset_type},
            ) from exc

    def planning_review_profiles(self) -> dict[str, str]:
        return dict(self._asset_review_profile)

    def review_profile_for_binding(self, name: str) -> str:
        bindings = self.config.get("review_profile_bindings")
        value = bindings.get(name) if isinstance(bindings, dict) else None
        if not isinstance(value, str) or not value.strip() or value not in self.routes:
            raise NovelOSError("invalid_review_profile", "未知 Review Profile 业务绑定", {"binding": name})
        return value

    def review_profile_for_entity(self, entity_type: str) -> str:
        bindings = self.config.get("review_profile_bindings")
        entity_bindings = bindings.get("entity_authority") if isinstance(bindings, dict) else None
        value = entity_bindings.get(entity_type) if isinstance(entity_bindings, dict) else None
        if not isinstance(value, str) or value not in self.routes:
            raise NovelOSError(
                "invalid_review_profile",
                "未知 Entity Review Profile 业务绑定",
                {"entity_type": entity_type},
            )
        return value

    def cross_consistency_profile(self) -> str:
        gate = self.config.get("cross_consistency_gate")
        value = gate.get("profile") if isinstance(gate, dict) else None
        if not isinstance(value, str) or value not in self.routes:
            raise NovelOSError("invalid_review_profile", "交叉一致性 Profile 配置非法")
        return value

    def is_strict(self, name: str) -> bool:
        key = name if name.startswith("strict_") else f"strict_{name}"
        if key not in self.enforcement:
            raise NovelOSError("configuration_error", "未知 enforcement 开关", {"name": name})
        return self.enforcement[key]

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

    def validate_output(self, output_type: str, output: Any) -> None:
        validator = self.output_validators.get(output_type)
        if validator is None:
            return
        try:
            validator.validate(output)
        except jsonschema.ValidationError as exc:
            path = list(exc.path)
            raise NovelOSError(
                "invalid_agent_result",
                f"Agent output 不符合 output_type Schema：path={path}，reason={exc.message}",
                {
                    "output_type": output_type,
                    "path": path,
                    "schema_path": list(exc.schema_path),
                    "reason": exc.message,
                },
            ) from exc

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
        if any(not isinstance(profile, str) or not profile.strip() for profile in routes):
            raise NovelOSError("configuration_error", "review_profile_routes Profile 名必须是非空字符串")
        for profile, packages in routes.items():
            if not isinstance(packages, list) or not packages:
                raise NovelOSError("configuration_error", "review_profile_routes 列表不能为空", {"profile": profile})
            if any(not isinstance(pkg, str) or not pkg.strip() for pkg in packages):
                raise NovelOSError("configuration_error", "review_profile_routes 必须是非空字符串列表", {"profile": profile})
            if len(packages) != len(set(packages)):
                raise NovelOSError("configuration_error", "review_profile_routes 包含重复包名", {"profile": profile})
        references: list[tuple[str, str]] = []
        for role_id, role in self.roles.items():
            value = role.get("review_profile")
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip():
                raise NovelOSError(
                    "configuration_error",
                    "Agent role review_profile 必须是非空字符串或 null",
                    {"role_id": role_id},
                )
            if value == "dynamic":
                if role_id != "review_agent":
                    raise NovelOSError(
                        "configuration_error",
                        "只有 review_agent 可以使用 dynamic Review Profile",
                        {"role_id": role_id},
                    )
                continue
            references.append((f"roles.{role_id}.review_profile", value))
        gate = self.config.get("cross_consistency_gate")
        if not isinstance(gate, dict) or not isinstance(gate.get("profile"), str) or not gate["profile"].strip():
            raise NovelOSError("configuration_error", "cross_consistency_gate.profile 必须是非空字符串")
        references.append(("cross_consistency_gate.profile", gate["profile"]))

        bindings = self.config.get("review_profile_bindings")
        if not isinstance(bindings, dict) or set(bindings) != _REVIEW_PROFILE_BINDING_KEYS:
            raise NovelOSError(
                "configuration_error",
                "review_profile_bindings 字段不完整或包含未知字段",
                {
                    "expected": sorted(_REVIEW_PROFILE_BINDING_KEYS),
                    "actual": sorted(bindings) if isinstance(bindings, dict) else None,
                },
            )
        entity_bindings = bindings["entity_authority"]
        if not isinstance(entity_bindings, dict) or set(entity_bindings) != _ENTITY_REVIEW_BINDING_KEYS:
            raise NovelOSError(
                "configuration_error",
                "entity_authority Review Profile 绑定不完整或包含未知字段",
                {
                    "expected": sorted(_ENTITY_REVIEW_BINDING_KEYS),
                    "actual": sorted(entity_bindings) if isinstance(entity_bindings, dict) else None,
                },
            )
        for name in ("chapter_acceptance", "continuity_promotion"):
            value = bindings[name]
            if not isinstance(value, str) or not value.strip():
                raise NovelOSError(
                    "configuration_error",
                    "Review Profile 业务绑定必须是非空字符串",
                    {"path": f"review_profile_bindings.{name}"},
                )
            references.append((f"review_profile_bindings.{name}", value))
        for entity_type, value in entity_bindings.items():
            if not isinstance(value, str) or not value.strip():
                raise NovelOSError(
                    "configuration_error",
                    "Entity Review Profile 绑定必须是非空字符串",
                    {"path": f"review_profile_bindings.entity_authority.{entity_type}"},
                )
            references.append((f"review_profile_bindings.entity_authority.{entity_type}", value))
        invalid = [ref for ref in references if ref[1] not in routes]
        if invalid:
            raise NovelOSError(
                "configuration_error",
                "配置引用了未注册的 Review Profile",
                {"invalid": [{"path": path, "profile": profile} for path, profile in invalid]},
            )

    def _derive_planning_review_profiles(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for role_id, role in self.roles.items():
            if role.get("kind") != "planning_asset":
                continue
            asset_type = role.get("owned_asset_type")
            profile = role.get("review_profile")
            if not isinstance(asset_type, str) or not asset_type.strip() or not isinstance(profile, str) or not profile.strip():
                raise NovelOSError("configuration_error", "规划 Agent 必须声明 asset_type 与 review_profile", {"role_id": role_id})
            if profile not in self.routes:
                raise NovelOSError("configuration_error", "规划 Agent 引用了未注册 Profile", {"role_id": role_id, "profile": profile})
            if asset_type in result:
                raise NovelOSError("configuration_error", "规划资产类型存在重复 Profile owner", {"asset_type": asset_type})
            result[asset_type] = profile
        return result

    @staticmethod
    def _validate_enforcement(value: Any) -> dict[str, bool]:
        defaults = {"strict_isolation_evidence": False, "strict_cross_consistency": False}
        if value is None:
            return defaults
        if not isinstance(value, dict) or set(value) - set(defaults):
            raise NovelOSError("configuration_error", "runtime.enforcement 配置非法")
        result = dict(defaults)
        for key, flag in value.items():
            if not isinstance(flag, bool):
                raise NovelOSError("configuration_error", "enforcement 开关必须是 boolean", {"key": key})
            result[key] = flag
        return result
