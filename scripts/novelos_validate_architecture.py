#!/usr/bin/env python
"""校验 architecture 资产 metadata（结构化机制清单）是否符合 schema 并做语义校验。

用 jsonschema + config/schemas/architecture-metadata.schema.json 做确定性校验，不调 LLM。
语义校验（schema 之外的可判定规则）：

- 血缘双源覆盖：机制 sources 全体至少一条 direction_field 与一条 persona_part
  （只贴 direction 字段名或只贴 persona 标签 = 单源血缘，贴标签式消费无抓手）。
- 油耗×档位（若给定 --scale）：双引擎 escalation_levels 对照档位下限——
  短篇 ≥2 / 中篇 ≥3 / 长篇 ≥3 / 超长篇 ≥5（与 book_soul cadence 数字门同源对齐）。
- 主线密度一致性：tier 与 beats_per_volume 匹配（高 ≥1 / 中 0.5-1 / 低 <0.5）。
- 空窗上限×档位（若给定 --scale）：gap_limit_volumes 不得超档位上限——
  短篇 1 / 中篇 2 / 长篇 3 / 超长篇 4（柯南式低密度合法，但空窗随规模受限）。
- 单元弧粒度：min_chapters ≤ max_chapters。

用法::

    python scripts/novelos_validate_architecture.py metadata.json [--scale "长篇（100-300万字）"]
    cat metadata.json | python scripts/novelos_validate_architecture.py --scale 中篇
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "config" / "schemas" / "architecture-metadata.schema.json"

# scale 档位前缀 → (油耗分级下限, 主线空窗上限卷数)；与 story-direction 规模表同源对齐
_SCALE_ENGINE_RULES: dict[str, tuple[int, int]] = {
    "短篇": (2, 1),
    "中篇": (3, 2),
    "长篇": (3, 3),
    "超长篇": (5, 4),
}

# 主线密度 tier → (beats_per_volume 下限, 上限)；低密度上限开区间用 strict=False 表达
_TIER_BEATS_RULES: dict[str, tuple[float, float]] = {
    "高": (1.0, 6.0),
    "中": (0.5, 1.0),
    "低": (0.0, 0.5),
}


def _match_scale(scale: str) -> str | None:
    for prefix in _SCALE_ENGINE_RULES:
        if scale.startswith(prefix):
            return prefix
    return None


def validate(metadata: dict, scale: str | None = None) -> list[str]:
    """返回错误列表，空列表表示通过。"""
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors = [e.message for e in validator.iter_errors(metadata)]

    mechanisms = metadata.get("mechanisms", [])
    source_types = {s["source_type"] for m in mechanisms for s in m.get("sources", [])}
    if mechanisms and "direction_field" not in source_types:
        errors.append("机制 sources 无 direction_field 条目——上游翻译血缘缺失")
    if mechanisms and "persona_part" not in source_types:
        errors.append("机制 sources 无 persona_part 条目——persona 消费是声明而非可核验血缘（目光/盲区/库存任一部件均可）")

    unit_arc = metadata.get("unit_arc")
    if unit_arc and unit_arc.get("min_chapters", 0) > unit_arc.get("max_chapters", 0):
        errors.append(f"unit_arc 粒度倒置：min {unit_arc['min_chapters']} > max {unit_arc['max_chapters']}")

    density = metadata.get("mainline_density")
    if density:
        tier, beats = density.get("tier"), density.get("beats_per_volume")
        if tier in _TIER_BEATS_RULES and isinstance(beats, (int, float)):
            low, high = _TIER_BEATS_RULES[tier]
            if not (low <= beats < high) and not (tier == "高" and beats == high):
                errors.append(
                    f"mainline_density.tier={tier} 与 beats_per_volume={beats} 失配"
                    f"（{tier} 档要求 {'≥1' if tier == '高' else f'[{low}, {high})'}）"
                )
        if scale:
            prefix = _match_scale(scale)
            if prefix is None:
                errors.append(f"--scale 不认识的档位: {scale!r}（须以 短篇/中篇/长篇/超长篇 开头）")
            else:
                gap_cap = _SCALE_ENGINE_RULES[prefix][1]
                gap = density.get("gap_limit_volumes")
                if isinstance(gap, (int, float)) and gap > gap_cap:
                    errors.append(
                        f"mainline_density.gap_limit_volumes={gap} 超出 {prefix} 档空窗上限 {gap_cap} 卷"
                        "——低密度主线合法但空窗随规模受限（柯南式爆发点设计见方法论）"
                    )

    engines = metadata.get("engines")
    if engines and scale:
        prefix = _match_scale(scale)
        if prefix is None:
            errors.append(f"--scale 不认识的档位: {scale!r}（须以 短篇/中篇/长篇/超长篇 开头）")
        else:
            floor = _SCALE_ENGINE_RULES[prefix][0]
            for engine in ("production", "integrator"):
                spec = engines.get(engine)
                if isinstance(spec, dict):
                    levels = spec.get("escalation_levels")
                    if isinstance(levels, int) and levels < floor:
                        errors.append(
                            f"engines.{engine}.escalation_levels={levels} 低于 {prefix} 档下限 {floor}"
                            "——油耗数字门与 story-direction cadence 规则同源"
                        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 architecture metadata JSON")
    parser.add_argument("file", nargs="?", help="architecture metadata JSON 文件路径（不给则从 stdin 读）")
    parser.add_argument("--scale", help="项目 setup.scale 档位（激活油耗/空窗数字门）")
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
    print("PASS: architecture metadata 校验通过")
    print(f"mechanisms: {len(data.get('mechanisms', []))} 条（耦合规格齐）")
    density = data.get("mainline_density", {})
    print(f"mainline_density: {density.get('tier')} 档，beats/卷 {density.get('beats_per_volume')}，"
          f"空窗上限 {density.get('gap_limit_volumes')} 卷")
    unit_arc = data.get("unit_arc", {})
    print(f"unit_arc: {unit_arc.get('min_chapters')}-{unit_arc.get('max_chapters')} 章")
    engines = data.get("engines", {})
    print(f"engines: production 油耗 {engines.get('production', {}).get('escalation_levels')} 级 / "
          f"integrator 油耗 {engines.get('integrator', {}).get('escalation_levels')} 级")


if __name__ == "__main__":
    main()
