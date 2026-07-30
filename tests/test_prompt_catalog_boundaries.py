from __future__ import annotations

import json
import unittest
from pathlib import Path

from novelos_mcp.catalog import CatalogStore

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "catalog" / "skills"
FIXTURE_PATH = ROOT / "tasks" / "07_prompt_catalog" / "fixtures" / "deterministic" / "world_fixtures.json"


class PromptCatalogBoundariesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CatalogStore(CATALOG_DIR)
        with FIXTURE_PATH.open(encoding="utf-8") as f:
            self.fixtures = json.load(f)

    def test_single_system_cost_boundary(self) -> None:
        fixture = self.fixtures["single_system_cost"]
        pkg_name = fixture["expected_package"]
        rule_pkg = self.store.get(pkg_name)
        self.assertEqual("world_contract", rule_pkg["metadata"]["asset"])
        contract = self.store.get_resource(pkg_name, "contract")
        self.assertIn("architecture", contract)
        self.assertIn("strategy", contract)

    def test_dual_system_contact_boundary(self) -> None:
        fixture = self.fixtures["dual_system_contact"]
        pkg_name = fixture["expected_package"]
        interaction_pkg = self.store.get(pkg_name)
        self.assertEqual("world_contract", interaction_pkg["metadata"]["asset"])
        self.assertEqual("generate", interaction_pkg["metadata"]["capability"])
        prompt = self.store.get_resource(pkg_name, "prompt")
        self.assertIn("双体系", prompt)

    def test_realist_no_power_boundary(self) -> None:
        fixture = self.fixtures["realist_no_power"]
        search_params = fixture["expected_search"]
        packages = self.store.search(**search_params)
        candidate_names = [item["name"] for item in packages["candidates"]]
        valid_selected = [n for n in candidate_names if n not in fixture["forbidden_packages"]]
        selection = self.store.validate_selection(valid_selected, candidate_names, packages["snapshot_hash"])
        selected_names = set(selection["selected_names"])
        for forbidden in fixture["forbidden_packages"]:
            self.assertNotIn(forbidden, selected_names, f"Realist selection failed to exclude {forbidden}")
            pkg = self.store.get(forbidden)
            self.assertTrue(any("无能力等级" in item for item in pkg["metadata"]["avoid_when"]))

    def test_writing_fixtures_deterministic_boundaries(self) -> None:
        writing_fixture_path = ROOT / "tasks" / "07_prompt_catalog" / "fixtures" / "deterministic" / "writing_fixtures.json"
        with writing_fixture_path.open(encoding="utf-8") as f:
            writing_fixtures = json.load(f)

        self.assertEqual(5, len(writing_fixtures))
        for key, fix in writing_fixtures.items():
            search_kwargs = {k: v for k, v in fix.items() if k in ("stage", "asset", "capability", "lifecycle")}
            search_res = self.store.search(**search_kwargs)
            names = [c["name"] for c in search_res["candidates"]]
            self.assertIn(fix["expected_package"], names, f"Fixture {key} missing package {fix['expected_package']}")
            val_res = self.store.validate_selection([fix["expected_package"]], names, search_res["snapshot_hash"])
            self.assertTrue(val_res["valid"])

            # 深入读取与校验 Writing 包资源契约
            pkg_name = fix["expected_package"]
            prompt = self.store.get_resource(pkg_name, "prompt")
            self.assertTrue(bool(prompt), f"Package {pkg_name} prompt is empty")
            if pkg_name == "prose-revision":
                contract = self.store.get_resource(pkg_name, "contract")
                self.assertIn("forbidden_actions", contract)
                self.assertIn("approve_draft", contract)
                self.assertIn("commit_authority", contract)

    def test_social_control_boundary(self) -> None:
        fixture = self.fixtures["social_control"]
        pkg_name = fixture["expected_package"]
        social_pkg = self.store.get(pkg_name)
        self.assertEqual("world_contract", social_pkg["metadata"]["asset"])
        prompt = self.store.get_resource(pkg_name, "prompt")
        self.assertIn("垄断", prompt)

    def test_writing_and_review_boundary_rules(self) -> None:
        revision_pkg = self.store.get("prose-revision")
        self.assertEqual("revise", revision_pkg["metadata"]["capability"])
        self.assertEqual("chapter", revision_pkg["metadata"]["asset"])

        contract = self.store.get_resource("prose-revision", "contract")
        self.assertIn("forbidden_actions", contract)
        self.assertIn("commit_authority", contract)
        self.assertIn("approve_draft", contract)

        review_contract = self.store.get_resource("prose-quality-review", "contract")
        self.assertIn("review_receipt", review_contract)
        self.assertIn("forbidden_actions", review_contract)
        self.assertIn("commit_authority", review_contract)


if __name__ == "__main__":
    unittest.main()
