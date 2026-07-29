from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Sequence

from novelos.domain import Chapter, Entity, MemoryHit


class SQLiteRepository:
    """Persistence implementation. It contains no prompts or routing logic."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._session() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS chapters (
                    number INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS entities (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    description TEXT NOT NULL,
                    state_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    label TEXT NOT NULL,
                    content TEXT NOT NULL,
                    chapter_number INTEGER,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chapter_number) REFERENCES chapters(number)
                );
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
                CREATE INDEX IF NOT EXISTS idx_memories_chapter ON memories(chapter_number);
                """
            )

    def chapter_count(self) -> int:
        with self._session() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM chapters").fetchone()
        return int(row["count"])

    def save_chapter(self, chapter: Chapter) -> None:
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO chapters(number, title, content, summary)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(number) DO UPDATE SET
                    title = excluded.title,
                    content = excluded.content,
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (chapter.number, chapter.title, chapter.content, chapter.summary),
            )

    def latest_chapters(self, limit: int) -> list[Chapter]:
        with self._session() as connection:
            rows = connection.execute(
                "SELECT number, title, content, summary FROM chapters ORDER BY number DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            Chapter(row["number"], row["title"], row["content"], row["summary"])
            for row in reversed(rows)
        ]

    def upsert_entity(self, entity: Entity) -> None:
        with self._session() as connection:
            connection.execute(
                """
                INSERT INTO entities(name, kind, description, state_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    kind = excluded.kind,
                    description = excluded.description,
                    state_json = excluded.state_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (entity.name, entity.kind, entity.description, json.dumps(entity.state)),
            )

    def list_entities(self, names: Sequence[str] = ()) -> list[Entity]:
        sql = "SELECT kind, name, description, state_json FROM entities"
        parameters: tuple[object, ...] = ()
        if names:
            placeholders = ",".join("?" for _ in names)
            sql += f" WHERE name IN ({placeholders})"
            parameters = tuple(names)
        sql += " ORDER BY name"
        with self._session() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            Entity(row["kind"], row["name"], row["description"], json.loads(row["state_json"]))
            for row in rows
        ]

    def add_memory(
        self,
        category: str,
        label: str,
        content: str,
        chapter_number: int | None = None,
    ) -> int:
        with self._session() as connection:
            cursor = connection.execute(
                "INSERT INTO memories(category, label, content, chapter_number) VALUES (?, ?, ?, ?)",
                (category, label, content, chapter_number),
            )
            return int(cursor.lastrowid)

    def search(self, query: str, limit: int = 12) -> list[MemoryHit]:
        pattern = f"%{query}%"
        with self._session() as connection:
            rows = connection.execute(
                """
                SELECT 'memory' AS source, category AS kind, label,
                       content, chapter_number
                FROM memories
                WHERE ? = '' OR label LIKE ? OR content LIKE ? OR category LIKE ?
                UNION ALL
                SELECT 'chapter' AS source, 'chapter' AS kind,
                       'Chapter ' || number || ': ' || title AS label,
                       CASE WHEN summary = '' THEN substr(content, 1, 800) ELSE summary END AS content,
                       number AS chapter_number
                FROM chapters
                WHERE ? != '' AND (title LIKE ? OR summary LIKE ? OR content LIKE ?)
                ORDER BY chapter_number DESC
                LIMIT ?
                """,
                (query, pattern, pattern, pattern, query, pattern, pattern, pattern, limit),
            ).fetchall()
        return [
            MemoryHit(row["kind"], row["label"], row["content"], row["chapter_number"])
            for row in rows
        ]
