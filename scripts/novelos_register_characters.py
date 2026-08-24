#!/usr/bin/env python
"""人物注册表幂等登记：契约 roster 落库 + 动态配角登记 + 状态对账。

人物注册表（characters 表，migration 018 重建）是人物状态的唯一锚点：
主要人物全量设计的 roster、章纲执行卡预登记的次要角色、连续性提取的
状态迁移（active/peripheral/dormant/departed/transformed/dead）都在这里合流。

入口（可同用，单事务）：
- `--roster <json>`：character_contract 锁定时传入 metadata.character_roster
  数组（schema 见 planning-candidate.schema.json 的 $defs/character_roster）。
  落库为 role_class=main/secondary，arc_role 与预期退场写 state_json。
  重锁对账：曾在旧 roster（有 arc_role）但不在新 roster 的人物会 WARN，
  提示用 --status-update 退役或补回。
- `--entry <json>`：动态配角登记，单对象或数组：
  {name, role_class: minor|secondary, first_chapter_id?, notes?}。
  卷纲锁定时班底（metadata.volume_characters）也走本入口，条目可带
  arc_role / 预期退场（八值 enum）/ 来源卷（整数）/ 微档案 / 登记备注 /
  source:"volume_outline"，随 state_json 落库。
- `--status-update <json>`：连续性状态迁移（character_status 晋升后），
  单对象或数组（一章多个迁移一次提交）。dead 必须带 死亡型 exit_type；
  非退场状态不得携带 exit_type，且会清空遗留退场痕迹（复活不留半截
  exit_chapter_id）；每次迁移在 state_json.状态史 追加一条审计记录。
- `--pending-status`：账本↔注册表对账——比对已 promoted 候选集中每个
  人物的最新 character_status 候选与注册表现状，漂移即逐条列出并以
  非零码退出（novel-continuity 收尾必跑）。
- `--audit-entries`（T39）：卷纲班底落表终核——locked 卷纲的
  volume_characters 逐名对注册表，漏跑 `--entry` 即非零退出；附带
  WARN 列出 volume_settings 待登记入 world 的条目。
- `--world <json>`（T37）：world_contract metadata——登记时席位对账：
  roster/entry 的 seat_ref 引用不存在的席位 = FAIL；写库后报告 world
  标注「待契约认领/待卷级班底」但仍无任何注册表认领人的席位（WARN
  提示，主要席位闭环的最后核对点）。

幂等：同名（project_id+name 唯一）已存在时更新 role_class 与 state_json
补充字段，**不覆盖** status/exit 字段（状态迁移只走连续性提取路径）。
roster 路径写 state_json 的字段：arc_role / 预期退场 / 登场卷 / seat_ref /
essence（T37 起人物卡要点，正文执行端 character_essence 槽消费）。

用法::

    # 契约锁定时
    python scripts/novelos_register_characters.py --project project:xxx --roster roster.json

    # 执行卡微档案 / 章节接受后补登记
    python scripts/novelos_register_characters.py --project project:xxx --entry entry.json

    # 连续性状态迁移（character_status 晋升后，支持数组）
    python scripts/novelos_register_characters.py --project project:xxx \\
        --status-update '[{"name": "沈青梧", "status": "departed", "exit_type": "迁移型", "exit_chapter_id": "chapter:xxx"}]'

    # 账本↔注册表对账（连续性收尾）
    python scripts/novelos_register_characters.py --project project:xxx --pending-status

    # 卷纲班底落表终核（卷纲锁定循环收尾 / 开下一卷前）
    python scripts/novelos_register_characters.py --project project:xxx --audit-entries
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "data" / "novelos-v2.db"
SCHEMA_PATH = REPO_ROOT / "config" / "schemas" / "planning-candidate.schema.json"

STATUS_VALUES = ("active", "peripheral", "dormant", "departed", "transformed", "dead")
EXIT_TYPES = ("完成型", "迁移型", "转化型", "关系型", "功能转移型", "休眠型", "死亡型")
EXIT_STATUSES = ("departed", "transformed", "dormant", "dead")


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
        et = e.get("预期退场")
        if et is not None and et not in EXIT_TYPES + ("持续活跃",):
            errors.append(f"entry[{i}]: 预期退场非法 {et!r}（{EXIT_TYPES} 或 持续活跃）")
        vol = e.get("来源卷")
        if vol is not None and not (isinstance(vol, int) and 1 <= vol <= 99):
            errors.append(f"entry[{i}]: 来源卷须为 1-99 整数，got {vol!r}")
    return errors


def _validate_status_update(update: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(update.get("name"), str) or not update["name"].strip():
        errors.append("status-update: name 非空必填")
    if update.get("status") not in STATUS_VALUES:
        errors.append(f"status-update: status 非法 {update.get('status')!r}（{STATUS_VALUES}）")
        return errors
    et = update.get("exit_type")
    if et is not None and et not in EXIT_TYPES:
        errors.append(f"status-update: exit_type 非法 {et!r}（{EXIT_TYPES}）")
    if update.get("status") == "dead" and et != "死亡型":
        errors.append("status-update: status=dead 时 exit_type 必须为 死亡型")
    if update.get("status") not in EXIT_STATUSES and et is not None:
        errors.append(
            f"status-update: status={update['status']!r} 是非退场状态，不应携带 exit_type"
            "（复活/回归会整体清空退场痕迹）"
        )
    return errors


def _norm_name(name: str) -> str:
    """近重名归一化：NFKC（全半角/组合字符）+ 去空白 + casefold。
    语义判级仍是 LLM 审查职责，这里只拦机器可判的归一化撞名。"""
    import unicodedata
    return "".join(unicodedata.normalize("NFKC", name).split()).casefold()


def _near_dup_warns(conn: sqlite3.Connection, project_id: str,
                    incoming: list[dict[str, Any]]) -> list[str]:
    """登记名 vs 在库名 + 批内的归一化撞名（原始名不同才算——完全同名走幂等合并）。"""
    warns: list[str] = []
    existing: dict[str, str] = {
        _norm_name(r["name"]): r["name"] for r in conn.execute(
            "SELECT name FROM characters WHERE project_id = ?", (project_id,))
    }
    batch: dict[str, str] = {}
    for item in incoming:
        raw, norm = item.get("name", ""), _norm_name(item.get("name", ""))
        if not norm:
            continue
        hit = existing.get(norm)
        if hit is not None and hit != raw:
            warns.append(f"WARN 近重名：{raw!r} 与在库人物 {hit!r} 归一化后相同"
                         "（全半角/空白/大小写）——确认是否笔误")
        elif norm in batch and batch[norm] != raw:
            warns.append(f"WARN 批内近重名：{raw!r} 与 {batch[norm]!r} 归一化后相同——确认是否笔误")
        batch.setdefault(norm, raw)
    return warns


def _seat_reconciliation(conn: sqlite3.Connection, project_id: str,
                         world: dict[str, Any],
                         incoming: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """席位对账：引用存在性（error）+ 写库后未认领承诺席位清单（warn）。"""
    seat_names = {s.get("name") for s in world.get("seats", []) if s.get("name")}
    errors: list[str] = []
    for item in incoming:
        ref = item.get("seat_ref")
        if ref and ref not in seat_names:
            errors.append(f"{item.get('name', '?')}.seat_ref 引用不存在的席位: {ref!r}")
    claimed: set[str] = set()
    for r in conn.execute(
            "SELECT state_json FROM characters WHERE project_id = ?", (project_id,)):
        try:
            ref = json.loads(r["state_json"] or "{}").get("seat_ref")
        except json.JSONDecodeError:
            continue
        if ref:
            claimed.add(ref)
    for item in incoming:
        if item.get("seat_ref"):
            claimed.add(item["seat_ref"])
    warns = [
        f"WARN 席位「{s['name']}」world 标注「{s.get('disposition')}」但注册表尚无认领人"
        for s in world.get("seats", [])
        if s.get("name") and s.get("disposition") in ("待契约认领", "待卷级班底")
        and s["name"] not in claimed
    ]
    return errors, warns


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


def _apply_status_update(conn: sqlite3.Connection, project_id: str,
                         upd: dict[str, Any]) -> str:
    """单条状态迁移：状态史审计 + 退场痕迹对称（非退场状态清空 exit 字段）。"""
    row = conn.execute(
        "SELECT id, status, exit_type, state_json FROM characters "
        "WHERE project_id = ? AND name = ?",
        (project_id, upd["name"]),
    ).fetchone()
    if row is None:
        # 连续性提名的状态人物可能尚未登记（动态配角漏登记）——按 minor 补建
        char_id = _upsert(
            conn, project_id, upd["name"], "minor",
            {"补登": "连续性状态迁移先于登记"}, upd.get("exit_chapter_id"),
        )
        old_status, state = "active", {"补登": "连续性状态迁移先于登记"}
    else:
        char_id, old_status, state = (
            row["id"], row["status"], json.loads(row["state_json"] or "{}"))
    state.setdefault("状态史", []).append({
        "from": old_status,
        "to": upd["status"],
        "exit_type": upd.get("exit_type"),
        "chapter_id": upd.get("exit_chapter_id"),
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    state_json = json.dumps(state, ensure_ascii=False)
    if upd["status"] in EXIT_STATUSES:
        conn.execute(
            "UPDATE characters SET status = ?, exit_type = ?, "
            "exit_chapter_id = COALESCE(?, exit_chapter_id), state_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (upd["status"], upd.get("exit_type"), upd.get("exit_chapter_id"),
             state_json, char_id),
        )
    else:
        # 复活/回归：退场痕迹整体清空，不留有 exit_chapter_id 无 exit_type 的半截记录
        conn.execute(
            "UPDATE characters SET status = ?, exit_type = NULL, "
            "exit_chapter_id = NULL, state_json = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (upd["status"], state_json, char_id),
        )
    return f"status {upd['name']} {old_status} -> {upd['status']}"


def check_pending_status(db_path: Path, project_id: str) -> int:
    """账本↔注册表对账：promoted 候选集中每人物最新 character_status
    候选 vs 注册表现状。漂移逐条列出，非零退出；无漂移输出对账通过。

    只比对每人物**最新**一条候选（按候选集 created_at 序）——历史迁移被
    后续迁移超越是正常状态机推进，不算漂移。
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            print(f"项目不存在: {project_id}")
            return 2
        try:
            sets = conn.execute(
                "SELECT s.id, CAST(r.content AS TEXT) AS cand_json "
                "FROM continuity_candidate_sets s "
                "JOIN resources r ON r.id = s.candidate_resource_id "
                "WHERE s.project_id = ? AND s.status = 'promoted' "
                "ORDER BY s.created_at, s.id",
                (project_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            print("对账跳过：库中无 continuity_candidate_sets 表。")
            return 0
        latest: dict[str, dict[str, str]] = {}
        for set_id, cand_json in sets:
            try:
                candidates = json.loads(cand_json).get("candidates", [])
            except (json.JSONDecodeError, AttributeError):
                continue
            for c in candidates:
                if c.get("type") == "character_status" and c.get("name"):
                    latest[c["name"]] = {"status": c.get("status", ""), "set": set_id}
        if not latest:
            print("对账通过：promoted 候选集中无 character_status 候选。")
            return 0
        drift: list[str] = []
        for name, want in sorted(latest.items()):
            row = conn.execute(
                "SELECT status FROM characters WHERE project_id = ? AND name = ?",
                (project_id, name),
            ).fetchone()
            if row is None:
                drift.append(f"DRIFT {name}：候选 {want['status']}（{want['set']}）但注册表未登记")
            elif row["status"] != want["status"]:
                drift.append(
                    f"DRIFT {name}：候选 {want['status']}（{want['set']}）"
                    f"≠ 注册表 {row['status']}"
                )
        if drift:
            for d in drift:
                print(d)
            print(f"\n对账发现 {len(drift)} 处漂移——漏跑 --status-update 或迁移被回滚，"
                  "处理完再继续后续章节。")
            return 1
        print(f"对账通过：{len(latest)} 个人物状态与注册表一致。")
        return 0
    finally:
        conn.close()


def run(db_path: Path, project_id: str, roster: list[dict[str, Any]] | None,
        entries: list[dict[str, Any]] | None,
        status_update: dict[str, Any] | list[dict[str, Any]] | None,
        world: dict[str, Any] | None = None) -> int:
    updates = None
    if status_update is not None:
        updates = [status_update] if isinstance(status_update, dict) else list(status_update)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            print(f"项目不存在: {project_id}")
            return 2

        errors: list[str] = []
        roster_warns: list[str] = []
        incoming = list(roster or []) + list(entries or [])
        roster_warns += _near_dup_warns(conn, project_id, incoming)
        if world is not None and incoming:
            seat_errors, seat_warns = _seat_reconciliation(conn, project_id, world, incoming)
            errors += seat_errors
            roster_warns += seat_warns
        if roster is not None:
            errors += _validate_roster(roster)
            # 重锁对账：曾在旧 roster（state_json 带 arc_role）但不在新 roster 的人物
            roster_names = {item["name"] for item in roster}
            was_rostered = {
                r["name"] for r in conn.execute(
                    "SELECT name, state_json FROM characters WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
                if "arc_role" in json.loads(r["state_json"] or "{}")
            }
            for name in sorted(was_rostered - roster_names):
                roster_warns.append(
                    f"WARN 人物「{name}」曾在旧契约 roster 但不在新 roster——若契约修订"
                    "删除了该人物，用 --status-update 退役（休眠型/迁移型）；若误删请补回"
                )
        if entries is not None:
            errors += _validate_entries(entries)
        if updates is not None:
            for upd in updates:
                errors += _validate_status_update(upd)
        if errors:
            for e in errors:
                print(f"FAIL {e}")
            return 1

        results: list[str] = []
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        try:
            for item in roster or []:
                patch = {"arc_role": item["arc_role"], "预期退场": item["预期退场"],
                         "登场卷": item["登场卷"]}
                for extra in ("seat_ref", "essence"):
                    if item.get(extra):
                        patch[extra] = item[extra]
                char_id = _upsert(conn, project_id, item["name"], item["role_class"], patch)
                results.append(f"roster {item['name']} -> {char_id}")
            for item in entries or []:
                patch = {k: v for k, v in item.items() if k not in ("name", "role_class")}
                char_id = _upsert(
                    conn, project_id, item["name"], item.get("role_class", "secondary"),
                    patch, item.get("first_chapter_id"),
                )
                results.append(f"entry {item['name']} -> {char_id}")
            for upd in updates or []:
                results.append(_apply_status_update(conn, project_id, upd))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        for line in results:
            print(line)
        for w in roster_warns:
            print(w)
        print(f"完成（{len(results)} 项，单事务提交）。")
        return 0
    finally:
        conn.close()


def check_audit_entries(db_path: Path, project_id: str) -> int:
    """卷纲班底落表终核（T39）：locked 卷纲的 volume_characters 逐名对注册表。

    漏跑 --entry = FAIL 非零退出（卷纲锁定后班底必须落注册表——执行卡
    「卷纲已登记」的引用才不悬空）。附带列出 volume_settings 中
    disposition=登记入world 的待登记条目（WARN 提示走 world change
    proposal，不影响退出码）。T39 前旧卷纲无 volume_characters 字段则跳过。
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        proj = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if proj is None:
            print(f"项目不存在: {project_id}")
            return 2
        rows = conn.execute(
            "SELECT scope_ref, revision, metadata_json FROM planning_assets "
            "WHERE project_id = ? AND asset_type = 'volume_outline' AND status = 'locked' "
            "ORDER BY scope_ref, revision", (project_id,)).fetchall()
        latest: dict[str, tuple[int, dict]] = {}
        for scope, revision, meta_json in rows:
            if scope not in latest or revision > latest[scope][0]:
                try:
                    latest[scope] = (revision, json.loads(meta_json or "{}") or {})
                except json.JSONDecodeError:
                    latest[scope] = (revision, {})
        missing: list[str] = []
        pending_settings: list[str] = []
        n_entries = 0
        for scope, (_, meta) in sorted(latest.items()):
            for p in meta.get("volume_characters") or []:
                n_entries += 1
                name = p.get("name")
                hit = conn.execute(
                    "SELECT 1 FROM characters WHERE project_id = ? AND name = ?",
                    (project_id, name)).fetchone()
                if hit is None:
                    missing.append(f"卷纲[{scope}] 班底 {name} 未入注册表——漏跑 --entry")
            pending_settings += [
                f"卷纲[{scope}] 设定 {s.get('name')}（{s.get('kind')}）待登记入 world"
                for s in meta.get("volume_settings") or []
                if s.get("disposition") == "登记入world"
            ]
        for w in pending_settings:
            print(f"WARN: {w}（锁定后应走 world change proposal）")
        if missing:
            print(f"FAIL（{len(missing)} 处班底未落表）:")
            for m in missing:
                print(f"  - {m}")
            return 1
        print(f"PASS: 卷纲班底落表终核通过（{len(latest)} 卷，{n_entries} 条班底"
              + (f"，待登记设定 {len(pending_settings)} 项见 WARN" if pending_settings else "")
              + "）。")
        return 0
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--project", required=True, help="项目 ID（project:xxx）")
    parser.add_argument("--roster", type=Path, help="character_roster JSON 路径（契约锁定时）")
    parser.add_argument("--entry", type=Path, help="动态配角登记 JSON（单对象或数组）")
    parser.add_argument("--status-update", help="状态迁移 JSON 路径或内联 JSON（单对象或数组，character_status 晋升后）")
    parser.add_argument("--pending-status", action="store_true",
                        help="账本↔注册表对账：promoted character_status 候选 vs 注册表现状，漂移非零退出")
    parser.add_argument("--audit-entries", action="store_true",
                        help="卷纲班底落表终核：locked 卷纲 volume_characters 逐名对注册表，漏跑 --entry 非零退出")
    parser.add_argument("--world", type=Path,
                        help="world_contract metadata JSON——启用席位对账（seat_ref 存在性 FAIL + 未认领承诺席位 WARN）")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()

    if args.pending_status:
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"数据库不存在: {db_path}")
            return 2
        return check_pending_status(db_path, args.project)

    if args.audit_entries:
        db_path = Path(args.db)
        if not db_path.exists():
            print(f"数据库不存在: {db_path}")
            return 2
        return check_audit_entries(db_path, args.project)

    if not args.roster and not args.entry and not args.status_update:
        parser.error("至少提供 --roster / --entry / --status-update / --pending-status / --audit-entries 之一")

    roster = _load(args.roster) if args.roster else None
    entries = _load(args.entry) if args.entry else None
    if isinstance(entries, dict):
        entries = [entries]
    status_update: Any = None
    if args.status_update:
        status_update = (json.loads(args.status_update)
                         if args.status_update.lstrip().startswith(("[", "{"))
                         else _load(Path(args.status_update)))

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return 2
    world = _load(args.world) if args.world else None
    return run(db_path, args.project, roster, entries, status_update, world)


if __name__ == "__main__":
    sys.exit(main())
