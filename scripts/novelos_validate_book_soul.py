#!/usr/bin/env python
"""校验 book_soul JSON 是否符合 schema 并做语义校验。

用 jsonschema + config/schemas/book-soul.schema.json 做确定性校验，不调 LLM。
语义校验（schema 之外的可判定规则）：

- lineage（若提供）：organizing_principle 与 central_contradiction 各至少一条
  映射（允许 variation 变奏条目），血缘核验才有结构化抓手。
- cadence_plan（若提供且给定 --scale）：兑现次数对照档位数字门——
  短篇 1-2 次 / 中篇 ≥3 / 长篇 ≥3 / 超长篇 ≥5，短篇超 2 次报错
  （30 万字短篇铺多层矛盾收不了尾）。

用法::

    python scripts/novelos_validate_book_soul.py book_soul.json [--scale "长篇（100-300万字）"]
    cat book_soul.json | python scripts/novelos_validate_book_soul.py --scale 中篇
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "schemas" / "book-soul.schema.json"

# scale 档位前缀 → (兑现次数下限, 上限)；None 上限 = 不设上限
_SCALE_CADENCE_RULES: dict[str, tuple[int, int | None]] = {
    "短篇": (1, 2),
    "中篇": (3, None),
    "长篇": (3, None),
    "超长篇": (5, None),
}


def _match_scale(scale: str) -> str | None:
    for prefix in _SCALE_CADENCE_RULES:
        if scale.startswith(prefix):
            return prefix
    return None


def validate(book_soul: dict, scale: str | None = None) -> list[str]:
    """返回错误列表，空列表表示通过。"""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(book_soul)]

    lineage = book_soul.get("lineage")
    if lineage:
        fields = {item["field"] for item in lineage}
        for must in ("organizing_principle", "central_contradiction"):
            if must not in fields:
                errors.append(f"lineage 缺 {must} 的映射条目——血缘核验无抓手")

    cadence = book_soul.get("cadence_plan")
    if cadence and scale:
        prefix = _match_scale(scale)
        if prefix is None:
            errors.append(f"--scale 不认识的档位: {scale!r}（须以 短篇/中篇/长篇/超长篇 开头）")
        else:
            low, high = _SCALE_CADENCE_RULES[prefix]
            count = cadence["fulfillment_count"]
            if count < low or (high is not None and count > high):
                bound = f"{low}-{high} 次" if high is not None else f"≥{low} 次"
                errors.append(
                    f"cadence_plan.fulfillment_count={count} 与 {prefix} 档位失配"
                    f"（要求 {bound}）——数字门见 story-direction 规模表"
                )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 book_soul JSON")
    parser.add_argument("file", nargs="?", help="book_soul JSON 文件路径（不给则从 stdin 读）")
    parser.add_argument("--scale", help="项目 setup.scale 档位（激活 cadence_plan 数字门）")
    args = parser.parse_args()

    if args.file:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        data = json.load(sys.stdin)

    errors = validate(data, args.scale)
    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
    else:
        print("PASS: book_soul 校验通过")
        # 输出 schema_version 供确认
        print(f"schema_version: {data.get('schema_version', 'missing')}")
        if "lineage" in data:
            variations = sum(1 for item in data["lineage"] if item.get("variation"))
            print(f"lineage: {len(data['lineage'])} 条映射（变奏 {variations}）")
        if "cadence_plan" in data:
            plan = data["cadence_plan"]
            print(f"cadence_plan: 兑现 {plan['fulfillment_count']} 次，间隔约 {plan['interval_volumes']} 卷")


if __name__ == "__main__":
    main()
