#!/usr/bin/env python3
"""从只读 Git commit 和来源工作树生成 NovelOS Prompt Catalog 迁移清单。

支持默认写入和 --check 两种模式。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

FIELDNAMES = (
    "source_state",
    "source_ref",
    "source_path",
    "source_hash",
    "metadata_path",
    "lifecycle",
    "license_origin",
    "existing_disposition",
)


@dataclass(frozen=True)
class PromptInventoryRow:
    source_state: str
    source_ref: str
    source_path: str
    source_hash: str
    metadata_path: str
    lifecycle: str
    license_origin: str
    existing_disposition: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_state": self.source_state,
            "source_ref": self.source_ref,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "metadata_path": self.metadata_path,
            "lifecycle": self.lifecycle,
            "license_origin": self.license_origin,
            "existing_disposition": self.existing_disposition,
        }


def compute_sha256(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def parse_metadata_lifecycle(metadata_file: Path) -> str:
    if not metadata_file.exists():
        return "uncommitted"
    try:
        content = metadata_file.read_text(encoding="utf-8")
        match = re.search(r"^lifecycle:\s*([a-zA-Z0-9_\-]+)", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return "uncommitted"


def load_source_snapshot(project_root: Path) -> tuple[Path, str]:
    snapshot_path = project_root / "tasks" / "migration" / "source_snapshot.toml"
    if not snapshot_path.exists():
        raise RuntimeError(f"Snapshot config missing: {snapshot_path}")
    with snapshot_path.open("rb") as f:
        data = tomllib.load(f)
    repo = Path(data.get("source_repository", "/Users/yiyi/github/novelos"))
    commit = data.get("source_commit", "")
    if not commit or len(commit) != 40 or not re.match(r"^[0-9a-fA-F]{40}$", commit):
        raise ValueError(f"Invalid source_commit: {commit}")
    return repo, commit


def load_catalog_dispositions(project_root: Path) -> list[dict[str, str]]:
    disp_path = project_root / "tasks" / "migration" / "catalog_disposition.csv"
    if not disp_path.exists():
        raise RuntimeError(f"Disposition file missing: {disp_path}")
    with disp_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    if len(rows) != 138:
        raise ValueError(f"Expected 138 disposition rows, got {len(rows)}")
    return rows


def build_inventory(project_root: Path) -> list[PromptInventoryRow]:
    repo_path, source_commit = load_source_snapshot(project_root)
    disp_rows = load_catalog_dispositions(project_root)

    rows: list[PromptInventoryRow] = []
    committed_prompt_paths: set[str] = set()
    disp_map: dict[str, dict[str, str]] = {}

    for d in disp_rows:
        meta_rel = d["source_path"]  # e.g. backend/plugins/craft/skills/dash_ellipsis_guide/metadata.yaml
        if not meta_rel.endswith("metadata.yaml"):
            raise ValueError(f"Unexpected source_path in disposition: {meta_rel}")
        prompt_rel = meta_rel[:-13] + "prompt.md"

        if prompt_rel in committed_prompt_paths:
            raise ValueError(f"Duplicate prompt path in disposition: {prompt_rel}")
        committed_prompt_paths.add(prompt_rel)
        disp_map[prompt_rel] = d

        # Read prompt from git commit
        try:
            prompt_bytes = subprocess.check_output(
                ["git", "-C", str(repo_path), "show", f"{source_commit}:{prompt_rel}"],
                stderr=subprocess.PIPE,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to git show {source_commit}:{prompt_rel}: {e.stderr.decode()}") from e

        prompt_hash = compute_sha256(prompt_bytes)

        rows.append(
            PromptInventoryRow(
                source_state="committed",
                source_ref=source_commit,
                source_path=prompt_rel,
                source_hash=prompt_hash,
                metadata_path=meta_rel,
                lifecycle=d["lifecycle"],
                license_origin=d["license_origin"],
                existing_disposition=d["disposition"],
            )
        )

    # Check worktree
    try:
        status_out = subprocess.check_output(
            ["git", "-C", str(repo_path), "status", "--porcelain"],
            text=True,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run git status on {repo_path}: {e.stderr.decode()}") from e

    # Find candidate worktree skills under backend/plugins/
    # We look for skill directories in git status or filesystem under backend/plugins/
    plugins_dir = repo_path / "backend" / "plugins"
    if plugins_dir.exists():
        for prompt_file in plugins_dir.glob("**/skills/*/prompt.md"):
            rel_prompt = str(prompt_file.relative_to(repo_path))
            rel_meta = str(prompt_file.parent.relative_to(repo_path) / "metadata.yaml")
            meta_file = prompt_file.parent / "metadata.yaml"

            if not meta_file.exists():
                continue

            content_bytes = prompt_file.read_bytes()
            curr_hash = compute_sha256(content_bytes)

            if rel_prompt in committed_prompt_paths:
                # Check if modified relative to commit
                committed_row = next(r for r in rows if r.source_path == rel_prompt)
                if curr_hash != committed_row.source_hash:
                    rows.append(
                        PromptInventoryRow(
                            source_state="worktree_modified",
                            source_ref="WORKTREE",
                            source_path=rel_prompt,
                            source_hash=curr_hash,
                            metadata_path=rel_meta,
                            lifecycle=parse_metadata_lifecycle(meta_file),
                            license_origin=committed_row.license_origin,
                            existing_disposition="excluded_from_committed_source",
                        )
                    )
            else:
                # Uncommitted new package
                rows.append(
                    PromptInventoryRow(
                        source_state="worktree_uncommitted",
                        source_ref="WORKTREE",
                        source_path=rel_prompt,
                        source_hash=curr_hash,
                        metadata_path=rel_meta,
                        lifecycle=parse_metadata_lifecycle(meta_file),
                        license_origin="unverified",
                        existing_disposition="excluded_from_committed_source",
                    )
                )

    # Sort rows by source_state, source_path
    rows.sort(key=lambda r: (r.source_state, r.source_path))
    return rows


def generate_csv_content(rows: list[PromptInventoryRow]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.to_dict())
    return out.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build prompt migration inventory CSV.")
    parser.add_argument("--check", action="store_true", help="Check CSV against expected calculation without modifying file.")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent
    target_csv = project_root / "tasks" / "07_prompt_catalog" / "source_prompt_inventory.csv"

    try:
        rows = build_inventory(project_root)
        expected_content = generate_csv_content(rows)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    committed_count = sum(1 for r in rows if r.source_state == "committed")
    uncommitted_count = sum(1 for r in rows if r.source_state == "worktree_uncommitted")
    modified_count = sum(1 for r in rows if r.source_state == "worktree_modified")

    if committed_count != 138:
        print(f"ERROR: Committed prompt count ({committed_count}) != 138", file=sys.stderr)
        return 1

    if args.check:
        if not target_csv.exists():
            print(f"ERROR: Target CSV does not exist: {target_csv}", file=sys.stderr)
            return 1
        current_content = target_csv.read_text(encoding="utf-8")
        if current_content != expected_content:
            print("ERROR: Inventory CSV out of sync with calculation.", file=sys.stderr)
            return 1
        print(f"OK: Inventory CSV is up to date ({committed_count} committed, {uncommitted_count} uncommitted, {modified_count} modified).")
        return 0
    else:
        target_csv.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        temp_file = target_csv.with_suffix(".tmp")
        temp_file.write_text(expected_content, encoding="utf-8")
        temp_file.replace(target_csv)
        print(f"SUCCESS: Wrote inventory to {target_csv} ({committed_count} committed, {uncommitted_count} uncommitted, {modified_count} modified).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
