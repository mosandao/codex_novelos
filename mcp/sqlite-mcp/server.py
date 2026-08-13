"""极薄 SQLite MCP Server。

暴露一个 ``execute_sql`` 工具，直接对 NovelOS 数据库执行 SQL。
替代 NovelOS MCP 的 89 个领域工具——main agent / sub agent 用 SQL
直接读写核心业务表。

启动方式（.codex/config.toml）::

    [mcp_servers.sqlite]
    command = ".venv/bin/python"
    args = ["mcp/sqlite-mcp/server.py", "--db-path", "data/novelos-v2.db"]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("novelos-sqlite")

_DB_PATH: str = ""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    """把 BLOB 列（bytes）解码为 UTF-8 字符串，方便 JSON 序列化。"""
    return {k: v.decode("utf-8") if isinstance(v, bytes) else v for k, v in row.items()}


@mcp.tool()
def execute_sql(
    sql: str,
    params: list[Any] | None = None,
) -> str:
    """在 NovelOS 数据库上执行 SQL。

    * SELECT / PRAGMA → 返回 ``{"rows": [...], "count": N}``
    * INSERT / UPDATE / DELETE → 返回 ``{"rowcount": N}``
    * 错误 → 返回 ``{"error": "..."}``（不抛异常，让调用方判断）

    BLOB 列（如 resources.content）自动解码为 UTF-8 字符串返回。

    写 resource 时用 ``CAST(? AS BLOB)`` 确保 BLOB 存储::

        INSERT INTO resources (id, media_type, content, content_hash)
        VALUES (?, 'text/markdown', CAST(? AS BLOB), ?)
    """
    conn = _connect()
    try:
        cur = conn.execute(sql, params or [])
        if cur.description is not None:
            rows = [_decode_row(dict(r)) for r in cur.fetchall()]
            conn.commit()
            return json.dumps({"rows": rows, "count": len(rows)}, ensure_ascii=False)
        conn.commit()
        return json.dumps({"rowcount": cur.rowcount}, ensure_ascii=False)
    except Exception as exc:
        conn.rollback()
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    finally:
        conn.close()


def main() -> None:
    global _DB_PATH
    parser = argparse.ArgumentParser(description="NovelOS SQLite MCP Server")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("NOVELOS_DB_PATH", "data/novelos-v2.db"),
        help="SQLite database path (default: data/novelos-v2.db)",
    )
    args = parser.parse_args()
    _DB_PATH = args.db_path
    mcp.run()


if __name__ == "__main__":
    main()
