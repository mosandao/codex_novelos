from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "catalog" / "skills"
FIXTURE_PATH = ROOT / "tasks" / "07_prompt_catalog" / "fixtures" / "deterministic" / "world_fixtures.json"


# --------------------------------------------------------------------------- #
# 轻量 catalog 访问 helper（替代已退役的 novelos_mcp.catalog.CatalogStore）。
# catalog/skills 结构：分类/<包名>/{metadata,prompt,contract,provenance}.yaml|.md
# --------------------------------------------------------------------------- #


def _hash(names: list[str]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(sorted(names), ensure_ascii=False).encode()).hexdigest()


def _all_packages() -> dict[str, Path]:
    """返回 {包名: 包目录}，遍历所有分类子目录。"""
    pkgs: dict[str, Path] = {}
    for cat_dir in sorted(CATALOG_DIR.iterdir()):
        if not cat_dir.is_dir():
            continue
        for pkg_dir in sorted(cat_dir.iterdir()):
            if pkg_dir.is_dir() and (pkg_dir / "metadata.yaml").is_file():
                pkgs[pkg_dir.name] = pkg_dir
    return pkgs


def _metadata(name: str) -> dict[str, Any]:
    return yaml.safe_load((_all_packages()[name] / "metadata.yaml").read_text(encoding="utf-8"))


def _resource_text(name: str, resource: str) -> str:
    pkg = _all_packages()[name]
    for ext in (".yaml", ".yml", ".md", ".json"):
        candidate = pkg / f"{resource}{ext}"
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def _search(
    stage: str | None = None,
    asset: str | None = None,
    capability: str | None = None,
    lifecycle: str = "active",
) -> dict[str, Any]:
    candidates: list[dict[str, str]] = []
    for name, pkg_dir in _all_packages().items():
        meta = yaml.safe_load((pkg_dir / "metadata.yaml").read_text(encoding="utf-8"))
        if stage and meta.get("stage") != stage:
            continue
        if asset and meta.get("asset") != asset:
            continue
        if capability and meta.get("capability") != capability:
            continue
        if lifecycle and meta.get("lifecycle", "active") != lifecycle:
            continue
        candidates.append({"name": name})
    names = [c["name"] for c in candidates]
    return {"candidates": candidates, "snapshot_hash": _hash(names)}


def _validate_selection(selected: list[str], candidate_names: list[str], snapshot_hash: str) -> dict[str, Any]:
    """对齐原 CatalogStore.validate_selection(selected_names, candidate_names, snapshot_hash) 签名。"""
    valid = _hash(candidate_names) == snapshot_hash and all(s in candidate_names for s in selected)
    return {"valid": valid, "selected_names": selected if valid else []}


class PromptCatalogBoundariesTest(unittest.TestCase):
    def setUp(self) -> None:
        with FIXTURE_PATH.open(encoding="utf-8") as f:
            self.fixtures = json.load(f)

    def test_single_system_cost_boundary(self) -> None:
        fixture = self.fixtures["single_system_cost"]
        pkg_name = fixture["expected_package"]
        self.assertEqual("world_contract", _metadata(pkg_name)["asset"])
        contract = _resource_text(pkg_name, "contract")
        self.assertIn("architecture", contract)
        self.assertIn("strategy", contract)

    def test_dual_system_contact_boundary(self) -> None:
        fixture = self.fixtures["dual_system_contact"]
        pkg_name = fixture["expected_package"]
        meta = _metadata(pkg_name)
        self.assertEqual("world_contract", meta["asset"])
        self.assertEqual("generate", meta["capability"])
        prompt = _resource_text(pkg_name, "prompt")
        self.assertIn("双体系", prompt)

    def test_realist_no_power_boundary(self) -> None:
        fixture = self.fixtures["realist_no_power"]
        search_params = fixture["expected_search"]
        packages = _search(**search_params)
        candidate_names = [item["name"] for item in packages["candidates"]]
        valid_selected = [n for n in candidate_names if n not in fixture["forbidden_packages"]]
        selection = _validate_selection(valid_selected, candidate_names, packages["snapshot_hash"])
        selected_names = set(selection["selected_names"])
        for forbidden in fixture["forbidden_packages"]:
            self.assertNotIn(forbidden, selected_names, f"Realist selection failed to exclude {forbidden}")
            meta = _metadata(forbidden)
            self.assertTrue(any("无能力等级" in item for item in meta.get("avoid_when", [])))

    def test_writing_fixtures_deterministic_boundaries(self) -> None:
        writing_fixture_path = ROOT / "tasks" / "07_prompt_catalog" / "fixtures" / "deterministic" / "writing_fixtures.json"
        with writing_fixture_path.open(encoding="utf-8") as f:
            writing_fixtures = json.load(f)

        self.assertEqual(5, len(writing_fixtures))
        for key, fix in writing_fixtures.items():
            search_kwargs = {k: v for k, v in fix.items() if k in ("stage", "asset", "capability", "lifecycle")}
            search_res = _search(**search_kwargs)
            names = [c["name"] for c in search_res["candidates"]]
            self.assertIn(fix["expected_package"], names, f"Fixture {key} missing package {fix['expected_package']}")
            val_res = _validate_selection([fix["expected_package"]], names, search_res["snapshot_hash"])
            self.assertTrue(val_res["valid"])

            pkg_name = fix["expected_package"]
            prompt = _resource_text(pkg_name, "prompt")
            self.assertTrue(bool(prompt), f"Package {pkg_name} prompt is empty")
            if pkg_name == "prose-revision":
                contract = _resource_text(pkg_name, "contract")
                self.assertIn("forbidden_actions", contract)
                self.assertIn("approve_draft", contract)
                self.assertIn("commit_authority", contract)

    def test_social_control_boundary(self) -> None:
        fixture = self.fixtures["social_control"]
        pkg_name = fixture["expected_package"]
        self.assertEqual("world_contract", _metadata(pkg_name)["asset"])
        prompt = _resource_text(pkg_name, "prompt")
        self.assertIn("垄断", prompt)

    def test_writing_and_review_boundary_rules(self) -> None:
        revision_meta = _metadata("prose-revision")
        self.assertEqual("revise", revision_meta["capability"])
        self.assertEqual("chapter", revision_meta["asset"])

        contract = _resource_text("prose-revision", "contract")
        self.assertIn("forbidden_actions", contract)
        self.assertIn("commit_authority", contract)
        self.assertIn("approve_draft", contract)

        review_contract = _resource_text("prose-quality-review", "contract")
        self.assertIn("review_receipt", review_contract)
        self.assertIn("forbidden_actions", review_contract)
        self.assertIn("commit_authority", review_contract)


if __name__ == "__main__":
    unittest.main()
