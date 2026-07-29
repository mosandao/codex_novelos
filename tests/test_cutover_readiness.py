from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tasks" / "cutover" / "readiness.json"


class CutoverReadinessTest(unittest.TestCase):
    def test_report_is_fail_closed_until_external_gates_and_cleanup_complete(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual("not_ready", report["status"])
        self.assertTrue(report["gates"]["documentation_complete"])
        self.assertTrue(report["gates"]["unified_runner_ready"])
        self.assertTrue(report["gates"]["cutover_plan_valid"])
        self.assertTrue(report["gates"]["database_restore_drill_passed"])
        self.assertTrue(report["gates"]["repository_hygiene_prepared"])
        self.assertTrue(report["gates"]["seed_authorized"])
        self.assertFalse(report["gates"]["git_review_baseline_available"])
        self.assertEqual(
            {
                "codex_config_switched",
                "legacy_model_config_removed",
                "legacy_runtime_removed",
                "quality_experiment_complete",
                "git_review_baseline_available",
            },
            set(report["blockers"]),
        )


if __name__ == "__main__":
    unittest.main()
