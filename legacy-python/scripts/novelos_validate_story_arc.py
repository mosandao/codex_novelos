#!/usr/bin/env python
"""跨卷故事弧结构化出口校验：弧清单/映射表/台账/变奏分配 + 档位机器门 + 载体对账。

校验 `story_arc` 候选的 metadata（schema 见
config/schemas/story-arc-metadata.schema.json，T38）：

1. schema 结构（arcs / volume_plan / arc_volume_map / plant_payoff_ledger /
   variation_alloc / open_window / decision_points）；
2. **弧数 × scale 档位区间**：短篇 1-2 / 中篇 2-3 / 长篇 3-5 / 超长篇 5-7；
   主线弧（kind=主线）恰 1 条；
3. **映射表机器门**：arc_id 全部存在、卷号不越界、每弧至少 1 格；
   每卷 ≥1 条「推进」（全休眠 = error）；「推进」≤2 条（超出 warn）；
   同时活跃（推进/兑现/收束）≤4（超出 error）；弧 ≥3 条时禁全推进（warn）；
4. **载体对账**（`--character`/`--world` 或 `--project` 自动取）：
   ref_type=roster 回指契约 roster 人物名、ref_type=seat 回指 world 席位名
   ——不存在 = error；latent（远卷待造载体）= WARN；主线/人物/关系弧必须
   ≥1 个 roster 具名载体；弧首个活跃卷不得早于载体登场卷；
5. **种收台账机器门**：close_volume 与 exempt 二选一（缺一 = error，兼有 = error）；
   收束卷晚于种下卷；卷 2 起每卷至少兑现一条（close 或 partial 命中该卷）；
6. **变奏分配对账**：mech_ref 回指 architecture mechanisms 机制名（`--architecture`
   提供时，不存在 = error）；同一 test_ref 分配 >3 次 = warn（剩余空间评估）；
7. **卷计划对表**：卷号连续；卷字数总和 vs strategy stages 字数总和比值
   落在 [0.6, 1.6]（`--strategy` 提供时，越界 warn）；
8. **开放窗口**：strategy terminal_mode=open 时 open_window 必填（缺 = error）。

`--project <id>` 自动解析：setup.scale + locked character/world/architecture/
strategy 的 metadata_json——显式传参优先。

用法::

    python scripts/novelos_validate_story_arc.py metadata.json --project project:xxx
    python scripts/novelos_validate_story_arc.py metadata.json --scale "长篇" \
        --character c.json --world w.json --architecture a.json --strategy s.json

退出码：0 通过 / 1 缺陷 / 2 输入错误。WARN 不影响通过（exit 0），逐条打印。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "config/schemas/story-arc-metadata.schema.json"

_SCALE_ARC_RULES: dict[str, tuple[int, int]] = {
    "短篇": (1, 2),
    "中篇": (2, 3),
    "长篇": (3, 5),
    "超长篇": (5, 7),
}

_ACTIVE_DUTIES = {"推进", "兑现", "收束"}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(metadata: dict, scale: str | None = None,
             character: dict | None = None, world: dict | None = None,
             architecture: dict | None = None,
             strategy: dict | None = None) -> tuple[list[str], list[str]]:
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

    arcs = metadata["arcs"]
    plan = metadata["volume_plan"]
    amap = metadata["arc_volume_map"]
    ledger = metadata["plant_payoff_ledger"]
    n_vols = len(plan)

    # --- 卷计划：卷号连续 ---
    idx = [v["index"] for v in plan]
    if idx != list(range(1, n_vols + 1)):
        errors.append(f"volume_plan 卷号不连续: {idx}——须为 1..{n_vols}")

    # --- 弧数 × scale 档位 ---
    if scale is not None:
        if scale not in _SCALE_ARC_RULES:
            errors.append(f"未知 scale 档位 {scale!r}（{_SCALE_ARC_RULES.keys()}）")
        else:
            low, high = _SCALE_ARC_RULES[scale]
            n = len(arcs)
            if n < low:
                errors.append(f"弧数 {n} 低于 {scale} 档区间 [{low}, {high}] 下限——线程轴单薄")
            elif n > high:
                errors.append(f"弧数 {n} 超出 {scale} 档区间 [{low}, {high}] 上限——弧线过散，收束不住")
    mainline = [a for a in arcs if a["kind"] == "主线"]
    if len(mainline) != 1:
        errors.append(f"主线弧须恰 1 条（当前 {len(mainline)}）——central_contradiction 的唯一承载")

    arc_ids = [a["arc_id"] for a in arcs]
    dup = {i for i in arc_ids if arc_ids.count(i) > 1}
    if dup:
        errors.append(f"arc_id 重复: {sorted(dup)}")

    # --- 映射表机器门 ---
    by_volume: dict[int, list[tuple[str, str]]] = {}
    arc_rows: dict[str, list[int]] = {}
    for row in amap:
        aid, vol = row["arc_id"], row["volume"]
        if aid not in arc_ids:
            errors.append(f"映射表引用不存在的 arc_id: {aid}")
            continue
        if not 1 <= vol <= n_vols:
            errors.append(f"弧 {aid} 映射卷 {vol} 越界（volume_plan 共 {n_vols} 卷）")
            continue
        by_volume.setdefault(vol, []).append((aid, row["duty"]))
        arc_rows.setdefault(aid, []).append(vol)
    for a in arcs:
        if a["arc_id"] not in arc_rows:
            errors.append(f"弧 {a['arc_id']} 在映射表无任何职责格——每弧至少一格")
    for vol in range(1, n_vols + 1):
        rows = by_volume.get(vol, [])
        if not rows:
            errors.append(f"卷 {vol} 映射表无任何弧职责格")
            continue
        duties = [d for _, d in rows]
        advancing = [d for d in duties if d == "推进"]
        active = [d for d in duties if d in _ACTIVE_DUTIES]
        if not active:
            errors.append(f"卷 {vol} 无任何活跃弧（推进/兑现/收束皆无）——全蓄势/全休眠是调度失败")
        elif not advancing:
            warns.append(f"卷 {vol} 无「推进」弧（仅兑现/收束）——终卷形态合法，其余卷提示节奏软塌")
        if len(advancing) > 2:
            warns.append(f"卷 {vol} 推进弧 {len(advancing)} 条（>2）——活跃焦点过散")
        if len(active) > 4:
            errors.append(f"卷 {vol} 同时活跃弧 {len(active)} 条（>4）——超出并行活跃上限")
        if len(arcs) >= 3 and len(set(duties)) == 1 and duties[0] in _ACTIVE_DUTIES:
            warns.append(f"卷 {vol} 全部弧同职责「{duties[0]}」——全推进/全兑现同样不合格，须有蓄势/休眠弧")

    # --- 载体对账（character/world 为可选对账输入：未提供时整体跳过，按空集全拦是误伤）---
    roster: list[dict] = (character or {}).get("character_roster") if character else []
    roster_names = {p.get("name"): p for p in roster or []}
    seat_names = {s.get("name") for s in (world or {}).get("seats", [])} if world else set()
    for a in arcs:
        kind, aid = a["kind"], a["arc_id"]
        carriers = a.get("carriers") or []
        named = [c for c in carriers if c["ref_type"] == "roster"]
        if character is not None and kind in ("主线", "人物", "关系") and not named:
            errors.append(f"弧 {aid}（{kind}）无 roster 具名载体——人物类弧必须绑定契约人物")
        for c in carriers:
            if c["ref_type"] == "roster" and character is not None and c["ref"] not in roster_names:
                errors.append(f"弧 {aid} 载体 {c['ref']!r} 不在契约 roster——引用不存在的人物")
            elif c["ref_type"] == "seat" and world is not None and c["ref"] not in seat_names:
                errors.append(f"弧 {aid} 载体席位 {c['ref']!r} 不在 world 岗位表——引用不存在的席位")
            elif c["ref_type"] == "latent":
                warns.append(f"弧 {aid} 载体 {c['ref']!r} 为 latent（待造）——远卷对手可暂悬空，"
                             "近硬窗内须落位（roster/席位/班底）")
        first_vol = min(arc_rows.get(aid, [n_vols + 1]))
        for c in named:
            p = roster_names.get(c["ref"]) or {}
            debut = p.get("登场卷")
            if isinstance(debut, int) and first_vol < debut:
                errors.append(f"弧 {aid} 首个活跃卷 {first_vol} 早于载体 {c['ref']} 登场卷 {debut}"
                              "——弧不能在人物登场前活跃")

    # --- 种收台账机器门 ---
    for row in ledger:
        has_close, has_exempt = row.get("close_volume") is not None, bool(row.get("exempt"))
        if has_close and has_exempt:
            errors.append(f"台账行 {row['line_id']} 兼有 close_volume 与 exempt——二选一")
        elif not has_close and not has_exempt:
            errors.append(f"台账行 {row['line_id']} 既无 close_volume 也无 exempt"
                          "——只种不收：给收束卷，或引用豁免（deliberate_silences / open 喂料线）")
        plant = row["plant_volume"]
        if not 1 <= plant <= n_vols:
            errors.append(f"台账行 {row['line_id']} 种下卷 {plant} 越界")
        elif has_close and row["close_volume"] <= plant:
            errors.append(f"台账行 {row['line_id']} 收束卷不晚于种下卷——先收后种")
        for pv in row.get("partial_payoffs") or []:
            if not 1 <= pv <= n_vols or (has_close and pv >= row["close_volume"]):
                errors.append(f"台账行 {row['line_id']} 阶段兑现卷 {pv} 越界或不早于收束卷")
    for vol in range(2, n_vols + 1):
        hit = any(r.get("close_volume") == vol or vol in (r.get("partial_payoffs") or [])
                  for r in ledger)
        if not hit:
            errors.append(f"卷 {vol} 无任何前序悬念兑现（close/partial 均未命中）"
                          "——每卷至少兑现一条，读者容忍的是晚收益不是无收益")

    # --- 变奏分配对账 ---
    mech_names = {m.get("name") for m in (architecture or {}).get("mechanisms", [])}
    alloc_count: dict[str, int] = {}
    for row in metadata.get("variation_alloc") or []:
        alloc_count[row["test_ref"]] = alloc_count.get(row["test_ref"], 0) + 1
        if not 1 <= row["volume"] <= n_vols:
            errors.append(f"变奏分配 {row['test_ref']!r} 卷 {row['volume']} 越界")
        ref = row.get("mech_ref")
        if ref and mech_names and ref not in mech_names:
            errors.append(f"变奏分配 {row['test_ref']!r} 的 mech_ref {ref!r}"
                          " 不在 architecture mechanisms——变奏声明须引用真实机制")
    for t, n in alloc_count.items():
        if n > 3:
            warns.append(f"母题 {t!r} 已分配 {n} 次变奏（>3）——须评估剩余空间，耗尽即转收束")

    # --- 卷计划 vs strategy 阶段字数 ---
    if strategy:
        stages = strategy.get("stages") or []
        try:
            stage_sum = sum(s["word_range"]["max"] for s in stages)
            plan_sum = sum(v["word_range"]["max"] for v in plan)
            if stage_sum and plan_sum and not 0.6 <= plan_sum / stage_sum <= 1.6:
                warns.append(f"卷计划总字数 {plan_sum} 与 strategy 阶段字数总和 {stage_sum} "
                             f"比值 {plan_sum / stage_sum:.2f} 越界 [0.6, 1.6]——卷切分与阶段骨架对表")
        except (KeyError, TypeError):
            warns.append("strategy stages 缺 word_range——卷计划与阶段字数对表跳过")
        if strategy.get("terminal_mode") == "open" and "open_window" not in metadata:
            errors.append("strategy terminal_mode=open 但缺 open_window——开放连载必须声明滚动窗口"
                          "（近 hard_volumes 卷硬格，远卷软格待重映射）")

    return errors, warns


def _resolve_from_db(project_id: str, db_path: Path) -> dict[str, Any]:
    """--project 自动解析：setup.scale + locked character/world/architecture/strategy metadata。

    查不到不硬失败（旧库/测试库缺表走显式传参路径），打 stderr 提示。
    """
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
            for key, asset in (("character", "character_contract"), ("world", "world_contract"),
                               ("architecture", "architecture"), ("strategy", "strategy")):
                mrow = conn.execute(
                    "SELECT metadata_json FROM planning_assets WHERE project_id = ? "
                    "AND asset_type = ? AND status = 'locked' "
                    "ORDER BY revision DESC LIMIT 1", (project_id, asset)).fetchone()
                if mrow is not None:
                    try:
                        out[key] = json.loads(mrow[0] or "{}")
                    except json.JSONDecodeError:
                        pass
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        print(f"[validate_story_arc] --project 解析降级（{exc}）——用显式传参补齐对账输入",
              file=sys.stderr)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="story_arc metadata 校验（弧数档位 + 映射表 + 台账 + 载体/机制对账）")
    parser.add_argument("metadata", type=Path, help="候选 metadata JSON 路径")
    parser.add_argument("--scale", help="setup.scale 档位（短篇/中篇/长篇/超长篇）——启用弧数机器门")
    parser.add_argument("--character", type=Path, help="character_contract metadata JSON——启用载体对账")
    parser.add_argument("--world", type=Path, help="world_contract metadata JSON——启用席位载体对账")
    parser.add_argument("--architecture", type=Path, help="architecture metadata JSON——启用变奏机制对账")
    parser.add_argument("--strategy", type=Path, help="strategy metadata JSON——启用卷计划/open 窗口对表")
    parser.add_argument("--project", help="项目 ID——自动解析 scale 与四上游 locked metadata（显式传参优先）")
    parser.add_argument("--db", default=str(ROOT / "data/novelos-v2.db"))
    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"ERROR: 文件不存在: {args.metadata}", file=sys.stderr)
        sys.exit(2)
    db_meta: dict[str, Any] = {}
    if args.project:
        db_meta = _resolve_from_db(args.project, Path(args.db))
    scale = args.scale or db_meta.get("scale")
    character = _load(args.character) if args.character else db_meta.get("character")
    world = _load(args.world) if args.world else db_meta.get("world")
    architecture = _load(args.architecture) if args.architecture else db_meta.get("architecture")
    strategy = _load(args.strategy) if args.strategy else db_meta.get("strategy")
    metadata = _load(args.metadata)
    errors, warns = validate(metadata, scale=scale, character=character, world=world,
                             architecture=architecture, strategy=strategy)

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        print(f"FAIL（{len(errors)} 处缺陷）:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    n_map = len(metadata["arc_volume_map"])
    print(f"PASS: {len(metadata['arcs'])} 弧 × {len(metadata['volume_plan'])} 卷"
          f"（映射 {n_map} 格，台账 {len(metadata['plant_payoff_ledger'])} 行）"
          + (f"，弧数符合 {scale} 档区间" if scale else "")
          + ("，载体对账通过" if character is not None or world is not None else "")
          + ("，机制对账通过" if architecture is not None else "")
          + f"（WARN {len(warns)} 条）。")


if __name__ == "__main__":
    main()
