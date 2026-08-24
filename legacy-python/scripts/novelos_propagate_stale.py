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


def _classify_fine(conn: sqlite3.Connection, upstream_id: str) -> list[dict[str, str]]:
    """精细分类（机械，无 LLM）：直接下游按依赖边版本号 + 内容 hash 双重比对。

    判定：边记录的 upstream_version == 该 scope 当前 locked revision → neutral（已对齐）；
    两个 revision 的 content_hash 相同 → neutral（变更未动内容，观测等价下不误伤）；
    否则 → stale。间接下游不自动标，列为「间接待重估」——保守正确。
    字段级语义等价（改动动了下游没消费的字段）需要消费快照支持，留待后续。
    """
    scope_row = conn.execute(
        "SELECT project_id, asset_type, scope_ref FROM planning_assets WHERE id = ?",
        (upstream_id,),
    ).fetchone()
    if scope_row is None:
        return []
    pid, atype, scope = scope_row[0], scope_row[1], scope_row[2]

    def _rev_hash(revision: int) -> str | None:
        row = conn.execute(
            "SELECT r.content_hash FROM planning_assets pa "
            "JOIN resources r ON r.id = pa.content_resource_id "
            "WHERE pa.project_id = ? AND pa.asset_type = ? AND pa.scope_ref = ? "
            "AND pa.revision = ?",
            (pid, atype, scope, revision),
        ).fetchone()
        return row[0] if row else None

    current = conn.execute(
        "SELECT revision FROM planning_assets WHERE project_id = ? AND asset_type = ? "
        "AND scope_ref = ? AND status = 'locked' ORDER BY revision DESC LIMIT 1",
        (pid, atype, scope),
    ).fetchone()
    if current is None:
        return []
    m = int(current[0])
    h_m = _rev_hash(m)

    result: list[dict[str, str]] = []
    rows = conn.execute(
        "SELECT pa.id, pa.asset_type, pa.scope_ref, pa.status, pad.upstream_version "
        "FROM planning_asset_dependencies pad "
        "JOIN planning_assets pa ON pa.id = pad.asset_id "
        "WHERE pad.upstream_asset_id = ? AND pa.status = 'locked'",
        (upstream_id,),
    ).fetchall()
    for row in rows:
        v = int(row["upstream_version"])
        if v == m:
            verdict = "neutral"
            reason = f"依赖边已对齐 rev {m}"
        elif _rev_hash(v) == h_m and h_m is not None:
            verdict = "neutral"
            reason = f"rev {v} 与 rev {m} content_hash 相同（内容未变）"
        else:
            verdict = "stale"
            reason = f"依赖 rev {v}，当前 rev {m} 且内容已变"
        result.append({
            "id": row["id"], "asset_type": row["asset_type"],
            "scope_ref": row["scope_ref"], "status": row["status"],
            "verdict": verdict, "reason": reason,
        })
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
    parser.add_argument("--fine", action="store_true",
                        help="精细模式：依赖边版本 + content_hash 双重比对，内容未变的下游不误伤（默认保留粗模式全量标 stale）")
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

    if args.fine:
        classified = _classify_fine(conn, args.asset)
        stale = [c for c in classified if c["verdict"] == "stale"]
        print(f"上游: {args.asset} [{upstream['asset_type']}]（精细模式）")
        for c in classified:
            print(f"  [{c['verdict']:>7}] {c['id']}  {c['asset_type']:18s}  {c['reason']}")
        indirect = _collect_downstream(conn, args.asset)
        indirect_ids = {d['id'] for d in indirect} - {c['id'] for c in classified}
        if indirect_ids:
            print(f"  间接待重估（不自动标）: {', '.join(sorted(indirect_ids))}")
        if not classified:
            print("无直接下游依赖边。")
        elif args.check:
            print("\n[干跑模式] 未执行 UPDATE。去掉 --check 执行。")
        else:
            for c in stale:
                conn.execute(
                    "UPDATE planning_assets SET status='stale', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (c["id"],))
            conn.commit()
            print(f"\n精细模式已标记 {len(stale)} 个资产为 stale（neutral {len(classified) - len(stale)} 个不误伤）。")
        conn.close()
        return

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
