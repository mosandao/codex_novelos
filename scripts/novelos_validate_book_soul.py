#!/usr/bin/env python
"""校验 book_soul JSON 是否符合 schema。

用 NovelOS MCP 的 CreativeContractStore 做确定性校验。
不调 LLM。

用法::

    python scripts/novelos_validate_book_soul.py book_soul.json
    cat book_soul.json | python scripts/novelos_validate_book_soul.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 复用 NovelOS MCP 的校验逻辑（不复制代码）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp" / "novelos" / "src"))

try:
    from novelos_mcp.creative_contracts import CreativeContractStore

    _SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "schemas" / "book-soul.schema.json"

    def validate(book_soul: dict) -> list[str]:
        """返回错误列表，空列表表示通过。"""
        store = CreativeContractStore(_SCHEMA_PATH.parent)
        try:
            store.validate_book_soul(book_soul)
            return []
        except Exception as exc:
            return [str(exc)]

except ImportError:
    # 如果 novelos_mcp 不可用，回退到直接 jsonschema 校验
    import jsonschema

    _SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "schemas" / "book-soul.schema.json"

    def validate(book_soul: dict) -> list[str]:
        schema = json.loads(_SCHEMA_PATH.read_text())
        validator = jsonschema.Draft202012Validator(schema)
        return [e.message for e in validator.iter_errors(book_soul)]


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 book_soul JSON")
    parser.add_argument("file", nargs="?", help="book_soul JSON 文件路径（不给则从 stdin 读）")
    args = parser.parse_args()

    if args.file:
        data = json.loads(Path(args.file).read_text())
    else:
        data = json.load(sys.stdin)

    errors = validate(data)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("PASS: book_soul 校验通过")
        # 输出 schema_version 供确认
        print(f"schema_version: {data.get('schema_version', 'missing')}")


if __name__ == "__main__":
    main()
