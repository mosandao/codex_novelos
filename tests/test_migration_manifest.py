from __future__ import annotations

import csv
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "tasks" / "migration"


class MigrationManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        with (MIGRATION / "source_snapshot.toml").open("rb") as handle:
            self.snapshot = tomllib.load(handle)
        with (MIGRATION / "source_manifest.csv").open(encoding="utf-8", newline="") as handle:
            self.rows = list(csv.DictReader(handle))

    def test_manifest_covers_frozen_tree_once(self) -> None:
        paths = [row["source_path"] for row in self.rows]
        self.assertEqual(self.snapshot["file_count"], len(paths))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual({self.snapshot["source_commit"]}, {row["source_commit"] for row in self.rows})

    def test_manifest_has_valid_hashes_provenance_and_targets(self) -> None:
        production_targets: list[str] = []
        for row in self.rows:
            self.assertRegex(row["source_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertTrue(row["license_origin"])
            self.assertTrue(row["tests_to_port"])
            if row["classification"] in {"direct", "adapt"}:
                self.assertNotEqual("-", row["target_path"])
                production_targets.append(row["target_path"])
            else:
                self.assertEqual("-", row["target_path"])
        self.assertEqual(len(production_targets), len(set(production_targets)))

    def test_rejected_runtime_and_ui_are_explicit(self) -> None:
        classifications = {row["source_path"]: row["classification"] for row in self.rows}
        rejected_prefixes = (
            "frontend/",
            "backend/src/presentation/",
            "backend/src/application/runtime/",
            "backend/src/application/sub_agents/",
            "backend/src/infrastructure/llm/",
        )
        for path, classification in classifications.items():
            if path.startswith(rejected_prefixes):
                self.assertEqual("reject", classification, path)

    def test_inventory_counts_match_snapshot(self) -> None:
        with (MIGRATION / "table_inventory.csv").open(encoding="utf-8", newline="") as handle:
            tables = list(csv.DictReader(handle))
        with (MIGRATION / "skill_inventory.csv").open(encoding="utf-8", newline="") as handle:
            skills = list(csv.DictReader(handle))
        with (MIGRATION / "seed_inventory.csv").open(encoding="utf-8", newline="") as handle:
            seed_tables = list(csv.DictReader(handle))
        with (MIGRATION / "dirty_inventory.csv").open(encoding="utf-8", newline="") as handle:
            dirty = list(csv.DictReader(handle))
        self.assertEqual(self.snapshot["table_count"], len(tables))
        self.assertEqual(self.snapshot["skill_count"], len(skills))
        self.assertEqual(self.snapshot["seed_knowledge_table_count"], len(seed_tables))
        self.assertEqual(self.snapshot["seed_knowledge_record_count"], sum(int(row["record_count"]) for row in seed_tables))
        self.assertEqual(self.snapshot["dirty_status_count_observed"], len(dirty))
        self.assertEqual(len(tables), len({row["table_name"] for row in tables}))
        self.assertEqual(len(skills), len({row["source_path"] for row in skills}))
        self.assertTrue(all(re.fullmatch(r"sha256:[0-9a-f]{64}", row["source_hash"]) for row in skills))
        self.assertTrue(all(row["disposition"] == "excluded_from_committed_source" for row in dirty))

    def test_experimental_skills_are_deferred(self) -> None:
        manifest = {row["source_path"]: row for row in self.rows}
        with (MIGRATION / "skill_inventory.csv").open(encoding="utf-8", newline="") as handle:
            skills = list(csv.DictReader(handle))
        for skill in skills:
            if skill["lifecycle"] != "active":
                root = skill["source_path"].rsplit("/", 1)[0]
                members = [row for path, row in manifest.items() if path == root or path.startswith(f"{root}/")]
                self.assertTrue(members, root)
                self.assertEqual({"defer"}, {row["classification"] for row in members})


if __name__ == "__main__":
    unittest.main()
