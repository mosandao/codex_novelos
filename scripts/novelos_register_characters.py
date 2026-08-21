#!/usr/bin/env python
"""人物注册表幂等登记：契约 roster 落库 + 动态配角登记。

人物注册表（characters 表，migration 018 重建）是人物状态的唯一锚点：
主要人物全量设计的 roster、章纲执行卡预登记的次要角色、连续性提取的
状态迁移（active/peripheral/dormant/departed/transformed/dead）都在这里合流。

两个入口（可同用，单事务）：
- `--roster <json>`：character_contract 锁定时传入 metadata.character_roster
  数组（schema 见 planning-candidate.schema.json 的 $defs/character_roster）。
  落库为 role_class=main/secondary，arc_role 与预期退场写 state_json。
- `--entry <json>`：动态配角登记（执行卡微档案），单对象或数组：
  {name, role_class: minor|secondary, first_chapter_id?, notes?}。

幂等：同名（project_id+name 唯一）已存在时更新 role_class 与 state_json
补充字段，**不覆盖** status/exit 字段（状态迁移只走连续性提取路径）。

用法::

    # 契约锁定时
    python scripts/novelos_register_characters.py --project project:xxx --roster roster.json

    # 执行卡微档案 / 章节接受后补登记
    python scripts/novelos_register_characters.py --project project:xxx --entry entry.json

    # 连续性状态迁移（character_status 晋升后）
    python scripts/novelos_register_characters.py --project project:xxx \\
        --status-update '{"name": "沈青梧", "status": "departed", "exit_type": "迁移型", "exit_chapter_id": "chapter:xxx"}'
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "novelos-v2.db"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "planning-candidate.schema.json"

STATUS_VALUES = ("active", "peripheral", "dormant", "departed", "transformed", "dead")
EXIT_TYPES = ("完成型", "迁移型", "转化型", "关系型", "功能转移型", "休眠型", "死亡型")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_roster(roster: list[dict[str, Any]]) -> list[str]:
    """roster 按 planning-candidate $defs/character_roster 校验，返回错误清单。"""
    import jsonschema

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sub = dict(schema["$defs"]["character_roster"])
    sub["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    errors = []
    try:
        jsonschema.validate(roster, sub)
    except jsonschema.ValidationError as exc:
        for err in [exc] + list(exc.context or []):
            path = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"roster[{path}]: {err.message}")
    return errors


def _validate_entries(entries: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for i, e in enumerate(entries):
        name = e.get("name")
        if not isinstance(name, str) or not name.strip():
            errors.append(f"entry[{i}]: name 非空必填")
        rc = e.get("role_class", "secondary")
        if rc not in ("minor", "secondary", "main"):
            errors.append(f"entry[{i}]: role_class 非法 {rc!r}")
    return errors


def _validate_status_update(update: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(update.get("name"), str) or not update["name"].strip():
        errors.append("status-update: name 非空必填")
    if update.get("status") not in STATUS_VALUES:
        errors.append(f"status-update: status 非法 {update.get('status')!r}（{STATUS_VALUES}）")
    et = update.get("exit_type")
    if et is not None and et not in EXIT_TYPES:
        errors.append(f"status-update: exit_type 非法 {et!r}（{EXIT_TYPES}）")
    if update.get("status") == "dead" and update.get("exit_type") != "死亡型":
        errors.append("status-update: status=dead 时 exit_type 必须为 死亡型")
    return errors


def _upsert(conn: sqlite3.Connection, project_id: str, name: str, role_class: str,
            state_patch: dict[str, Any], first_chapter_id: str | None = None) -> str:
    existing = conn.execute(
        "SELECT id, state_json FROM characters WHERE project_id = ? AND name = ?",
        (project_id, name),
    ).fetchone()
    if existing is None:
        char_id = f"character:{uuid.uuid4()}"
        conn.execute(
            "INSERT INTO characters (id, project_id, name, role_class, status, "
            " state_json, first_chapter_id) VALUES (?, ?, ?, ?, 'active', ?, ?)",
            (char_id, project_id, name, role_class,
             json.dumps(state_patch, ensure_ascii=False), first_chapter_id),
        )
        return char_id
    state = json.loads(existing[1] or "{}")
    state.update(state_patch)
    conn.execute(
        "UPDATE characters SET role_class = ?, state_json = ?, "
        "first_chapter_id = COALESCE(?, first_chapter_id), updated_at = CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (role_class, json.dumps(state, ensure_ascii=False), first_chapter_id, existing[0]),
    )
    return existing[0]


def run(db_path: Path, project_id: str, roster: list[dict[str, Any]] | None,
        entries: list[dict[str, Any]] | None,
        status_update: dict[str, Any] | None) -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            print(f"项目不存在: {project_id}")
            return 2

        errors: list[str] = []
        if roster is not None:
            errors += _validate_roster(roster)
        if entries is not None:
            errors += _validate_entries(entries)
        if status_update is not None:
            errors += _validate_status_update(status_update)
        if errors:
            for e in errors:
                print(f"FAIL {e}")
            return 1

        results: list[str] = []
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item in roster or []:
                char_id = _upsert(
                    conn, project_id, item["name"], item["role_class"],
                    {"arc_role": item["arc_role"], "预期退场": item["预期退场"],
                     "登场卷": item["登场卷"]},
                )
                results.append(f"roster {item['name']} -> {char_id}")
            for item in entries or []:
                patch = {k: v for k, v in item.items() if k not in ("name", "role_class")}
                char_id = _upsert(
                    conn, project_id, item["name"], item.get("role_class", "secondary"),
                    patch, item.get("first_chapter_id"),
                )
                results.append(f"entry {item['name']} -> {char_id}")
            if status_update is not None:
                row = conn.execute(
                    "SELECT id FROM characters WHERE project_id = ? AND name = ?",
                    (project_id, status_update["name"]),
                ).fetchone()
                if row is None:
                    # 连续性提名的状态人物可能尚未登记（动态配角漏登记）——按 minor 补建
                    char_id = _upsert(
                        conn, project_id, status_update["name"], "minor",
                        {"补登": "连续性状态迁移先于登记"}, status_update.get("chapter_id"),
                    )
                else:
                    char_id = row[0]
                conn.execute(
                    "UPDATE characters SET status = ?, exit_type = ?, "
                    "exit_chapter_id = COALESCE(?, exit_chapter_id), "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (status_update["status"], status_update.get("exit_type"),
                     status_update.get("exit_chapter_id"), char_id),
                )
                results.append(f"status {status_update['name']} -> {status_update['status']}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        for line in results:
            print(line)
        print(f"完成（{len(results)} 项，单事务提交）。")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="项目 ID（project:xxx）")
    parser.add_argument("--roster", type=Path, help="character_roster JSON 路径（契约锁定时）")
    parser.add_argument("--entry", type=Path, help="动态配角登记 JSON（单对象或数组）")
    parser.add_argument("--status-update", help="状态迁移 JSON 路径或内联 JSON（character_status 晋升后）")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    if not args.roster and not args.entry and not args.status_update:
        parser.error("至少提供 --roster / --entry / --status-update 之一")

    roster = _load(args.roster) if args.roster else None
    entries = _load(args.entry) if args.entry else None
    if isinstance(entries, dict):
        entries = [entries]
    status_update = None
    if args.status_update:
        status_update = (json.loads(args.status_update)
                         if args.status_update.lstrip().startswith("{")
                         else _load(Path(args.status_update)))

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return 2
    return run(db_path, args.project, roster, entries, status_update)


if __name__ == "__main__":
    sys.exit(main())
