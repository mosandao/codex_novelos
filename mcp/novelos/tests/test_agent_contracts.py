from __future__ import annotations

import json
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


ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "config" / "agents.yaml"
SCHEMA_ROOT = ROOT / "config" / "schemas"
CATALOG_ROOT = ROOT / "catalog" / "skills"


class AgentContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.roles = cls.config["roles"]

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

    def test_review_profile_routes_validation_and_unknown_profile_fail_closed(self) -> None:
        from novelos_mcp.agent_contracts import AgentContractStore
        from novelos_mcp import NovelOSError

        store = AgentContractStore(CONFIG_PATH)
        expected_profiles = [
            "planning-direction", "planning-architecture", "planning-strategy",
            "planning-character-contract", "planning-world-contract", "planning-story-arc",
            "planning-volume-outline", "planning-chapter-plan",
            "planning-character-world-cross-consistency", "entity-character",
            "entity-world", "entity-faction", "entity-rule", "entity-timeline",
            "prose-v1", "continuity-v1",
        ]
        for profile in expected_profiles:
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


if __name__ == "__main__":
    unittest.main()
