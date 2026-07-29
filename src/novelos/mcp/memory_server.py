from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from novelos.mcp.memory import MemoryMCPService


def create_server(database_path: str | Path) -> Any:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP support is not installed. Run: python3 -m pip install -e '.[mcp]'"
        ) from exc

    service = MemoryMCPService(database_path)
    service.initialize()
    server = FastMCP("novelos-memory")

    server.tool()(service.latest_chapters)
    server.tool(name="search_memory")(service.search_memory)
    server.tool()(service.list_entities)
    server.tool()(service.save_chapter)
    server.tool()(service.upsert_entity)
    server.tool()(service.add_memory)
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NovelOS Memory MCP server")
    parser.add_argument(
        "--database",
        default=os.environ.get("NOVELOS_DB_PATH", "data/novelos.db"),
    )
    args = parser.parse_args()
    create_server(args.database).run(transport="stdio")


if __name__ == "__main__":
    main()

