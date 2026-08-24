from __future__ import annotations

import argparse
import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "docs" / "archive" / "tasks" / "migration" / "skill_inventory.csv"
DEFAULT_OUTPUT = ROOT / "docs" / "archive" / "tasks" / "migration" / "catalog_disposition.csv"
AUTHORIZED_ORIGIN = "user-authorized"
AUTHORIZED_TARGETS = {
    "dash_ellipsis_guide": "catalog/skills/craft/dash-ellipsis-guide",
    "mobile_formatting": "catalog/skills/craft/mobile-formatting",
    "plot_conflict_craft": "catalog/skills/planning/chapter-plan-execution-card",
    "plot_emotional_pull": "catalog/skills/planning/chapter-plan-execution-card",
    "plot_hook_craft": "catalog/skills/planning/chapter-plan-execution-card",
    "scene_dialogue_craft": "catalog/skills/writing/scene-dialogue",
    "scene_fight_craft": "catalog/skills/writing/scene-fight-craft",
    "shuangwen_techniques": "catalog/skills/craft/shuangwen-techniques",
    "architecture-rule-system": "catalog/skills/expansions/world-rule-system",
    "architecture-ap2": "catalog/skills/expansions/world-growth-resource",
    "architecture-ap3": "catalog/skills/expansions/world-social-power",
    "architecture-mechanism-single": "catalog/skills/expansions/world-system-interaction",
    "architecture-mechanism-dual": "catalog/skills/expansions/world-system-interaction",
    "architecture-mechanism-multi": "catalog/skills/expansions/world-system-interaction",
    "architecture-expectation": "catalog/skills/expansions/story-expectation-design",
    "architecture-narrative-promise": "catalog/skills/expansions/story-expectation-design",
    "architecture-causal-plot": "catalog/skills/expansions/story-causal-structure",
    "architecture-pov-contract": "catalog/skills/expansions/story-pov-tone-contract",
    "architecture-tone": "catalog/skills/expansions/story-pov-tone-contract",
    "writer-rewrite": "catalog/skills/expansions/prose-revision",
    "humanizer": "catalog/skills/expansions/prose-revision",
}
FIELDS = [
    "plugin",
    "skill",
    "source_path",
    "source_hash",
    "lifecycle",
    "stage",
    "asset",
    "capability",
    "license_origin",
    "disposition",
    "target_path",
    "decision_reason",
]


def build(source: Path) -> list[dict[str, str]]:
    with source.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    rows: list[dict[str, str]] = []
    for source_row in source_rows:
        row = {field: source_row[field] for field in FIELDS[:9]}
        if source_row["skill"] in AUTHORIZED_TARGETS:
            target = AUTHORIZED_TARGETS[source_row["skill"]]
            row.update(
                license_origin=AUTHORIZED_ORIGIN,
                lifecycle="active",
                disposition="adapt-authorized",
                target_path=target,
                decision_reason="用户已授权的包，适配后进入 Catalog",
            )
        elif source_row["lifecycle"] != "active":
            row.update(
                disposition="defer-experiment",
                target_path="-",
                decision_reason="实验包没有生产消费者和质量证据",
            )
        elif "user-authorized" not in source_row["license_origin"]:
            row.update(
                disposition="defer-license",
                target_path="-",
                decision_reason="来源仓库授权未核清，生产迁移失败关闭",
            )
        else:
            raise ValueError(f"已授权 Skill 缺少显式目标: {source_row['skill']}")
        rows.append(row)
    return rows


def validate(rows: list[dict[str, str]]) -> None:
    if len(rows) != 138:
        raise ValueError(f"来源 Skill 数量应为 138，实际为 {len(rows)}")
    source_paths = [row["source_path"] for row in rows]
    if len(source_paths) != len(set(source_paths)):
        raise ValueError("source_path 重复")
    for row in rows:
        if not row["source_hash"].startswith("sha256:") or len(row["source_hash"]) != 71:
            raise ValueError(f"source_hash 非法: {row['source_path']}")
        if row["disposition"] == "adapt-authorized":
            if row["license_origin"] != AUTHORIZED_ORIGIN or row["lifecycle"] != "active":
                raise ValueError(f"未授权内容进入适配队列: {row['source_path']}")
        elif row["target_path"] != "-":
            raise ValueError(f"延后项不能有目标路径: {row['source_path']}")


def write(rows: list[dict[str, str]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成或校验 Skill Catalog disposition Manifest")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = build(args.source)
    validate(rows)
    if args.check:
        with args.output.open(encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
        if rows != existing:
            write(rows, args.output)
            raise SystemExit("catalog_disposition.csv 与来源盘点不一致，已重新生成")
        return
    write(rows, args.output)


if __name__ == "__main__":
    main()
