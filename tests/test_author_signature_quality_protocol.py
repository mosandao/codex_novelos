from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "tasks" / "experiments" / "author_signature"


class AuthorSignatureQualityProtocolTest(unittest.TestCase):
    def test_bounded_cases_and_required_dimensions_are_frozen(self) -> None:
        cases = [
            json.loads(line)
            for line in (EXPERIMENT / "cases.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(5, len(cases))
        self.assertEqual(5, len({case["case_id"] for case in cases}))
        self.assertEqual(
            {
                "无作者约束基线",
                "绑定 Profile 但缺少有效 book_soul",
                "同一 Profile 下两个不同 book_soul",
                "两个不同 Profile 下的同一场景",
                "多章节思想与声音漂移",
            },
            {case["comparison"] for case in cases},
        )
        rubric = yaml.safe_load((EXPERIMENT / "rubric.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                "plan_fidelity",
                "canon_accuracy",
                "scene_causality",
                "character_voice",
                "prose_quality",
                "authorial_stance_fidelity",
                "voice_distinguishability",
                "character_independence",
                "long_form_drift",
            },
            set(rubric["dimensions"]),
        )
        self.assertTrue(rubric["blind_review"]["independent_reviewer_required"])

    def test_quality_status_fails_closed_without_live_evidence(self) -> None:
        status = json.loads((EXPERIMENT / "status.json").read_text(encoding="utf-8"))
        self.assertEqual("BLOCKED", status["status"])
        self.assertEqual("implemented_and_verified", status["functional_implementation_status"])
        self.assertEqual(0, status["completed_case_count"])
        self.assertFalse(status["routing_change_allowed"])
        self.assertFalse(status["quality_claim_allowed"])

    def test_catalog_prompts_encode_author_and_book_boundaries(self) -> None:
        direction = (ROOT / "catalog" / "skills" / "planning" / "story-direction" / "prompt.md").read_text(encoding="utf-8")
        chapter = (ROOT / "catalog" / "skills" / "planning" / "chapter-plan-execution-card" / "prompt.md").read_text(encoding="utf-8")
        writer = (ROOT / "catalog" / "skills" / "writing" / "chapter-draft-generation" / "prompt.md").read_text(encoding="utf-8")
        review = (ROOT / "catalog" / "skills" / "review" / "prose-quality-review" / "prompt.md").read_text(encoding="utf-8")
        for token in ("creator_signature_ref", "book_soul", "年龄、性别", "具体作者模仿"):
            self.assertIn(token, direction)
        for token in ("soul_pressure", "moral_residue", "低前景"):
            self.assertIn(token, chapter)
        for token in ("style_refs", "不得自行创建作者思想", "所有人物同声"):
            self.assertIn(token, writer)
        for token in ("Creator Profile revision/hash", "叙述者代替剧情讲道理", "长篇立场漂移"):
            self.assertIn(token, review)


if __name__ == "__main__":
    unittest.main()
