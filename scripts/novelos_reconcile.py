#!/usr/bin/env python
"""多原型确定性融合的 CLI 包装。

复用 NovelOS MCP 的 reconcile_project_wizard_archetypes。
不调 LLM（单原型路径）/ 传入预融合结果（多原型路径）。

用法::

    # 单原型：确定性打分
    python scripts/novelos_reconcile.py \
        --archetypes selected.json \
        --setup setup.json \
        --display-name "测试作者"

    # 多原型（≥2）：传入 Agent 融合结果
    python scripts/novelos_reconcile.py \
        --archetypes selected.json \
        --setup setup.json \
        --display-name "测试作者" \
        --fused-parent-version-id "creator-profile-version:xxx:1" \
        --fused-signature fused_signature.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "novelos" / "src"))

from novelos_mcp.service import NovelOSService  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="NovelOS 多原型确定性融合")
    parser.add_argument("--archetypes", required=True, help="selected_archetypes JSON 文件")
    parser.add_argument("--setup", required=True, help="project_setup JSON 文件")
    parser.add_argument("--display-name", required=True, help="融合后的展示名")
    parser.add_argument("--fused-parent-version-id", help="多原型路径：Agent 判定的 parent version ID")
    parser.add_argument("--fused-signature", help="多原型路径：完整融合签名 JSON 文件")
    parser.add_argument("--db", default="data/novelos-v2.db", help="数据库路径")
    args = parser.parse_args()

    archetypes = json.loads(Path(args.archetypes).read_text())
    setup = json.loads(Path(args.setup).read_text())

    fused_parent = args.fused_parent_version_id
    fused_sig = None
    if args.fused_signature:
        fused_sig = json.loads(Path(args.fused_signature).read_text())

    # NovelOSService 需要 catalog_path 和 seed_db；用默认值
    catalog_path = Path(__file__).resolve().parent.parent / "catalog"
    service = NovelOSService(
        database_path=args.db,
        catalog_path=str(catalog_path),
        agent_contract_path=str(Path(__file__).resolve().parent.parent / "config" / "agents.yaml"),
    )

    result = service.reconcile_project_wizard_archetypes(
        selected_archetypes=archetypes,
        project_setup=setup,
        display_name=args.display_name,
        fused_parent_version_id=fused_parent,
        fused_signature=fused_sig,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
