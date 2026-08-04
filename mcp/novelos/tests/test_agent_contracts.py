from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml
from referencing import Registry, Resource

from novelos_mcp.server import create_server
from novelos_mcp.service import (
    PLANNING_PRODUCERS,
    PLANNING_REVIEW_PROFILES,
    PLANNING_UPSTREAM_TYPES,
)
from agent_test_support import complete_review_run


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "config" / "agents.yaml"
SCHEMA_ROOT = ROOT / "config" / "schemas"
CATALOG_ROOT = ROOT / "catalog" / "skills"


class AgentContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.roles = cls.config["roles"]

    def _store_from_config(self, config: dict) -> "AgentContractStore":
        from novelos_mcp.agent_contracts import AgentContractStore

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(SCHEMA_ROOT, root / "config" / "schemas")
            config_path = root / "config" / "agents.yaml"
            config_path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            return AgentContractStore(config_path)

    def test_only_main_agent_is_persistent(self) -> None:
        persistent = [role_id for role_id, role in self.roles.items() if role["lifecycle"] == "persistent"]
        self.assertEqual(["main_agent"], persistent)
        self.assertEqual("main_agent", self.config["runtime"]["persistent_role"])
        self.assertFalse(self.roles["main_agent"]["must_destroy"])
        self.assertTrue(all(role["must_destroy"] for key, role in self.roles.items() if key != "main_agent"))

    def test_planning_roles_match_service_contracts_exactly(self) -> None:
        planning = {
            role["owned_asset_type"]: role
            for role in self.roles.values()
            if role["kind"] == "planning_asset"
        }
        self.assertEqual(set(PLANNING_UPSTREAM_TYPES), set(planning))
        for asset_type, role in planning.items():
            self.assertEqual(PLANNING_PRODUCERS[asset_type], role["display_name"])
            self.assertEqual(set(PLANNING_UPSTREAM_TYPES[asset_type]), set(role["required_upstream_types"]))
            self.assertEqual(PLANNING_REVIEW_PROFILES[asset_type], role["review_profile"])
            self.assertEqual(["planning_candidate", "change_proposal"], role["output_types"])

    def test_temporary_roles_only_receive_registered_read_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(Path(directory) / "novelos.db")
            registered = set(server._tool_manager._tools)
        for role_id, role in self.roles.items():
            if role_id == "main_agent":
                self.assertEqual(["*"], role["allowed_tools"])
                continue
            self.assertTrue(set(role["allowed_tools"]).issubset(registered), role_id)
            self.assertTrue(all(tool.split(".", 1)[-1] in {
                "get", "list", "search", "validate", "validate_input", "validate_output",
                "validate_contract_inputs", "get_subject", "review_route",
                "get_version",
                "recent_chapters", "search_facts", "get_entity_states", "get_authority_snapshot",
            } for tool in role["allowed_tools"]), role_id)

    def test_planning_catalog_packages_exist_and_match_assets(self) -> None:
        for role in self.roles.values():
            if role["kind"] != "planning_asset":
                continue
            matches = list(CATALOG_ROOT.glob(f"*/{role['catalog_package']}/metadata.yaml"))
            self.assertEqual(1, len(matches), role["catalog_package"])
            metadata = yaml.safe_load(matches[0].read_text(encoding="utf-8"))
            self.assertEqual(role["owned_asset_type"], metadata["asset"])

    def test_cross_consistency_gate_uses_independent_reviewer(self) -> None:
        gate = self.config["cross_consistency_gate"]
        self.assertEqual({"character_contract", "world_contract"}, set(gate["subject_types"]))
        self.assertEqual("story_arc", gate["required_before"])
        reviewer = self.roles[gate["reviewer_role"]]
        self.assertEqual("review", reviewer["kind"])
        self.assertIsNone(reviewer["owned_asset_type"])
        self.assertIn("review.get_subject", reviewer["allowed_tools"])
        self.assertTrue(
            all(
                "review.get_subject" not in role["allowed_tools"]
                for role_id, role in self.roles.items()
                if role_id not in {"main_agent", gate["reviewer_role"]}
            )
        )

    def test_context_builder_has_fail_closed_spawn_gate(self) -> None:
        gate = self.config["spawn_gates"]["context_builder"]
        self.assertEqual("complexity_reasons", gate["evidence_field"])
        self.assertEqual(
            {"cross_volume", "multiple_threads", "conflicting_facts", "context_overflow"},
            set(gate["allowed_values"]),
        )
        self.assertIn("complexity_reasons", self.roles["context_builder"]["minimum_inputs"])

    def test_typed_result_and_change_proposal_schemas_fail_closed(self) -> None:
        result_schema = json.loads((SCHEMA_ROOT / "agent-result.schema.json").read_text(encoding="utf-8"))
        change_schema = json.loads((SCHEMA_ROOT / "change-proposal.schema.json").read_text(encoding="utf-8"))
        registry = Registry().with_resource(change_schema["$id"], Resource.from_contents(change_schema))
        validator = jsonschema.Draft202012Validator(result_schema, registry=registry)
        valid = {
            "role": "architecture_agent",
            "run_id": "agent-run:1",
            "status": "completed",
            "input_refs": ["planning:direction:1"],
            "output_type": "planning_candidate",
            "output_ref": "novelos://resource/1",
            "change_proposals": [],
        }
        validator.validate(valid)
        invalid = dict(valid, unexpected=True)
        with self.assertRaises(jsonschema.ValidationError):
            validator.validate(invalid)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.Draft202012Validator(change_schema).validate({"reason": "缺少绑定字段"})

    def test_output_type_schemas_fail_closed(self) -> None:
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        store = AgentContractStore(CONFIG_PATH)
        store.validate_output("planning_candidate", "有效候选")
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            store.validate_output("planning_candidate", {"content": "错误外壳"})

        receipt = {
            "subject_type": "planning_asset",
            "subject_ref": "planning:1",
            "subject_hash": "sha256:" + "a" * 64,
            "verdict": "approved",
            "findings": [
                {
                    "severity": "note",
                    "code": "direction.coherent",
                    "message": "方向一致",
                    "evidence_refs": ["planning:1"],
                }
            ],
            "reviewer_profile": "planning-direction",
            "evidence_refs": ["planning:1"],
        }
        store.validate_output("review_receipt_candidate", receipt)
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            store.validate_output(
                "review_receipt_candidate",
                dict(receipt, reviewer_run_id="agent-run:forbidden"),
            )
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            store.validate_output(
                "review_receipt_candidate",
                dict(receipt, assessment={"summary": "普通 Review 不应携带"}),
            )

    def test_review_profile_routes_validation_and_unknown_profile_fail_closed(self) -> None:
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        store = AgentContractStore(CONFIG_PATH)
        for profile in self.config["review_profile_routes"]:
            packages = store.review_packages(profile)
            self.assertTrue(isinstance(packages, list) and len(packages) > 0, profile)

        for profile, specific in [
            ("planning-direction", "planning-direction-review"),
            ("planning-architecture", "planning-architecture-review"),
            ("planning-strategy", "planning-strategy-review"),
            ("planning-character-contract", "planning-character-contract-review"),
            ("planning-world-contract", "planning-world-contract-review"),
            ("planning-story-arc", "planning-story-arc-review"),
            ("planning-volume-outline", "planning-volume-outline-review"),
            ("planning-chapter-plan", "planning-chapter-plan-review"),
        ]:
            self.assertEqual(["planning-quality-review", specific], store.review_packages(profile))

        with self.assertRaisesRegex(NovelOSError, "未知 Review Profile"):
            store.review_packages("unknown-profile-x")

    def test_review_profile_bindings_are_configured_and_queryable(self) -> None:
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        store = AgentContractStore(CONFIG_PATH)
        self.assertFalse(store.is_strict("isolation_evidence"))
        self.assertFalse(store.is_strict("cross_consistency"))
        with self.assertRaisesRegex(NovelOSError, "未知 enforcement"):
            store.is_strict("unknown")
        self.assertEqual("planning-direction", store.review_profile_for_asset("direction"))
        self.assertEqual("prose-v1", store.review_profile_for_binding("chapter_acceptance"))
        self.assertEqual("continuity-v1", store.review_profile_for_binding("continuity_promotion"))
        self.assertEqual("entity-world", store.review_profile_for_entity("world"))
        self.assertEqual(
            "planning-character-world-cross-consistency",
            store.cross_consistency_profile(),
        )

    def test_review_profile_binding_shape_fails_closed_at_startup(self) -> None:
        from novelos_mcp import NovelOSError

        mutations = {
            "missing chapter acceptance": lambda payload: payload["review_profile_bindings"].pop("chapter_acceptance"),
            "misspelled continuity promotion": lambda payload: payload["review_profile_bindings"].__setitem__(
                "continuity_promotoin",
                payload["review_profile_bindings"].pop("continuity_promotion"),
            ),
            "missing timeline entity": lambda payload: payload["review_profile_bindings"]["entity_authority"].pop("timeline"),
            "empty reviewer profile": lambda payload: payload["roles"]["review_agent"].__setitem__("review_profile", ""),
            "unregistered business profile": lambda payload: payload["review_profile_bindings"].__setitem__(
                "chapter_acceptance", "not-registered"
            ),
            "unregistered planning profile": lambda payload: payload["roles"]["direction_agent"].__setitem__(
                "review_profile", "not-registered"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                config = copy.deepcopy(self.config)
                mutate(config)
                with self.assertRaisesRegex(NovelOSError, "configuration_error"):
                    self._store_from_config(config)

    def test_custom_service_profile_mapping_does_not_use_compatibility_snapshot(self) -> None:
        from novelos_mcp import NovelOSService

        config = copy.deepcopy(self.config)
        packages = config["review_profile_routes"].pop("planning-direction")
        config["review_profile_routes"]["custom-direction-review"] = packages
        config["roles"]["direction_agent"]["review_profile"] = "custom-direction-review"
        store = self._store_from_config(config)
        self.assertEqual("custom-direction-review", store.review_profile_for_asset("direction"))
        self.assertEqual("planning-direction", PLANNING_REVIEW_PROFILES["direction"])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(SCHEMA_ROOT, root / "config" / "schemas")
            config_path = root / "config" / "agents.yaml"
            config_path.write_text(
                yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            service = NovelOSService(root / "novelos.db", agent_contract_path=config_path)
            project = service.create_project("自定义 Profile")
            trace = service.start_trace("custom-profile", project["id"])
            candidate = service.create_planning_candidate(
                project["id"],
                "direction",
                project["id"],
                "方向",
                [],
                "方向智能体",
            )
            _, review = complete_review_run(
                service,
                trace["id"],
                "planning_asset",
                candidate["id"],
                candidate["subject_hash"],
                "custom-direction-review",
            )
            locked = service.lock_planning_asset(
                candidate["id"], review["id"], candidate["version"], trace["id"]
            )
            self.assertEqual("locked", locked["status"])

    def test_enforcement_config_fails_closed(self) -> None:
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        self.assertEqual(
            {"strict_isolation_evidence": False, "strict_cross_consistency": False},
            AgentContractStore._validate_enforcement(None),
        )
        self.assertEqual(
            {"strict_isolation_evidence": True, "strict_cross_consistency": True},
            AgentContractStore._validate_enforcement(
                {"strict_isolation_evidence": True, "strict_cross_consistency": True}
            ),
        )
        with self.assertRaisesRegex(NovelOSError, "boolean"):
            AgentContractStore._validate_enforcement({"strict_isolation_evidence": "false"})
        with self.assertRaisesRegex(NovelOSError, "非法"):
            AgentContractStore._validate_enforcement({"strict_unknown": True})

    def test_onboarding_agent_contract_is_well_formed(self) -> None:
        """引导融合智能体：受契约约束的临时角色，承载多原型 LLM 深度融合。"""
        from novelos_mcp.agent_contracts import AgentContractStore

        role = self.roles["onboarding_agent"]
        self.assertEqual("onboarding", role["kind"])
        self.assertEqual("temporary", role["lifecycle"])
        self.assertTrue(role["must_destroy"])
        self.assertIsNone(role["owned_asset_type"])
        self.assertIsNone(role["review_profile"])
        self.assertIsNone(role["catalog_package"])
        self.assertEqual(["creator_derivation_candidate", "change_proposal"], role["output_types"])
        self.assertEqual(set(self.roles["direction_agent"]["allowed_tools"]), set(role["allowed_tools"]))
        for required_input in ("selected_archetypes", "project_setup", "system_archetype_refs"):
            self.assertIn(required_input, role["minimum_inputs"])

        store = AgentContractStore(CONFIG_PATH)
        self.assertIn("onboarding_agent", store.roles)
        self.assertIn("creator_derivation_candidate", store.output_schemas)
        store.validate_spawn("onboarding_agent", {})

    def test_creator_derivation_candidate_schema_fail_closed(self) -> None:
        """creator_derivation_candidate 输出 schema：合法 payload 通过，缺字段被拒。"""
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        store = AgentContractStore(CONFIG_PATH)
        candidate = {
            "parent_version_id": "creator-profile-version:system-epic-framework:1",
            "parent_subject_hash": "sha256:" + "a" * 64,
            "display_name": "次子铸神纪",
            "signature": {
                "schema_version": 1,
                "sympathies": ["同理在规则缝隙中抗争的个体"],
                "distrusts": ["警惕无代价力量膨胀"],
                "recurring_attention": ["持续关注力量体系演进"],
                "narrative_principles": ["遵循力量必有代价的叙事逻辑"],
                "forbidden_conveniences": ["禁止无代价机械降神"],
                "expression_preferences": ["偏好宏阔克制的史诗笔触"],
                "negative_constraints": ["不得放弃力量体系的严密性"],
            },
            "merge_rationale": "体系史诗延展性最强，匹配神战/创世终局。",
        }
        store.validate_output("creator_derivation_candidate", candidate)

        incomplete = dict(candidate)
        incomplete["signature"] = {"schema_version": 1, "sympathies": ["x"]}
        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            store.validate_output("creator_derivation_candidate", incomplete)

        with self.assertRaisesRegex(NovelOSError, "output_type Schema"):
            store.validate_output(
                "creator_derivation_candidate",
                dict(candidate, parent_subject_hash="not-a-hash"),
            )

    def test_creator_derivation_candidate_signature_passes_deterministic_validation(self) -> None:
        """onboarding_agent 的 LLM 融合输出经确定性 validate_signature 收口可用。"""
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp.creative_contracts import CreativeContractStore

        store = AgentContractStore(CONFIG_PATH)
        cc = CreativeContractStore()
        candidate = {
            "parent_version_id": "creator-profile-version:system-epic-framework:1",
            "parent_subject_hash": "sha256:" + "a" * 64,
            "display_name": "次子铸神纪",
            "signature": {
                "schema_version": 1,
                "sympathies": ["同理在规则缝隙中抗争的个体"],
                "distrusts": ["警惕无代价力量膨胀"],
                "recurring_attention": ["持续关注力量体系演进"],
                "narrative_principles": ["遵循力量必有代价的叙事逻辑"],
                "forbidden_conveniences": ["禁止无代价机械降神"],
                "expression_preferences": ["偏好宏阔克制的史诗笔触"],
                "negative_constraints": ["不得放弃力量体系的严密性"],
            },
            "merge_rationale": "体系史诗为骨架，经营复兴承载起点。",
        }
        store.validate_output("creator_derivation_candidate", candidate)
        cc.validate_signature(candidate["signature"])


if __name__ == "__main__":
    unittest.main()
