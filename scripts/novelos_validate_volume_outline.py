#!/usr/bin/env python
"""卷纲结构化出口校验：卷号/字数对表/高潮门/线弧双向/单元编排/换图清算/终卷纪律。

校验 `volume_outline` 候选的 metadata（schema 见
config/schemas/volume-outline-metadata.schema.json，T39）：

1. schema 结构（volume_number / word_range / volume_form / lines / climax_positions /
   units / exit_settlement / new_plants / drift / test_alloc / volume_settings）；
2. **卷号连续性**（`--project`）：前置 locked 卷的 volume_number 须为 1..N-1 连续，
   本卷 = N——乱序规划（卷 2 未锁先规划卷 3）在此拦截；
3. **字数对表**（`--story-arc` 或 `--project`）：本卷 word_range 须与 volume_plan
   本卷行有交集（无交集 = error；target 出界 = warn）；
4. **高潮门**：climax_positions 升序且末位 = 1（卷末主高潮）；相邻间距 ×
   word_range.target ≤ 30 万字；target ≥ 20 万时高潮总数 ≥ ceil(target/25万)
   ——短篇退化（scale=短篇 或 target < 20 万）允许仅卷末主高潮；
5. **线弧双向**：跨卷弧线必须带 arc_id（回指存在的弧，且该弧本卷 duty 活跃——
   挂休眠弧 = warn）；映射表本卷活跃弧必须有冲突线承载（职责蒸发 = error）；
   线篇幅占比合计 90-110（越界 warn）；mainline_beats 对架构 beats_per_volume
   ±2（越界 warn）；tier=低 而主线占比 >55% = warn（低密度主线被卷内削平）；
6. **单元编排**：volume_form=单元编排 时 units 必填；非间歇单元主线渗透 ≥1 拍；
   章数窗 min ≤ max；单元窗总量超卷容量 warn；
7. **换图清算**：exit_settlement 的 cut/pre_close 引用台账 line_id 样式时对
   story_arc 台账核验（查无 = warn）；
8. **新种与终卷纪律**：new_plants 行 close_volume XOR exempt、收束卷 ≥ 本卷、
   line_id 不与既有台账冲突；终卷（本卷 = volume_plan 末卷）新种不得溢出终卷
   （error）；terminal_mode=closed 时终卷豁免 = error；
9. **变奏承接**：variation_alloc 本卷行须被 test_alloc 承接（漏承接 = warn），
   test_alloc 不得超出本卷分配行（另造变奏 = warn）；
10. **阶段区间**：stage_span 落在 strategy stages 索引范围内（越界 = error）；
11. **班底预检**（`--project`）：volume_characters 名字未入注册表 = warn
    （锁定后 `--entry` 登记；漏跑检测归 register --audit-entries）。

`--project <id>` 自动解析：setup.scale + locked story_arc/architecture/strategy
metadata + 前置锁定卷号 + 人物注册表名册——显式传参优先。

用法::

    python scripts/novelos_validate_volume_outline.py metadata.json --project project:xxx
    python scripts/novelos_validate_volume_outline.py metadata.json --scale "长篇" \
        --story-arc arc.json --architecture a.json --strategy s.json

退出码：0 通过 / 1 缺陷 / 2 输入错误。WARN 不影响通过（exit 0），逐条打印。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config/schemas/volume-outline-metadata.schema.json"

_ACTIVE_DUTIES = {"推进", "兑现", "收束"}
_SLUG = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
_CLIMAX_GAP_WORDS = 300_000      # 相邻高潮间距上限（字）
_CLIMAX_UNIT_WORDS = 250_000     # 高潮密度基准（字/个）


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(metadata: dict, scale: str | None = None,
             story_arc: dict | None = None, architecture: dict | None = None,
             strategy: dict | None = None,
             prev_volume_numbers: list[int] | None = None,
             registry_names: set[str] | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []

    try:
        import jsonschema
    except ImportError:
        print("缺少 jsonschema（.venv/bin/python 运行或 pip install jsonschema）", file=sys.stderr)
        sys.exit(2)

    try:
        jsonschema.validate(metadata, _load(SCHEMA_PATH))
    except jsonschema.ValidationError as exc:
        for err in [exc] + list(exc.context or []):
            path = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"metadata[{path}]: {err.message}")
        return errors, warns

    vol_no = metadata["volume_number"]
    target = metadata["word_range"]["target"]
    lines = metadata["lines"]

    # --- 卷号连续性（--project 提供前置卷号时）---
    if prev_volume_numbers is not None:
        expect = list(range(1, vol_no))
        if sorted(prev_volume_numbers) != expect:
            errors.append(f"前置锁定卷号 {sorted(prev_volume_numbers)} ≠ 1..{vol_no - 1}"
                          "——乱序规划：前置链按卷号注入，缺卷即错位，先补锁前置卷")
        elif vol_no in prev_volume_numbers:
            errors.append(f"卷 {vol_no} 已存在 locked 记录——这是修订而非新卷，走修订流程")

    arcs = (story_arc or {}).get("arcs") or []
    arc_ids = {a.get("arc_id") for a in arcs} if arcs else set()
    amap = (story_arc or {}).get("arc_volume_map") or []
    plan = (story_arc or {}).get("volume_plan") or []
    ledger = (story_arc or {}).get("plant_payoff_ledger") or []

    # --- 字数对表（story_arc 提供时）---
    if plan:
        row = next((v for v in plan if v.get("index") == vol_no), None)
        if row is None:
            errors.append(f"卷号 {vol_no} 不在 story_arc volume_plan（共 {len(plan)} 卷）"
                          "——卷号以卷计划为权威")
        else:
            pw = row.get("word_range") or {}
            w = metadata["word_range"]
            if pw.get("min") is not None and pw.get("max") is not None:
                if w["max"] < pw["min"] or w["min"] > pw["max"]:
                    errors.append(
                        f"本卷字数 [{w['min']}, {w['max']}] 与 volume_plan 卷 {vol_no} "
                        f"[{pw['min']}, {pw['max']}] 无交集——卷纲不得重切卷计划")
                elif not pw["min"] <= w["target"] <= pw["max"]:
                    warns.append(f"本卷 target {w['target']} 落在 volume_plan 区间外"
                                  "（交集内但偏离计划重心）")

    # --- 高潮门 ---
    positions = metadata["climax_positions"]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        errors.append(f"climax_positions 须严格升序且不重复: {positions}")
    else:
        if positions[-1] != 1:
            errors.append(f"climax_positions 末位 {positions[-1]} ≠ 1——卷末主高潮必须封顶")
        degenerate = target < _CLIMAX_UNIT_WORDS * 0.8 or scale == "短篇"
        pts = [0.0] + [float(p) for p in positions]
        if not degenerate:
            for i in range(1, len(pts)):
                gap_words = (pts[i] - pts[i - 1]) * target
                if gap_words > _CLIMAX_GAP_WORDS:
                    errors.append(
                        f"高潮 {i} 与前一节点间距 {int(gap_words)} 字（> {_CLIMAX_GAP_WORDS}）"
                        "——中段空窗，副高湂数按本卷字数条件化（每 20-30 万字一个）")
            need = math.ceil(target / _CLIMAX_UNIT_WORDS)
            if len(positions) < need:
                errors.append(f"高潮总数 {len(positions)} < {need}"
                              f"（target {target} 字 ÷ {_CLIMAX_UNIT_WORDS} 向上取整，含卷末主高潮）")
        elif len(positions) == 1 and target >= _CLIMAX_UNIT_WORDS:
            warns.append("短篇退化形态：仅卷末主高潮——确认这是刻意的紧凑卷而非漏报副高潮")

    # --- 线弧双向 ---
    for ln in lines:
        if ln["scope"] == "跨卷弧":
            aid = ln.get("arc_id")
            if not aid:
                errors.append(f"冲突线「{ln['name']}」scope=跨卷弧 但无 arc_id——跨卷线必须回指映射表")
            elif arcs and aid not in arc_ids:
                errors.append(f"冲突线「{ln['name']}」引用不存在的 arc_id: {aid}")
            elif amap:
                duty = next((r.get("duty") for r in amap
                             if r.get("arc_id") == aid and r.get("volume") == vol_no), None)
                if duty is None:
                    warns.append(f"冲突线「{ln['name']}」挂弧 {aid}，但映射表卷 {vol_no} 无该弧职责格")
                elif duty not in _ACTIVE_DUTIES:
                    warns.append(f"冲突线「{ln['name']}」挂弧 {aid} 本卷 duty={duty}"
                                 "——蓄势/休眠弧不得反向活跃承载")
        elif not ln.get("note"):
            warns.append(f"自含线「{ln['name']}」无加压/结算点声明——自含线靠独立开合替代弧调度")
    if arcs and amap:
        line_arcs = {ln.get("arc_id") for ln in lines if ln["scope"] == "跨卷弧"}
        for row in amap:
            if row.get("volume") == vol_no and row.get("duty") in _ACTIVE_DUTIES \
                    and row["arc_id"] not in line_arcs:
                errors.append(f"弧 {row['arc_id']} 本卷 duty={row['duty']} 但无冲突线承载——职责蒸发")
    share_sum = sum(ln["share_pct"] for ln in lines)
    if not 90 <= share_sum <= 110:
        warns.append(f"冲突线篇幅占比合计 {share_sum}%（合法窗 90-110）——配比申报失真")
    mainline_lines = [ln for ln in lines if ln.get("mainline")]
    if len(mainline_lines) > 1:
        errors.append(f"mainline 线 {len(mainline_lines)} 条（>1）——主线唯一")
    density = (architecture or {}).get("mainline_density") or {}
    if mainline_lines:
        share = mainline_lines[0]["share_pct"]
        tier = density.get("tier")
        if tier == "低" and share > 55:
            warns.append(f"主线占比 {share}% 而 mainline_density.tier=低——低密度主线被卷内排布削平")
        if tier == "高" and share < 30:
            warns.append(f"主线占比 {share}% 而 mainline_density.tier=高——高密度主线喂不饱")
    beats = metadata.get("mainline_beats")
    if beats is not None and density.get("beats_per_volume") is not None:
        if abs(beats - density["beats_per_volume"]) > 2:
            warns.append(f"mainline_beats {beats} 偏离架构 beats_per_volume "
                         f"{density['beats_per_volume']}（±2 内对表）")

    # --- 单元编排 ---
    if metadata["volume_form"] == "单元编排":
        units = metadata.get("units")
        if not units:
            errors.append("volume_form=单元编排 但缺 units——副本/案件/赛季卷必须有单元编排表")
        else:
            chapter_budget = math.ceil(target / 2500)
            window_sum = 0
            for u in units:
                w = u["chapter_window"]
                if w["min"] > w["max"]:
                    errors.append(f"单元 {u['unit_id']} 章数窗 min>max")
                if not u.get("interlude") and (u.get("mainline_advance") or 0) < 1:
                    errors.append(f"单元 {u['unit_id']} 非间歇但主线渗透 <1 拍"
                                  "——单元剧防散架：每单元至少推一步主线")
                window_sum += w["max"]
            if window_sum > chapter_budget:
                warns.append(f"单元章数窗总量 {window_sum} 超卷容量约 {chapter_budget} 章"
                             f"（target {target} ÷ 2500）——副本篇幅过长是单元剧头号差评")
    elif metadata.get("units"):
        warns.append("volume_form=连续四段 但带 units——改用单元编排形态或删表")

    # --- 换图清算 ---
    exit_set = metadata.get("exit_settlement")
    if exit_set:
        ledger_ids = {r.get("line_id") for r in ledger} if ledger else set()
        for field in ("cut", "pre_close"):
            for ref in exit_set.get(field) or []:
                if _SLUG.match(ref) and ledger_ids and ref not in ledger_ids:
                    warns.append(f"exit_settlement.{field} 引用台账无此 line_id: {ref}"
                                 "——斩断/离图收账须指向真实悬念行")

    # --- 新种与终卷纪律 ---
    seen: set[str] = set()
    for row in metadata.get("new_plants") or []:
        lid = row["line_id"]
        if lid in seen:
            errors.append(f"new_plants line_id 重复: {lid}")
        seen.add(lid)
        has_close, has_exempt = row.get("close_volume") is not None, bool(row.get("exempt"))
        if has_close and has_exempt:
            errors.append(f"新种 {lid} 兼有 close_volume 与 exempt——二选一")
        elif not has_close and not has_exempt:
            errors.append(f"新种 {lid} 既无 close_volume 也无 exempt——只种不收")
        if has_close and row["close_volume"] < vol_no:
            errors.append(f"新种 {lid} 收束卷 {row['close_volume']} 早于本卷 {vol_no}——先收后种")
        if ledger and lid in {r.get("line_id") for r in ledger}:
            errors.append(f"新种 {lid} 与既有台账 line_id 冲突——增量行不得复用旧 id")
    if plan:
        final_vol = max(v.get("index", 0) for v in plan)
        if vol_no == final_vol:
            for row in metadata.get("new_plants") or []:
                if row.get("close_volume") is not None and row["close_volume"] > vol_no:
                    errors.append(f"终卷新种 {row['line_id']} 收束卷 {row['close_volume']} 溢出终卷"
                                  "——终卷纪律：写到这里就该收了")
                if row.get("exempt") and (strategy or {}).get("terminal_mode") == "closed":
                    errors.append(f"终卷新种 {row['line_id']} 豁免而 terminal_mode=closed"
                                  "——闭合终局不留新坑")
            if (strategy or {}).get("terminal_mode") == "open" and \
                    any(r.get("exempt") for r in metadata.get("new_plants") or []):
                warns.append("终卷豁免新种（terminal_mode=open）——确认计入 open 滚动窗口")

    # --- 漂移清单 ---
    for row in metadata.get("drift") or []:
        if arcs and row["arc_id"] not in arc_ids:
            errors.append(f"drift 引用不存在的 arc_id: {row['arc_id']}")

    # --- 变奏承接 ---
    if story_arc:
        alloc_here = {r["test_ref"] for r in (story_arc.get("variation_alloc") or [])
                      if r.get("volume") == vol_no}
        claimed = {r["test_ref"] for r in metadata.get("test_alloc") or []}
        for ref in sorted(alloc_here - claimed):
            warns.append(f"variation_alloc 本卷行 {ref!r} 未被 test_alloc 承接——分配不得静默蒸发")
        for ref in sorted(claimed - alloc_here):
            warns.append(f"test_alloc {ref!r} 超出 variation_alloc 本卷分配——变奏以分配表为准，另造走 change proposal")

    # --- 阶段区间 ---
    span = metadata.get("stage_span")
    if span:
        stages = (strategy or {}).get("stages") or []
        if stages and not (1 <= span[0] <= span[1] <= len(stages)):
            errors.append(f"stage_span {span} 越界（strategy 共 {len(stages)} 阶段）")

    # --- 班底预检（注册表名册提供时）---
    if registry_names is not None:
        for p in metadata.get("volume_characters") or []:
            if p.get("name") not in registry_names:
                warns.append(f"班底 {p['name']} 尚未入注册表——锁定后跑 register --entry，漏跑由 --audit-entries 终核")

    settings = metadata.get("volume_settings") or []
    names = [s.get("name") for s in settings]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        errors.append(f"volume_settings 名称重复: {sorted(dup)}")
    pending = [s["name"] for s in settings if s.get("disposition") == "登记入world"]
    if pending:
        warns.append(f"volume_settings 待登记入 world（锁定后走 change proposal）: {pending}")

    return errors, warns


def _resolve_from_db(project_id: str, db_path: Path) -> dict[str, Any]:
    """--project 自动解析：scale + locked story_arc/architecture/strategy + 前置卷号 + 注册表。"""
    import sqlite3

    out: dict[str, Any] = {}
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                "SELECT metadata_json FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row is None:
                print(f"ERROR: 项目不存在: {project_id}", file=sys.stderr)
                sys.exit(2)
            try:
                setup = (json.loads(row[0] or "{}") or {}).get("setup") or {}
                raw_scale = setup.get("scale")
                if isinstance(raw_scale, str) and raw_scale:
                    out["scale"] = raw_scale.split("（")[0].strip()
            except json.JSONDecodeError:
                pass
            for key, asset in (("story_arc", "story_arc"), ("architecture", "architecture"),
                               ("strategy", "strategy")):
                mrow = conn.execute(
                    "SELECT metadata_json FROM planning_assets WHERE project_id = ? "
                    "AND asset_type = ? AND status = 'locked' "
                    "ORDER BY revision DESC LIMIT 1", (project_id, asset)).fetchone()
                if mrow is not None:
                    try:
                        out[key] = json.loads(mrow[0] or "{}")
                    except json.JSONDecodeError:
                        pass
            # 前置锁定卷：每 scope 取最高 revision 的 volume_number（T39 前旧资产无此字段则跳过）
            vrows = conn.execute(
                "SELECT scope_ref, revision, metadata_json FROM planning_assets "
                "WHERE project_id = ? AND asset_type = 'volume_outline' AND status = 'locked' "
                "ORDER BY scope_ref, revision", (project_id,)).fetchall()
            latest: dict[str, tuple[int, int]] = {}
            for scope, revision, meta_json in vrows:
                if scope not in latest or revision > latest[scope][0]:
                    try:
                        num = (json.loads(meta_json or "{}") or {}).get("volume_number")
                    except json.JSONDecodeError:
                        num = None
                    latest[scope] = (revision, num if isinstance(num, int) else None)
            nums = [n for _, n in latest.values() if n is not None]
            if nums:
                out["prev_volume_numbers"] = nums
            elif vrows:
                print("[validate_volume_outline] 前置卷无 volume_number（T39 前旧资产）"
                      "——卷号连续性核验跳过", file=sys.stderr)
            names = conn.execute(
                "SELECT name FROM characters WHERE project_id = ?", (project_id,)).fetchall()
            out["registry_names"] = {n[0] for n in names}
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        print(f"[validate_volume_outline] --project 解析降级（{exc}）——用显式传参补齐对账输入",
              file=sys.stderr)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="volume_outline metadata 校验（卷号/字数对表/高潮门/线弧双向/单元/换图/终卷）")
    parser.add_argument("metadata", type=Path, help="候选 metadata JSON 路径")
    parser.add_argument("--scale", help="setup.scale 档位（短篇/中篇/长篇/超长篇）——启用短篇退化分支")
    parser.add_argument("--story-arc", type=Path, help="story_arc metadata JSON——启用字数/线弧/变奏对账")
    parser.add_argument("--architecture", type=Path, help="architecture metadata JSON——启用主线密度对表")
    parser.add_argument("--strategy", type=Path, help="strategy metadata JSON——启用阶段区间/终局纪律")
    parser.add_argument("--project", help="项目 ID——自动解析 scale 与上游 metadata/前置卷号/注册表")
    parser.add_argument("--db", default=str(ROOT / "data/novelos-v2.db"))
    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"ERROR: 文件不存在: {args.metadata}", file=sys.stderr)
        sys.exit(2)
    db_meta: dict[str, Any] = {}
    if args.project:
        db_meta = _resolve_from_db(args.project, Path(args.db))
    scale = args.scale or db_meta.get("scale")
    story_arc = _load(args.story_arc) if args.story_arc else db_meta.get("story_arc")
    architecture = _load(args.architecture) if args.architecture else db_meta.get("architecture")
    strategy = _load(args.strategy) if args.strategy else db_meta.get("strategy")
    metadata = _load(args.metadata)
    errors, warns = validate(metadata, scale=scale, story_arc=story_arc,
                             architecture=architecture, strategy=strategy,
                             prev_volume_numbers=db_meta.get("prev_volume_numbers"),
                             registry_names=db_meta.get("registry_names"))

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        print(f"FAIL（{len(errors)} 处缺陷）:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    n_lines = len(metadata["lines"])
    form = metadata["volume_form"]
    print(f"PASS: 卷 {metadata['volume_number']}（{form}，{n_lines} 线，"
          f"高潮 {len(metadata['climax_positions'])} 位，target {metadata['word_range']['target']} 字）"
          + ("，字数对表通过" if story_arc else "")
          + ("，卷号连续" if db_meta.get("prev_volume_numbers") is not None else "")
          + f"（WARN {len(warns)} 条）。")


if __name__ == "__main__":
    main()
