from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from novelos_mcp import NovelOSService
from novelos_mcp.storage.database import _apply_migration


class MigrationTest(unittest.TestCase):
    def test_missing_forward_migration_is_applied_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "novelos.db"
            service = NovelOSService(database)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")])
                connection.execute("DROP TABLE trace_steps")
                connection.execute("DROP TABLE traces")
                connection.execute("DELETE FROM schema_migrations WHERE version=2")
                connection.commit()
            NovelOSService(database)
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], [row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")])

                self.assertIsNotNone(connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='traces'").fetchone())

    def test_failed_migration_rolls_back_schema_and_version_together(self) -> None:
        with closing(sqlite3.connect(":memory:")) as connection:
            connection.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY)")
            with self.assertRaises(sqlite3.OperationalError):
                _apply_migration(
                    connection,
                    99,
                    "CREATE TABLE partial_state(id INTEGER); ALTER TABLE missing_table ADD COLUMN value TEXT;",
                )
            self.assertIsNone(
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='partial_state'"
                ).fetchone()
            )
            self.assertEqual(
                0,
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
            )


if __name__ == "__main__":
    unittest.main()
