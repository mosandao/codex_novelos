from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "tasks" / "experiments" / "agent_quality"


def load_jsonl(name: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (DATASET_ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class AgentQualityDatasetTest(unittest.TestCase):
    def test_dataset_sizes_ids_and_planning_coverage(self) -> None:
        planning = load_jsonl("planning.jsonl")
        character_world = load_jsonl("character_world.jsonl")
        writer = load_jsonl("writer_ab.jsonl")
        context = load_jsonl("context_builder_ab.jsonl")
        self.assertEqual((40, 10, 10, 10), tuple(map(len, (planning, character_world, writer, context))))
        all_cases = [*planning, *character_world, *writer, *context]
        ids = [case["case_id"] for case in all_cases]
        self.assertEqual(len(ids), len(set(ids)))
        counts = Counter(case["asset_type"] for case in planning)
        self.assertEqual({5}, set(counts.values()))
        induced = Counter(case["asset_type"] for case in planning if case["cross_layer_inducement"])
        self.assertEqual(set(counts), set(induced))
        self.assertEqual({1}, set(induced.values()))
        self.assertTrue(all(case["context_builder_expected"] for case in context))
        self.assertTrue(
            all(
                "cross_volume" in case["complexity_reasons"]
                and set(case["complexity_reasons"]) <= {
                    "cross_volume",
                    "multiple_threads",
                    "conflicting_facts",
                }
                for case in context
            )
        )

        manifest = load_jsonl("execution_manifest.jsonl")
        self.assertEqual(70, len(manifest))
        self.assertEqual(set(ids), {case["case_id"] for case in manifest})

    def test_rubric_preserves_blind_evidence_and_thresholds(self) -> None:
        rubric = yaml.safe_load((DATASET_ROOT / "rubric.yaml").read_text(encoding="utf-8"))
        self.assertTrue(rubric["blind_review"]["randomize_order"])
        self.assertTrue(rubric["blind_review"]["hide_execution_mode"])
        self.assertEqual(0.6, rubric["writer_ab"]["retention_rule"]["minimum_clear_win_rate"])
        self.assertFalse(rubric["writer_ab"]["retention_rule"]["canon_regression_allowed"])
        self.assertEqual(0.6, rubric["context_builder_ab"]["retention_rule"]["minimum_clear_win_rate"])
        self.assertFalse(rubric["context_builder_ab"]["retention_rule"]["fact_regression_allowed"])


if __name__ == "__main__":
    unittest.main()
