# Harness 适配层（codex / zcode / deepseek）

> 事实源 `adapters/source/harness.yaml`（content_hash: `sha256:a23ea7aa70740693`）。
> 本文件由 `legacy-python/scripts/novelos_build_adapters.py` 生成——改事实源后必须重新生成。

## 核心契约（三家共用，零变体）

- **sub agent ABI**：组装产物文件（novelos_compose_prompt.py 的 stdout / data/compositions/ 落盘件）——三家用同一份，零变体
- **主控只做三件事**：跑脚本（python legacy-python/scripts/*.py）；读文件（组装产物 / catalog 方法论）；把组装产物交给 sub agent

## 接入指引

### codex

- **入口文件**：AGENTS.md
- 读取仓库根 AGENTS.md 作为主控规则；无独立 skill 注册机制，sub agent 由主控按 Agent 工具派发。

### zcode

- **入口文件**：AGENTS.md、.agents/skills/novel-*/SKILL.md
- AGENTS.md 为主控规则；六个 novel-* SKILL.md 是技能入口（含 SQL 细节的操作层，手写维护、非生成物，仅做一致性校验）。

### deepseek

- **入口文件**：~/github/novelos/backend/config.yaml（NOVELOS_CONFIG 可覆盖）、入口服务：uvicorn src.presentation.main:app --port 6100（FastAPI）
- 自托管 NovelOS backend harness（~/github/novelos，只读仓）。三要素——① 入口 = FastAPI 服务（非 CLI 读 AGENTS.md），配置 backend/config.yaml；② 命令/技能注册 = PluginKernel + backend/plugins/ 插件目录（craft/derivative/game/... 题材包，经 /skills 页面写入），SubAgent 自持 prompt contract（SubContext.kernel 注入 PluginKernel 自行 load+assemble）；③ sub agent = SubAgent Protocol（src/application/runtime/sub_agent.py：run(task, SubContext, llm) -> SubResult，无状态纯函数不碰库，Runtime 经 CommitBatch 持久化），LLM 经多 provider gateway 路由（可路由 DeepSeek API；指令技术源自 deepseek 指令库回填）。对接方式 = 组装产物作为 skill_prompt/snippets 注入 SubContext（ABI 对应物）。

## 验证命令（任何 harness 改动后必跑）

```bash
python -m unittest discover -s legacy-python/tests
```
python -m compileall -q legacy-python/scripts legacy-python/tests catalog config
python legacy-python/scripts/check_repository_hygiene.py --check
python legacy-python/scripts/build_catalog_manifest.py --check

（生成于 build 时；事实源 content_hash `sha256:a23ea7aa70740693` 锚定同步）
