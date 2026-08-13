#!/usr/bin/env python
"""项目投影渲染的 CLI 包装。

把权威数据库内容渲染为 Markdown 文件目录（novels/<项目目录>/）。
复用 NovelOS MCP 的 ProjectionEngine。

用法::

    python scripts/novelos_render_projection.py --project project:xxx
    python scripts/novelos_render_projection.py --project project:xxx --output novels/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "novelos" / "src"))

from novelos_mcp.service import NovelOSService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="渲染 NovelOS 项目投影")
    parser.add_argument("--project", required=True, help="项目 ID (如 project:xxx)")
    parser.add_argument("--output", default="novels", help="输出根目录 (default: novels)")
    parser.add_argument("--db", default="data/novelos-v2.db", help="数据库路径")
    args = parser.parse_args()

    catalog_path = Path(__file__).resolve().parent.parent / "catalog"
    service = NovelOSService(
        database_path=args.db,
        catalog_path=str(catalog_path),
        agent_contract_path=str(Path(__file__).resolve().parent.parent / "config" / "agents.yaml"),
    )

    result = service.render_project_projection(args.project, output_root=args.output)
    print(f"渲染完成: {result.get('output_directory', '?')}")
    print(f"文件数: {result.get('rendered_file_count', 0)}")


if __name__ == "__main__":
    main()
