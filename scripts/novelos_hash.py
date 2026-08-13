#!/usr/bin/env python
"""计算 NovelOS content_hash（sha256:前缀）。

用法::

    echo -n "内容" | python scripts/novelos_hash.py
    python scripts/novelos_hash.py < file.txt
    python scripts/novelos_hash.py --text "直接传文本"

输出格式：sha256:<64 hex>（71 字符，与数据库 CHECK 约束一致）。
"""

from __future__ import annotations

import argparse
import hashlib
import sys


def content_hash(content: str | bytes) -> str:
    payload = content.encode("utf-8") if isinstance(content, str) else content
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def main() -> None:
    parser = argparse.ArgumentParser(description="计算 NovelOS content_hash")
    parser.add_argument("--text", help="直接传入文本（不从 stdin 读）")
    args = parser.parse_args()

    if args.text is not None:
        print(content_hash(args.text))
    else:
        data = sys.stdin.buffer.read()
        print(content_hash(data))


if __name__ == "__main__":
    main()
