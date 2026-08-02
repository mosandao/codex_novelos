#!/usr/bin/env python3
"""从权威迁移产物生成可重建的交付统计和延后项汇总。"""

from __future__ import annotations

import argparse
import csv
import json
import re
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from check_cutover_readiness import build as build_readiness
    from summarize_agent_quality_results import DEFAULT_DATASET, DEFAULT_RESULTS, summary_is_current
except ModuleNotFoundError:  # 作为 scripts 命名空间模块导入时使用。
    from scripts.check_cutover_readiness import build as build_readiness
    from scripts.summarize_agent_quality_results import DEFAULT_DATASET, DEFAULT_RESULTS, summary_is_current


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "tasks" / "migration"
DEFAULT_OUTPUT = MIGRATION / "migration_summary.json"


class MigrationSummaryError(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationSummaryError(f"无法读取 JSON：{path}") from exc
    if not isinstance(payload, dict):
        raise MigrationSummaryError(f"JSON 顶层必须是对象：{path}")
    return payload


def _csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise MigrationSummaryError(f"无法读取 CSV：{path}") from exc


def _counter(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    try:
        return dict(sorted(Counter(row[field] for row in rows).items()))
    except KeyError as exc:
        raise MigrationSummaryError(f"清单缺少字段：{field}") from exc


def _require_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise MigrationSummaryError(f"{label} 不一致：期望 {expected!r}，实际 {actual!r}")


def _quality() -> dict[str, Any]:
    manifest_path = DEFAULT_DATASET / "execution_manifest.jsonl"
    try:
        case_count = sum(1 for line in manifest_path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError as exc:
        raise MigrationSummaryError(f"无法读取质量实验清单：{manifest_path}") from exc
    summary_path = DEFAULT_RESULTS / "summary.json"
    if not summary_path.is_file():
        deferral = _json(DEFAULT_DATASET / "deferral.json")
        if deferral.get("status") == "deferred":
            completed_path = DEFAULT_RESULTS / "case_results.jsonl"
            completed = (
                sum(1 for line in completed_path.read_text(encoding="utf-8").splitlines() if line.strip())
                if completed_path.is_file()
                else 0
            )
            return {
                "case_count": case_count,
                "completed_case_count": completed,
                "status": "deferred",
                "summary_current": False,
                "partial_results_non_authoritative": bool(deferral.get("partial_results_non_authoritative")),
                "writer_policy": deferral.get("writer_policy"),
                "context_builder_policy": deferral.get("context_builder_policy"),
            }
        return {"case_count": case_count, "status": "not_run", "summary_current": False}
    summary = _json(summary_path)
    current = summary_is_current(DEFAULT_DATASET, DEFAULT_RESULTS)
    return {
        "case_count": case_count,
        "status": summary.get("status") if current else "invalid",
        "summary_current": current,
        "writer_decision": summary.get("writer_decision") if current else None,
        "context_builder_decision": summary.get("context_builder_decision") if current else None,
    }


def build(root: Path = ROOT) -> dict[str, Any]:
    migration = root / "tasks" / "migration"
    with (migration / "source_snapshot.toml").open("rb") as handle:
        snapshot = tomllib.load(handle)
    source_rows = _csv(migration / "source_manifest.csv")
    table_rows = _csv(migration / "table_inventory.csv")
    catalog_rows = _csv(migration / "catalog_disposition.csv")
    legacy = _json(migration / "legacy_migration_report.json")
    restore = _json(migration / "schema12_restore_drill.json")
    export_drill = _json(migration / "schema12_export_drill.json")
    seed = _json(migration / "seed_source_inventory.json")

    source_classifications = _counter(source_rows, "classification")
    table_waves = _counter(table_rows, "wave")
    catalog_dispositions = _counter(catalog_rows, "disposition")
    _require_equal(len(source_rows), snapshot["file_count"], "来源文件数量")
    _require_equal(
        source_classifications,
        {
            "adapt": snapshot["manifest_adapt"],
            "defer": snapshot["manifest_defer"],
            "direct": snapshot["manifest_direct"],
            "reject": snapshot["manifest_reject"],
        },
        "来源分类统计",
    )
    _require_equal(
        table_waves,
        {
            "A": snapshot["tables_wave_a"],
            "B": snapshot["tables_wave_b"],
            "C": snapshot["tables_wave_c"],
            "D": snapshot["tables_wave_d"],
        },
        "表波次统计",
    )
    _require_equal(len(catalog_rows), snapshot["skill_count"], "Skill disposition 数量")
    for table, count in legacy["migrated_counts"].items():
        _require_equal(legacy["source_counts"].get(table), count, f"Legacy 来源 {table} 计数")
        _require_equal(legacy["target_counts"].get(table), count, f"Legacy 目标 {table} 计数")
    _require_equal(legacy["quarantined_counts"], {}, "Legacy 隔离记录")
    logical = restore.get("logical_snapshot", {})
    _require_equal(restore.get("restore_drill"), "passed", "当前 Schema 恢复演练")
    _require_equal(logical.get("quick_check"), "ok", "当前 Schema quick_check")
    _require_equal(export_drill.get("export_restore_drill"), "passed", "当前 Schema 导出恢复演练")
    _require_equal(export_drill.get("logical_snapshot"), logical, "备份与导出恢复逻辑快照")
    _require_equal(seed.get("table_count"), snapshot["seed_knowledge_table_count"], "seed 表数量")
    _require_equal(seed.get("row_count"), snapshot["seed_knowledge_record_count"], "seed 记录数量")

    authorization_text = (migration / "seed_authorization_audit.md").read_text(encoding="utf-8")
    conclusion = re.search(r"^结论：`([^`]+)`", authorization_text, flags=re.MULTILINE)
    if conclusion is None:
        raise MigrationSummaryError("seed 授权审计缺少机器可读结论")
    seed_authorization = conclusion.group(1)
    quality = _quality() if root == ROOT else _quality_for_root(root)
    readiness = build_readiness() if root == ROOT else _json(root / "tasks" / "cutover" / "readiness.json")
    import yaml
    active_catalog_count = 0
    experiment_catalog_count = 0
    for meta_file in (root / "catalog" / "skills").rglob("metadata.yaml"):
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8"))
        if meta.get("lifecycle") == "active":
            active_catalog_count += 1
        elif meta.get("lifecycle") == "experiment":
            experiment_catalog_count += 1
    production_catalog_count = active_catalog_count

    deferred_source = [row for row in source_rows if row["classification"] == "defer"]
    wave_d_tables = [row["table_name"] for row in table_rows if row["wave"] == "D"]
    deferred_catalog = {
        key: value for key, value in catalog_dispositions.items() if key.startswith("defer-")
    }
    blockers = list(readiness.get("blockers", []))
    status = "completed" if readiness.get("status") == "ready" else "prepared"
    return {
        "schema_version": 1,
        "status": status,
        "source": {
            "repository": snapshot["source_repository"],
            "commit": snapshot["source_commit"],
            "tree": snapshot["source_tree"],
            "file_count": len(source_rows),
            "classification_counts": source_classifications,
        },
        "storage": {
            "legacy_source_hash": legacy["source_hash"],
            "legacy_import_id": legacy["import_id"],
            "migrated_counts": legacy["migrated_counts"],
            "quarantined_counts": legacy["quarantined_counts"],
            "target_hashes": legacy["target_hashes"],
            "schema_versions": logical["schema_versions"],
            "logical_hash": logical["logical_hash"],
            "restore_drill": restore["restore_drill"],
            "export_restore_drill": export_drill["export_restore_drill"],
            "export_manifest_hash": export_drill["export_manifest_hash"],
        },
        "catalog": {
            "source_skill_count": len(catalog_rows),
            "disposition_counts": catalog_dispositions,
            "production_package_count": production_catalog_count,
            "experiment_package_count": experiment_catalog_count,
        },
        "quality_experiment": quality,
        "seed": {
            "authorization": seed_authorization,
            "source_hash": seed["source_hash"],
            "table_count": seed["table_count"],
            "row_count": seed["row_count"],
            "migrated": seed_authorization == "authorized" and (root / "mcp" / "novelos" / "resources" / "seed.db").is_file(),
        },
        "deferred": {
            "source_manifest_count": len(deferred_source),
            "source_manifest_by_reason": _counter(deferred_source, "reason"),
            "wave_d_tables": wave_d_tables,
            "catalog_disposition_counts": deferred_catalog,
            "cutover_blockers": blockers,
        },
    }


def _quality_for_root(root: Path) -> dict[str, Any]:
    manifest = root / "tasks" / "experiments" / "agent_quality" / "execution_manifest.jsonl"
    count = sum(1 for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip())
    summary_path = manifest.parent / "results" / "summary.json"
    if not summary_path.is_file():
        return {"case_count": count, "status": "not_run", "summary_current": False}
    return {"case_count": count, "status": "unverified", "summary_current": False}


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="生成或校验 NovelOS 迁移统计与延后项汇总")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        content = render(build())
    except (KeyError, OSError, MigrationSummaryError) as exc:
        raise SystemExit(str(exc)) from exc
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != content:
            raise SystemExit(f"迁移汇总不是当前证据的可重建结果：{args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
