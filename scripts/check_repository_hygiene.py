#!/usr/bin/env python3
"""检查 NovelOS 仓库的 prospective Git 文件集和本地敏感产物。"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "tasks" / "cutover" / "hygiene.json"
REQUIRED_IGNORE_RULES = {
    "__pycache__/",
    "*.py[cod]",
    ".venv/",
    ".pytest_cache/",
    "*.egg-info/",
    "data/*.db",
    "data/*.db-*",
    "data/**/*.db",
    "data/**/*.db-*",
    "data/exports/",
    "novels/",
    ".DS_Store",
    "*.log",
    ".env",
    ".env.*",
    "!.env.example",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
}
IGNORE_REPRESENTATIVES = (
    "scratch/__pycache__/module.pyc",
    ".venv/bin/python",
    "data/local.db",
    "data/migration/local.db-wal",
    "data/exports/book/manifest.json",
    "novels/example/README.md",
    ".DS_Store",
    "server.log",
    ".env.local",
    "private.pem",
)
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
GENERATED_SUFFIXES = {".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".log", ".p12", ".pfx", ".pem", ".key"}
GENERATED_PARTS = {"__pycache__", ".venv", ".pytest_cache"}
ALLOWED_TRACKED_BINARIES = {"mcp/novelos/resources/seed.db"}


class HygieneError(ValueError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=check,
    )


def _paths(payload: bytes) -> list[str]:
    return sorted(item.decode("utf-8", errors="strict") for item in payload.split(b"\0") if item)


def _is_prohibited(path: str) -> bool:
    if path in ALLOWED_TRACKED_BINARIES:
        return False
    candidate = Path(path)
    if any(part in GENERATED_PARTS or part.endswith(".egg-info") for part in candidate.parts):
        return True
    if candidate.name == ".DS_Store" or candidate.name == ".env" or candidate.name.startswith(".env."):
        return candidate.name != ".env.example"
    lower = path.lower()
    return any(lower.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def _sensitive_files(root: Path) -> list[str]:
    results: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in {".git", ".venv"} for part in relative.parts):
            continue
        name = path.name
        if (
            name == ".env"
            or (name.startswith(".env.") and name != ".env.example")
            or path.suffix.lower() in SENSITIVE_SUFFIXES
        ):
            results.append(relative.as_posix())
    return sorted(results)


def build(root: Path = ROOT) -> dict[str, Any]:
    ignore_path = root / ".gitignore"
    try:
        rules = {
            line.strip()
            for line in ignore_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError as exc:
        raise HygieneError("无法读取 .gitignore") from exc
    missing_rules = sorted(REQUIRED_IGNORE_RULES - rules)
    if missing_rules:
        raise HygieneError(f".gitignore 缺少规则：{missing_rules}")

    for representative in IGNORE_REPRESENTATIVES:
        result = _git(root, "check-ignore", "--no-index", "-q", "--", representative, check=False)
        if result.returncode != 0:
            raise HygieneError(f"生成或敏感产物未被忽略：{representative}")

    tracked = _paths(_git(root, "ls-files", "-z").stdout)
    prospective = _paths(_git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout)
    report_relative = DEFAULT_OUTPUT.relative_to(ROOT).as_posix() if root == ROOT else "tasks/cutover/hygiene.json"
    prospective = [path for path in prospective if path != report_relative]
    prohibited = sorted(path for path in prospective if _is_prohibited(path))
    if prohibited:
        raise HygieneError(f"prospective Git 文件集包含禁止产物：{prohibited}")
    sensitive = _sensitive_files(root)
    if sensitive:
        raise HygieneError(f"仓库内发现本地敏感文件：{sensitive}")

    baseline = _git(root, "rev-parse", "--verify", "HEAD", check=False).returncode == 0
    return {
        "schema_version": 1,
        "status": "passed" if baseline else "prepared",
        "git_baseline_available": baseline,
        "tracked_file_count": len(tracked),
        "prospective_file_count": len(prospective),
        "prohibited_file_count": 0,
        "sensitive_file_count": 0,
        "required_ignore_rules": sorted(REQUIRED_IGNORE_RULES),
        "allowed_tracked_binaries": sorted(ALLOWED_TRACKED_BINARIES),
    }


# 工作树瞬时计数：随开发者未跟踪文件、git 状态波动，不进入黄金快照比对。
# 禁止产物检测仍由 ``build()`` 即时执行并经 ``prohibited_file_count`` 报告，
# 因此剥离这两个计数不会放松安全门禁，只消除合法未跟踪文件造成的快照假阳性。
INSTANTANEOUS_FIELDS = ("prospective_file_count", "tracked_file_count")


def snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """从 ``build()`` 结果派生结构性快照：剥离随工作树瞬时状态波动的计数。

    安全语义不变——``build()`` 已对禁止产物和敏感文件 fail-closed，剥离的仅是
    「此刻 git 跟踪/未跟踪文件总数」这两个诊断计数，避免开发者临时文件让黄金文件失配。
    """
    return {key: value for key, value in payload.items() if key not in INSTANTANEOUS_FIELDS}


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="生成或校验 NovelOS 仓库产物卫生报告")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        report = build()
    except (HygieneError, OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    content = render(snapshot(report))
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != content:
            raise SystemExit(f"仓库卫生报告不是当前 prospective Git 文件集结果：{args.output}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
