#!/usr/bin/env python
"""导出作者内核名册镜像 ui/kernel-roster.js（向导「选择已有内核」的数据源）。

向导是 file:// 协议静态页，不能查库；内核名册只能以 <script> 镜像注入
（与 project-wizard-data.js 同机制）。本脚本从 data/novelos-v2.db 读取
ownership='author_kernel' 且 status='active' 的内核（每 profile 取最高
revision 版本），生成 `window.NOVELOS_KERNEL_ROSTER = [...]`。

镜像只是便利层：权威校验在 novelos_create_project.py 入口（库内反查
kernel_version_id + subject_hash），镜像过期只会导致选项陈旧，不会放进
非法内核。每次建核/修订内核后重跑本脚本刷新镜像。

用法::

    python scripts/novelos_export_kernel_roster.py            # 写入 ui/kernel-roster.js
    python scripts/novelos_export_kernel_roster.py --check    # 校验镜像与库一致
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "novelos-v2.db"
ROSTER_FILE = REPO_ROOT / "ui" / "kernel-roster.js"

HEADER = "// 由 scripts/novelos_export_kernel_roster.py 生成——请勿手改；建核/修订内核后重跑刷新。\n"


def build_roster(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT v.id AS kernel_version_id, v.subject_hash, v.revision,
               p.display_name, CAST(r.content AS TEXT) AS kernel_json
        FROM creator_profile_versions v
        JOIN creator_profiles p ON p.id = v.profile_id
        JOIN resources r ON r.id = v.content_resource_id
        WHERE p.ownership = 'author_kernel' AND p.status = 'active'
          AND v.revision = (
              SELECT MAX(v2.revision) FROM creator_profile_versions v2
              WHERE v2.profile_id = v.profile_id)
        ORDER BY p.created_at DESC
        """
    ).fetchall()
    roster = []
    for row in rows:
        identity = json.loads(row["kernel_json"]).get("identity", {})
        roster.append({
            "kernel_version_id": row["kernel_version_id"],
            "subject_hash": row["subject_hash"],
            "revision": row["revision"],
            "display_name": row["display_name"],
            "core_questions": list(identity.get("core_questions", []))[:3],
        })
    return roster


def render(roster: list[dict]) -> str:
    return (HEADER + "window.NOVELOS_KERNEL_ROSTER = "
            + json.dumps(roster, ensure_ascii=False, indent=2) + ";\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--check", action="store_true", help="校验镜像与库一致，不一致报错退出")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        roster = build_roster(conn)
    finally:
        conn.close()
    content = render(roster)

    if args.check:
        current = ROSTER_FILE.read_text(encoding="utf-8") if ROSTER_FILE.exists() else ""
        if current != content:
            print("kernel-roster.js 与库不一致——重跑 scripts/novelos_export_kernel_roster.py 刷新")
            return 1
        print(f"kernel-roster.js 与库一致（{len(roster)} 个内核）。")
        return 0

    ROSTER_FILE.write_text(content, encoding="utf-8")
    print(f"已写入 {ROSTER_FILE}（{len(roster)} 个内核）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
