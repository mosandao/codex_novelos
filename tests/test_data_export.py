from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.backup_novelos_database import build_manifest as build_backup_manifest
from scripts.backup_novelos_database import create_backup, logical_snapshot
from novelos_mcp import NovelOSService
from scripts.export_novelos_data import (
    DEFAULT_DRILL,
    ExportError,
    export_database,
    load_and_verify_export,
    restore_export,
)


class DataExportTest(unittest.TestCase):
    @staticmethod
    def _signature(label: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "sympathies": [f"维护{label}中的普通人尊严"],
            "distrusts": [f"警惕{label}中不承担代价的权力"],
            "recurring_attention": [f"观察{label}如何进入日常关系"],
            "narrative_principles": ["通过选择和后果表达判断"],
            "forbidden_conveniences": ["不得用一句道歉抹平长期伤害"],
            "expression_preferences": ["克制议论并保留事实空白"],
            "negative_constraints": ["不模仿具体作者"],
        }

    def test_jsonl_export_restores_the_exact_logical_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            with closing(sqlite3.connect(source)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    CREATE TABLE notes(id TEXT PRIMARY KEY, body TEXT NOT NULL, payload BLOB);
                    CREATE TABLE note_audit(note_id TEXT PRIMARY KEY);
                    CREATE TRIGGER notes_audit AFTER INSERT ON notes
                    BEGIN
                        INSERT INTO note_audit(note_id) VALUES (NEW.id);
                    END;
                    INSERT INTO schema_migrations VALUES (1, 'base');
                    INSERT INTO notes VALUES ('n1', '中文正文', X'00FF');
                    """
                )
                connection.commit()
            export_dir = root / "export"
            restored = root / "restored.db"
            export_database(source, export_dir)
            manifest = load_and_verify_export(export_dir)
            restore_export(export_dir, restored)
            self.assertEqual(manifest["logical_snapshot"], logical_snapshot(restored, immutable=True))
            with closing(sqlite3.connect(restored)) as connection:
                connection.execute("INSERT INTO notes VALUES ('n2', '恢复后', NULL)")
                self.assertEqual(2, connection.execute("SELECT COUNT(*) FROM note_audit").fetchone()[0])

    def test_tampered_export_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            with closing(sqlite3.connect(source)) as connection:
                connection.executescript(
                    """
                    CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL);
                    INSERT INTO schema_migrations VALUES (1, 'base');
                    """
                )
                connection.commit()
            export_dir = root / "export"
            manifest = export_database(source, export_dir)
            table_path = export_dir / manifest["tables"][0]["path"]
            table_path.write_text("[2,\"tampered\"]\n", encoding="utf-8")
            with self.assertRaisesRegex(ExportError, "Hash 不匹配"):
                load_and_verify_export(export_dir)

    def test_creator_profile_history_and_exact_binding_survive_jsonl_restore(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            service = NovelOSService(source)
            created = service.create_creator_profile("恢复测试作者", self._signature("城市"))
            first = created["version"]
            revised = service.revise_creator_profile(
                created["profile"]["id"],
                created["profile"]["version"],
                self._signature("家庭"),
            )["version"]
            system_archetype = service.list_system_archetypes()[0]["latest_version"]
            project = service.create_project_with_creator(
                "精确绑定恢复测试",
                "",
                {},
                {
                    "mode": "derive",
                    "parent_version_id": system_archetype["id"],
                    "parent_subject_hash": system_archetype["subject_hash"],
                    "display_name": "恢复测试作者·派生",
                    "overrides": {"recurring_attention": ["测试精确绑定恢复"]},
                },
            )["project"]


            export_dir = root / "export"
            restored = root / "restored.db"
            export_database(source, export_dir)
            restore_export(export_dir, restored)
            restored_service = NovelOSService(restored)
            binding = restored_service.get_project_creator_binding(project["id"])
            self.assertEqual("derive", binding["binding_mode"])
            self.assertTrue(binding["profile_version_id"].startswith("creator-profile-version:"))

            self.assertEqual(
                first["subject_hash"],
                restored_service.get_creator_profile_version(first["id"])["subject_hash"],
            )
            self.assertEqual(
                revised["subject_hash"],
                restored_service.get_creator_profile_version(revised["id"])["subject_hash"],
            )

            backup = root / "backup.db"
            create_backup(source, backup)
            backup_manifest = build_backup_manifest(source, backup)
            self.assertEqual("passed", backup_manifest["restore_drill"])
            counts = backup_manifest["logical_snapshot"]["table_counts"]
            self.assertEqual(20, counts["creator_profiles"])

            self.assertEqual(21, counts["creator_profile_versions"])

            self.assertEqual(1, counts["project_creator_bindings"])

    def test_real_database_export_drill_is_current(self) -> None:
        drill = json.loads(DEFAULT_DRILL.read_text(encoding="utf-8"))
        backup = json.loads(
            (DEFAULT_DRILL.parent / "schema12_restore_drill.json").read_text(encoding="utf-8")
        )
        self.assertEqual("passed", drill["export_restore_drill"])
        self.assertEqual(backup["logical_snapshot"], drill["logical_snapshot"])
        self.assertEqual(len(drill["logical_snapshot"]["table_counts"]), drill["table_count"])
        self.assertEqual(sum(drill["logical_snapshot"]["table_counts"].values()), drill["row_count"])


if __name__ == "__main__":
    unittest.main()
