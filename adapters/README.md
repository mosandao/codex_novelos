# Harness 适配层（codex / zcode / deepseek）

> 事实源 `adapters/source/harness.yaml`（content_hash: `sha256:1fdc1b1d92aadd5d`）。
> 本文件由 `scripts/novelos_build_adapters.py` 生成——改事实源后必须重新生成。

## 核心契约（三家共用，零变体）

- **sub agent ABI**：组装产物文件（novelos_compose_prompt.py 的 stdout / data/compositions/ 落盘件）——三家用同一份，零变体
- **主控只做三件事**：跑脚本（.venv/bin/python scripts/*.py）；读文件（组装产物 / catalog 方法论）；把组装产物交给 sub agent

## 接入指引

### codex

- **入口文件**：AGENTS.md
- 读取仓库根 AGENTS.md 作为主控规则；无独立 skill 注册机制，sub agent 由主控按 Agent 工具派发。

### zcode

- **入口文件**：AGENTS.md、.agents/skills/novel-*/SKILL.md
- AGENTS.md 为主控规则；六个 novel-* SKILL.md 是技能入口（含 SQL 细节的操作层，手写维护、非生成物，仅做一致性校验）。

### deepseek

- **入口文件**：（待确认）
- 入口约定未确认（T29-P4-2 BLOCKED）——确认后在本文件登记 entry_files 与注册方式，重新生成 README。

## 验证命令（任何 harness 改动后必跑）

```bash
.venv/bin/python -m unittest discover -s tests
```
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check

（生成于 build 时；事实源 content_hash `sha256:1fdc1b1d92aadd5d` 锚定同步）
