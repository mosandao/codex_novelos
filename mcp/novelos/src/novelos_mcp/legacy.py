from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

from novelos_mcp.errors import NovelOSError
from novelos_mcp.hashing import content_hash
from novelos_mcp.storage import Database


CORE_TABLES = (
    "projects", "books", "volumes", "chapters", "characters",
    "worlds", "factions", "rules", "timelines", "reviews",
)
WAVE_B_TABLES = (
    "chapter_facts", "continuity_candidate_sets", "continuity_update_results",
    "chapter_completion_checkpoints", "narrative_promises", "expectation_ledgers",
    "relationship_states", "arc_states",
)
REQUIRED_COLUMNS = {
    "projects": {"id", "name", "config", "runtime_version", "plugin_versions", "metadata"},
    "books": {"id", "project_id", "title", "sort_order", "metadata"},
    "volumes": {"id", "book_id", "title", "sort_order", "metadata"},
    "chapters": {"id", "volume_id", "title", "content", "status", "sort_order", "metadata"},
}


def _identifier(prefix: str) -> str:
    return f"{prefix}:{uuid.uuid4()}"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"legacy_raw": str(value)} if isinstance(default, dict) else [str(value)]


def _safe_object(value: Any) -> dict[str, Any]:
    parsed = _safe_json(value, {})
    return parsed if isinstance(parsed, dict) else {"legacy_value": parsed}


def _safe_list(value: Any) -> list[Any]:
    parsed = _safe_json(value, [])
    return parsed if isinstance(parsed, list) else [parsed]


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone():
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


def _resource(connection: sqlite3.Connection, content: str, media_type: str = "text/markdown") -> tuple[str, str]:
    digest = content_hash(content)
    existing = connection.execute(
        "SELECT id FROM resources WHERE content_hash=? AND media_type=?", (digest, media_type)
    ).fetchone()
    if existing:
        return str(existing["id"]), digest
    resource_id = _identifier("resource")
    connection.execute(
        "INSERT INTO resources(id, media_type, content, content_hash) VALUES (?, ?, ?, ?)",
        (resource_id, media_type, content.encode("utf-8"), digest),
    )
    return resource_id, digest


def _table_hash(connection: sqlite3.Connection, table: str) -> str:
    rows = []
    for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY id'):
        item = {}
        for key in row.keys():
            value = row[key]
            item[key] = f"sha256:{hashlib.sha256(value).hexdigest()}" if isinstance(value, bytes) else value
        rows.append(item)
    return content_hash(_canonical(rows))


