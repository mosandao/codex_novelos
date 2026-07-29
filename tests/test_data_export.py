from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.backup_novelos_database import logical_snapshot
from scripts.export_novelos_data import (
    DEFAULT_DRILL,
    ExportError,
    export_database,
    load_and_verify_export,
    restore_export,
)


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

    def test_real_database_export_drill_is_current(self) -> None:
        drill = json.loads(DEFAULT_DRILL.read_text(encoding="utf-8"))
        backup = json.loads(
            (DEFAULT_DRILL.parent / "schema9_restore_drill.json").read_text(encoding="utf-8")
        )
        self.assertEqual("passed", drill["export_restore_drill"])
        self.assertEqual(backup["logical_snapshot"], drill["logical_snapshot"])
        self.assertEqual(len(drill["logical_snapshot"]["table_counts"]), drill["table_count"])
        self.assertEqual(sum(drill["logical_snapshot"]["table_counts"].values()), drill["row_count"])


if __name__ == "__main__":
    unittest.main()
