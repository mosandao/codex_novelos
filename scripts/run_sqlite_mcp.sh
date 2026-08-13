#!/usr/bin/env bash
# 启动 NovelOS SQLite MCP Server
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python mcp/sqlite-mcp/server.py --db-path data/novelos-v2.db
