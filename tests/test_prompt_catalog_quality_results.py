from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_prompt_catalog_quality import validate_case_evidence


class PromptCatalogQualityResultsTest(unittest.TestCase):
    def test_missing_evidence_fields_fails_validation(self) -> None:
        case = {
            "case_id": "case_1",
            "baseline_hash": "sha256:111",
            # 缺少 candidate_hash, package_hash 等
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            err = validate_case_evidence(case, Path(tmpdir))
            self.assertIsNotNone(err)
            self.assertIn("缺少必要的证据字段", err)

    def test_missing_receipt_file_fails_validation(self) -> None:
        case = {
            "case_id": "case_1",
            "category": "World",
            "input_hash": "sha256:000",
            "baseline_hash": "sha256:111",
            "candidate_hash": "sha256:222",
            "package_hash": "sha256:333",
            "anonymous_ab_map": {"A": "baseline", "B": "candidate", "unblinded_selection": "candidate"},
            "reviewer_run_id": "run-1",
            "receipt_ref": "receipt-1",
            "scores": {"relevance": 5, "coherence": 5, "depth": 5, "boundary_compliance": 5, "safety": 5},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            err = validate_case_evidence(case, Path(tmpdir))
            self.assertIsNotNone(err)
            self.assertIn("找不到对应的 Review Receipt 文件", err)

    def test_tampered_receipt_fails_validation(self) -> None:
        case = {
            "case_id": "case_1",
            "category": "World",
            "input_hash": "sha256:000",
            "baseline_hash": "sha256:111",
            "candidate_hash": "sha256:222",
            "package_hash": "sha256:333",
            "anonymous_ab_map": {"A": "baseline", "B": "candidate", "unblinded_selection": "candidate"},
            "reviewer_run_id": "run-1",
            "receipt_ref": "receipt-1",
            "scores": {"relevance": 5, "coherence": 5, "depth": 5, "boundary_compliance": 5, "safety": 5},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            receipt_file = tmppath / "receipt-1.json"
            receipt_file.write_text(json.dumps({
                "reviewer_run_id": "run-1",
                "subject_hash": "sha256:tampered_hash", # Hash 篡改
            }), encoding="utf-8")
            err = validate_case_evidence(case, tmppath)
            self.assertIsNotNone(err)
            self.assertIn("candidate_hash 与 Receipt 记录不匹配", err)

    def test_minimal_tampered_receipt_without_5_dimensions_fails(self) -> None:
        case = {
            "case_id": "case_1",
            "category": "World",
            "input_hash": "sha256:000",
            "baseline_hash": "sha256:111",
            "candidate_hash": "sha256:222",
            "package_hash": "sha256:333",
            "anonymous_ab_map": {"A": "baseline", "B": "candidate", "unblinded_selection": "candidate"},
            "reviewer_run_id": "run-1",
            "receipt_ref": "receipt-1",
            "scores": {"relevance": 5, "coherence": 5, "depth": 5, "boundary_compliance": 5, "safety": 5},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            receipt_file = tmppath / "receipt-1.json"
            # 极简 Receipt (缺少 5 维 scores 和 findings)
            receipt_file.write_text(json.dumps({
                "reviewer_run_id": "run-1",
                "subject_hash": "sha256:222",
            }), encoding="utf-8")
            err = validate_case_evidence(case, tmppath)
            self.assertIsNotNone(err)
            self.assertIn("verdict 非法", err)

    def test_valid_evidence_passes(self) -> None:
        case = {
            "case_id": "case_1",
            "category": "World",
            "input_hash": "sha256:000",
            "baseline_hash": "sha256:111",
            "candidate_hash": "sha256:222",
            "package_hash": "sha256:333",
            "anonymous_ab_map": {"A": "baseline", "B": "candidate", "unblinded_selection": "candidate"},
            "reviewer_run_id": "run-1",
            "receipt_ref": "receipt-1",
            "scores": {"relevance": 5, "coherence": 5, "depth": 5, "boundary_compliance": 5, "safety": 5},
            "blocking_count": 0,
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            receipt_file = tmppath / "receipt-1.json"
            receipt_file.write_text(json.dumps({
                "reviewer_run_id": "run-1",
                "subject_hash": "sha256:222",
                "verdict": "pass",
                "findings": [],
                "scores": {"relevance": 5, "coherence": 5, "depth": 5, "boundary_compliance": 5, "safety": 5},
                "blocking_count": 0,
            }), encoding="utf-8")
            err = validate_case_evidence(case, tmppath)
            self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
