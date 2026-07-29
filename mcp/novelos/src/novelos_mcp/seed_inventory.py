from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from novelos_mcp.errors import NovelOSError


INVENTORY_SCHEMA_VERSION = 1
SQLITE_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")
_INVENTORY_FIELDS = {
    "schema_version",
    "source_commit",
    "source_path",
    "source_hash",
    "quick_check",
    "table_prefix",
    "table_count",
    "row_count",
    "tables",
}
_TABLE_FIELDS = {"name", "row_count", "schema_hash", "content_hash"}


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalize(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return value


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def active_sqlite_sidecars(path: Path) -> list[Path]:
    return [
        candidate
        for suffix in SQLITE_SIDECAR_SUFFIXES
        if (candidate := Path(f"{path.resolve()}{suffix}")).exists()
    ]


def inspect_seed_database(path: Path, table_prefix: str = "kb_") -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise NovelOSError("knowledge_unavailable", "seed.db 文件不存在", {"path": str(resolved)})
    sidecars = active_sqlite_sidecars(resolved)
    if sidecars:
        raise NovelOSError(
            "knowledge_integrity_error",
            "seed.db 存在活动 SQLite sidecar",
            {"paths": [str(candidate) for candidate in sidecars]},
        )
    uri = f"file:{resolved}?mode=ro&immutable=1"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            names = [
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                if str(row[0]).startswith(table_prefix)
            ]
            tables: list[dict[str, Any]] = []
            for name in names:
                schema_row = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
                ).fetchone()
                if schema_row is None or not isinstance(schema_row[0], str):
                    raise NovelOSError(
                        "knowledge_integrity_error", "knowledge table 缺少可验证 Schema", {"table": name}
                    )
                schema = schema_row[0]
                digest = hashlib.sha256()
                rows = connection.execute(
                    f"SELECT * FROM {_quote_identifier(name)} ORDER BY rowid"
                ).fetchall()
                for row in rows:
                    payload = [_normalize(value) for value in row]
                    digest.update(
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    )
                    digest.update(b"\n")
                tables.append(
                    {
                        "name": name,
                        "row_count": len(rows),
                        "schema_hash": f"sha256:{hashlib.sha256(schema.encode('utf-8')).hexdigest()}",
                        "content_hash": f"sha256:{digest.hexdigest()}",
                    }
                )
    except sqlite3.DatabaseError as exc:
        raise NovelOSError(
            "knowledge_integrity_error", "seed.db 不是可验证的 SQLite 数据库", {"path": str(resolved)}
        ) from exc
    return {
        "source_hash": hash_file(resolved),
        "quick_check": quick_check,
        "table_prefix": table_prefix,
        "table_count": len(tables),
        "row_count": sum(int(table["row_count"]) for table in tables),
        "tables": tables,
    }


def build_seed_inventory(
    path: Path,
    source_commit: str,
    source_path: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "source_commit": source_commit,
        "source_path": source_path or str(path),
        **inspect_seed_database(path),
    }


def load_seed_inventory(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise NovelOSError(
            "knowledge_inventory_invalid", "seed inventory 文件不存在", {"path": str(resolved)}
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise NovelOSError(
            "knowledge_inventory_invalid", "seed inventory 不是有效 JSON", {"path": str(resolved)}
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _INVENTORY_FIELDS:
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory 顶层字段不完整或包含未知字段")
    if payload["schema_version"] != INVENTORY_SCHEMA_VERSION:
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory Schema 版本不受支持")
    if not isinstance(payload["source_commit"], str) or not payload["source_commit"].strip():
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory 缺少 source_commit")
    if not isinstance(payload["source_path"], str) or not payload["source_path"].strip():
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory 缺少 source_path")
    if payload["quick_check"] != "ok" or payload["table_prefix"] != "kb_":
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory quick_check 或 table_prefix 非法")
    if not isinstance(payload["tables"], list) or not payload["tables"]:
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory tables 不能为空")
    names: list[str] = []
    row_count = 0
    for table in payload["tables"]:
        if not isinstance(table, dict) or set(table) != _TABLE_FIELDS:
            raise NovelOSError("knowledge_inventory_invalid", "seed inventory table 字段非法")
        if not isinstance(table["name"], str) or not table["name"].startswith("kb_"):
            raise NovelOSError("knowledge_inventory_invalid", "seed inventory table 名称非法")
        if (
            not isinstance(table["row_count"], int)
            or isinstance(table["row_count"], bool)
            or table["row_count"] < 0
        ):
            raise NovelOSError("knowledge_inventory_invalid", "seed inventory row_count 非法")
        for field in ("schema_hash", "content_hash"):
            if not _is_sha256(table[field]):
                raise NovelOSError("knowledge_inventory_invalid", f"seed inventory {field} 非法")
        names.append(table["name"])
        row_count += table["row_count"]
    if not _is_sha256(payload["source_hash"]):
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory source_hash 非法")
    if names != sorted(set(names)):
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory tables 必须唯一且按名称排序")
    for field in ("table_count", "row_count"):
        if (
            not isinstance(payload[field], int)
            or isinstance(payload[field], bool)
            or payload[field] < 0
        ):
            raise NovelOSError("knowledge_inventory_invalid", f"seed inventory {field} 非法")
    if payload["table_count"] != len(names) or payload["row_count"] != row_count:
        raise NovelOSError("knowledge_inventory_invalid", "seed inventory 汇总计数不一致")
    return payload


def validate_seed_database(seed_path: Path, inventory_path: Path) -> dict[str, Any]:
    expected = load_seed_inventory(inventory_path)
    actual = inspect_seed_database(seed_path, expected["table_prefix"])
    expected_integrity = {field: expected[field] for field in actual}
    if actual != expected_integrity:
        mismatches = sorted(field for field in actual if actual[field] != expected_integrity[field])
        raise NovelOSError(
            "knowledge_integrity_error",
            "seed.db 与冻结 inventory 不一致",
            {"mismatches": mismatches},
        )
    return expected
