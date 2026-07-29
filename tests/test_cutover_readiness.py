from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tasks" / "cutover" / "readiness.json"


class CutoverReadinessTest(unittest.TestCase):
    def test_report_accepts_explicit_quality_deferral_and_requires_completed_cutover(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual("ready", report["status"])
        self.assertTrue(report["gates"]["documentation_complete"])
        self.assertTrue(report["gates"]["unified_runner_ready"])
        self.assertTrue(report["gates"]["cutover_plan_valid"])
        self.assertTrue(report["gates"]["database_restore_drill_passed"])
        self.assertTrue(report["gates"]["repository_hygiene_prepared"])
        self.assertTrue(report["gates"]["seed_authorized"])
        self.assertTrue(report["gates"]["git_review_baseline_available"])
        self.assertFalse(report["gates"]["quality_experiment_complete"])
        self.assertTrue(report["gates"]["quality_experiment_deferred"])
        self.assertTrue(report["gates"]["quality_experiment_dispositioned"])
        self.assertEqual([], report["blockers"])
        self.assertNotIn("quality_experiment_complete", report["blockers"])


if __name__ == "__main__":
    unittest.main()
