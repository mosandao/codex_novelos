#!/usr/bin/env python
"""校验 strategy 资产 metadata（结构化阶段骨架）是否符合 schema 并做语义校验。

用 jsonschema + config/schemas/strategy-metadata.schema.json 做确定性校验，不调 LLM。
语义校验（schema 之外的可判定规则）：

- 上游消费覆盖：consumption 七行枚举齐全（缺行 = 上游产出静默蒸发）。
- 阶段数×档位（若给定 --scale）：短篇 1-2 / 中篇 2-4 / 长篇 3-8 / 超长篇 5-12
  （区间中位 25-40 万字/阶段，与旧「≥20 万字」启发式同源；30-40 万带宽不再无解）。
- 存债连续上限：连续 payoff=debt 阶段 ≤ debt_streak_limit；全书至少一个
  heavy/light 阶段（只种不收 = blocking 的机器形态）。
- 中盘续命：阶段数 ≥3 必须有 midpoint_renewal（中盘塌陷是长篇头部弃书原因）。
- 终局纪律（terminal_mode=closed）：terminal 类承诺条数 ≤ closure_budget
  （超限 = 赶工烂尾形态）；末阶段 word_range.min ≥ terminal.word_floor（防压缩）。
- 换挡位置合法：midpoint_renewal.stage 落在阶段表内。

用法::

    python scripts/novelos_validate_strategy.py metadata.json [--scale "长篇（100-300万字）"]
    cat metadata.json | python scripts/novelos_validate_strategy.py --scale 中篇
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "schemas" / "strategy-metadata.schema.json"

# scale 档位前缀 → 阶段数区间；与 story-direction 规模表、book_soul cadence 门同源对齐
_SCALE_STAGE_RULES: dict[str, tuple[int, int]] = {
    "短篇": (1, 2),
    "中篇": (2, 4),
    "长篇": (3, 8),
    "超长篇": (5, 12),
}

_CONSUMPTION_OUTPUTS = {
    "rhythm_table", "reveal_ladder", "promise_cadence", "power_escalation",
    "spiral_rotation", "engine_config", "upstream_receipts",
}


def _match_scale(scale: str) -> str | None:
    for prefix in _SCALE_STAGE_RULES:
        if scale.startswith(prefix):
            return prefix
    return None


def validate(metadata: dict, scale: str | None = None) -> list[str]:
    """返回错误列表，空列表表示通过。"""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(metadata)]

    outputs = {row.get("output") for row in metadata.get("consumption", [])}
    missing = _CONSUMPTION_OUTPUTS - outputs
    if missing:
        errors.append(f"上游消费表缺行：{sorted(missing)}——上游产出在阶段边界静默蒸发")

    stages = metadata.get("stages", [])
    if scale:
        prefix = _match_scale(scale)
        if prefix is None:
            errors.append(f"--scale 不认识的档位: {scale!r}（须以 短篇/中篇/长篇/超长篇 开头）")
        else:
            low, high = _SCALE_STAGE_RULES[prefix]
            if not (low <= len(stages) <= high):
                errors.append(
                    f"阶段数 {len(stages)} 超出 {prefix} 档区间 [{low}, {high}]"
                    "——区间外须论证豁免（空转/无曲线两端失败模式由区间拦截）"
                )

    if stages:
        limit = metadata.get("pairing_cycle", {}).get("debt_streak_limit", 2)
        streak = max_streak = 0
        for st in stages:
            if st.get("payoff") == "debt":
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak > limit:
            errors.append(
                f"连续纯存债阶段 {max_streak} 段超上限 {limit}——存债阶段合法但须有 progress 并按周期爆发兑付"
            )
        if not any(st.get("payoff") in ("heavy", "light") for st in stages):
            errors.append("全书无任何 heavy/light 阶段——只种不收（至少一个兑付爆发阶段）")

    if len(stages) >= 3 and "midpoint_renewal" not in metadata:
        errors.append("阶段数 ≥3 而无 midpoint_renewal——中盘塌陷（中期疲软）是长篇头部弃书原因，中段必须有换挡事件")

    renewal = metadata.get("midpoint_renewal")
    if renewal and stages and not (1 <= renewal.get("stage", 0) <= len(stages)):
        errors.append(f"midpoint_renewal.stage={renewal.get('stage')} 不在阶段表内（1-{len(stages)}）")

    if metadata.get("terminal_mode") == "closed":
        terminal = metadata.get("terminal", {})
        terminal_claims = sum(
            1 for c in metadata.get("claim_ledger", []) if c.get("disposition") == "terminal")
        budget = terminal.get("closure_budget")
        if isinstance(budget, int) and terminal_claims > budget:
            errors.append(
                f"终局待收承诺 {terminal_claims} 条超收束预算 {budget}——鞭尸式赶工烂尾形态，剩余应转 silence 或中途收"
            )
        floor = terminal.get("word_floor")
        last_min = stages[-1].get("word_range", {}).get("min") if stages else None
        if isinstance(floor, int) and isinstance(last_min, int) and last_min < floor:
            errors.append(
                f"终局阶段字数下限 {last_min} 万 < 声明下限 {floor} 万——终局压缩是赶工烂尾的典型形态"
            )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 strategy metadata JSON")
    parser.add_argument("file", nargs="?", help="strategy metadata JSON 文件路径（不给则从 stdin 读）")
    parser.add_argument("--scale", help="项目 setup.scale 档位（激活阶段数×档位数字门）")
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
    print("PASS: strategy metadata 校验通过")
    stages = data.get("stages", [])
    print(f"stages: {len(stages)} 个（payoff 分布 "
          + "/".join(st.get("payoff", "?") for st in stages) + "）")
    print(f"terminal_mode: {data.get('terminal_mode')}"
          + (f"，收束预算 {data.get('terminal', {}).get('closure_budget')} 条 / 字数下限 "
             f"{data.get('terminal', {}).get('word_floor')} 万" if data.get("terminal_mode") == "closed" else ""))
    ledger = data.get("claim_ledger", [])
    print(f"claim_ledger: {len(ledger)} 条"
          f"（midstory {sum(1 for c in ledger if c['disposition'] == 'midstory')}"
          f" / terminal {sum(1 for c in ledger if c['disposition'] == 'terminal')}"
          f" / silence {sum(1 for c in ledger if c['disposition'] == 'silence')}）")


if __name__ == "__main__":
    main()
