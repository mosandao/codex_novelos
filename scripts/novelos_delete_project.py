#!/usr/bin/env python
"""删除 NovelOS 项目（数据库内容 + 投影目录）。

一个项目分布在多张表，且存在大量 ``ON DELETE RESTRICT`` 约束
（``planning_asset_dependencies.upstream_asset_id``、``reviews``、
``resources`` 等不级联），不能简单 ``DELETE FROM projects``。本脚本在
``foreign_keys=OFF`` 下按依赖逆序手动删除各表，清理孤儿，最后用
``foreign_keys=ON`` 复验完整性。

关键设计：
- 显式事务（``isolation_level=None`` + 手动 ``BEGIN/COMMIT``），避免连接
  关闭时未提交回滚——这是逐表手动删除最容易踩的坑。
- 只删项目专属内容资源（``planning_assets``/``chapters``/实体/连续性的
  ``resource_id``），**不动** ``creator_profile_versions`` 引用的共享系统原型
  资源（跨项目共享，删了会破坏其他项目）。
- 投影目录按 ``manifest.json`` 的 ``project_id`` 匹配删除，不依赖目录命名。

用法::

    # 干跑：调查项目范围，不删除
    python scripts/novelos_delete_project.py --project project:xxx --dry-run

    # 删前备份数据库
    python scripts/novelos_delete_project.py --project project:xxx --backup

    # 执行删除（默认同时删投影目录）
    python scripts/novelos_delete_project.py --project project:xxx

    # 额外清理全库孤儿 reviews/dependencies（非本项目遗留的死数据）
    python scripts/novelos_delete_project.py --project project:xxx --clean-orphans
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DB = "data/novelos-v2.db"
DEFAULT_NOVELS = "novels"

# 项目专属内容资源的来源列（不含 creator_profile_versions——后者跨项目共享）。
_RESOURCE_SOURCES = [
    "SELECT content_resource_id FROM planning_assets WHERE project_id=?",
    """SELECT c.content_resource_id FROM chapters c
       JOIN volumes v ON c.volume_id=v.id JOIN books b ON v.book_id=b.id
       WHERE b.project_id=?""",
    "SELECT description_resource_id FROM characters WHERE project_id=? AND description_resource_id IS NOT NULL",
    "SELECT description_resource_id FROM worlds WHERE project_id=? AND description_resource_id IS NOT NULL",
    "SELECT description_resource_id FROM narrative_promises WHERE project_id=? AND description_resource_id IS NOT NULL",
    "SELECT description_resource_id FROM expectation_ledgers WHERE project_id=? AND description_resource_id IS NOT NULL",
    "SELECT state_resource_id FROM relationship_states WHERE project_id=? AND state_resource_id IS NOT NULL",
    "SELECT state_resource_id FROM arc_states WHERE project_id=? AND state_resource_id IS NOT NULL",
    "SELECT description_resource_id FROM chapter_facts WHERE project_id=? AND description_resource_id IS NOT NULL",
]
# 连续性账本表（均有 project_id 外键，逐表删）。
_CONTINUITY_TABLES = [
    "chapter_facts", "timelines", "arc_states",
    "relationship_states", "expectation_ledgers", "narrative_promises",
]


def _placeholders(n: int) -> str:
    return ",".join("?" * n)


def collect_ids(conn: sqlite3.Connection, pid: str) -> dict[str, Any]:
    """收集项目相关的所有实体 id 与待删资源 id。"""
    asset_ids = [r[0] for r in conn.execute(
        "SELECT id FROM planning_assets WHERE project_id=?", (pid,))]
    chapter_ids = [r[0] for r in conn.execute(
        """SELECT c.id FROM chapters c JOIN volumes v ON c.volume_id=v.id
           JOIN books b ON v.book_id=b.id WHERE b.project_id=?""", (pid,))]
    volume_ids = [r[0] for r in conn.execute(
        "SELECT v.id FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?", (pid,))]
    book_ids = [r[0] for r in conn.execute(
        "SELECT id FROM books WHERE project_id=?", (pid,))]
    subject_refs = set(asset_ids + chapter_ids + volume_ids + book_ids)
    resource_ids: set[str] = set()
    for sql in _RESOURCE_SOURCES:
        resource_ids.update(r[0] for r in conn.execute(sql, (pid,)) if r[0])
    resource_ids.discard(None)
    return {
        "assets": asset_ids, "chapters": chapter_ids, "volumes": volume_ids,
        "books": book_ids, "subjects": subject_refs, "resources": resource_ids,
    }


def survey(conn: sqlite3.Connection, pid: str) -> dict[str, Any]:
    """打印项目在各表的规模，返回 collect_ids 结果。"""
    row = conn.execute("SELECT id, name FROM projects WHERE id=?", (pid,)).fetchone()
    if row is None:
        sys.exit(f"找不到项目 {pid}")
    print(f"项目：{row[1]}（{row[0]}）")
    ids = collect_ids(conn, pid)

    def cnt(sql: str, args: tuple = (pid,)) -> int:
        return conn.execute(sql, args).fetchone()[0]

    print(f"  books={cnt('SELECT count(*) FROM books WHERE project_id=?')}  "
          f"volumes={cnt('SELECT count(*) FROM volumes v JOIN books b ON v.book_id=b.id WHERE b.project_id=?')}  "
          f"chapters={cnt('SELECT count(*) FROM chapters c JOIN volumes v ON c.volume_id=v.id JOIN books b ON v.book_id=b.id WHERE b.project_id=?')}")
    print("  planning_assets：")
    for r in conn.execute(
        "SELECT asset_type, status, count(*) FROM planning_assets WHERE project_id=? "
        "GROUP BY asset_type, status ORDER BY asset_type", (pid,)
    ).fetchall():
        print(f"    {r[0]:20s} {r[1]:12s} x{r[2]}")
    rev = cnt(
        f"SELECT count(*) FROM reviews WHERE subject_ref IN ({_placeholders(len(ids['subjects']))})",
        tuple(ids["subjects"]),
    ) if ids["subjects"] else 0
    print(f"  待删：resources={len(ids['resources'])}  reviews={rev}  "
          f"characters={cnt('SELECT count(*) FROM characters WHERE project_id=?')}  "
          f"worlds={cnt('SELECT count(*) FROM worlds WHERE project_id=?')}")
    return ids


def delete_project(conn: sqlite3.Connection, pid: str, ids: dict[str, Any]) -> None:
    """按依赖逆序删除项目（foreign_keys=OFF + 显式事务）。"""
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")
    steps: list[tuple[str, int]] = []

    def exe(label: str, sql: str, args: tuple = ()) -> None:
        steps.append((label, conn.execute(sql, args).rowcount))

    assets = ids["assets"]
    if assets:
        exe("planning_asset_dependencies",
            f"DELETE FROM planning_asset_dependencies WHERE asset_id IN ({_placeholders(len(assets))}) "
            f"OR upstream_asset_id IN ({_placeholders(len(assets))})",
            tuple(assets) + tuple(assets))
    if ids["subjects"]:
        exe("reviews",
            f"DELETE FROM reviews WHERE subject_ref IN ({_placeholders(len(ids['subjects']))})",
            tuple(ids["subjects"]))
    for table in _CONTINUITY_TABLES:
        exe(table, f"DELETE FROM {table} WHERE project_id=?", (pid,))
    if ids["chapters"]:
        exe("chapters", f"DELETE FROM chapters WHERE id IN ({_placeholders(len(ids['chapters']))})",
            tuple(ids["chapters"]))
    if ids["volumes"]:
        exe("volumes", f"DELETE FROM volumes WHERE id IN ({_placeholders(len(ids['volumes']))})",
            tuple(ids["volumes"]))
    exe("planning_assets", "DELETE FROM planning_assets WHERE project_id=?", (pid,))
    exe("characters", "DELETE FROM characters WHERE project_id=?", (pid,))
    exe("worlds", "DELETE FROM worlds WHERE project_id=?", (pid,))
    exe("project_creator_bindings", "DELETE FROM project_creator_bindings WHERE project_id=?", (pid,))
    exe("books", "DELETE FROM books WHERE project_id=?", (pid,))
    exe("projects", "DELETE FROM projects WHERE id=?", (pid,))
    if ids["resources"]:
        exe("resources", f"DELETE FROM resources WHERE id IN ({_placeholders(len(ids['resources']))})",
            tuple(ids["resources"]))

    conn.execute("COMMIT")
    conn.execute("PRAGMA foreign_keys=ON")
    print("--- 删除行数 ---")
    for label, n in steps:
        print(f"  {label}: {n}")


def clean_orphans(conn: sqlite3.Connection) -> None:
    """清理全库孤儿 reviews/dependencies（非本项目删除造成的历史遗留）。"""
    conn.execute("BEGIN")
    r1 = conn.execute(
        "DELETE FROM reviews WHERE subject_type='planning_asset' "
        "AND subject_ref NOT IN (SELECT id FROM planning_assets)"
    ).rowcount
    r2 = conn.execute(
        "DELETE FROM planning_asset_dependencies WHERE asset_id NOT IN (SELECT id FROM planning_assets) "
        "OR upstream_asset_id NOT IN (SELECT id FROM planning_assets)"
    ).rowcount
    conn.execute("COMMIT")
    print(f"清理全库孤儿：reviews={r1}  dependencies={r2}")


def verify(conn: sqlite3.Connection, pid: str) -> None:
    """复验项目残留与全库孤儿（foreign_keys=ON）。"""
    conn.execute("PRAGMA foreign_keys=ON")
    left = conn.execute("SELECT count(*) FROM projects WHERE id=?", (pid,)).fetchone()[0]
    left_pa = conn.execute(
        "SELECT count(*) FROM planning_assets WHERE project_id=?", (pid,)).fetchone()[0]
    orphan_rev = conn.execute(
        "SELECT count(*) FROM reviews WHERE subject_type='planning_asset' "
        "AND subject_ref NOT IN (SELECT id FROM planning_assets)"
    ).fetchone()[0]
    orphan_dep = conn.execute(
        "SELECT count(*) FROM planning_asset_dependencies d WHERE d.asset_id NOT IN (SELECT id FROM planning_assets) "
        "OR d.upstream_asset_id NOT IN (SELECT id FROM planning_assets)"
    ).fetchone()[0]
    print("=== 完整性验证 ===")
    print(f"  项目残留：project={left}  planning_assets={left_pa}")
    print(f"  全库孤儿：reviews={orphan_rev}  dependencies={orphan_dep}")
    if orphan_rev or orphan_dep:
        print("  （孤儿非本次删除造成，可用 --clean-orphans 清理）")


def remove_projection(novels_root: str, pid: str) -> None:
    """按 manifest.json 的 project_id 匹配并删除投影目录。"""
    root = Path(novels_root)
    if not root.exists():
        print("投影根目录不存在，跳过")
        return
    removed: list[str] = []
    for manifest in root.glob("*/manifest.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("project_id") == pid:
            target = manifest.parent
            shutil.rmtree(target)
            removed.append(str(target))
    print(f"删除投影目录：{removed or '无'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="删除 NovelOS 项目（数据库+投影）")
    parser.add_argument("--project", required=True, help="项目 ID（如 project:xxx）")
    parser.add_argument("--db", default=DEFAULT_DB, help="数据库路径")
    parser.add_argument("--novels", default=DEFAULT_NOVELS, help="投影根目录")
    parser.add_argument("--dry-run", action="store_true", help="仅调查，不删除")
    parser.add_argument("--backup", action="store_true", help="删前备份数据库")
    parser.add_argument("--no-projection", action="store_true", help="不删投影目录")
    parser.add_argument("--clean-orphans", action="store_true", help="额外清理全库孤儿 reviews/dependencies")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None  # 手动控制事务，避免连接关闭回滚
    try:
        ids = survey(conn, args.project)
        if args.dry_run:
            print("（dry-run，不执行删除）")
            return
        if args.backup:
            bak = Path(args.db).with_name(Path(args.db).name + f".bak-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(args.db, bak)
            print(f"已备份：{bak}")
        delete_project(conn, args.project, ids)
        if args.clean_orphans:
            clean_orphans(conn)
        verify(conn, args.project)
    finally:
        conn.close()

    if not args.no_projection:
        remove_projection(args.novels, args.project)


if __name__ == "__main__":
    main()
