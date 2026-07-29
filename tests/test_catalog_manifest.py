from __future__ import annotations

import csv
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tasks" / "migration" / "catalog_disposition.csv"


class CatalogDispositionManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        with MANIFEST.open(encoding="utf-8", newline="") as handle:
            self.rows = list(csv.DictReader(handle))

    def test_every_source_skill_has_one_failed_closed_disposition(self) -> None:
        self.assertEqual(138, len(self.rows))
        self.assertEqual(138, len({row["source_path"] for row in self.rows}))
        self.assertEqual(
            {"adapt-authorized": 8, "defer-license": 92, "defer-experiment": 38},
            dict(Counter(row["disposition"] for row in self.rows)),
        )

    def test_only_explicitly_authorized_active_skills_have_targets(self) -> None:
        targets = []
        for row in self.rows:
            self.assertRegex(row["source_hash"], r"^sha256:[0-9a-f]{64}$")
            if row["disposition"] == "adapt-authorized":
                self.assertEqual("active", row["lifecycle"])
                self.assertEqual("awesome-novel-skill:GPL-3.0:user-authorized", row["license_origin"])
                self.assertNotEqual("-", row["target_path"])
                targets.append(row["target_path"])
            else:
                self.assertEqual("-", row["target_path"])
        self.assertEqual(6, len(set(targets)))
        for target in targets:
            self.assertTrue((ROOT / target).is_dir(), target)


if __name__ == "__main__":
    unittest.main()
