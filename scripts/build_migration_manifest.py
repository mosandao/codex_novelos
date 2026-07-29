#!/usr/bin/env python3
"""从只读 Git commit 生成 NovelOS 迁移盘点文件。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sqlite3
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


MANIFEST_FIELDS = (
    "source_commit",
    "source_path",
    "source_hash",
    "target_path",
    "classification",
    "license_origin",
    "reason",
    "tests_to_port",
    "status",
)
CLASSIFICATIONS = {"direct", "adapt", "defer", "reject"}


@dataclass(frozen=True)
class Decision:
    classification: str
    target_path: str
    reason: str
    tests_to_port: str


def git(source: Path, *args: str, text: bool = True, quiet: bool = False) -> str | bytes:
    return subprocess.check_output(
        ["git", "-C", str(source), *args],
        text=text,
        stderr=subprocess.DEVNULL if quiet else None,
    )


def target_under(prefix: str, source_path: str, marker: str) -> str:
    relative = source_path.split(marker, 1)[1]
    return f"{prefix}/{relative}"


def classify(source_path: str) -> Decision:
    reject_prefixes = (
        "frontend/",
        "backend/src/presentation/",
        "backend/src/application/runtime/",
        "backend/src/application/sub_agents/",
        "backend/src/infrastructure/llm/",
    )
    if source_path.startswith(reject_prefixes):
        return Decision("reject", "-", "旧 UI、LLM 或 Agent Runtime 不进入纯 Codex 生产路径", "not_applicable")
    if "__pycache__" in source_path or source_path.endswith((".pyc", ".pyo")):
        return Decision("reject", "-", "生成缓存不是迁移来源", "not_applicable")
    if source_path == "backend/src/infrastructure/sqlite/seed.db":
        return Decision(
            "direct",
            "mcp/novelos/resources/seed.db",
            "只读知识库按内容 Hash 原样迁移",
            "mcp/novelos/tests/test_seed_integrity.py",
        )
    if source_path.startswith("backend/src/domain/"):
        target = target_under("mcp/novelos/src/novelos_mcp/domain", source_path, "backend/src/domain/")
        return Decision("adapt", target, "提取领域契约并移除旧 Runtime 耦合", "mcp/novelos/tests/domain")
    if source_path.startswith("backend/src/infrastructure/sqlite/"):
        name = source_path.rsplit("/", 1)[-1]
        if any(token in name for token in ("shadow", "work_completion", "writer_shadow")):
            return Decision("defer", "-", "Shadow 或高级完成度存储不属于 V1", "deferred-wave-d")
        target = target_under("mcp/novelos/src/novelos_mcp/storage", source_path, "backend/src/infrastructure/sqlite/")
        return Decision("adapt", target, "迁移 Schema、Repository 与事务语义", "mcp/novelos/tests/storage")
    if source_path.startswith("backend/src/infrastructure/plugin/"):
        target = target_under("mcp/novelos/src/novelos_mcp/catalog", source_path, "backend/src/infrastructure/plugin/")
        return Decision("adapt", target, "保留 Catalog 硬过滤、Schema 和 Validator，删除语义路由", "mcp/novelos/tests/catalog")
    if source_path.startswith("backend/plugins/"):
        target = target_under("mcp/novelos/catalog", source_path, "backend/plugins/")
        return Decision("adapt", target, "迁移为按需 Catalog 包并补充 provenance", "mcp/novelos/tests/catalog")
    if source_path.startswith("backend/src/application/"):
        deferred_tokens = (
            "/evaluation/",
            "shadow",
            "automation_promotion",
            "work_completion",
            "recovery",
            "evidence_case_freeze",
        )
        if any(token in source_path for token in deferred_tokens):
            return Decision("defer", "-", "高级评测、Shadow、恢复或自动晋级延后", "deferred-wave-d")
        target = target_under("mcp/novelos/migration_specs/application", source_path, "backend/src/application/")
        return Decision("adapt", target, "只提取契约、确定性校验和失败语义，不复制编排 Runtime", "mcp/novelos/tests/services")
    if source_path.startswith("backend/tests/"):
        name = source_path.rsplit("/", 1)[-1]
        if any(token in source_path for token in ("/fixtures/", "evaluation", "shadow", "recovery", "work_completion")):
            return Decision("defer", "-", "高级或夹具场景随对应能力波次迁移", "deferred-test-fixture")
        target = f"mcp/novelos/tests/ported/{name}"
        return Decision("adapt", target, "移植为 Domain、Storage、Catalog 或 MCP 协议回归场景", target)
    if source_path.startswith("backend/resources/"):
        return Decision("defer", "-", "资源需先完成许可证和实际消费者审查", "deferred-resource-audit")
    if source_path == "docs/third_party/awesome_novel_skill.md":
        return Decision(
            "adapt",
            "mcp/novelos/catalog/provenance/awesome_novel_skill.md",
            "保留 awesome-novel-skill 的 GPL-3.0 与用户授权来源记录",
            "mcp/novelos/tests/catalog/test_provenance.py",
        )
    if source_path.startswith(("docs/", "tasks/", "scripts/", "backend/scripts/")):
        return Decision("defer", "-", "仅作为迁移参考，不进入 V1 生产包", "documentation-review")
    return Decision("reject", "-", "仓库配置、说明或旧构建入口不直接迁移", "not_applicable")


def license_for(source_path: str) -> str:
    if source_path.startswith("backend/plugins/craft/") or source_path in {
        "docs/third_party/awesome_novel_skill.md",
        "docs/awesome_novel_migration_plan.md",
    }:
        return "awesome-novel-skill:GPL-3.0:user-authorized"
    if source_path.startswith("backend/resources/autonomous/external_writing_reference"):
        return "external-reference:license-unverified:research-only"
    return "novelos-repository:license-unverified"


def scalar(metadata: str, key: str) -> str:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", metadata)
    if not match:
        return ""
    return match.group(1).strip().strip('"\'')


def table_wave(name: str) -> tuple[str, str]:
    wave_a = {"projects", "books", "volumes", "chapters", "characters", "worlds", "factions", "rules", "timelines", "reviews"}
    wave_b = {
        "chapter_facts", "continuity_candidate_sets", "continuity_update_results",
        "chapter_completion_checkpoints", "narrative_promises", "expectation_ledgers",
        "relationship_states", "arc_states",
    }
    wave_c_prefixes = ("planning_", "architecture_", "story_planning_", "story_direction_")
    if name in wave_a:
        return "A", "核心创作数据"
    if name in wave_b:
        return "B", "记忆与连续性"
    if name.startswith(wave_c_prefixes) or name == "prompt_recipes":
        return "C", "规划资产"
    return "D", "高级完成度或未确认消费者"


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(source: Path, commit_ref: str, output_dir: Path) -> None:
    commit = str(git(source, "rev-parse", commit_ref)).strip()
    tree = str(git(source, "rev-parse", f"{commit}^{{tree}}")).strip()
    paths = str(git(source, "ls-tree", "-r", "--name-only", commit)).splitlines()

    skill_metadata: dict[str, str] = {}
    for source_path in paths:
        if re.match(r"^backend/plugins/[^/]+/skills/[^/]+/metadata\.yaml$", source_path):
            skill_metadata[source_path.rsplit("/", 1)[0]] = git(
                source, "show", f"{commit}:{source_path}", text=False
            ).decode("utf-8")

    manifest: list[dict[str, str]] = []
    backend_python_files = 0
    backend_python_lines = 0
    backend_test_files = 0
    for source_path in paths:
        content = git(source, "show", f"{commit}:{source_path}", text=False)
        decision = classify(source_path)
        if source_path.startswith("backend/plugins/") and "/skills/" in source_path:
            parts = source_path.split("/")
            skill_root = "/".join(parts[:5])
            lifecycle = scalar(skill_metadata.get(skill_root, ""), "lifecycle") or "unspecified"
            if lifecycle != "active":
                decision = Decision("defer", "-", f"Skill lifecycle={lifecycle}，完成质量评测前不进入生产 Catalog", "deferred-skill-evaluation")
        if source_path.startswith("backend/src/") and source_path.endswith(".py"):
            backend_python_files += 1
            backend_python_lines += len(content.decode("utf-8").splitlines())
        if source_path.startswith("backend/tests/test_") and source_path.endswith(".py"):
            backend_test_files += 1
        manifest.append({
            "source_commit": commit,
            "source_path": source_path,
            "source_hash": f"sha256:{hashlib.sha256(content).hexdigest()}",
            "target_path": decision.target_path,
            "classification": decision.classification,
            "license_origin": license_for(source_path),
            "reason": decision.reason,
            "tests_to_port": decision.tests_to_port,
            "status": {"direct": "planned", "adapt": "planned", "defer": "deferred", "reject": "rejected"}[decision.classification],
        })
    write_csv(output_dir / "source_manifest.csv", MANIFEST_FIELDS, manifest)

    schema_path = "backend/src/infrastructure/sqlite/schema.sql"
    schema = git(source, "show", f"{commit}:{schema_path}", text=False).decode("utf-8")
    tables = sorted(set(re.findall(r"(?im)^CREATE TABLE(?: IF NOT EXISTS)?\s+([a-zA-Z0-9_]+)", schema)))
    table_rows = []
    for name in tables:
        wave, reason = table_wave(name)
        table_rows.append({"table_name": name, "wave": wave, "reason": reason, "status": "planned" if wave != "D" else "deferred"})
    write_csv(output_dir / "table_inventory.csv", ("table_name", "wave", "reason", "status"), table_rows)

    skill_rows = []
    for skill_root, metadata in sorted(skill_metadata.items()):
        source_path = f"{skill_root}/metadata.yaml"
        parts = source_path.split("/")
        skill_rows.append({
            "plugin": parts[2],
            "skill": parts[4],
            "source_path": source_path,
            "source_hash": f"sha256:{hashlib.sha256(metadata.encode('utf-8')).hexdigest()}",
            "lifecycle": scalar(metadata, "lifecycle") or "unspecified",
            "stage": scalar(metadata, "stage") or "unspecified",
            "asset": scalar(metadata, "asset") or "unspecified",
            "capability": scalar(metadata, "capability") or "unspecified",
            "license_origin": license_for(source_path),
        })
    write_csv(
        output_dir / "skill_inventory.csv",
        ("plugin", "skill", "source_path", "source_hash", "lifecycle", "stage", "asset", "capability", "license_origin"),
        skill_rows,
    )

    seed_content = git(source, "show", f"{commit}:backend/src/infrastructure/sqlite/seed.db", text=False)
    with tempfile.NamedTemporaryFile(suffix=".db") as temporary:
        temporary.write(seed_content)
        temporary.flush()
        connection = sqlite3.connect(f"file:{temporary.name}?mode=ro", uri=True)
        seed_tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'kb_%' ORDER BY name"
            )
        ]
        seed_rows = [
            {"table_name": name, "record_count": str(connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])}
            for name in seed_tables
        ]
        connection.close()
    write_csv(output_dir / "seed_inventory.csv", ("table_name", "record_count"), seed_rows)

    dirty_rows = []
    status_text = str(git(source, "status", "--porcelain=v1"))
    for line in status_text.splitlines():
        status = line[:2]
        dirty_path = line[3:]
        if " -> " in dirty_path:
            dirty_path = dirty_path.split(" -> ", 1)[1]
        worktree_path = source / dirty_path
        worktree_hash = "-"
        if worktree_path.is_file():
            worktree_hash = f"sha256:{hashlib.sha256(worktree_path.read_bytes()).hexdigest()}"
        try:
            head_content = git(source, "show", f"{commit}:{dirty_path}", text=False, quiet=True)
            head_hash = f"sha256:{hashlib.sha256(head_content).hexdigest()}"
        except subprocess.CalledProcessError:
            head_hash = "-"
        dirty_rows.append({
            "status": status,
            "path": dirty_path,
            "head_hash": head_hash,
            "worktree_hash": worktree_hash,
            "disposition": "excluded_from_committed_source",
        })
    write_csv(
        output_dir / "dirty_inventory.csv",
        ("status", "path", "head_hash", "worktree_hash", "disposition"),
        dirty_rows,
    )

    classifications = Counter(row["classification"] for row in manifest)
    waves = Counter(row["wave"] for row in table_rows)
    tracked_diff = git(source, "diff", "--binary", commit, text=False)
    untracked_paths = str(git(source, "ls-files", "--others", "--exclude-standard")).splitlines()
    untracked_fingerprint = hashlib.sha256()
    for path in sorted(untracked_paths):
        untracked_fingerprint.update(path.encode("utf-8"))
        untracked_fingerprint.update(b"\0")
        candidate = source / path
        if candidate.is_file():
            untracked_fingerprint.update(hashlib.sha256(candidate.read_bytes()).digest())
        untracked_fingerprint.update(b"\0")
    status_hash = hashlib.sha256(status_text.encode("utf-8")).hexdigest()
    seed_record_count = sum(int(row["record_count"]) for row in seed_rows)
    snapshot = (
        f'source_repository = "{source}"\n'
        f'source_ref = "{commit_ref}"\n'
        f'source_commit = "{commit}"\n'
        f'source_tree = "{tree}"\n'
        'source_policy = "committed-head-only"\n'
        f'file_count = {len(paths)}\n'
        f'backend_python_file_count = {backend_python_files}\n'
        f'backend_python_line_count = {backend_python_lines}\n'
        f'backend_test_file_count = {backend_test_files}\n'
        f'skill_count = {len(skill_rows)}\n'
        f'table_count = {len(table_rows)}\n'
        f'seed_knowledge_table_count = {len(seed_rows)}\n'
        f'seed_knowledge_record_count = {seed_record_count}\n'
        f'dirty_status_count_observed = {len(dirty_rows)}\n'
        f'dirty_status_sha256 = "sha256:{status_hash}"\n'
        f'tracked_diff_sha256 = "sha256:{hashlib.sha256(tracked_diff).hexdigest()}"\n'
        f'untracked_files_sha256 = "sha256:{untracked_fingerprint.hexdigest()}"\n'
        f'manifest_direct = {classifications["direct"]}\n'
        f'manifest_adapt = {classifications["adapt"]}\n'
        f'manifest_defer = {classifications["defer"]}\n'
        f'manifest_reject = {classifications["reject"]}\n'
        f'tables_wave_a = {waves["A"]}\n'
        f'tables_wave_b = {waves["B"]}\n'
        f'tables_wave_c = {waves["C"]}\n'
        f'tables_wave_d = {waves["D"]}\n'
        'license_note = "No repository-level license file at source commit; preserve per-source provenance and fail closed before content migration."\n'
    )
    (output_dir / "source_snapshot.toml").write_text(snapshot, encoding="utf-8")


def validate(output_dir: Path) -> None:
    with (output_dir / "source_manifest.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or tuple(rows[0]) != MANIFEST_FIELDS:
        raise ValueError("Manifest 字段不完整")
    paths = [row["source_path"] for row in rows]
    if len(paths) != len(set(paths)):
        raise ValueError("Manifest 存在重复 source_path")
    targets = [row["target_path"] for row in rows if row["classification"] in {"direct", "adapt"}]
    if len(targets) != len(set(targets)):
        raise ValueError("Manifest 存在重复生产 target_path")
    for row in rows:
        if row["classification"] not in CLASSIFICATIONS:
            raise ValueError(f"非法分类: {row['classification']}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", row["source_hash"]):
            raise ValueError(f"非法 Hash: {row['source_path']}")
        if not all(row[field] for field in MANIFEST_FIELDS):
            raise ValueError(f"Manifest 空字段: {row['source_path']}")
        migrates = row["classification"] in {"direct", "adapt"}
        if migrates == (row["target_path"] == "-"):
            raise ValueError(f"目标路径与分类冲突: {row['source_path']}")
    for inventory_name, key in (
        ("table_inventory.csv", "table_name"),
        ("skill_inventory.csv", "source_path"),
        ("seed_inventory.csv", "table_name"),
        ("dirty_inventory.csv", "path"),
    ):
        with (output_dir / inventory_name).open(encoding="utf-8", newline="") as handle:
            inventory = list(csv.DictReader(handle))
        values = [row[key] for row in inventory]
        if len(values) != len(set(values)):
            raise ValueError(f"{inventory_name} 存在重复 {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("/Users/yiyi/github/novelos"))
    parser.add_argument("--commit", default="HEAD")
    parser.add_argument("--output-dir", type=Path, default=Path("tasks/migration"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        build(args.source.resolve(), args.commit, args.output_dir)
    validate(args.output_dir)


if __name__ == "__main__":
    main()
