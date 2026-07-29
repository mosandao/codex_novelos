from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator


def _apply_migration(connection: sqlite3.Connection, version: int, script: str) -> None:
    transaction = (
        "BEGIN IMMEDIATE;\n"
        f"{script.rstrip()}\n"
        f"INSERT INTO schema_migrations(version) VALUES ({version});\n"
        "COMMIT;"
    )
    try:
        connection.executescript(transaction)
    except Exception:
        connection.rollback()
        raise


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self.read() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")}
            migration_files = [(1, files("novelos_mcp.storage").joinpath("schema.sql"))]
            migration_root = files("novelos_mcp.storage").joinpath("migrations")
            migration_files.extend(
                (int(path.name.split("_", 1)[0]), path)
                for path in migration_root.iterdir()
                if path.name.endswith(".sql") and path.name.split("_", 1)[0].isdigit()
            )
            for version, path in sorted(migration_files):
                if version in applied:
                    continue
                _apply_migration(connection, version, path.read_text(encoding="utf-8"))

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
