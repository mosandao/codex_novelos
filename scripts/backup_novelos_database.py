from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "novelos-v2.db"
DEFAULT_BACKUP = ROOT / "data" / "migration" / "novelos-v2-schema11-backup.db"
DEFAULT_MANIFEST = ROOT / "tasks" / "migration" / "schema11_restore_drill.json"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _normalize(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    return value


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def logical_snapshot(path: Path, *, immutable: bool = False) -> dict[str, Any]:
    immutable_query = "&immutable=1" if immutable else ""
    uri = f"file:{path.resolve()}?mode=ro{immutable_query}"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        quick_check = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        if quick_check != "ok":
            raise RuntimeError(f"数据库完整性检查失败：{path}: {quick_check}")
        names = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        digest = hashlib.sha256()
        counts: dict[str, int] = {}
        for name in names:
            schema = str(
                connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
                ).fetchone()[0]
            )
            digest.update(name.encode("utf-8"))
            digest.update(b"\0")
            digest.update(schema.encode("utf-8"))
            digest.update(b"\n")
            columns = connection.execute(f"PRAGMA table_info({_quote(name)})").fetchall()
            primary = [str(row[1]) for row in sorted(columns, key=lambda row: row[5]) if row[5]]
            order = ", ".join(_quote(column) for column in primary) if primary else "rowid"
            rows = connection.execute(f"SELECT * FROM {_quote(name)} ORDER BY {order}").fetchall()
            counts[name] = len(rows)
            for row in rows:
                payload = [_normalize(value) for value in row]
                digest.update(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                )
                digest.update(b"\n")
        versions = [
            int(row[0])
            for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]
    return {
        "quick_check": quick_check,
        "schema_versions": versions,
        "table_counts": counts,
        "logical_hash": f"sha256:{digest.hexdigest()}",
    }


def create_backup(source: Path, backup: Path) -> None:
    if source.resolve() == backup.resolve():
        raise RuntimeError("备份路径不能与正式数据库相同")
    if not source.is_file():
        raise RuntimeError(f"正式数据库不存在：{source}")
    if backup.exists():
        raise RuntimeError(f"备份已存在，拒绝覆盖：{backup}")
    backup.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.resolve()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source_connection:
        with closing(sqlite3.connect(backup)) as backup_connection:
            source_connection.backup(backup_connection)
            backup_connection.commit()


def restore_drill(backup: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="novelos-restore-") as directory:
        restored = Path(directory) / "restored.db"
        backup_uri = f"file:{backup.resolve()}?mode=ro&immutable=1"
        with closing(sqlite3.connect(backup_uri, uri=True)) as backup_connection:
            with closing(sqlite3.connect(restored)) as restored_connection:
                backup_connection.backup(restored_connection)
                restored_connection.commit()
        return logical_snapshot(restored, immutable=True)


def build_manifest(source: Path, backup: Path) -> dict[str, Any]:
    source_snapshot = logical_snapshot(source)
    backup_snapshot = logical_snapshot(backup, immutable=True)
    restored_snapshot = restore_drill(backup)
    if source_snapshot != backup_snapshot or backup_snapshot != restored_snapshot:
        raise RuntimeError("正式库、备份和恢复库的逻辑快照不一致")
    return {
        "schema_version": 1,
        "source_path": str(source.resolve()),
        "backup_path": str(backup.resolve()),
        "source_file_hash": _file_hash(source),
        "backup_file_hash": _file_hash(backup),
        "logical_snapshot": source_snapshot,
        "restore_drill": "passed",
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="备份 NovelOS 数据库并执行临时恢复演练")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--backup", type=Path, default=DEFAULT_BACKUP)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--resume", action="store_true", help="采用本脚本已创建但尚未生成 manifest 的备份")
    args = parser.parse_args()
    if not args.check:
        if args.resume:
            if not args.backup.is_file() or args.manifest.exists():
                raise SystemExit("--resume 只允许采用已存在备份且 manifest 尚不存在的中断状态")
        else:
            create_backup(args.source, args.backup)
    if not args.backup.is_file():
        raise SystemExit(f"备份不存在：{args.backup}")
    content = render(build_manifest(args.source, args.backup))
    if args.check:
        if not args.manifest.is_file() or args.manifest.read_text(encoding="utf-8") != content:
            raise SystemExit(f"备份恢复证据不是最新结果：{args.manifest}")
        return
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
