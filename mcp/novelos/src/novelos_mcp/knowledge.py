from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from novelos_mcp.errors import NovelOSError
from novelos_mcp.seed_inventory import active_sqlite_sidecars, validate_seed_database


class KnowledgeStore:
    def __init__(
        self,
        path: str | Path | None,
        inventory_path: str | Path | None = None,
    ) -> None:
        self.path = Path(path).resolve() if path else None
        self.inventory_path = Path(inventory_path).resolve() if inventory_path else None
        self._verified_signature: tuple[int, int, int, int, int] | None = None
        if (self.path is None) != (self.inventory_path is None):
            raise NovelOSError(
                "knowledge_unavailable", "seed.db 与冻结 inventory 必须同时配置"
            )
        if self.path is not None and self.inventory_path is not None:
            validate_seed_database(self.path, self.inventory_path)
            self._verified_signature = self._signature(self.path)

    @staticmethod
    def _signature(path: Path) -> tuple[int, int, int, int, int]:
        stat = path.stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)

    def _connect(self) -> sqlite3.Connection:
        if self.path is None or not self.path.is_file():
            raise NovelOSError("knowledge_unavailable", "未配置可用的只读 seed.db")
        try:
            current_signature = self._signature(self.path)
        except OSError as exc:
            raise NovelOSError("knowledge_unavailable", "seed.db 无法读取") from exc
        if active_sqlite_sidecars(self.path):
            raise NovelOSError("knowledge_integrity_error", "seed.db 在校验后出现 SQLite sidecar")
        if self._verified_signature != current_signature:
            raise NovelOSError("knowledge_integrity_error", "seed.db 在完整性校验后发生变化")
        connection = sqlite3.connect(f"file:{self.path}?mode=ro&immutable=1", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        return connection

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _tables(connection: sqlite3.Connection) -> list[str]:
        return [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            if str(row["name"]).startswith("kb_")
        ]

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> list[tuple[str, str]]:
        quoted = table.replace('"', '""')
        return [
            (str(row["name"]), str(row["type"]).upper())
            for row in connection.execute(f'PRAGMA table_info("{quoted}")')
        ]

    def search(self, query: str, tables: list[str] | None = None, limit: int = 20) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            raise NovelOSError("invalid_argument", "knowledge query 不能为空")
        if not 1 <= limit <= 100:
            raise NovelOSError("invalid_pagination", "knowledge limit 必须为 1..100")
        with self._read() as connection:
            available = self._tables(connection)
            selected = tables or available
            invalid = sorted(set(selected) - set(available))
            if invalid:
                raise NovelOSError("invalid_argument", "包含未知 knowledge table", {"tables": invalid})
            results: list[dict[str, Any]] = []
            for table in selected:
                columns = self._columns(connection, table)
                text_columns = [name for name, kind in columns if "TEXT" in kind]
                if not text_columns:
                    continue
                identifier = "id" if any(name == "id" for name, _ in columns) else columns[0][0]
                expression = " || ' ' || ".join(f"COALESCE(CAST(\"{name}\" AS TEXT), '')" for name in text_columns)
                rows = connection.execute(
                    f'SELECT * FROM "{table}" WHERE ({expression}) LIKE ? LIMIT ?',
                    (f"%{normalized}%", limit - len(results)),
                ).fetchall()
                for row in rows:
                    record = dict(row)
                    title = self._title(record)
                    results.append({
                        "table": table,
                        "id": str(record[identifier]),
                        "title": title,
                        "category": self._category(record),
                        "resource_ref": f"novelos://knowledge/{table}/{record[identifier]}",
                    })
                    if len(results) >= limit:
                        return results
            return results

    def get(self, table: str, record_id: str) -> dict[str, Any]:
        with self._read() as connection:
            available = self._tables(connection)
            if table not in available:
                raise NovelOSError("not_found", "knowledge table 不存在", {"table": table})
            columns = self._columns(connection, table)
            identifier = "id" if any(name == "id" for name, _ in columns) else columns[0][0]
            row = connection.execute(
                f'SELECT * FROM "{table}" WHERE CAST("{identifier}" AS TEXT)=?', (record_id,)
            ).fetchone()
            if row is None:
                raise NovelOSError("not_found", "knowledge record 不存在", {"table": table, "id": record_id})
            return dict(row)

    def get_resource(self, table: str, record_id: str) -> str:
        return json.dumps(self.get(table, record_id), ensure_ascii=False, indent=2, sort_keys=True)

    @staticmethod
    def _title(record: dict[str, Any]) -> str:
        preferred = ("name", "title", "technique_name", "archetype_name", "setting_name", "book_name", "label")
        for key in preferred:
            if record.get(key):
                return str(record[key])
        for key, value in record.items():
            if key.endswith("_name") and value:
                return str(value)
        return str(next((value for value in record.values() if isinstance(value, str) and value), record.get("id", "")))

    @staticmethod
    def _category(record: dict[str, Any]) -> str | None:
        for key in ("category", "sub_category", "genre", "world_type", "character_role"):
            if record.get(key):
                return str(record[key])
        return None
