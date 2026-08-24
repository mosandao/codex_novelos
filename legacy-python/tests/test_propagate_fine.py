from __future__ import annotations

import sqlite3
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.novelos_propagate_stale import _classify_fine


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE planning_assets (
        id TEXT PRIMARY KEY, project_id TEXT, asset_type TEXT, scope_ref TEXT,
        revision INTEGER, status TEXT, content_resource_id TEXT, metadata_json TEXT);
    CREATE TABLE planning_asset_dependencies (
        asset_id TEXT, upstream_asset_id TEXT, upstream_version INTEGER);
    CREATE TABLE resources (id TEXT PRIMARY KEY, content BLOB, content_hash TEXT);
    """)
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    # 上游 direction：rev1（旧内容）+ rev2（新内容）+ rev3（与 rev2 同 hash——纯元数据变更）
    conn.executemany("INSERT INTO resources VALUES (?, CAST(? AS BLOB), ?)", [
        ("res:d1", "# v1", "sha256:" + "1" * 64),
        ("res:d2", "# v2 changed", "sha256:" + "2" * 64),
        ("res:d3", "# v2 changed", "sha256:" + "2" * 64),
    ])
    conn.executemany("INSERT INTO planning_assets VALUES (?,?,?,?,?,?,?,?)", [
        ("pa:d1", "p", "direction", "book", 1, "superseded", "res:d1", "{}"),
        ("pa:d2", "p", "direction", "book", 2, "superseded", "res:d2", "{}"),
        ("pa:d3", "p", "direction", "book", 3, "locked", "res:d3", "{}"),
        # 下游 A：依赖 rev1（内容已变）→ stale
        ("pa:a", "p", "architecture", "book", 1, "locked", "res:d2", "{}"),
        # 下游 B：依赖 rev2（hash 与当前 rev3 相同）→ neutral
        ("pa:b", "p", "architecture", "book2", 1, "locked", "res:d2", "{}"),
        # 下游 C：依赖 rev3（已对齐）→ neutral
        ("pa:c", "p", "architecture", "book3", 1, "locked", "res:d2", "{}"),
    ])
    conn.executemany("INSERT INTO planning_asset_dependencies VALUES (?,?,?)", [
        ("pa:a", "pa:d1", 1),
        ("pa:b", "pa:d1", 2),
        ("pa:c", "pa:d1", 3),
    ])


class FineClassification(unittest.TestCase):
    """P5：依赖边版本 + content_hash 双重比对——内容未变不误伤。"""

    def test_three_way_classification(self):
        conn = _make_db()
        _seed(conn)
        result = {c["id"]: c for c in _classify_fine(conn, "pa:d1")}
        self.assertEqual(result["pa:a"]["verdict"], "stale")      # rev1 → 内容已变
        self.assertEqual(result["pa:b"]["verdict"], "neutral")    # rev2 hash == rev3 hash
        self.assertEqual(result["pa:c"]["verdict"], "neutral")    # 已对齐 rev3
        self.assertIn("content_hash 相同", result["pa:b"]["reason"])

    def test_fine_marks_not_more_than_coarse(self):
        conn = _make_db()
        _seed(conn)
        fine_stale = {c["id"] for c in _classify_fine(conn, "pa:d1") if c["verdict"] == "stale"}
        from scripts.novelos_propagate_stale import _collect_downstream
        coarse = {d["id"] for d in _collect_downstream(conn, "pa:d1")}
        self.assertTrue(fine_stale <= coarse)  # 细模式标记数 ≤ 粗模式


if __name__ == "__main__":
    unittest.main()