class LegacyMigrator:
    def __init__(self, source_path: str | Path, target_path: str | Path) -> None:
        self.source_path = Path(source_path).resolve()
        self.target_path = Path(target_path).resolve()

    def migrate(self) -> dict[str, Any]:
        self._validate_source_file()
        source_hash = _file_hash(self.source_path)
        Database(self.target_path).initialize()
        with closing(sqlite3.connect(f"file:{self.source_path}?mode=ro", uri=True)) as source:
            source.row_factory = sqlite3.Row
            source.execute("PRAGMA query_only = ON")
            quick_check = source.execute("PRAGMA quick_check").fetchone()[0]
            if quick_check != "ok":
                raise NovelOSError("source_integrity", "legacy 数据库 quick_check 失败", {"result": quick_check})
            self._validate_schema(source)
            source_counts = {
                table: len(_rows(source, table)) for table in (*CORE_TABLES, *WAVE_B_TABLES)
            }
            report = self._import(source, source_hash, source_counts)
        return report

    def _validate_source_file(self) -> None:
        if not self.source_path.is_file():
            raise NovelOSError("source_not_found", "legacy 数据库不存在", {"path": str(self.source_path)})
        wal = Path(f"{self.source_path}-wal")
        if wal.exists() and wal.stat().st_size:
            raise NovelOSError("source_not_frozen", "legacy 数据库存在活动 WAL，请先形成静态快照")
        if self.source_path == self.target_path:
            raise NovelOSError("invalid_target", "来源和目标数据库不能相同")

    @staticmethod
    def _validate_schema(source: sqlite3.Connection) -> None:
        for table, required in REQUIRED_COLUMNS.items():
            columns = {row["name"] for row in source.execute(f'PRAGMA table_info("{table}")')}
            missing = sorted(required - columns)
            if missing:
                raise NovelOSError("unsupported_source_schema", "legacy Schema 缺少字段", {"table": table, "missing": missing})

    def _import(
        self,
        source: sqlite3.Connection,
        source_hash: str,
        source_counts: dict[str, int],
    ) -> dict[str, Any]:
        database = Database(self.target_path)
        import_id = _identifier("legacy-import")
        migrated = Counter()
        quarantined = Counter()
        chapter_hashes: dict[str, str] = {}
        with database.transaction() as target:
            if target.execute("SELECT 1 FROM legacy_imports WHERE source_hash=?", (source_hash,)).fetchone():
                raise NovelOSError("already_imported", "该 legacy 数据库 Hash 已迁移", {"source_hash": source_hash})
            target.execute(
                "INSERT INTO legacy_imports(id, source_path, source_hash, source_schema, report_json) VALUES (?, ?, ?, ?, '{}')",
                (import_id, str(self.source_path), source_hash, "novelos-legacy-sqlite-v1"),
            )
            self._projects(source, target, migrated)
            self._books(source, target, migrated)
            self._volumes(source, target, migrated)
            self._chapters(source, target, migrated, chapter_hashes)
            self._described_entities(source, target, "characters", migrated)
            self._described_entities(source, target, "worlds", migrated)
            self._described_entities(source, target, "factions", migrated)
            self._rules(source, target, migrated)
            self._timelines(source, target, migrated)
            self._reviews(source, target, migrated, chapter_hashes)
            self._facts(source, target, import_id, migrated, quarantined)
            for table in WAVE_B_TABLES[1:]:
                self._quarantine_table(source, target, import_id, table, quarantined)
            target_counts = {
                table: target.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in (*CORE_TABLES, "chapter_facts")
            }
            target_hashes = {
                table: _table_hash(target, table)
                for table in (*CORE_TABLES, "chapter_facts")
            }
            report = {
                "import_id": import_id,
                "source_path": str(self.source_path),
                "source_hash": source_hash,
                "source_counts": source_counts,
                "migrated_counts": dict(sorted(migrated.items())),
                "quarantined_counts": dict(sorted(quarantined.items())),
                "target_counts": target_counts,
                "target_hashes": target_hashes,
            }
            if _file_hash(self.source_path) != source_hash:
                raise NovelOSError("source_changed", "legacy 数据库在迁移期间发生变化")
            target.execute(
                "UPDATE legacy_imports SET report_json=? WHERE id=?", (_canonical(report), import_id)
            )
        return report

    @staticmethod
    def _projects(source: sqlite3.Connection, target: sqlite3.Connection, migrated: Counter[str]) -> None:
        for row in _rows(source, "projects"):
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy"] = {
                "config": _safe_object(row.get("config")),
                "runtime_version": row.get("runtime_version"),
                "plugin_versions": _safe_object(row.get("plugin_versions")),
            }
            target.execute(
                "INSERT INTO projects(id, name, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (row["id"], row["name"], _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["projects"] += 1

    @staticmethod
    def _books(source: sqlite3.Connection, target: sqlite3.Connection, migrated: Counter[str]) -> None:
        for row in _rows(source, "books"):
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy_sort_order"] = row.get("sort_order")
            target.execute(
                "INSERT INTO books(id, project_id, title, description, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["project_id"], row["title"], row.get("description") or "", _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["books"] += 1

    @staticmethod
    def _ranked(rows: Iterable[dict[str, Any]], parent_field: str) -> dict[str, int]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            grouped[str(row[parent_field])].append(row)
        result = {}
        for values in grouped.values():
            for number, row in enumerate(sorted(values, key=lambda item: (item.get("sort_order", 0), item["id"])), 1):
                result[str(row["id"])] = number
        return result

    def _volumes(self, source: sqlite3.Connection, target: sqlite3.Connection, migrated: Counter[str]) -> None:
        rows = _rows(source, "volumes")
        numbers = self._ranked(rows, "book_id")
        for row in rows:
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy_sort_order"] = row.get("sort_order")
            target.execute(
                "INSERT INTO volumes(id, book_id, number, title, summary, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["book_id"], numbers[row["id"]], row["title"], row.get("description") or "", _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["volumes"] += 1

    def _chapters(
        self,
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        migrated: Counter[str],
        chapter_hashes: dict[str, str],
    ) -> None:
        rows = _rows(source, "chapters")
        numbers = self._ranked(rows, "volume_id")
        for row in rows:
            resource_id, digest = _resource(target, row.get("content") or "")
            chapter_hashes[row["id"]] = digest
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy_status"] = row.get("status")
            metadata["legacy_sort_order"] = row.get("sort_order")
            target.execute(
                "INSERT INTO chapters(id, volume_id, number, title, status, content_resource_id, subject_hash, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)",
                (row["id"], row["volume_id"], numbers[row["id"]], row["title"], resource_id, digest, _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["chapters"] += 1

    @staticmethod
    def _described_entities(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        table: str,
        migrated: Counter[str],
    ) -> None:
        for row in _rows(source, table):
            resource_id, _ = _resource(target, row.get("description") or "")
            metadata = _safe_object(row.get("metadata"))
            if table == "characters":
                state = {
                    "role": row.get("role"), "goal": row.get("goal"),
                    "personality": row.get("personality"),
                    "relations": _safe_list(row.get("relations")), "legacy_metadata": metadata,
                }
            elif table == "worlds":
                state = {"magic_system": row.get("magic_system"), "geography": row.get("geography"), "legacy_metadata": metadata}
            else:
                state = {"member_ids": _safe_list(row.get("member_ids")), "legacy_metadata": metadata}
            target.execute(
                f"INSERT INTO {table}(id, project_id, name, description_resource_id, state_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["project_id"], row["name"], resource_id, _canonical(state), row["created_at"], row["updated_at"]),
            )
            migrated[table] += 1

    @staticmethod
    def _rules(source: sqlite3.Connection, target: sqlite3.Connection, migrated: Counter[str]) -> None:
        for row in _rows(source, "rules"):
            resource_id, _ = _resource(target, row.get("description") or "")
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy_category"] = row.get("category")
            target.execute(
                "INSERT INTO rules(id, project_id, name, description_resource_id, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["project_id"], row["name"], resource_id, _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["rules"] += 1

    @staticmethod
    def _timelines(source: sqlite3.Connection, target: sqlite3.Connection, migrated: Counter[str]) -> None:
        sequence_by_project: Counter[str] = Counter()
        for row in sorted(_rows(source, "timelines"), key=lambda item: (item["project_id"], item["id"])):
            events = _safe_list(row.get("events"))
            if not isinstance(events, list) or not events:
                events = [{"title": row["name"], "description": row.get("description") or "", "time_marker": "legacy"}]
            for index, event in enumerate(events):
                sequence_by_project[row["project_id"]] += 1
                title = str(event.get("title") or f"事件 {index + 1}")
                description = str(event.get("description") or "")
                resource_id, _ = _resource(target, description)
                metadata = {
                    "legacy_timeline_id": row["id"], "legacy_timeline_name": row["name"],
                    "time_marker": event.get("time_marker"),
                    "involved_character_ids": event.get("involved_character_ids") or [],
                    "legacy_metadata": _safe_object(row.get("metadata")),
                }
                target.execute(
                    "INSERT INTO timelines(id, project_id, label, sequence, description_resource_id, source_ref, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"{row['id']}:event:{index + 1}", row["project_id"], f"{row['name']}: {title}", sequence_by_project[row["project_id"]], resource_id, f"legacy-timeline:{row['id']}", _canonical(metadata), row["created_at"], row["updated_at"]),
                )
                migrated["timelines"] += 1

    @staticmethod
    def _reviews(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        migrated: Counter[str],
        chapter_hashes: dict[str, str],
    ) -> None:
        approved_chapters = set()
        for row in _rows(source, "reviews"):
            subject_ref = str(row["target_artifact_id"])
            subject_type = str(row["target_type"])
            is_bound_chapter = subject_type == "chapter" and subject_ref in chapter_hashes
            digest = chapter_hashes.get(subject_ref, content_hash(f"legacy-unbound:{subject_type}:{subject_ref}"))
            accepted = bool(row.get("accepted")) and is_bound_chapter
            findings = []
            for suggestion in _safe_list(row.get("suggestions")):
                findings.append({"severity": "warning", "message": str(suggestion), "excerpt": ""})
            if row.get("comments"):
                findings.append({"severity": "note", "message": str(row["comments"]), "excerpt": ""})
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy"] = {"score": row.get("score"), "resolved": bool(row.get("resolved")), "accepted": bool(row.get("accepted"))}
            target.execute(
                "INSERT INTO reviews(id, subject_type, subject_ref, subject_hash, verdict, findings_json, reviewer_profile, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["id"], subject_type, subject_ref, digest, "approved" if accepted else "rejected", _canonical(findings), f"legacy:{row['reviewer_name']}", _canonical(metadata), row["created_at"]),
            )
            if accepted:
                approved_chapters.add(subject_ref)
            migrated["reviews"] += 1
        for chapter_id in approved_chapters:
            target.execute("UPDATE chapters SET status='accepted', version=version+1 WHERE id=?", (chapter_id,))

    @staticmethod
    def _facts(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        import_id: str,
        migrated: Counter[str],
        quarantined: Counter[str],
    ) -> None:
        rows = _rows(source, "chapter_facts")
        existing_ids = {row["id"] for row in rows}
        for row in rows:
            chapter = target.execute("SELECT status, subject_hash FROM chapters WHERE id=?", (row["source_chapter_id"],)).fetchone()
            if chapter is None:
                LegacyMigrator._quarantine_row(
                    target, import_id, "chapter_facts", row, "legacy fact 引用不存在的章节"
                )
                quarantined["chapter_facts"] += 1
                continue
            source_hash = row.get("source_content_hash") or "legacy-unbound"
            status = str(row.get("status") or "candidate")
            can_accept = chapter and chapter["status"] == "accepted" and chapter["subject_hash"] == source_hash and status == "accepted"
            target_status = "accepted" if can_accept else "quarantined"
            resource_id, _ = _resource(target, row.get("description") or "")
            metadata = _safe_object(row.get("metadata"))
            metadata["legacy_status"] = status
            target.execute(
                "INSERT INTO chapter_facts(id, project_id, source_chapter_id, source_content_hash, fact_type, subject, description_resource_id, status, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["project_id"], row["source_chapter_id"], source_hash, row["fact_type"], row["subject"], resource_id, target_status, _canonical(metadata), row["created_at"], row["updated_at"]),
            )
            migrated["chapter_facts"] += 1
        for row in rows:
            superseded_by = row.get("superseded_by")
            if superseded_by and superseded_by in existing_ids:
                target.execute("UPDATE chapter_facts SET superseded_by=? WHERE id=?", (superseded_by, row["id"]))

    @staticmethod
    def _quarantine_table(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        import_id: str,
        table: str,
        quarantined: Counter[str],
    ) -> None:
        for row in _rows(source, table):
            LegacyMigrator._quarantine_row(
                target, import_id, table, row, "旧记录不满足新 Hash/Receipt/版本协议"
            )
            quarantined[table] += 1

    @staticmethod
    def _quarantine_row(
        target: sqlite3.Connection,
        import_id: str,
        table: str,
        row: dict[str, Any],
        reason: str,
    ) -> None:
        payload = _canonical(row)
        resource_id, digest = _resource(target, payload, "application/json")
        target.execute(
            "INSERT INTO legacy_quarantine(id, import_id, source_table, source_id, source_hash, payload_resource_id, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_identifier("quarantine"), import_id, table, str(row.get("id", "")), digest, resource_id, reason),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="迁移只读 NovelOS legacy SQLite 到新 MCP Schema")
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = LegacyMigrator(args.source, args.target).migrate()
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")


if __name__ == "__main__":
    main()
