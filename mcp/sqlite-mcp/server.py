"""极薄 SQLite MCP Server（纯标准库实现）。

通过 JSON-RPC 2.0 over stdio 暴露一个 ``execute_sql`` 工具，直接对 NovelOS
数据库执行 SQL。不依赖 FastMCP / pydantic / mcp SDK，因此无需 pip 安装即可在
DSH / Codex 中作为 stdio MCP server 启动。

协议子集：initialize / notifications/initialized / tools/list / tools/call / ping。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "novelos-sqlite"
SERVER_VERSION = "1.0.0"

_DB_PATH: str = "data/novelos-v2.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    """把 BLOB 列（bytes）解码为 UTF-8 字符串，方便 JSON 序列化。"""
    return {k: v.decode("utf-8") if isinstance(v, bytes) else v for k, v in row.items()}


def _execute_sql(sql: str, params: list[Any] | None = None) -> str:
    """执行 SQL，返回与旧 FastMCP 实现一致的 JSON 文本。

    * SELECT / PRAGMA -> {"rows": [...], "count": N}
    * INSERT / UPDATE / DELETE -> {"rowcount": N}
    * 错误 -> {"error": "..."}（不抛异常，让调用方判断）
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
    except Exception as exc:  # noqa: BLE001 - 返回 JSON 错误而非崩溃
        conn.rollback()
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
    finally:
        conn.close()


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "name": "execute_sql",
            "description": (
                "在 NovelOS 数据库上执行 SQL。SELECT/PRAGMA 返回 "
                '{"rows": [...], "count": N}；INSERT/UPDATE/DELETE 返回 '
                '{"rowcount": N}；错误返回 {"error": "..."}。'
                "BLOB 列自动按 UTF-8 解码。写 resources.content 请用 CAST(? AS BLOB)。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "要执行的 SQL 语句"},
                    "params": {
                        "type": "array",
                        "items": {},
                        "description": "可选绑定参数（列表）",
                    },
                },
                "required": ["sql"],
            },
        }
    ]


def _write_message(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _handle_request(request: dict[str, Any]) -> None:
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params") or {}

    if method == "initialize":
        requested_version = params.get("protocolVersion") or PROTOCOL_VERSION
        _write_message(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": requested_version,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                },
            }
        )
        return

    if method == "ping":
        _write_message({"jsonrpc": "2.0", "id": req_id, "result": {}})
        return

    if method == "tools/list":
        _write_message(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": _tool_definitions()},
            }
        )
        return

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name != "execute_sql":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {"error": f"unknown tool: {name}"}, ensure_ascii=False
                                ),
                            }
                        ],
                        "isError": True,
                    },
                }
            )
            return
        sql = arguments.get("sql", "")
        raw_params = arguments.get("params")
        params_list: list[Any] | None = raw_params if isinstance(raw_params, list) else None
        text = _execute_sql(sql, params_list)
        _write_message(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                },
            }
        )
        return

    # 未知方法：有 id 才回 JSON-RPC error；notification 直接忽略。
    if req_id is not None:
        _write_message(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
        )


def main() -> None:
    global _DB_PATH
    parser = argparse.ArgumentParser(description="NovelOS SQLite MCP Server (stdlib)")
    parser.add_argument(
        "--db-path",
        default=os.environ.get("NOVELOS_DB_PATH", "data/novelos-v2.db"),
        help="SQLite database path (default: data/novelos-v2.db)",
    )
    args = parser.parse_args()
    _DB_PATH = args.db_path

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(message.get("method", "")).startswith("notifications/"):
            continue
        _handle_request(message)


if __name__ == "__main__":
    main()