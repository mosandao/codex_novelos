# NovelOS Agent 规则

作为本仓库唯一长期存在的**主控智能体**：理解需求、规划任务、选择最小执行方式、汇总结果。

## 分层架构

```
L0 权威存储   data/novelos-v2.db + config/（schemas / system_archetypes / genre-packs）
L1 确定性运行时 scripts/（compose / create / validate / propagate / hash / render / adapters）
L2 方法论组件 catalog/skills/**（prompt.md 主干 + modules/ + manifest v2）
L3 组装产物   data/compositions/（content_hash + 命中模块 + 槽位清单——可追溯地基）
L4 harness 适配 adapters/（单源 adapters/source/harness.yaml → 生成 README + 一致性校验）
L5 会话编排  .agents/skills/novel-*（手写操作层）+ 本文件路由协议
```

## 数据库访问

**SQLite MCP** 是数据库唯一入口（`execute_sql` 读写 `data/novelos-v2.db`）。MCP 不可用时用 `.venv/bin/python -c "import sqlite3; ..."`。SQL 模板见 `.agents/skills/novel-project/sql-reference.md`。

写库三件事：① ID 格式 `类型:uuid`（Python `uuid.uuid4()`）；② 写 `resources.content` 必须 `CAST(? AS BLOB)`；③ 写 resource 同时算 content_hash（`scripts/novelos_hash.py`）。

确定性脚本：`novelos_create_project.py`（创建管线：入口校验→候选容错→校验门→单事务落库，**禁止手工 INSERT 绕过**）、`novelos_compose_prompt.py`（方法论组装器）、`novelos_hash.py`、`novelos_validate_book_soul.py`、`novelos_render_projection.py`、`novelos_propagate_stale.py`、`novelos_delete_project.py`、`novelos_build_adapters.py`。

## 路由顺序

1. 简单读写/搜索/Git/浏览器/API 直接执行。
2. 有业务流程不需隔离上下文的任务，加载项目 Skill（`.agents/skills/novel-*`）。
3. 需要隔离上下文或大范围推理时创建 sub agent（Agent 工具）。

## 规划资产依赖顺序

direction → architecture → strategy → character‖world（可并行）→ story_arc → volume_outline → chapter_plan。资产存 `planning_assets`，状态 `candidate` → `locked` → （上游变更时）`stale`；上游修订后运行 `novelos_propagate_stale.py`。

## Agent 角色

| Agent | 资产 | catalog 目录 |
|---|---|---|
| 引导融合（onboarding） | 作者签名融合 | `onboarding/creator-signature-fusion` |
| 方向 | `direction` | `planning/story-direction` |
| 架构 | `architecture` | `planning/story-architecture` |
| 策略 | `strategy` | `planning/story-strategy` |
| 人物 ‖ 世界 | `character_contract` / `world_contract` | `planning/character-contract` / `world-contract` |
| 故事弧 | `story_arc` | `planning/story-arc` |
| 卷规划 | `volume_outline` | `planning/volume-outline` |
| 章节规划 | `chapter_plan` | `planning/chapter-plan-execution-card` |
| 写作 | 正文 | `writing/chapter-draft-generation` |
| 审查 | Review Receipt | `review/*`（每资产对偶 + 横切三审查） |
| 连续性 | 六类账本 | `continuity/continuity-candidate-extraction` |

**方法论获取（按资产分流，以 `novelos_compose_prompt.py` 的 ASSET_DIRS 注册表为准）**：已注册资产用组装器 `--asset <asset> --project <id>`（审查另加 `--subject`；修复重试加 `--review-feedback` + `--round`；语义路由加 `--proposal`）一步产出完整注入文本——主干 + 条件模块 + 输入数据区（persona/上游原文/canon 最小集/craft 卡）+ 自检汇总，不 Read prompt.md、不手工拼注入。组装产物即主控↔sub agent 的 ABI（三家 harness 零变体，见 `adapters/README.md`）。配方矩阵（每资产的槽位×发散档位×决策权限×输出契约）权威在 `config/agent-recipes.json`。

## 小说工作流

