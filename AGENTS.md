# NovelOS Agent 规则（零 Python 演进期）

本仓库正在执行**零 Python 演进路线**（路线图见 `tasks/README.md`）：视图链已 JS 化，写路径校验门暂存 `legacy-python/` 待 JS 门替代。本文件按过渡期现状书写，R1/R2 交付后同步收敛。

## 分层架构

```
L0 权威存储   data/novelos-v2.db + config/（schemas ×18 · genre-packs · system_archetypes）
              —— schemas 与 SQL migrations 与语言无关，是 JS 门直接复用的资产
L1 运行时     目标态：插件 host JS 工具（唯一读写口）
              过渡态：legacy-python/scripts/*.py（只维护不新增，待整体删除）
L2 方法论     catalog/skills/**（prompt.md 主干 + modules/ + manifest v2）——语言无关，原样有效
L3 组装产物   data/compositions/
L4 harness 适配 adapters/（单源 adapters/source/harness.yaml）
L5 会话编排   .agents/skills/novel-*（六个操作层技能）+ 本文件路由协议
UI            plugin/client/（viewer 原型 docs/novelos-viewer-prototype.html + wizard 三件套）
```

## 数据库访问（过渡期规则）

**写路径**：当前唯一守门人 = `legacy-python\scripts\novelos_create_project.py`（jsonschema 门 + BEGIN IMMEDIATE 单事务）。禁止手工 INSERT 绕过校验门直接写库。写库三件事不变：① ID 格式 `类型:uuid`；② 写 `resources.content` 必须 `CAST(? AS BLOB)`；③ 写 resource 同时算 content_hash。R2 交付后写入口收敛为插件 defineTool，届时 legacy-python 整体删除。

**读路径**：人类看 `dsh-novelos-viewer` 面板（sql.js 只读）；agent 查库用一次性 node:sqlite 查询或等插件查询工具就绪。Python MCP 通道已删除，不要再寻找它。

## 路由顺序

1. 简单读写/搜索/Git/浏览器/API 直接执行。
2. 有业务流程不需隔离上下文的任务，加载项目 Skill（`.agents/skills/novel-*`）。
3. 需要隔离上下文或大范围推理时创建 sub agent。

## 规划资产依赖顺序

direction → architecture → strategy → world → character → story_arc → volume_outline → chapter_plan。
世界先行：world 设岗位不造人，character 认领席位；上游修订沿依赖边自动标 stale 并运行传播。资产存 `planning_assets`，状态 `candidate` → `locked` → （上游变更时）`stale`。

## Agent 角色

| Agent | 资产 | catalog 目录 |
|---|---|---|
| 内核融合 | author_kernel（create/revise，八维五段式+四归因） | `onboarding/author-kernel-fusion` |
| 分身融合 | creator_signature（parent=内核版本） | `onboarding/creator-signature-fusion` |
| 方向／架构／策略／世界／人物／故事弧／卷纲／章纲 | direction / architecture / strategy / world_contract / character_contract / story_arc / volume_outline / chapter_plan | `planning/*` |
| 写作 | 正文（persona 盲区硬边界：转喻/侧写/留白绕开） | `writing/*` |
| 审查 | Review Receipt（blocking+warning 必修） | `review/*` |
| 连续性 | 六账本+人物状态候选 | `continuity/*` |

## 方法论获取

已注册资产一律用组装器产出注入文本（主干 + 条件模块 + 输入数据区 + 自检汇总），资产分流以 `legacy-python\scripts\novelos_compose_prompt.py` 的 ASSET_DIRS 注册表为准，不 Read prompt.md、不手工拼注入：

```
python legacy-python\scripts\novelos_compose_prompt.py --asset <asset> --project <id>
审查另加 --subject；修复重试加 --review-feedback + --round
（注意：过渡期运行 py 门用仓库根 `.venv\Scripts\python.exe`——由 `py -3.10 -m venv .venv` 重建，装 jsonschema+pyyaml；全局 Python 是 3.15.0a7 alpha，rpds DLL 不兼容不可用）
```

配方矩阵权威在 `config/agent-recipes.json`；组装产物即主控↔sub agent 的 ABI（三家 harness 零变体）。

## 多模型分工

角色→模型映射存 `dsh-novelos-viewer` 设置卡（roleWriter/roleReviewer/roleMemory，格式 `provider:model` 或裸 model 名，留空=沿用主会话模型）。编排前调 `novelos_model_roles` 工具（或面板 `/model-roles` 路由）读取，再在 workflow/subagent 按 per-agent provider/model 覆盖：写作=强创意模型；审查=异构厂商模型（防共谋）；记忆提取=廉价快速模型。方法论与校验门均模型无关——映射只影响编排，不改代码。

## 小说工作流

1. `$novel-memory` 组织上下文（canon 最小集经组装器注入）。
2. `$novel-writing` 起草 → sub agent → 经校验门落库。
3. `$novel-review` 审查：blocking+warning 必修，修复 = 新 revision 受控重组装；3 轮未收敛或同因复发 → 升级用户裁决，禁止无限打转。
4. `$novel-continuity` 提取连续性：账本候选与注册表对账漂移非零退出，处理完才开下一章。
5. **用户实时打断与修改（最高优先级）**：任何阶段用户提出修改——①暂停生成与提交；②按影响面分流（setup 级→UPDATE+全量 stale 重审；资产级→change proposal 走上游修订；章内级→审查回执受控重组装）；③呈报影响面清单获确认后执行。禁止以「生成进行中」为由推迟用户指令。

## 项目创建向导

收到「创建小说项目」请求，首步打开 `dsh-novelos-viewer` 面板的「项目向导」入口（host 托管 `/api/wizard`，kernel 名册由 host 经 node:sqlite 实时直查，无需刷新镜像）；面板不可用时允许浏览器直接打开 `plugin/client/project-wizard.html`（file:// 离线模式）。流程：向导产出 `novelos.project.create.v3` JSON → 入口校验门（FAIL 拒绝）→ mode=create 先建核（kernel-fusion 注入 → 融合 agent → 校验门落库）→ 分身派生 → 单事务六表落库。

## 重要约束

- **零 Python 纪律**：新增工具/脚本一律 JS（Node 22+，node:sqlite/ajv/crypto）；不得在 scripts/ 新建 .py。
- **单渲染器**：HTML(JS) 是唯一人类视图；md 投影已退役，不要重建。
- **数据库备份**：任何 schema 变更前先复制 `data/novelos-v2.db`。
- **裁决门红线**：mismatch 仅警告即放行 = 纸面化（红队 F2 教训），任何门 FAIL 必须阻断退出。
- `/Users/yiyi/github/novelos` 只读（生产环境）。

## 任务连续性

多阶段工作前读 `tasks/README.md`（零 Python 路线图 + 重组裁决记录）；历史账本在 `docs/archive/tasks/`。状态只用 `TODO`/`IN PROGRESS`/`DONE`/`BLOCKED`；生产路径接通且验证通过才 `DONE`。

## 书写语言

文档默认中文；代码标识符、命令、路径、SQL 关键字与状态字面量保持英文。
