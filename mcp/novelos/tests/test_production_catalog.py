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
        core_set = WAVE_A | set(PLANNING_PACKAGES.values()) | ADAPTED_STYLE_PACKAGES
        actual_names = {item["name"] for item in result["candidates"]}
        self.assertTrue(core_set.issubset(actual_names))
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

    def test_wave_d_expansion_packages_are_active(self) -> None:
        # expansion skill 已从 experiment 转 active，成为主干 skill 的可选方法素材。
        # 见 world-contract / story-architecture / chapter-draft-generation prompt 的"可选方法素材"节。
        expansion_names = {
            "story-causal-structure",
            "story-expectation-design",
            "story-pov-tone-contract",
            "world-rule-system",
            "world-growth-resource",
            "world-social-power",
            "world-system-interaction",
            "scenario-atlas",
            "prose-revision",
        }
        active_packages = self.store.search(lifecycle="active")
        active_names = {item["name"] for item in active_packages["candidates"]}
        for name in expansion_names:
            self.assertIn(name, active_names, f"{name} 应已转 active")

        # 主干 skill priority=10，expansion priority=20/30，主干应排在候选首位
        arch_result = self.store.search(stage="plan", asset="architecture", capability="generate")
        self.assertEqual("story-architecture", arch_result["candidates"][0]["name"])

        world_result = self.store.search(stage="plan", asset="world_contract", capability="generate")
        self.assertEqual("world-contract", world_result["candidates"][0]["name"])

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
            # expansion skill 转 active 后同 asset 候选变多，但主干 priority=10 < expansion priority=20，
            # 主干 skill 必须排在候选首位
            self.assertEqual(expected_name, result["candidates"][0]["name"], asset)

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
            # expansion skill 转 active 后，其 origin=adapted 的 source_hash 也进入 search 结果
            "sha256:af160fc1031809e0cedfd0429faaa0bfd69266d9bf9e8280ad0a4f1918b5fc5a",
            "sha256:3189727364783a2650907d9fef6283aab75a4bf26b8d157be23076e344d1ee47",
            "sha256:e98d50a736cba695eb892f4510f9794d4edbef4a3aaf239081ced794709847e2",
            "sha256:a596f60f6a7cae0dfe476a961cc2413dbbe831c400d40ed14ba58b9f79ecf211",
            "sha256:3fd7756cd485c2c39346000ce4508132b0d392e2cec27d2210e9cd5fcdb16ec0",
            "sha256:edb10ed3e19e6a3a9eb4f0bb3a51ec37e33151b8cfe7fe6e51abb9a894188baa",
            "sha256:22b694960d62ba970c01a3e474f971af595d647542c61ad19c113c75699093b9",
            "sha256:b78f6d9d663f2dcb6c9785b03be06631c1a8dbae727dfb97cc203a3e8c2bc714",
            "sha256:b09ee30290376501b46bfde6f16c06647f21e1421c9bc27ecdbb47f2e22706b0",
            "sha256:af86502b190dc6de19f7dbe5ad5409c59a563a178aafa324de116ccf0652ce91",
            "sha256:2388dec0bbc759c9905be8517e50ba7865717ae9ae4a671d3969db64355b7062",
            "sha256:935d8bb236071af59bfe1ef276542821bd44787abc9ea9caaddf03cf946ed327",
            "sha256:e13d21169fdc4eaf7acdbd2b0ab21a6696a02167a5fdec2e6af123938e4356be",
        }
        actual_hashes = set()
        for candidate in self.store.search()["candidates"]:
            provenance = self.store.get(candidate["name"])["provenance"]
            if provenance["origin"] != "adapted":
                continue
            actual_hashes.add(provenance["source_hash"])
            actual_hashes.update(item["source_hash"] for item in provenance.get("additional_sources", []))
        self.assertEqual(expected_hashes, actual_hashes)

    def test_planning_review_rubrics_are_distinct_and_correctly_bound(self) -> None:
        gen_prompt = self.store.get_resource("planning-quality-review", "prompt")
        self.assertIn("通用规划质量审查契约", gen_prompt)

        dir_prompt = self.store.get_resource("planning-direction-review", "prompt")
        self.assertIn("无上游依赖", dir_prompt)
        self.assertIn("核心冲突", dir_prompt)

        arch_prompt = self.store.get_resource("planning-architecture-review", "prompt")
        self.assertIn("已锁定的 `direction`", arch_prompt)
        self.assertIn("因果骨架", arch_prompt)


if __name__ == "__main__":
    unittest.main()