1. `$novel-memory` 组织上下文（canon 最小集经组装器注入；定制检索才手查）。
2. `$novel-writing` 起草（composer `--asset chapter-draft` 出厂注入 → sub agent → SQL INSERT）。
3. `$novel-review` 审查（composer `--asset <asset>-review --subject <id>` → INSERT reviews）。
4. **审查-修复循环**：blocking+warning 必须修复，修复 = 新 revision 经 `--review-feedback` 受控重组装；只剩 note 才锁定/接受。**循环边界：3 轮未收敛或同因复发 → 升级用户裁决，禁止无限打转**（详见 novel-review SKILL）。
5. 接受后 `$novel-continuity` 提取连续性。已接受章节局部修改可直接 UPDATE，除非改变章节状态。

## 创作方法论

- `catalog/skills/` 是方法论唯一来源；阶段配方（发散档位 expansive/balanced/constrained × 决策权限 propose_only/judge/execute/flag）见 `config/agent-recipes.json` 与 `documentation/agent-recipes.md`。
- Writer 必须遵守 `style_refs`（Creator Profile + Direction）；persona 的 `blindspots.cannot_write` 是硬边界——盲区场景必须按条目绕开方式处理（转喻/侧写/留白/借他人之口），全知叙述假装在场 = persona 未生效，prose-quality-review 判 blocking。
- `book_soul` 属 Story Direction（v2 十三字段含 power_currency），用 `scripts/novelos_validate_book_soul.py` 校验。

## 项目创建向导

**强制首步**：收到「创建/新建小说项目」请求，第一个动作必须是 `open ui/project-wizard.html`。禁止用 CLI 问卷/自由文本替代（频道级联、原型打分、人格素材编辑都依赖页面交互）。仅用户明确无法用浏览器时才 fallback 并说明原因。

流程：① 向导产出 `novelos.project.create.v2` JSON（setup v2 + selected_archetypes + user_persona_hints）；② **入口校验** `novelos_create_project.py --payload <json>`（schema + 词表级联 + 原型三方比对，FAIL 拒绝）；③ **原型融合** `novelos_compose_prompt.py --asset fusion --payload <json>` 产出完整注入文本 → 引导融合智能体（先立人再落规，含跨批次指纹去重）；④ **落库** `--payload <json> --candidate <json>`（校验门 + 单事务六表，禁手工 INSERT）。`parent_rationale` 含错配警告时**呈报用户裁决，未获裁决不落库**；候选解析失败要求 agent 重出，主控禁改写内容。一书一分身是有意设计（只允许 derive，无 reuse）。

**setup 变更**（连载中改频道/平台/基调）：① `UPDATE projects SET metadata_json = json_set(metadata_json,'$.setup',json('…'))`；② 立即全部 locked 资产标 stale（propagate_stale）重走审查。禁止静默改后继续写作。

## 用户投影

`novelos_render_projection.py --project <id> --output novels/` 渲染权威库为 Markdown 目录（创作约束/规划/大纲/正文/人物/世界/连续性/manifest）。单向派生，编辑不回写。

## 重要约束

- **NovelOS MCP 已彻底删除**（migration 016 已删门禁表，源码不在仓库），不要尝试恢复。SQLite MCP wrapper 在 `mcp/sqlite-mcp/`，由 `.codex/config.toml` 注册。
- **数据库备份**：任何 schema 变更前 `cp data/novelos-v2.db data/novelos-v2.db.bak`。
- **换 harness 指引**：核心（SQLite + Python 脚本 + Markdown 方法论）harness 中立；适配差异只在入口件（见 `adapters/README.md`），catalog 与 scripts 零改动。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

## 任务连续性

执行多阶段工作前先读 `tasks/README.md`。状态只用 `TODO` / `IN PROGRESS` / `DONE` / `BLOCKED`；从依赖已满足的第一个未完成项继续；生产路径接通且验证通过才 `DONE`。`/Users/yiyi/github/novelos` 只读。

## 书写语言

`AGENTS.md`、`tasks/`、项目 SKILL.md 与维护文档默认中文；代码标识符、命令、路径、SQL 关键字与状态字面量保持英文。
