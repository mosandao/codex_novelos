#!/usr/bin/env python3
"""单元测试：Prompt Migration Inventory 生成与格式校验"""

import csv
import re
import unittest
from pathlib import Path

from scripts.build_prompt_migration_inventory import FIELDNAMES, build_inventory, generate_csv_content


class TestPromptMigrationInventory(unittest.TestCase):
    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parent.parent
        self.csv_path = self.project_root / "tasks" / "07_prompt_catalog" / "source_prompt_inventory.csv"

    def test_build_inventory_structure_and_counts(self) -> None:
        rows = build_inventory(self.project_root)
        self.assertGreater(len(rows), 138)

        committed_rows = [r for r in rows if r.source_state == "committed"]
        self.assertEqual(len(committed_rows), 138)

        uncommitted_rows = [r for r in rows if r.source_state == "worktree_uncommitted"]
        modified_rows = [r for r in rows if r.source_state == "worktree_modified"]

        self.assertEqual(len(uncommitted_rows), 12)
        self.assertEqual(len(modified_rows), 1)

        # Uniqueness check on (source_state, source_path)
        keys = [(r.source_state, r.source_path) for r in rows]
        self.assertEqual(len(keys), len(set(keys)))

        # Hash format check (sha256:64hex)
        hash_pattern = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
        for r in rows:
            self.assertTrue(hash_pattern.match(r.source_hash), f"Invalid hash: {r.source_hash} for {r.source_path}")

        # Check existing_disposition for worktree items
        for r in uncommitted_rows + modified_rows:
            self.assertEqual(r.existing_disposition, "excluded_from_committed_source")
            self.assertEqual(r.source_ref, "WORKTREE")

    def test_source_prompt_inventory_csv_file_matches(self) -> None:
        self.assertTrue(self.csv_path.exists(), "source_prompt_inventory.csv should exist")
        rows = build_inventory(self.project_root)
        expected_csv = generate_csv_content(rows)
        actual_csv = self.csv_path.read_text(encoding="utf-8")
        self.assertEqual(actual_csv, expected_csv)

        # Check fieldnames
        with self.csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            self.assertEqual(tuple(header), FIELDNAMES)


if __name__ == "__main__":
    unittest.main()
