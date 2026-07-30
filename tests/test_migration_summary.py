from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.build_migration_summary import DEFAULT_OUTPUT, MigrationSummaryError, build, render


ROOT = Path(__file__).resolve().parents[1]


class MigrationSummaryTest(unittest.TestCase):
    def test_summary_is_rebuilt_from_authoritative_artifacts(self) -> None:
        expected = render(build())
        self.assertEqual(expected, DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        summary = json.loads(expected)
        self.assertEqual("completed", summary["status"])
        self.assertEqual(1260, summary["source"]["file_count"])
        self.assertEqual(29, summary["catalog"]["production_package_count"])
        self.assertEqual(8, summary["catalog"]["experiment_package_count"])
        self.assertEqual("authorized", summary["seed"]["authorization"])
        self.assertTrue(summary["seed"]["migrated"])
        self.assertEqual("deferred", summary["quality_experiment"]["status"])
        self.assertEqual(70, summary["quality_experiment"]["case_count"])
        self.assertEqual(2, summary["quality_experiment"]["completed_case_count"])
        self.assertEqual([], summary["deferred"]["cutover_blockers"])

    def test_summary_exposes_all_intentional_deferrals(self) -> None:
        summary = build()
        self.assertEqual(633, summary["deferred"]["source_manifest_count"])
        self.assertEqual(5, len(summary["deferred"]["wave_d_tables"]))
        self.assertEqual(
            {"defer-experiment": 37, "defer-license": 80},
            summary["deferred"]["catalog_disposition_counts"],
        )

    def test_tampered_source_snapshot_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "tasks", root / "tasks")
            shutil.copytree(ROOT / "catalog", root / "catalog")
            snapshot = root / "tasks" / "migration" / "source_snapshot.toml"
            snapshot.write_text(
                snapshot.read_text(encoding="utf-8").replace("file_count = 1260", "file_count = 1259"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(MigrationSummaryError, "来源文件数量"):
                build(root)


if __name__ == "__main__":
    unittest.main()
