from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from novelos_mcp import NovelOSError
from novelos_mcp.legacy import LegacyMigrator


LEGACY_SCHEMA = """
CREATE TABLE projects(id TEXT PRIMARY KEY, name TEXT, config TEXT, runtime_version TEXT, plugin_versions TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE books(id TEXT PRIMARY KEY, project_id TEXT, title TEXT, description TEXT, sort_order INTEGER, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE volumes(id TEXT PRIMARY KEY, book_id TEXT, title TEXT, description TEXT, sort_order INTEGER, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE chapters(id TEXT PRIMARY KEY, volume_id TEXT, title TEXT, content TEXT, status TEXT, sort_order INTEGER, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE characters(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, role TEXT, goal TEXT, personality TEXT, description TEXT, relations TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE worlds(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, description TEXT, magic_system TEXT, geography TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE factions(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, description TEXT, member_ids TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE rules(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, description TEXT, category TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE timelines(id TEXT PRIMARY KEY, project_id TEXT, name TEXT, description TEXT, events TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE reviews(id TEXT PRIMARY KEY, target_artifact_id TEXT, target_type TEXT, reviewer_name TEXT, score REAL, suggestions TEXT, comments TEXT, resolved INTEGER, accepted INTEGER, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE chapter_facts(id TEXT PRIMARY KEY, project_id TEXT, source_chapter_id TEXT, source_content_hash TEXT, fact_type TEXT, subject TEXT, description TEXT, status TEXT, superseded_by TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
CREATE TABLE continuity_candidate_sets(id TEXT PRIMARY KEY, project_id TEXT, chapter_id TEXT, source_content_hash TEXT, authority_snapshot TEXT, subject_hash TEXT, owners TEXT, status TEXT, created_at TEXT, updated_at TEXT, metadata TEXT);
"""


def create_legacy_database(path: Path) -> None:
    now = "2026-01-01T00:00:00Z"
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(LEGACY_SCHEMA)
        connection.execute(
            "INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)",
            ("project-1", "旧项目", '{"theme":"dark"}', "1.0", '{"craft":"2"}', now, now, '{"owner":"author"}'),
        )
        connection.execute(
            "INSERT INTO books VALUES (?,?,?,?,?,?,?,?)",
            ("book-1", "project-1", "旧书", "说明", 0, now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO volumes VALUES (?,?,?,?,?,?,?,?)",
            ("volume-1", "book-1", "旧卷", "卷说明", 0, now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO chapters VALUES (?,?,?,?,?,?,?,?,?)",
            ("chapter-1", "volume-1", "第一章", "旧正文", "completed", 0, now, now, '{"execution_card":{"goal":"进入城内"}}'),
        )
        connection.execute(
            "INSERT INTO characters VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("character-1", "project-1", "林舟", "protagonist", "进城", "谨慎", "信使", "[]", now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO worlds VALUES (?,?,?,?,?,?,?,?,?)",
            ("world-1", "project-1", "边城", "边境城市", "无", "山谷", now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO factions VALUES (?,?,?,?,?,?,?,?)",
            ("faction-1", "project-1", "巡夜司", "执法机构", '["character-1"]', now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO rules VALUES (?,?,?,?,?,?,?,?)",
            ("rule-1", "project-1", "夜禁", "子时后禁行", "law", now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO timelines VALUES (?,?,?,?,?,?,?,?)",
            ("timeline-1", "project-1", "主线", "主线时间", '[{"time_marker":"子时","title":"关门","description":"城门关闭","involved_character_ids":["character-1"]}]', now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("review-1", "chapter-1", "chapter", "Critic", 9.0, '["加强结尾"]', "可以接受", 1, 1, now, now, "{}"),
        )
        connection.execute(
            "INSERT INTO continuity_candidate_sets VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("set-1", "project-1", "chapter-1", "sha256:" + "a" * 64, "{}", "sha256:" + "b" * 64, '["character"]', "accepted", now, now, "{}"),
        )
        connection.commit()


class LegacyMigratorTest(unittest.TestCase):
    def test_wave_a_is_mapped_and_legacy_continuity_is_quarantined(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "legacy.db"
            target = root / "target.db"
            create_legacy_database(source)

            report = LegacyMigrator(source, target).migrate()

            self.assertEqual(1, report["migrated_counts"]["projects"])
            self.assertEqual(1, report["quarantined_counts"]["continuity_candidate_sets"])
            with closing(sqlite3.connect(target)) as connection:
                connection.row_factory = sqlite3.Row
                chapter = connection.execute("SELECT * FROM chapters WHERE id='chapter-1'").fetchone()
                review = connection.execute("SELECT * FROM reviews WHERE id='review-1'").fetchone()
                character = connection.execute("SELECT * FROM characters WHERE id='character-1'").fetchone()
                timeline = connection.execute("SELECT * FROM timelines WHERE id='timeline-1:event:1'").fetchone()
                self.assertEqual("accepted", chapter["status"])
                self.assertEqual(chapter["subject_hash"], review["subject_hash"])
                self.assertEqual("approved", review["verdict"])
                self.assertEqual("protagonist", json.loads(character["state_json"])["role"])
                self.assertEqual("主线: 关门", timeline["label"])
                self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM legacy_quarantine").fetchone()[0])

            with self.assertRaisesRegex(NovelOSError, "already_imported"):
                LegacyMigrator(source, target).migrate()

    def test_invalid_source_schema_leaves_no_imported_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "invalid.db"
            target = root / "target.db"
            with closing(sqlite3.connect(source)) as connection:
                connection.execute("CREATE TABLE projects(id TEXT PRIMARY KEY, name TEXT)")
                connection.commit()
            with self.assertRaisesRegex(NovelOSError, "unsupported_source_schema"):
                LegacyMigrator(source, target).migrate()
            with closing(sqlite3.connect(target)) as connection:
                self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM legacy_imports").fetchone()[0])
                self.assertEqual(0, connection.execute("SELECT COUNT(*) FROM projects").fetchone()[0])

    def test_active_wal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "legacy.db"
            target = root / "target.db"
            create_legacy_database(source)
            Path(f"{source}-wal").write_bytes(b"active")
            with self.assertRaisesRegex(NovelOSError, "source_not_frozen"):
                LegacyMigrator(source, target).migrate()


if __name__ == "__main__":
    unittest.main()
