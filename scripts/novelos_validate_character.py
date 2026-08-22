#!/usr/bin/env python
"""人物契约结构化出口校验：roster schema + 规模档位机器门 + 席位对账。

校验 `character_contract` 候选的 metadata（roster schema 见
config/schemas/planning-candidate.schema.json 的 $defs/character_roster）：

1. roster 结构（name/role_class/arc_role/登场卷/预期退场/seat_ref）；
2. **roster 规模 × scale 档位区间**（T36 机器门）：
   短篇 2-5 / 中篇 3-8 / 长篇 5-12 / 超长篇 8-16——立档人物数不含班底/微档案；
   区间不足由卷级班底补员，超出说明契约越权吸食班底职责；
3. 重名（roster 内同名 = 注册表唯一键冲突）；
4. main 至少 1 人（主角在场）；
5. 席位对账（`--world` 或 `--project` 自动取）：roster.seat_ref 全部回指
   world seats 存在的席位名；处置分级（T37）——「待契约认领」但无人认领
   = **error**（契约层必须兑现处置承诺，标注不是免检标签）；「待卷级班底」
   无人认领 = WARN（卷级义务，锁定卷纲后由 register --world 终核）；
   未标注处置 = WARN；「显式虚位」= 静默（有意不填是正确状态）。

`--project <id>` 自动解析（T37）：--scale 缺省时取 projects.metadata_json
的 setup.scale；--world 缺省时取 locked world_contract 的 metadata_json——
漏传参不再导致机器门静默降级。

用法::

    python scripts/novelos_validate_character.py metadata.json --project project:xxx
    python scripts/novelos_validate_character.py metadata.json --scale "长篇" --world world-metadata.json

退出码：0 通过 / 1 缺陷 / 2 输入错误。WARN 不影响通过（exit 0），逐条打印。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "config/schemas/planning-candidate.schema.json"

_SCALE_ROSTER_RULES: dict[str, tuple[int, int]] = {
    "短篇": (2, 5),
    "中篇": (3, 8),
    "长篇": (5, 12),
    "超长篇": (8, 16),
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(metadata: dict, scale: str | None = None,
             world: dict | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []

    try:
        import jsonschema
    except ImportError:
        print("缺少 jsonschema（.venv/bin/python 运行或 pip install jsonschema）", file=sys.stderr)
        sys.exit(2)

    schema = _load(SCHEMA_PATH)
    sub = dict(schema["$defs"]["character_roster"])
    sub["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    roster = metadata.get("character_roster")
    if roster is None:
        errors.append("metadata.character_roster 缺失——立档人物必须有结构化出口")
        return errors, warns
    try:
        jsonschema.validate(roster, sub)
    except jsonschema.ValidationError as exc:
        for err in [exc] + list(exc.context or []):
            path = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(f"roster[{path}]: {err.message}")
        return errors, warns

    names = [p["name"] for p in roster]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        errors.append(f"roster 重名: {'、'.join(sorted(dup))}——人物注册表 project_id+name 唯一")
    if not any(p.get("role_class") == "main" for p in roster):
        errors.append("roster 无 main 人物——主角必须立档（role_class=main）")

    if scale is not None:
        if scale not in _SCALE_ROSTER_RULES:
            errors.append(f"未知 scale 档位 {scale!r}（{_SCALE_ROSTER_RULES.keys()}）")
        else:
            low, high = _SCALE_ROSTER_RULES[scale]
            n = len(roster)
            if n < low:
                errors.append(f"roster 规模 {n} 低于 {scale} 档区间 [{low}, {high}] 下限"
                              "——主线载体缺口：补立档或确认由卷级班底承载并说明")
            elif n > high:
                errors.append(f"roster 规模 {n} 超出 {scale} 档区间 [{low}, {high}] 上限"
                              "——契约越权吸食班底职责：次要角色移交卷纲/执行卡")

    if world is not None:
        seat_names = {s.get("name") for s in world.get("seats", [])}
        claimed = set()
        for p in roster:
            ref = p.get("seat_ref")
            if ref:
                claimed.add(ref)
                if ref not in seat_names:
                    errors.append(f"roster[{p['name']}].seat_ref 引用不存在的席位: {ref!r}")
        for s in world.get("seats", []):
            if s["name"] in claimed or s.get("disposition") == "显式虚位":
                continue
            disp = s.get("disposition")
            if disp == "待契约认领":
                errors.append(
                    f"席位「{s['name']}」标注「待契约认领」但 roster 无人认领"
                    "——处置标注是承诺不是免检标签：认领（seat_ref）或经 change "
                    "proposal 改 world 处置")
            elif disp == "待卷级班底":
                warns.append(f"席位「{s['name']}」标注「待卷级班底」——卷纲班底义务，"
                             "锁定卷纲时 register --world 终核")
            else:
                warns.append(f"席位「{s['name']}」未被认领且无处置标注"
                             "——主要席位须在正文标注 认领/移交班底/虚位 之一")

    return errors, warns


def _resolve_from_db(project_id: str, db_path: Path) -> tuple[str | None, dict | None]:
    """--project 自动解析：setup.scale + locked world_contract metadata。
    查不到不硬失败（旧库/测试库缺表走显式传参路径），打 stderr 提示。"""
    import sqlite3

    scale: str | None = None
    world: dict | None = None
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
                # setup.scale 存完整标签（如「超长篇（300万字以上）」），档位键取括号前缀
                raw_scale = setup.get("scale")
                if isinstance(raw_scale, str) and raw_scale:
                    scale = raw_scale.split("（")[0].strip()
            except json.JSONDecodeError:
                pass
            wrow = conn.execute(
                "SELECT metadata_json FROM planning_assets WHERE project_id = ? "
                "AND asset_type = 'world_contract' AND status = 'locked' "
                "ORDER BY revision DESC LIMIT 1", (project_id,)).fetchone()
            if wrow is not None:
                try:
                    world = json.loads(wrow[0] or "{}")
                except json.JSONDecodeError:
                    pass
        finally:
            conn.close()
    except sqlite3.OperationalError as exc:
        print(f"[validate_character] --project 解析降级（{exc}）——用显式 --scale/--world",
              file=sys.stderr)
    return scale, world


def main() -> None:
    parser = argparse.ArgumentParser(description="character_contract metadata 校验（roster + 规模档位 + 席位对账）")
    parser.add_argument("metadata", type=Path, help="候选 metadata JSON 路径")
    parser.add_argument("--scale", help="setup.scale 档位（短篇/中篇/长篇/超长篇）——启用规模机器门")
    parser.add_argument("--world", type=Path, help="world_contract metadata JSON——启用席位对账")
    parser.add_argument("--project", help="项目 ID——自动解析 scale 与 locked world（显式传参优先）")
    parser.add_argument("--db", default=str(ROOT / "data/novelos-v2.db"))
    args = parser.parse_args()

    if not args.metadata.exists():
        print(f"ERROR: 文件不存在: {args.metadata}", file=sys.stderr)
        sys.exit(2)
    scale, db_world = (None, None)
    if args.project:
        scale, db_world = _resolve_from_db(args.project, Path(args.db))
    scale = args.scale or scale
    world = _load(args.world) if args.world else db_world
    metadata = _load(args.metadata)
    errors, warns = validate(metadata, scale=scale, world=world)

    for w in warns:
        print(f"WARN: {w}")
    if errors:
        print(f"FAIL（{len(errors)} 处缺陷）:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print(f"PASS: character_roster {len(metadata.get('character_roster', []))} 人结构合法"
          + (f"，规模符合 {scale} 档区间" if scale else "")
          + ("，席位对账通过" if world is not None else "")
          + f"（WARN {len(warns)} 条）。")


if __name__ == "__main__":
    main()
