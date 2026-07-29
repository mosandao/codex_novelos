from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("/Users/yiyi/github/novelos/backend/src/infrastructure/sqlite/seed.db")
DEFAULT_OUTPUT = ROOT / "tasks" / "migration" / "seed_source_inventory.json"
PRODUCTION_SOURCE = ROOT / "mcp" / "novelos" / "resources" / "seed.db"
PRODUCTION_OUTPUT = ROOT / "mcp" / "novelos" / "resources" / "seed-inventory.json"
SOURCE_COMMIT = "902d7e62f55bc8bc2862e2b9574b5ee2f5f33403"
SOURCE_PATH = "backend/src/infrastructure/sqlite/seed.db"
MCP_SOURCE = ROOT / "mcp" / "novelos" / "src"
if str(MCP_SOURCE) not in sys.path:
    sys.path.insert(0, str(MCP_SOURCE))

from novelos_mcp.seed_inventory import build_seed_inventory  # noqa: E402

def render(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="构建 seed.db 只读来源完整性清单")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = args.source or (PRODUCTION_SOURCE if args.production else DEFAULT_SOURCE)
    output = args.output or (PRODUCTION_OUTPUT if args.production else DEFAULT_OUTPUT)
    provenance_path = SOURCE_PATH if args.production else None
    content = render(build_seed_inventory(source, SOURCE_COMMIT, provenance_path))
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != content:
            raise SystemExit(f"seed inventory 不是最新结果：{output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
