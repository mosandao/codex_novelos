from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.summarize_agent_quality_results import QualityResultError, build_summary, summary_is_current


ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = ROOT / "tasks" / "experiments" / "agent_quality"


def _hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


class AgentQualityResultsTest(unittest.TestCase):
    def _build_complete_bundle(self, root: Path) -> None:
        evidence_root = root / "evidence"
        output_root = root / "outputs"
        subject_root = root / "subjects"
        assessment_root = root / "assessments"
        receipt_root = root / "receipts"
        for path in (evidence_root, output_root, subject_root, assessment_root, receipt_root):
            path.mkdir(parents=True)
        manifest = _jsonl(DATASET_ROOT / "execution_manifest.jsonl")
        inputs = {
            str(record["case_id"]): record
            for name in ("planning", "character_world", "writer_ab", "context_builder_ab")
            for record in _jsonl(DATASET_ROOT / f"{name}.jsonl")
        }
        dataset_seen: dict[str, int] = {}
        results: list[dict[str, object]] = []
        dimensions = {
            "planning": ["asset_completeness", "upstream_fidelity", "ownership_boundary", "evidence_and_impact"],
            "character_world": ["conflict_detection", "evidence_precision", "repair_actionability"],
            "writer_ab": ["plan_fidelity", "canon_accuracy", "scene_causality", "character_voice", "prose_quality"],
            "context_builder_ab": ["fact_recall", "context_relevance", "contradiction_detection"],
        }
        for plan in manifest:
            case_id = str(plan["case_id"])
            dataset = str(plan["dataset"])
            index = dataset_seen.get(dataset, 0)
            dataset_seen[dataset] = index + 1
            executions = []
            mode_by_label = {item["label"]: item["mode"] for item in plan["executions"]}
            for item in plan["executions"]:
                label = str(item["label"])
                mode = str(item["mode"])
                main = mode in {"main_plus_skill", "memory_skill"}
                media_type = "application/json" if dataset == "context_builder_ab" else "text/markdown"
                extension = "json" if media_type == "application/json" else "md"
                output_content = (
                    _canonical({"case_id": case_id, "label": label, "mode_result": mode})
                    if media_type == "application/json"
                    else f"{case_id}:{label}:{mode}".encode()
                )
                executions.append(
                    {
                        "label": label,
                        "actor": "main_agent" if main else "temporary_agent",
                        "trace_id": f"trace:{case_id}",
                        "producer_run_id": None if main else f"agent-run:{case_id}:{label}",
                        "output_ref": f"novelos://resource/{case_id}:{label}",
                        "output_path": f"outputs/{case_id}-{label}.{extension}",
                        "output_hash": _hash(output_content),
                        "media_type": media_type,
                    }
                )
                (root / str(executions[-1]["output_path"])).write_bytes(output_content)
            base: dict[str, object] = {
                "case_id": case_id,
                "input_hash": plan["input_hash"],
                "status": "completed",
                "blocking": False,
            }
            if dataset == "planning":
                base["scores"] = {"candidate": {name: 4 for name in dimensions[dataset]}}
                base["boundary_passed"] = True
            elif dataset == "character_world":
                base["scores"] = {"pair": {name: 4 for name in dimensions[dataset]}}
                base["conflict_detected"] = True
            else:
                target_mode = "isolated_writer_agent" if dataset == "writer_ab" else "context_builder"
                target_label = next(label for label, mode in mode_by_label.items() if mode == target_mode)
                other_label = next(label for label in ("A", "B") if label != target_label)
                scores = {label: {name: 4 for name in dimensions[dataset]} for label in ("A", "B")}
                if index < 6:
                    scores[target_label] = {name: 5 for name in dimensions[dataset]}
                    scores[other_label] = {name: 3 for name in dimensions[dataset]}
                    winner = target_label
                else:
                    winner = "tie"
                base["scores"] = scores
                base["winner"] = winner
                base["regression_labels"] = []

            assessment = {
                "schema_version": 1,
                "case_id": case_id,
                "scores": base["scores"],
                "blocking": base["blocking"],
            }
            if dataset == "planning":
                assessment["boundary_passed"] = base["boundary_passed"]
            elif dataset == "character_world":
                assessment["conflict_detected"] = base["conflict_detected"]
            else:
                assessment["winner"] = base["winner"]
                assessment["regression_labels"] = base["regression_labels"]
            assessment_content = _canonical(assessment)
            assessment_path = assessment_root / f"{case_id}.json"
            assessment_path.write_bytes(assessment_content)
            assessment_ref = f"novelos://resource/{case_id}:assessment"

            subject = {
                "schema_version": 1,
                "case_id": case_id,
                "input_hash": plan["input_hash"],
                "outputs": sorted(
                    (
                        {
                            "label": execution["label"],
                            "output_ref": execution["output_ref"],
                            "output_hash": execution["output_hash"],
                            "media_type": execution["media_type"],
                        }
                        for execution in executions
                    ),
                    key=lambda item: str(item["label"]),
                ),
                "review_profile": plan["review_profile"],
            }
            subject_content = _canonical(subject)
            subject_path = subject_root / f"{case_id}.json"
            subject_path.write_bytes(subject_content)
            subject_hash = _hash(subject_content)
            subject_ref = f"review-subject:{case_id}"

            receipt = {
                "id": f"review:{case_id}",
                "subject_type": "review_subject",
                "subject_ref": subject_ref,
                "subject_hash": subject_hash,
                "verdict": "approved",
                "findings": [],
                "reviewer_profile": plan["review_profile"],
                "evidence_refs": [execution["output_ref"] for execution in executions],
                "reviewer_run_id": f"agent-run:{case_id}:review",
                "assessment_ref": assessment_ref,
            }
            receipt_content = _canonical(receipt)
            receipt_path = receipt_root / f"{case_id}.json"
            receipt_path.write_bytes(receipt_content)

            evidence = {
                "schema_version": 2,
                "case_id": case_id,
                "input": inputs[case_id],
                "input_hash": plan["input_hash"],
                "executions": executions,
                "review": {
                    "trace_id": f"trace:{case_id}",
                    "subject_ref": subject_ref,
                    "subject_path": f"subjects/{case_id}.json",
                    "subject_hash": subject_hash,
                    "receipt_path": f"receipts/{case_id}.json",
                    "receipt_hash": _hash(receipt_content),
                    "assessment_path": f"assessments/{case_id}.json",
                    "assessment_hash": _hash(assessment_content),
                    "assessment_ref": assessment_ref,
                },
            }
            evidence_content = _canonical(evidence)
            evidence_path = evidence_root / f"{case_id}.json"
            evidence_path.write_bytes(evidence_content)
            base["evidence_path"] = f"evidence/{case_id}.json"
            base["evidence_hash"] = _hash(evidence_content)
            base["review_subject_hash"] = subject_hash
            results.append(base)
        (root / "case_results.jsonl").write_text(
            "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in results),
            encoding="utf-8",
        )

    def test_complete_evidence_is_recomputed_into_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            summary = build_summary(DATASET_ROOT, results_root)
            self.assertEqual("completed", summary["status"])
            self.assertEqual(70, summary["case_count"])
            self.assertEqual("retain", summary["writer_decision"])
            self.assertEqual("exception_only", summary["context_builder_decision"])
            self.assertEqual(0.6, summary["writer_clear_win_rate"])
            self.assertEqual(0.6, summary["context_builder_clear_win_rate"])
            self.assertFalse(summary_is_current(DATASET_ROOT, results_root))
            (results_root / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(summary_is_current(DATASET_ROOT, results_root))

    def test_missing_case_and_tampered_evidence_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            path = results_root / "case_results.jsonl"
            lines = path.read_text(encoding="utf-8").splitlines()
            path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityResultError, "完整覆盖"):
                build_summary(DATASET_ROOT, results_root)

        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            evidence = next((results_root / "evidence").glob("*.json"))
            evidence.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(QualityResultError, "evidence_hash"):
                build_summary(DATASET_ROOT, results_root)

    def test_scores_and_anonymous_outputs_are_bound_to_receipt_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            path = results_root / "case_results.jsonl"
            records = _jsonl(path)
            writer = next(record for record in records if str(record["case_id"]).startswith("writer-"))
            writer["scores"]["A"]["canon_accuracy"] = 1
            path.write_text(
                "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QualityResultError, "Receipt assessment"):
                build_summary(DATASET_ROOT, results_root)

        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            output = next((results_root / "outputs").iterdir())
            output.write_text("被替换的匿名输出", encoding="utf-8")
            with self.assertRaisesRegex(QualityResultError, "匿名输出"):
                build_summary(DATASET_ROOT, results_root)

    def test_agent_runs_cannot_be_reused_across_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            results_root = Path(directory)
            self._build_complete_bundle(results_root)
            evidence_files = sorted((results_root / "evidence").glob("*.json"))
            with_producers = []
            for path in evidence_files:
                payload = json.loads(path.read_text(encoding="utf-8"))
                producer = next(
                    (
                        execution
                        for execution in payload["executions"]
                        if execution["producer_run_id"] is not None
                    ),
                    None,
                )
                if producer is not None:
                    with_producers.append((path, payload, producer))
                if len(with_producers) == 2:
                    break
            first_run = with_producers[0][2]["producer_run_id"]
            target_path, target_payload, target_execution = with_producers[1]
            target_execution["producer_run_id"] = first_run
            target_content = _canonical(target_payload)
            target_path.write_bytes(target_content)

            results_path = results_root / "case_results.jsonl"
            records = _jsonl(results_path)
            target_case = target_payload["case_id"]
            next(record for record in records if record["case_id"] == target_case)[
                "evidence_hash"
            ] = _hash(target_content)
            results_path.write_text(
                "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in records),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(QualityResultError, "复用了 Agent run"):
                build_summary(DATASET_ROOT, results_root)


if __name__ == "__main__":
    unittest.main()
