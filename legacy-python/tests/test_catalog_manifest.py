from __future__ import annotations

import csv
import unittest
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs" / "archive" / "tasks" / "migration" / "catalog_disposition.csv"


class CatalogDispositionManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        with MANIFEST.open(encoding="utf-8", newline="") as handle:
            self.rows = list(csv.DictReader(handle))

    def test_every_source_skill_has_one_failed_closed_disposition(self) -> None:
        self.assertEqual(138, len(self.rows))
        self.assertEqual(138, len({row["source_path"] for row in self.rows}))
        self.assertEqual(
            {"adapt-authorized": 21, "defer-license": 80, "defer-experiment": 37},
            dict(Counter(row["disposition"] for row in self.rows)),
        )

    def test_only_explicitly_authorized_active_skills_have_targets(self) -> None:
        targets = []
        for row in self.rows:
            self.assertRegex(row["source_hash"], r"^sha256:[0-9a-f]{64}$")
            self.assertIn(row["license_origin"], {
                "user-authorized",
                "novelos-repository:license-unverified",
            })
            if row["disposition"] == "adapt-authorized":
                self.assertNotEqual("-", row["target_path"])
                targets.append(row["target_path"])
            else:
                self.assertEqual("-", row["target_path"])
        self.assertEqual(14, len(set(targets)))
        for target in targets:
            self.assertTrue((ROOT / target).is_dir(), target)

    def test_provenance_source_commit_and_paths_exist(self) -> None:
        import yaml
        sources_by_target = {}
        for row in self.rows:
            if row["target_path"] != "-":
                sources_by_target.setdefault(row["target_path"], []).append(row)

        for target_path, disp_rows in sources_by_target.items():
            prov_file = ROOT / target_path / "provenance.yaml"
            self.assertTrue(prov_file.is_file(), f"Missing provenance.yaml in {target_path}")
            prov_data = yaml.safe_load(prov_file.read_text(encoding="utf-8"))
            self.assertTrue(bool(prov_data.get("source_commit")))
            prov_dir = Path(str(prov_data.get("source_path", ""))).parent
            disp_dirs = [Path(row["source_path"]).parent for row in disp_rows]
            self.assertIn(prov_dir, disp_dirs)

    def test_three_way_consistency_disposition_manifest_provenance(self) -> None:
        import yaml
        exec_manifest_file = ROOT / "docs" / "archive" / "tasks" / "07_prompt_catalog" / "execution_manifest.csv"
        with exec_manifest_file.open(encoding="utf-8", newline="") as h:
            exec_rows = list(csv.DictReader(h))
        done_exec_rows = [r for r in exec_rows if r["status"] == "done"]
        self.assertEqual(13, len(done_exec_rows))

        disp_by_skill = {r["skill"]: r for r in self.rows}

        for exec_row in done_exec_rows:
            skill = exec_row["skill"]
            self.assertTrue(bool(skill), f"exec_row {exec_row['item_id']} missing skill column")
            self.assertIn(skill, disp_by_skill, f"Skill {skill} not found in catalog_disposition.csv")
            disp_row = disp_by_skill[skill]

            self.assertEqual("adapt-authorized", disp_row["disposition"])
            self.assertEqual("user-authorized", disp_row["license_origin"])

            exec_src_dir = Path(exec_row["source_path"]).parent
            disp_src_dir = Path(disp_row["source_path"]).parent
            self.assertEqual(exec_src_dir, disp_src_dir, f"Source directory mismatch for {skill}")

            target_path = disp_row["target_path"]
            prov_file = ROOT / target_path / "provenance.yaml"
            self.assertTrue(prov_file.is_file(), f"Missing provenance.yaml in {target_path}")
            prov_data = yaml.safe_load(prov_file.read_text(encoding="utf-8"))

            self.assertEqual("user-authorized", prov_data.get("license"))
            self.assertEqual(exec_row["source_ref"], prov_data.get("source_commit"))

            primary_src_dir = Path(str(prov_data.get("source_path", ""))).parent
            add_sources = [
                Path(s["source_path"]).parent
                for s in prov_data.get("additional_sources", [])
                if isinstance(s, dict) and "source_path" in s
            ]
            valid_dirs = [primary_src_dir] + add_sources
            self.assertIn(exec_src_dir, valid_dirs, f"Provenance source directory mismatch for {skill}")


if __name__ == "__main__":
    unittest.main()
