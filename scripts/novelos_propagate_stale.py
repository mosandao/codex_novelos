#!/usr/bin/env python
"""上游规划资产变更后，递归标记下游 stale。

原来由 NovelOS MCP 在 revision 时自动传播。完全替代后由本脚本承担。
依赖 planning_asset_dependencies 表（记录 asset → upstream_asset 的版本关系）。

用法::

    # 干跑：显示会被标记 stale 的资产，不实际执行
    python scripts/novelos_propagate_stale.py --check --asset planning:xxx

    # 执行：标记下游 stale
    python scripts/novelos_propagate_stale.py --asset planning:xxx
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _collect_downstream(conn: sqlite3.Connection, asset_id: str) -> list[dict[str, str]]:
    """递归查询依赖图，收集所有下游（直接 + 间接）locked 资产。

    planning_asset_dependencies.asset_id 依赖 upstream_asset_id。
    所以 upstream 变更时，所有 asset_id 依赖它的记录对应的资产都是下游。
    """
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    queue = [asset_id]

    while queue:
        current = queue.pop(0)
        rows = conn.execute(
            """
            SELECT pa.id, pa.project_id, pa.asset_type, pa.scope_ref, pa.status
            FROM planning_asset_dependencies pad
            JOIN planning_assets pa ON pa.id = pad.asset_id
            WHERE pad.upstream_asset_id = ?
              AND pa.status = 'locked'
            """,
            (current,),
        ).fetchall()
        for row in rows:
            aid = row["id"]
            if aid in seen:
                continue
            seen.add(aid)
            result.append({
                "id": aid,
                "project_id": row["project_id"],
                "asset_type": row["asset_type"],
                "scope_ref": row["scope_ref"],
                "status": row["status"],
            })
            queue.append(aid)

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="传播 stale：上游变更后标记下游")
    parser.add_argument(
        "--db",
        default="data/novelos-v2.db",
        help="SQLite 数据库路径 (default: data/novelos-v2.db)",
    )
    parser.add_argument("--asset", required=True, help="变更的上游 asset_id (如 planning:xxx)")
    parser.add_argument("--check", action="store_true", help="干跑模式：只显示，不执行")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: 数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # 确认上游资产存在
    upstream = conn.execute(
        "SELECT id, asset_type, status FROM planning_assets WHERE id = ?", (args.asset,)
    ).fetchone()
    if upstream is None:
        print(f"ERROR: 资产不存在: {args.asset}", file=sys.stderr)
        sys.exit(1)

    downstream = _collect_downstream(conn, args.asset)

    if not downstream:
        print(f"无下游 locked 资产需要标记 stale（上游: {args.asset} [{upstream['asset_type']}]）")
        conn.close()
        return

    print(f"上游: {args.asset} [{upstream['asset_type']}] (当前 status={upstream['status']})")
    print(f"下游 ({len(downstream)} 个 locked 资产将被标记 stale):")
    for d in downstream:
        print(f"  {d['id']}  {d['asset_type']:20s}  {d['scope_ref']}")

    if args.check:
        print("\n[干跑模式] 未执行 UPDATE。去掉 --check 执行。")
    else:
        for d in downstream:
            conn.execute(
                "UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (d["id"],),
            )
        conn.commit()
        print(f"\n已标记 {len(downstream)} 个资产为 stale。")

    conn.close()


if __name__ == "__main__":
    main()
