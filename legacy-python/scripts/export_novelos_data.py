#!/usr/bin/env python3
"""将 NovelOS SQLite 权威数据导出为可校验、可恢复的确定性 JSONL。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

try:
    from backup_novelos_database import _file_hash, logical_snapshot
except ModuleNotFoundError:  # 作为 scripts 命名空间模块导入时使用。
    from scripts.backup_novelos_database import _file_hash, logical_snapshot


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "data" / "novelos-v2.db"
DEFAULT_DRILL = ROOT / "docs" / "archive" / "tasks" / "migration" / "schema18_export_drill.json"
MANIFEST_FIELDS = {"schema_version", "logical_snapshot", "schema", "tables"}
TABLE_FIELDS = {"name", "columns", "path", "row_count", "content_hash"}


class ExportError(ValueError):
    pass


def _bytes_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _json_line(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _encode(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"bytes_hex"} and isinstance(value["bytes_hex"], str):
        try:
            return bytes.fromhex(value["bytes_hex"])
        except ValueError as exc:
            raise ExportError("bytes_hex 不是合法十六进制") from exc
    return value


def _snapshot_database(source: Path, target: Path) -> None:
    if not source.is_file():
        raise ExportError(f"数据库不存在：{source}")
    source_uri = f"file:{source.resolve()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source_connection:
        with closing(sqlite3.connect(target)) as target_connection:
            source_connection.backup(target_connection)
            target_connection.commit()


def _schema(connection: sqlite3.Connection) -> tuple[str, str]:
    rows = connection.execute(
        "SELECT type, sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
        "ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 WHEN 'trigger' THEN 2 ELSE 3 END, name"
    ).fetchall()
    before_data = "".join(
        str(sql).rstrip().rstrip(";") + ";\n" for object_type, sql in rows if object_type == "table"
    )
    after_data = "".join(
        str(sql).rstrip().rstrip(";") + ";\n" for object_type, sql in rows if object_type != "table"
    )
    return before_data, after_data


def _table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[list[str], list[str]]:
    columns = connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
    names = [str(row[1]) for row in columns]
    primary = [str(row[1]) for row in sorted(columns, key=lambda row: row[5]) if row[5]]
    if not names:
        raise ExportError(f"无法读取表列：{table}")
    return names, primary


def _write_export(snapshot: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True)
    tables_dir = output / "tables"
    tables_dir.mkdir()
    snapshot_uri = f"file:{snapshot.resolve()}?mode=ro&immutable=1"
    with closing(sqlite3.connect(snapshot_uri, uri=True)) as connection:
        schema_text, post_schema_text = _schema(connection)
        schema_content = schema_text.encode("utf-8")
        post_schema_content = post_schema_text.encode("utf-8")
        (output / "schema.sql").write_bytes(schema_content)
        (output / "post_schema.sql").write_bytes(post_schema_content)
        table_entries: list[dict[str, Any]] = []
        for index, table in enumerate(_table_names(connection), 1):
            columns, primary = _table_columns(connection, table)
            order = ", ".join(_quote(column) for column in primary) if primary else "rowid"
            selected = ", ".join(_quote(column) for column in columns)
            rows = connection.execute(f"SELECT {selected} FROM {_quote(table)} ORDER BY {order}")
            relative = f"tables/{index:04d}.jsonl"
            target = output / relative
            digest = hashlib.sha256()
            count = 0
            with target.open("wb") as stream:
                for row in rows:
                    line = _json_line([_encode(value) for value in row])
                    stream.write(line)
                    digest.update(line)
                    count += 1
            table_entries.append(
                {
                    "name": table,
                    "columns": columns,
                    "path": relative,
                    "row_count": count,
                    "content_hash": "sha256:" + digest.hexdigest(),
                }
            )
    manifest = {
        "schema_version": 1,
        "logical_snapshot": logical_snapshot(snapshot, immutable=True),
        "schema": {
            "path": "schema.sql",
            "content_hash": _bytes_hash(schema_content),
            "post_path": "post_schema.sql",
            "post_content_hash": _bytes_hash(post_schema_content),
        },
        "tables": table_entries,
    }
    (output / "manifest.json").write_text(render(manifest), encoding="utf-8")
    return manifest


def export_database(source: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ExportError(f"导出目录已存在，拒绝覆盖：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="novelos-export-build-", dir=output.parent) as directory:
        temporary = Path(directory)
        snapshot = temporary / "snapshot.db"
        staged = temporary / "export"
        _snapshot_database(source, snapshot)
        manifest = _write_export(snapshot, staged)
        os.replace(staged, output)
    return manifest


def load_and_verify_export(export_dir: Path) -> dict[str, Any]:
    manifest_path = export_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"无法读取导出 Manifest：{manifest_path}") from exc
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_FIELDS or manifest["schema_version"] != 1:
        raise ExportError("导出 Manifest 顶层字段或版本不匹配")
    schema = manifest["schema"]
    if (
        not isinstance(schema, dict)
        or set(schema) != {"path", "content_hash", "post_path", "post_content_hash"}
        or schema["path"] != "schema.sql"
        or schema["post_path"] != "post_schema.sql"
    ):
        raise ExportError("导出 Schema 记录非法")
    schema_path = export_dir / "schema.sql"
    post_schema_path = export_dir / "post_schema.sql"
    if not schema_path.is_file() or _bytes_hash(schema_path.read_bytes()) != schema["content_hash"]:
        raise ExportError("导出 Schema Hash 不匹配")
    if not post_schema_path.is_file() or _bytes_hash(post_schema_path.read_bytes()) != schema["post_content_hash"]:
        raise ExportError("导出后置 Schema Hash 不匹配")
    entries = manifest["tables"]
    if not isinstance(entries, list) or not entries:
        raise ExportError("导出表清单不能为空")
    expected_files = {"manifest.json", "schema.sql", "post_schema.sql"}
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != TABLE_FIELDS:
            raise ExportError("导出表条目字段不匹配")
        name = entry["name"]
        if not isinstance(name, str) or not name or name in names:
            raise ExportError("导出表名非法或重复")
        names.add(name)
        relative = entry["path"]
        if not isinstance(relative, str) or not relative.startswith("tables/") or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ExportError(f"导出表路径非法：{relative!r}")
        expected_files.add(relative)
        path = export_dir / relative
        if not path.is_file() or _bytes_hash(path.read_bytes()) != entry["content_hash"]:
            raise ExportError(f"导出表 Hash 不匹配：{name}")
        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) != entry["row_count"]:
            raise ExportError(f"导出表计数不匹配：{name}")
        columns = entry["columns"]
        if not isinstance(columns, list) or not columns or any(not isinstance(column, str) for column in columns):
            raise ExportError(f"导出表列非法：{name}")
        for line in lines:
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExportError(f"导出表 JSONL 非法：{name}") from exc
            if not isinstance(row, list) or len(row) != len(columns):
                raise ExportError(f"导出表行宽不匹配：{name}")
    actual_files = {
        path.relative_to(export_dir).as_posix()
        for path in export_dir.rglob("*")
        if path.is_file()
    }
    if actual_files != expected_files:
        raise ExportError("导出目录存在缺失或未声明文件")
    return manifest


def restore_export(export_dir: Path, target: Path) -> None:
    if target.exists():
        raise ExportError(f"恢复目标已存在，拒绝覆盖：{target}")
    manifest = load_and_verify_export(export_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(target)) as connection:
            connection.executescript((export_dir / "schema.sql").read_text(encoding="utf-8"))
            for entry in manifest["tables"]:
                columns = entry["columns"]
                placeholders = ", ".join("?" for _ in columns)
                column_sql = ", ".join(_quote(column) for column in columns)
                statement = f"INSERT INTO {_quote(entry['name'])} ({column_sql}) VALUES ({placeholders})"
                rows = []
                for line in (export_dir / entry["path"]).read_text(encoding="utf-8").splitlines():
                    rows.append(tuple(_decode(value) for value in json.loads(line)))
                connection.executemany(statement, rows)
            connection.executescript((export_dir / "post_schema.sql").read_text(encoding="utf-8"))
            connection.commit()
    except Exception:
        target.unlink(missing_ok=True)
        raise


def build_drill(source: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="novelos-export-drill-") as directory:
        root = Path(directory)
        export_dir = root / "export"
        restored = root / "restored.db"
        manifest = export_database(source, export_dir)
        verified = load_and_verify_export(export_dir)
        if manifest != verified:
            raise ExportError("生成与复核的导出 Manifest 不一致")
        restore_export(export_dir, restored)
        restored_snapshot = logical_snapshot(restored, immutable=True)
        if restored_snapshot != manifest["logical_snapshot"]:
            raise ExportError("导出恢复后的逻辑快照与来源不一致")
        return {
            "schema_version": 1,
            "source_path": str(source.resolve()),
            "source_file_hash": _file_hash(source),
            "logical_snapshot": manifest["logical_snapshot"],
            "export_manifest_hash": _bytes_hash(render(manifest).encode("utf-8")),
            "table_count": len(manifest["tables"]),
            "row_count": sum(entry["row_count"] for entry in manifest["tables"]),
            "export_restore_drill": "passed",
        }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="导出 NovelOS 数据或校验导出恢复演练")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output-dir", type=Path)
    group.add_argument("--write-drill", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--drill-manifest", type=Path, default=DEFAULT_DRILL)
    args = parser.parse_args()
    try:
        if args.output_dir is not None:
            export_database(args.source, args.output_dir)
            return
        content = render(build_drill(args.source))
    except (ExportError, OSError, sqlite3.Error) as exc:
        raise SystemExit(str(exc)) from exc
    if args.check:
        if not args.drill_manifest.is_file() or args.drill_manifest.read_text(encoding="utf-8") != content:
            raise SystemExit(f"导出恢复证据不是当前结果：{args.drill_manifest}")
        return
    args.drill_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.drill_manifest.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
