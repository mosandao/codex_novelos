from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.backup_novelos_database import build_manifest as build_backup_manifest
from scripts.backup_novelos_database import create_backup, logical_snapshot
from scripts.export_novelos_data import (
    DEFAULT_DRILL,
    ExportError,
    export_database,
    load_and_verify_export,
    restore_export,
)


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


# creator 相关表的精简 DDL（仅含导出/恢复测试所需列），替代原 NovelOSService 夹具。
_CREATOR_DDL = """
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE resources(
    id TEXT PRIMARY KEY, media_type TEXT, content BLOB,
    content_hash TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE creator_profiles(
    id TEXT PRIMARY KEY, display_name TEXT, status TEXT, version INTEGER DEFAULT 1,
    ownership TEXT DEFAULT 'user', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE creator_profile_versions(
    id TEXT PRIMARY KEY, profile_id TEXT, revision INTEGER,
    content_resource_id TEXT, subject_hash TEXT, parent_version_id TEXT,
    derivation_resource_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE project_creator_bindings(
    project_id TEXT PRIMARY KEY, profile_id TEXT, profile_version_id TEXT,
    profile_revision INTEGER, subject_hash TEXT, binding_mode TEXT,
    version INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class DataExportTest(unittest.TestCase):
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
        """用 SQL INSERT 构造 creator 数据，验证导出/恢复/备份保真（不再依赖 NovelOSService）。"""
        import hashlib

        def _h(payload: str) -> str:
            return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.db"
            with closing(sqlite3.connect(source)) as connection:
                connection.executescript(_CREATOR_DDL)
                # 1 个 profile + 2 个 version（模拟 history）+ 1 个 binding
                sig1 = json.dumps(_signature("城市"), ensure_ascii=False)
                sig2 = json.dumps(_signature("家庭"), ensure_ascii=False)
                h1, h2 = _h(sig1), _h(sig2)
                connection.executemany(
                    "INSERT INTO resources(id, media_type, content, content_hash) VALUES (?,?,?,?)",
                    [
                        ("resource:sig:v1", "application/json", sig1.encode("utf-8"), h1),
                        ("resource:sig:v2", "application/json", sig2.encode("utf-8"), h2),
                    ],
                )
                connection.execute(
                    "INSERT INTO creator_profiles(id, display_name, status, version, ownership) "
                    "VALUES ('creator-profile:test', '恢复测试作者', 'active', 2, 'user')"
                )
                connection.executemany(
                    "INSERT INTO creator_profile_versions(id, profile_id, revision, content_resource_id, subject_hash) "
                    "VALUES (?,?,?,?,?)",
                    [
                        ("creator-profile-version:test:1", "creator-profile:test", 1, "resource:sig:v1", h1),
                        ("creator-profile-version:test:2", "creator-profile:test", 2, "resource:sig:v2", h2),
                    ],
                )
                connection.execute(
                    "INSERT INTO project_creator_bindings(project_id, profile_id, profile_version_id, "
                    "profile_revision, subject_hash, binding_mode) VALUES "
                    "('project:test', 'creator-profile:test', 'creator-profile-version:test:2', 2, ?, 'derive')",
                    (h2,),
                )
                connection.execute("INSERT INTO schema_migrations VALUES (1, 'base')")
                connection.commit()

            export_dir = root / "export"
            restored = root / "restored.db"
            export_database(source, export_dir)
            restore_export(export_dir, restored)

            with closing(sqlite3.connect(restored)) as conn:
                binding = conn.execute(
                    "SELECT binding_mode, profile_version_id FROM project_creator_bindings WHERE project_id='project:test'"
                ).fetchone()
                self.assertEqual("derive", binding[0])
                self.assertTrue(binding[1].startswith("creator-profile-version:"))
                versions = conn.execute(
                    "SELECT subject_hash FROM creator_profile_versions ORDER BY revision"
                ).fetchall()
                self.assertEqual([h1, h2], [v[0] for v in versions])

            backup = root / "backup.db"
            create_backup(source, backup)
            backup_manifest = build_backup_manifest(source, backup)
            self.assertEqual("passed", backup_manifest["restore_drill"])
            counts = backup_manifest["logical_snapshot"]["table_counts"]
            self.assertEqual(1, counts["creator_profiles"])
            self.assertEqual(2, counts["creator_profile_versions"])
            self.assertEqual(1, counts["project_creator_bindings"])

    def test_real_database_export_drill_is_current(self) -> None:
        drill = json.loads(DEFAULT_DRILL.read_text(encoding="utf-8"))
        backup = json.loads(
            (DEFAULT_DRILL.parent / "schema18_restore_drill.json").read_text(encoding="utf-8")
        )
        self.assertEqual("passed", drill["export_restore_drill"])
        self.assertEqual(backup["logical_snapshot"], drill["logical_snapshot"])
        self.assertEqual(len(drill["logical_snapshot"]["table_counts"]), drill["table_count"])
        self.assertEqual(sum(drill["logical_snapshot"]["table_counts"].values()), drill["row_count"])


if __name__ == "__main__":
    unittest.main()
