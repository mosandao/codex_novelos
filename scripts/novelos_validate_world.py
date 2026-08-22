#!/usr/bin/env python
"""世界契约结构化出口校验：world-metadata schema + 机器门。

校验 `world_contract` 候选的 metadata（schema 见 config/schemas/world-metadata.schema.json）：

1. schema 结构（seats / lexicon / dimension_costs / decision_points）；
2. 岗位重名（同名席位 = 设位混乱）；
3. 代价两轴机器门：
   - 压制型必带 release（schema 已拦，此处复核给出中文报错）；
   - bearer=protagonist_permanent 必带 book_soul_ref（主角永久代价不在默认菜单，
     与 strategy costs 的 declared_in_book_soul 门同构——本阶段不得新增主角永久代价）；
   - 不可逆档必须声明 threshold（反噬到第几层回不去）；
4. 席位处置枚举合法。

用法::

    python scripts/novelos_validate_world.py metadata.json

退出码：0 通过 / 1 缺陷。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config/schemas/world-metadata.schema.json"

REVERSIBILITY = ("可逆", "压制", "不可逆")
DISPOSITIONS = ("待契约认领", "待卷级班底", "显式虚位")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(metadata: dict) -> list[str]:
    errors: list[str] = []

    try:
        import jsonschema
    except ImportError:
        print("缺少 jsonschema（.venv/bin/python 运行或 pip install jsonschema）", file=sys.stderr)
        sys.exit(2)

    schema = _load(SCHEMA_PATH)
    try:
        jsonschema.validate(metadata, schema)
    except jsonschema.ValidationError as exc:
        for err in [exc] + list(exc.context or []):
            path = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"schema[{path}]: {err.message}")
        return errors

    seats = metadata.get("seats", [])
    names = [s.get("name", "") for s in seats]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        errors.append(f"岗位重名: {'、'.join(sorted(dup))}——同名席位使 seat_ref 回指歧义")
    for i, s in enumerate(seats):
        d = s.get("disposition")
        if d is not None and d not in DISPOSITIONS:
            errors.append(f"seats[{i}].disposition 非法 {d!r}（{DISPOSITIONS}）")

    for i, c in enumerate(metadata.get("dimension_costs", [])):
        rev = c.get("reversibility")
        if rev == "压制" and not (c.get("release") or "").strip():
            errors.append(f"dimension_costs[{i}]（{c.get('dimension')}）压制型代价缺解除通道 release"
                          "——封印/禁制类机制无解除通道即死设定")
        if rev == "不可逆" and not (c.get("threshold") or "").strip():
            errors.append(f"dimension_costs[{i}]（{c.get('dimension')}）不可逆档缺阈值 threshold"
                          "——回不去的边界在哪必须可指认")
        if c.get("bearer") == "protagonist_permanent" and not (c.get("book_soul_ref") or "").strip():
            errors.append(f"dimension_costs[{i}]（{c.get('dimension')}）主角永久代价缺 book_soul_ref"
                          "——世界层不得新增主角永久代价，只许回指 strategy 已声明的条目")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="world_contract metadata 校验（schema + 代价两轴机器门）")
    parser.add_argument("metadata", type=Path, help="候选 metadata JSON 路径")
    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"ERROR: 文件不存在: {args.metadata}", file=sys.stderr)
        sys.exit(2)

    metadata = _load(args.metadata)
    errors = validate(metadata)

    if errors:
        print(f"FAIL（{len(errors)} 处缺陷）:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    seats = len(metadata.get("seats", []))
    costs = len(metadata.get("dimension_costs", []))
    print(f"PASS: world-metadata 结构合法——席位 {seats} 个、代价维度 {costs} 个、"
          f"语域四件套齐、决策点 {len(metadata.get('decision_points', []))} 个。")


if __name__ == "__main__":
    main()
