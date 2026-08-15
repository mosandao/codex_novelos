#!/usr/bin/env python3
"""harness 适配层单源生成器 + 一致性校验器。

build：从 adapters/source/harness.yaml 生成 adapters/README.md（三 harness 接入指引，
内容哈希锚定事实源——改 source 不重新生成 = check 红）。
check：一致性校验——① README 与 source 同步；② AGENTS.md 含组装器分流指引；
③ .agents/skills 无指向已注册资产的旧式 prompt.md 注入指令（防 P0-3 类矛盾复发）。

用法：
  .venv/bin/python scripts/novelos_build_adapters.py           # build + check
  .venv/bin/python scripts/novelos_build_adapters.py --check   # 只校验
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "adapters/source/harness.yaml"
README = ROOT / "adapters/README.md"
AGENTS = ROOT / "AGENTS.md"
SKILLS_DIR = ROOT / ".agents/skills"


def _render(source: dict) -> str:
    lines = [
        "# Harness 适配层（codex / zcode / deepseek）",
        "",
        f"> 事实源 `adapters/source/harness.yaml`（content_hash: `{_source_hash(source)}`）。",
        "> 本文件由 `scripts/novelos_build_adapters.py` 生成——改事实源后必须重新生成。",
        "",
        "## 核心契约（三家共用，零变体）",
        "",
        f"- **sub agent ABI**：{source['core_contract']['sub_agent_abi']}",
        f"- **主控只做三件事**：{'；'.join(source['core_contract']['main_agent_duties'])}",
        "",
        "## 接入指引",
        "",
    ]
    for name, cfg in source["harnesses"].items():
        entries = "、".join(cfg["entry_files"]) if cfg["entry_files"] else "（待确认）"
        lines += [f"### {name}", "",
                  f"- **入口文件**：{entries}",
                  f"- {cfg['notes']}", ""]
    lines += ["## 验证命令（任何 harness 改动后必跑）", ""]
    lines += [f"```bash\n{c}\n```" if i == 0 else c
              for i, c in enumerate(source['core_contract']['verify_commands'])]
    lines += ["", f"（生成于 build 时；事实源 content_hash `{_source_hash(source)}` 锚定同步）"]
    return "\n".join(lines) + "\n"


def _source_hash(source: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def build() -> None:
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    README.write_text(_render(source), encoding="utf-8")
    print(f"built {README.relative_to(ROOT)}")


def check() -> list[str]:
    errors: list[str] = []
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8") if README.exists() else ""
    if _source_hash(source) not in readme:
        errors.append("adapters/README.md 与 source/harness.yaml 漂移——运行 build 重新生成")
    agents = AGENTS.read_text(encoding="utf-8")
    if "novelos_compose_prompt.py" not in agents or "ASSET_DIRS" not in agents:
        errors.append("AGENTS.md 缺组装器分流指引（ASSET_DIRS 注册表）")
    # 已注册资产的旧式注入指令检测
    sys.path.insert(0, str(ROOT))
    from scripts.novelos_compose_prompt import ASSET_DIRS
    for skill_dir in ASSET_DIRS.values():
        rel = skill_dir.relative_to(ROOT)
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            text = skill_md.read_text(encoding="utf-8")
            if f"Read `{rel}/prompt.md`" in text:
                errors.append(f"{skill_md.relative_to(ROOT)} 含指向已注册资产 {rel} 的旧式注入指令")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="只校验不生成")
    args = parser.parse_args()
    if not args.check:
        build()
    errors = check()
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    if errors:
        return 1
    print("adapters check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
