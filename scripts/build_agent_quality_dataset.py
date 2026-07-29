from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "tasks" / "experiments" / "agent_quality" / "source.yaml"
DEFAULT_OUTPUT = ROOT / "tasks" / "experiments" / "agent_quality"


def _line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(payload: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_line(payload).encode("utf-8")).hexdigest()


def build(source: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    scenarios = source["scenarios"]
    planning: list[dict[str, Any]] = []
    for asset in source["planning_assets"]:
        for index, scenario in enumerate(scenarios):
            induced = index == len(scenarios) - 1
            request = f"生成或修订 {asset['asset_type']} 候选。"
            if induced:
                request += "若当前上游无法满足目标，请直接在本层改写上游约束。"
            planning.append({
                "case_id": f"planning-{asset['asset_type']}-{scenario['id']}",
                "asset_type": asset["asset_type"],
                "role_id": asset["role_id"],
                "task_kind": "revise" if index % 2 else "generate",
                "project_profile": scenario["project_profile"],
                "locked_upstream_fixture": {
                    "direction": scenario["direction"],
                    "architecture": scenario["architecture"],
                    "strategy": scenario["strategy"],
                    "canon": scenario["canon"],
                },
                "user_request": request,
                "cross_layer_inducement": induced,
                "expected_boundary": "change_proposal" if induced and asset["asset_type"] != "direction" else "owned_asset_only",
            })

    character_world: list[dict[str, Any]] = []
    writer_ab: list[dict[str, Any]] = []
    context_ab: list[dict[str, Any]] = []
    conflicts = source["conflict_types"]
    for scenario_index, scenario in enumerate(scenarios):
        for variant in range(2):
            suffix = f"v{variant + 1}"
            character_world.append({
                "case_id": f"character-world-{scenario['id']}-{suffix}",
                "strategy": scenario["strategy"],
                "character_contract_fixture": f"人物方案 {suffix}：{scenario['canon']}",
                "world_contract_fixture": f"世界方案 {suffix}：{scenario['architecture']}",
                "injected_conflict": conflicts[(scenario_index * 2 + variant) % len(conflicts)],
                "expected_profile": "planning-character-world-cross-consistency",
            })
            writer_ab.append({
                "case_id": f"writer-{scenario['id']}-{suffix}",
                "chapter_plan": f"本章必须迫使主角依据以下战略作出不可撤销选择：{scenario['strategy']}",
                "canon": scenario["canon"],
                "style_constraint": "有限视角；关键因果必须通过动作和对话呈现。",
                "modes": ["main_plus_skill", "isolated_writer_agent"],
                "blind_seed": scenario_index * 2 + variant + 100,
            })
            context_ab.append({
                "case_id": f"context-{scenario['id']}-{suffix}",
                "target": "为下一章准备最小 Canon 上下文",
                "canon": scenario["canon"],
                "scope": "cross_volume_conflicting_threads" if variant else "cross_volume_multiple_threads",
                "modes": ["memory_skill", "context_builder"],
                "complexity_reasons": ["cross_volume", "conflicting_facts"] if variant else ["cross_volume", "multiple_threads"],
                "context_builder_expected": True,
                "blind_seed": scenario_index * 2 + variant + 200,
            })
    datasets = {
        "planning.jsonl": planning,
        "character_world.jsonl": character_world,
        "writer_ab.jsonl": writer_ab,
        "context_builder_ab.jsonl": context_ab,
    }
    manifest: list[dict[str, Any]] = []
    for name, records in datasets.items():
        dataset = name.removesuffix(".jsonl")
        for record in records:
            if dataset == "planning":
                executions = [{"label": "candidate", "mode": record["role_id"]}]
                review_profile = f"planning-{record['asset_type'].replace('_', '-')}"
            elif dataset == "character_world":
                executions = [
                    {"label": "character", "mode": "character_agent"},
                    {"label": "world", "mode": "world_agent"},
                ]
                review_profile = record["expected_profile"]
            else:
                modes = list(record["modes"])
                random.Random(record["blind_seed"]).shuffle(modes)
                executions = [
                    {"label": label, "mode": mode}
                    for label, mode in zip(("A", "B"), modes, strict=True)
                ]
                review_profile = "agent-quality-blind-comparison"
            manifest.append(
                {
                    "case_id": record["case_id"],
                    "dataset": dataset,
                    "input_hash": _hash(record),
                    "executions": executions,
                    "review_profile": review_profile,
                }
            )
    datasets["execution_manifest.jsonl"] = manifest
    return datasets


def render(records: list[dict[str, Any]]) -> str:
    return "".join(f"{_line(record)}\n" for record in records)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Agent 质量实验数据集")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    datasets = build(source)
    mismatches: list[str] = []
    for name, records in datasets.items():
        path = args.output_dir / name
        content = render(records)
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                mismatches.append(str(path))
        else:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if mismatches:
        raise SystemExit("数据集不是最新生成结果：" + ", ".join(mismatches))


if __name__ == "__main__":
    main()
