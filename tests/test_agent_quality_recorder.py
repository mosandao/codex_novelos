from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from scripts.record_agent_quality_experiment import finalize_case, prepare_case, start_case


class AgentQualityRecorderTest(unittest.TestCase):
    def test_single_case_uses_stdio_mcp_and_builds_verifiable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "quality.db"
            results = root / "results"
            case_id = "planning-direction-gate_seal"
            started = asyncio.run(start_case(case_id, database, results))
            self.assertEqual("started", started["phase"])
            job = json.loads(Path(started["jobs"][0]["job_path"]).read_text(encoding="utf-8"))
            Path(job["staging_path"]).parent.mkdir(parents=True, exist_ok=True)
            Path(job["staging_path"]).write_text(
                json.dumps(
                    {
                        "asset_type": "direction",
                        "candidate": "每次开门都改变权力与封印状态。",
                        "upstream_fidelity": "符合项目约束",
                        "evidence_and_impact": "绑定公共安全与救人承诺",
                        "ownership_boundary": "仅方向层",
                        "change_proposals": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            prepared = asyncio.run(prepare_case(case_id, database, results))
            review_job = json.loads(Path(prepared["review_job_path"]).read_text(encoding="utf-8"))
            self.assertNotIn("isolated_writer_agent", review_job["instructions"])
            self.assertNotIn("main_plus_skill", review_job["instructions"])
            review_stage = Path(review_job["staging_path"])
            review_stage.write_text(
                json.dumps(
                    {
                        "assessment": {
                            "schema_version": 1,
                            "case_id": case_id,
                            "scores": {
                                "candidate": {
                                    "asset_completeness": 4,
                                    "upstream_fidelity": 4,
                                    "ownership_boundary": 4,
                                    "evidence_and_impact": 4,
                                }
                            },
                            "blocking": False,
                            "boundary_passed": True,
                        },
                        "findings": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            finalized = asyncio.run(finalize_case(case_id, database, results))
            self.assertEqual("finalized", finalized["phase"])
            evidence = json.loads((results / "evidence" / f"{case_id}.json").read_text(encoding="utf-8"))
            receipt = json.loads((results / "receipts" / f"{case_id}.json").read_text(encoding="utf-8"))
            self.assertEqual(2, evidence["schema_version"])
            self.assertEqual(evidence["review"]["trace_id"], evidence["executions"][0]["trace_id"])
            self.assertEqual(receipt["assessment_ref"], evidence["review"]["assessment_ref"])
            self.assertTrue(receipt["reviewer_run_id"].startswith("agent-run:"))


if __name__ == "__main__":
    unittest.main()
