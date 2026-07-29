from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from check_cutover_plan import plan_is_valid
    from check_repository_hygiene import DEFAULT_OUTPUT as HYGIENE_REPORT
    from check_repository_hygiene import build as build_hygiene
    from check_repository_hygiene import render as render_hygiene
    from summarize_agent_quality_results import DEFAULT_DATASET, DEFAULT_RESULTS, summary_is_current
except ModuleNotFoundError:  # 作为 scripts 命名空间模块导入时使用。
    from scripts.check_cutover_plan import plan_is_valid
    from scripts.check_repository_hygiene import DEFAULT_OUTPUT as HYGIENE_REPORT
    from scripts.check_repository_hygiene import build as build_hygiene
    from scripts.check_repository_hygiene import render as render_hygiene
    from scripts.summarize_agent_quality_results import DEFAULT_DATASET, DEFAULT_RESULTS, summary_is_current


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "tasks" / "cutover" / "readiness.json"
QUALITY_DEFERRAL = ROOT / "tasks" / "experiments" / "agent_quality" / "deferral.json"
MCP_SOURCE = ROOT / "mcp" / "novelos" / "src"
if str(MCP_SOURCE) not in sys.path:
    sys.path.insert(0, str(MCP_SOURCE))

from novelos_mcp.errors import NovelOSError  # noqa: E402
from novelos_mcp.seed_inventory import validate_seed_database  # noqa: E402


def _json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _seed_ready(authorization: str) -> bool:
    if "结论：`authorized`" not in authorization:
        return False
    seed = ROOT / "mcp" / "novelos" / "resources" / "seed.db"
    inventory = ROOT / "mcp" / "novelos" / "resources" / "seed-inventory.json"
    source_inventory = _json(ROOT / "tasks" / "migration" / "seed_source_inventory.json")
    if source_inventory is None:
        return False
    try:
        production = validate_seed_database(seed, inventory)
    except (NovelOSError, OSError):
        return False
    return (
        production.get("source_commit") == source_inventory.get("source_commit")
        and production.get("source_hash") == source_inventory.get("source_hash")
        and production.get("table_count") == source_inventory.get("table_count") == 23
        and production.get("row_count") == source_inventory.get("row_count") == 8108
        and production.get("tables") == source_inventory.get("tables")
    )


def _quality_deferred(agent_contract: str) -> bool:
    deferral = _json(QUALITY_DEFERRAL)
    return bool(
        deferral
        and deferral == {
            "schema_version": 1,
            "status": "deferred",
            "decision": "conservative-routing",
            "writer_policy": "retain-unvalidated-complete-chapter-only",
            "context_builder_policy": "exception-only",
            "partial_results_non_authoritative": True,
            "reason": "用户决定将完整 70-case 真实 Agent 质量实验推后，不阻塞纯 Codex 基础设施切换。",
            "resume_requirement": "完成全部 70 个唯一 case、独立 Reviewer、Receipt 和可重算 summary.json 后才能改变路由策略。",
        }
        and "spawn_condition: complete_chapter_or_long_scene_required" in agent_contract
        and "spawn_condition: cross_volume_or_context_overflow" in agent_contract
        and "evidence_field: complexity_reasons" in agent_contract
    )


def build() -> dict[str, Any]:
    docs = {
        "architecture.md",
        "flows.md",
        "permissions.md",
        "variables.md",
        "tests.md",
        "automation.md",
    }
    actual_docs = {path.name for path in (ROOT / "documentation").glob("*.md")}
    restore = _json(ROOT / "tasks" / "migration" / "schema9_restore_drill.json")
    export_drill = _json(ROOT / "tasks" / "migration" / "schema9_export_drill.json")
    quality = _json(DEFAULT_RESULTS / "summary.json")
    quality_evidence_valid = summary_is_current(DEFAULT_DATASET, DEFAULT_RESULTS)
    authorization = (ROOT / "tasks" / "migration" / "seed_authorization_audit.md").read_text(encoding="utf-8")
    codex_config = (ROOT / ".codex" / "config.toml").read_text(encoding="utf-8")
    config_example_path = ROOT / "config.example.toml"
    config_example = config_example_path.read_text(encoding="utf-8") if config_example_path.is_file() else ""
    agent_contract = (ROOT / "config" / "agents.yaml").read_text(encoding="utf-8")
    legacy_paths = [
        "src/novelos/agents",
        "src/novelos/application.py",
        "src/novelos/models.py",
        "src/novelos/skills",
        "src/novelos/mcp",
        "src/novelos/storage",
        "src/novelos/domain",
    ]
    git_baseline = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    ).returncode == 0
    hygiene = build_hygiene()
    hygiene_current = HYGIENE_REPORT.is_file() and HYGIENE_REPORT.read_text(encoding="utf-8") == render_hygiene(hygiene)
    quality_complete = bool(
        quality_evidence_valid
        and quality
        and quality.get("status") == "completed"
        and quality.get("writer_decision") in {"retain", "remove"}
        and quality.get("context_builder_decision") in {"exception_only", "remove"}
    )
    quality_deferred = _quality_deferred(agent_contract)
    gates = {
        "documentation_complete": actual_docs == docs,
        "unified_runner_ready": (ROOT / "scripts" / "run_novelos_mcp.sh").is_file(),
        "cutover_plan_valid": plan_is_valid(),
        "database_restore_drill_passed": bool(
            restore
            and restore.get("restore_drill") == "passed"
            and export_drill
            and export_drill.get("export_restore_drill") == "passed"
            and export_drill.get("logical_snapshot") == restore.get("logical_snapshot")
        ),
        "repository_hygiene_prepared": bool(
            hygiene_current
            and hygiene.get("prohibited_file_count") == 0
            and hygiene.get("sensitive_file_count") == 0
        ),
        "seed_authorized": _seed_ready(authorization),
        "quality_experiment_complete": quality_complete,
        "quality_experiment_deferred": quality_deferred,
        "quality_experiment_dispositioned": quality_complete or quality_deferred,
        "codex_config_switched": (
            "[mcp_servers.novelos]" in codex_config
            and "scripts/run_novelos_mcp.sh" in codex_config
            and "novelos-memory" not in codex_config
        ),
        "legacy_runtime_removed": not any((ROOT / path).exists() for path in legacy_paths),
        "legacy_model_config_removed": (
            not config_example_path.exists()
            and "[model]" not in config_example
            and "OPENAI_API_KEY" not in config_example
            and "OPENAI_MODEL" not in config_example
        ),
        "git_review_baseline_available": git_baseline,
    }
    informational = {"quality_experiment_complete"}
    blockers = sorted(name for name, passed in gates.items() if not passed and name not in informational)
    return {
        "schema_version": 1,
        "status": "ready" if not blockers else "not_ready",
        "gates": gates,
        "blockers": blockers,
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="检查 NovelOS 纯 Codex 切换就绪度")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = render(build())
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != content:
            raise SystemExit(f"切换就绪报告不是最新结果：{args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
