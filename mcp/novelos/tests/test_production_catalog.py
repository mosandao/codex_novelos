from __future__ import annotations

import unittest
from pathlib import Path

from novelos_mcp.catalog import CatalogStore


ROOT = Path(__file__).resolve().parents[3]
CATALOG_ROOT = ROOT / "catalog" / "skills"
WAVE_A = {
    "chapter-plan-execution-card",
    "chapter-draft-generation",
    "prose-quality-review",
    "continuity-candidate-extraction",
    "scene-dialogue",
    "scene-pacing",
}
PLANNING_PACKAGES = {
    "direction": "story-direction",
    "architecture": "story-architecture",
    "strategy": "story-strategy",
    "character_contract": "character-contract",
    "world_contract": "world-contract",
    "story_arc": "story-arc",
    "volume_outline": "volume-outline",
    "chapter_plan": "chapter-plan-execution-card",
}
ADAPTED_STYLE_PACKAGES = {
    "dash-ellipsis-guide",
    "mobile-formatting",
    "scene-fight-craft",
    "shuangwen-techniques",
}


class ProductionCatalogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.store = CatalogStore(CATALOG_ROOT)

    def test_wave_a_packages_are_searchable_and_lightweight(self) -> None:
        result = self.store.search(lifecycle="active")
        self.assertEqual(
            WAVE_A | set(PLANNING_PACKAGES.values()) | ADAPTED_STYLE_PACKAGES,
            {item["name"] for item in result["candidates"]},
        )
        for item in result["candidates"]:
            self.assertNotIn("prompt", item)
            self.assertRegex(item["package_hash"], r"^sha256:[0-9a-f]{64}$")

    def test_prompts_are_loaded_only_after_selection(self) -> None:
        result = self.store.search(stage="write", asset="chapter", capability="generate")
        self.assertEqual(["chapter-draft-generation"], [item["name"] for item in result["candidates"]])
        package = self.store.get("chapter-draft-generation")
        self.assertEqual("target-native", package["provenance"]["origin"])
        self.assertEqual("free_text", package["metadata"]["output_contract"])
        prompt = self.store.get_resource("chapter-draft-generation", "prompt")
        self.assertIn("章节执行卡", prompt)

    def test_typed_packages_declare_typed_result(self) -> None:
        for name in ("prose-quality-review", "continuity-candidate-extraction"):
            self.assertEqual("typed_result", self.store.get(name)["metadata"]["output_contract"])

    def test_authorized_craft_adaptation_has_exact_provenance(self) -> None:
        provenance = self.store.get("scene-dialogue")["provenance"]
        self.assertEqual("adapted", provenance["origin"])
        self.assertEqual("902d7e62f55bc8bc2862e2b9574b5ee2f5f33403", provenance["source_commit"])
        self.assertEqual(
            "sha256:3b2dfe3acda98db2b83242a936fe08ee0e4facc600cfb83c3d74147c698b8a95",
            provenance["source_hash"],
        )
        self.assertEqual("awesome-novel-skill:GPL-3.0:user-authorized", provenance["license"])

    def test_typed_output_validation_fails_closed(self) -> None:
        review = {
            "subject_hash": "sha256:" + "a" * 64,
            "verdict": "approved",
            "findings": [],
            "evidence_refs": ["chapter:1"],
            "reviewer_profile": "prose-v1",
        }
        self.assertTrue(self.store.validate_output("prose-quality-review", review)["valid"])
        review["unexpected"] = True
        invalid = self.store.validate_output("prose-quality-review", review)
        self.assertFalse(invalid["valid"])
        self.assertTrue(invalid["errors"])

        continuity = {
            "owners": ["unknown"],
            "candidates": [
                {"type": "fact", "fact_type": "location", "subject": "林舟", "description": "已入城"}
            ],
        }
        self.assertFalse(self.store.validate_output("continuity-candidate-extraction", continuity)["valid"])

    def test_typed_input_validation_binds_hash_and_authority(self) -> None:
        review_input = {
            "subject_ref": "chapter:1",
            "subject_hash": "sha256:" + "a" * 64,
            "reviewer_profile": "prose-v1",
            "context_refs": ["novelos://resource/context:1"],
        }
        self.assertTrue(self.store.validate_input("prose-quality-review", review_input)["valid"])
        review_input["subject_hash"] = "unbound"
        self.assertFalse(self.store.validate_input("prose-quality-review", review_input)["valid"])

        continuity_input = {
            "project_id": "project:1",
            "chapter_id": "chapter:1",
            "source_content_hash": "sha256:" + "b" * 64,
            "authority_snapshot": {
                "project_id": "project:1",
                "project_version": 1,
                "assets": {},
                "snapshot_hash": "sha256:" + "c" * 64,
            },
        }
        self.assertTrue(self.store.validate_input("continuity-candidate-extraction", continuity_input)["valid"])

    def test_each_planning_agent_asset_has_one_catalog_candidate(self) -> None:
        for asset, expected_name in PLANNING_PACKAGES.items():
            result = self.store.search(stage="plan", asset=asset, capability="generate")
            self.assertEqual([expected_name], [item["name"] for item in result["candidates"]], asset)

    def test_all_authorized_prompt_sources_are_present_once(self) -> None:
        expected_hashes = {
            "sha256:70b7729683f0f2e277d4e44807ddae930bb9cd864dd499b361e2f45717cb90f2",
            "sha256:3abadfa9c472aa5362dcdf515990b3de31ebd5607125c4fa33984e3aeddcc143",
            "sha256:cac64d6450ede3a332bcac2eef1e898abe51d7ecd8c7157c5e3ff4c52e459188",
            "sha256:410766142b1821e383a6094ebb21c9de2529d276a57d3018af6b6994b265e328",
            "sha256:a6210e7c389a8105d70bb88ac878d3d099c5b46d60827aa5ab8fb6732dd7dfe1",
            "sha256:3b2dfe3acda98db2b83242a936fe08ee0e4facc600cfb83c3d74147c698b8a95",
            "sha256:870c41d52d5d08cbeb91ca127ec0fd476d398366c604f3ee5830f47bc171a19e",
            "sha256:298432719e3d5ebc15e446425dd0e8285b8d7d398200dcccefc681507ed7ce21",
        }
        actual_hashes = set()
        for candidate in self.store.search()["candidates"]:
            provenance = self.store.get(candidate["name"])["provenance"]
            if provenance["origin"] != "adapted":
                continue
            actual_hashes.add(provenance["source_hash"])
            actual_hashes.update(item["source_hash"] for item in provenance.get("additional_sources", []))
        self.assertEqual(expected_hashes, actual_hashes)


if __name__ == "__main__":
    unittest.main()
