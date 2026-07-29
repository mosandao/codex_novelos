from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "tasks" / "cutover" / "removal_manifest.json"
REQUIRED_TOP_LEVEL = {
    "schema_version",
    "phase",
    "preconditions",
    "delete_paths",
    "modify_paths",
    "preserve_paths",
    "postconditions",
}
REQUIRED_DELETE_PATHS = {
    "src/novelos",
    "scripts/run_memory_mcp.sh",
    "pyproject.toml",
    "config.example.toml",
    "tests/test_architecture.py",
    "tests/test_config.py",
}
REQUIRED_PRECONDITIONS = {
    "seed_authorized",
    "quality_experiment_dispositioned",
    "git_review_baseline_available",
    "database_restore_drill_passed",
}
ALLOWED_LEGACY_ASSERTION_PATHS = {
    "scripts/check_cutover_plan.py",
    "scripts/check_cutover_readiness.py",
    "tests/test_shipping_artifacts.py",
}
LEGACY_PATTERNS = (
    re.compile(r"\bfrom\s+novelos(?:\.|\s|$)"),
    re.compile(r"\bimport\s+novelos(?:\.|\s|$)"),
    re.compile(r"novelos-memory|run_memory_mcp\.sh|OPENAI_MODEL|OPENAI_API_KEY|\[model\]|openai>=|novelos\.cli"),
)


class CutoverPlanError(ValueError):
    pass


def _relative_path(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise CutoverPlanError(f"{label} 必须是非空相对路径")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise CutoverPlanError(f"{label} 不能是绝对路径或逃逸仓库")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CutoverPlanError(f"{label} 逃逸仓库") from exc
    return resolved


def load_and_validate(root: Path = ROOT, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CutoverPlanError(f"无法读取 cutover manifest：{manifest_path}") from exc
    if not isinstance(payload, dict) or set(payload) != REQUIRED_TOP_LEVEL:
        raise CutoverPlanError("cutover manifest 顶层字段不匹配")
    if payload["schema_version"] != 1 or payload["phase"] not in {"prepared", "cutover"}:
        raise CutoverPlanError("cutover manifest schema_version 或 phase 非法")
    if set(payload["preconditions"]) != REQUIRED_PRECONDITIONS:
        raise CutoverPlanError("cutover preconditions 不完整")
    if not isinstance(payload["postconditions"], list) or not payload["postconditions"]:
        raise CutoverPlanError("cutover postconditions 不能为空")

    delete_entries = payload["delete_paths"]
    modify_entries = payload["modify_paths"]
    if not isinstance(delete_entries, list) or not isinstance(modify_entries, list):
        raise CutoverPlanError("delete_paths 和 modify_paths 必须是数组")
    delete_paths: dict[str, Path] = {}
    for entry in delete_entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "category", "reason", "replacements"}:
            raise CutoverPlanError("delete_paths 条目字段不匹配")
        path = str(entry["path"])
        if path in delete_paths:
            raise CutoverPlanError(f"重复删除路径：{path}")
        delete_paths[path] = _relative_path(root, path, "delete path")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise CutoverPlanError(f"删除路径缺少理由：{path}")
        if not isinstance(entry["replacements"], list) or not entry["replacements"]:
            raise CutoverPlanError(f"删除路径缺少替代证据：{path}")
        for replacement in entry["replacements"]:
            replacement_path = _relative_path(root, replacement, "replacement")
            if not replacement_path.exists():
                raise CutoverPlanError(f"替代路径不存在：{replacement}")
    if set(delete_paths) != REQUIRED_DELETE_PATHS:
        raise CutoverPlanError(
            f"删除范围不完整：缺少 {sorted(REQUIRED_DELETE_PATHS - set(delete_paths))}，未知 {sorted(set(delete_paths) - REQUIRED_DELETE_PATHS)}"
        )

    modify_paths: dict[str, Path] = {}
    for entry in modify_entries:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "required_after_cutover",
            "forbidden_after_cutover",
        }:
            raise CutoverPlanError("modify_paths 条目字段不匹配")
        path = str(entry["path"])
        if path in modify_paths or path in delete_paths:
            raise CutoverPlanError(f"重复或冲突修改路径：{path}")
        modify_paths[path] = _relative_path(root, path, "modify path")
        if not modify_paths[path].is_file():
            raise CutoverPlanError(f"待修改文件不存在：{path}")
        if not isinstance(entry["required_after_cutover"], list) or not isinstance(
            entry["forbidden_after_cutover"], list
        ):
            raise CutoverPlanError(f"待修改文件规则非法：{path}")

    preserve = payload["preserve_paths"]
    if not isinstance(preserve, list) or len(preserve) != len(set(preserve)):
        raise CutoverPlanError("preserve_paths 必须是唯一数组")
    for value in preserve:
        path = _relative_path(root, value, "preserve path")
        if not path.exists():
            raise CutoverPlanError(f"保留路径不存在：{value}")
        for deleted in delete_paths.values():
            if path == deleted or deleted in path.parents:
                raise CutoverPlanError(f"保留路径落在删除范围内：{value}")

    scan_paths = [root / "src", root / "scripts", root / "tests", root / ".codex"]
    scan_paths.extend(root / name for name in ("pyproject.toml", "config.example.toml"))
    candidates: list[Path] = []
    for path in scan_paths:
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(
                item
                for item in path.rglob("*")
                if item.is_file() and "__pycache__" not in item.parts and item.suffix in {".py", ".sh", ".toml"}
            )
    uncovered: list[str] = []
    for path in candidates:
        relative = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not any(pattern.search(content) for pattern in LEGACY_PATTERNS):
            continue
        covered = relative in modify_paths or relative in ALLOWED_LEGACY_ASSERTION_PATHS
        if not covered:
            resolved = path.resolve()
            covered = any(resolved == deleted or deleted in resolved.parents for deleted in delete_paths.values())
        if not covered:
            uncovered.append(relative)
    if uncovered:
        raise CutoverPlanError(f"发现未纳入清单的旧 Runtime 引用：{sorted(uncovered)}")

    if payload["phase"] == "prepared":
        missing = [path for path, resolved in delete_paths.items() if not resolved.exists()]
        if missing:
            raise CutoverPlanError(f"prepared 阶段待删除路径必须仍存在：{missing}")
    else:
        remaining = [path for path, resolved in delete_paths.items() if resolved.exists()]
        if remaining:
            raise CutoverPlanError(f"cutover 阶段仍有旧路径：{remaining}")
        for entry in modify_entries:
            content = modify_paths[str(entry["path"])].read_text(encoding="utf-8")
            missing = [value for value in entry["required_after_cutover"] if value not in content]
            forbidden = [value for value in entry["forbidden_after_cutover"] if value in content]
            if missing or forbidden:
                raise CutoverPlanError(
                    f"cutover 文件未满足目标：{entry['path']}，缺少 {missing}，残留 {forbidden}"
                )
    return payload


def plan_is_valid(root: Path = ROOT, manifest_path: Path = DEFAULT_MANIFEST) -> bool:
    try:
        load_and_validate(root, manifest_path)
    except CutoverPlanError:
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 NovelOS 最终切换删除与修改清单")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true", help="保留用于统一验证命令的显式检查标志")
    args = parser.parse_args()
    try:
        load_and_validate(ROOT, args.manifest)
    except CutoverPlanError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
