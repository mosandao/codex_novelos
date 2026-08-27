# NovelOS Agent 规则（零 Python）

本仓库已完成**零 Python 演进路线**（路线与验证记录见 `tasks/README.md`）：全部业务写门已 JS 化并收口为插件 defineTool（见「数据库访问」节），方法论组装器已 JS 化（见「方法论获取」节），`legacy-python/` 与 `.venv` 已删除，全仓无任何 .py。

## 分层架构

```
L0 权威存储   data/novelos-v2.db + config/（schemas ×18 · genre-packs（wizard-data.js 同步镜像，scripts/test-guardrails.mjs 守卫）· system_archetypes）
              —— schemas 与 SQL migrations 与语言无关，是 JS 门直接复用的资产
L1 运行时     插件 host JS 工具（唯一读写口，目标态达成）
L2 方法论     catalog/skills/**（prompt.md 主干 + modules/ + manifest v2）——语言无关，原样有效
L3 组装产物   data/compositions/
L4 harness 适配 adapters/（单源 adapters/source/harness.yaml）
L5 会话编排   .agents/skills/novel-*（六个操作层技能）+ 本文件路由协议
UI            plugin/dsh-novelos/（DSH 插件：侧栏+检查器+向导三件套 client/ · 原型 docs/prototype/novelos-dsh-panel.html）
```

## 数据库访问

**写路径**：唯一写入口 = `dsh-novelos-viewer` 插件 defineTool 门工具（ajv 校验 + node:sqlite BEGIN IMMEDIATE 单事务，FAIL 返回 ok:false 零写入）：

| 工具 | 用途 |
|---|---|
| `novelos_gate_entry` | 入口校验（只读）：向导 payload 结构+词表级联+内核反查 |
| `novelos_kernel_commit` | 内核候选校验落库；mode=create 可缝合返回 boundPayload |
| `novelos_project_commit` | 分身六表单事务落库；mismatch 须 `userAdjudicated:true`（F2 裁决门红线） |
| `novelos_register_characters` | 人物重锁登记/动态配角/状态迁移；pendingStatus/auditEntries 只读对账 |
| `novelos_propagate_stale` | 上游修订后沿依赖图标 stale（fine=精细不误伤） |
| `novelos_delete_project` | 项目整体删除（dryRun 调查/backup 备份/cleanOrphans 孤儿清理） |
| `novelos_review_commit` | Review Receipt 落库（reviewer_profile 须 `model:<provider:model>` 或 `agent:<name>@<model>` 格式——防共谋机器留痕） |
| `novelos_lock_asset` | 规划资产锁定：须绑定 approved 审查回执（封跳审/错绑），旧 locked 翻 superseded |
| `novelos_accept_chapter` | 章节接受：写 chapters.review_id 机器痕迹；已接受再改默认拒绝（force 仅 hash 未变时幂等重放） |
| `novelos_validate_asset` | R4 数字门（只读）：七件资产校验器语义（scale 规则表/量化阈值/席位对账），锁定前自查 |

状态机约束：`candidate → locked` 与章节接受必须经门工具完成并留下 review 关联（`db/migrations/019_state_machine_links.sql` 的 chapters.review_id）；裸 `UPDATE … SET status='locked'/'accepted'` 已退役。

禁止手工 INSERT/UPDATE 绕过门直接写库——agent 没有裸 SQL 写通道。写库三件事已在门内固化：① ID 格式 `类型:uuid`；② resources.content 经 BLOB 写入并同步 content_hash。

**读路径**：人类看 `dsh-novelos-viewer` 面板（sql.js 只读）；agent 查库用一次性 node:sqlite 只读查询。Python MCP 通道与 legacy-python 校验门均已删除，不要再寻找它们。

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

已注册资产一律用组装器产出注入文本（主干 + 条件模块 + 输入数据区 + 自检汇总），资产分流以 `scripts/novelos-compose-prompt.mjs` 的 ASSET_DIRS 注册表为准，不 Read prompt.md、不手工拼注入：

```
node scripts\novelos-compose-prompt.mjs --asset <asset> --project <id>
审查另加 --subject；修复重试加 --review-feedback + --round
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

收到「创建小说项目」请求，首步打开 `dsh-novelos` 侧栏「＋」的「项目向导」弹层（host 托管 `/novelos/wizard` 路由，kernel 名册由 host 经 node:sqlite 实时直查，无需刷新镜像）；面板不可用时允许浏览器直接打开 `plugin/dsh-novelos/client/project-wizard.html`（file:// 离线模式）。流程：向导产出 `novelos.project.create.v3` JSON → 入口校验门（FAIL 拒绝）→ mode=create 先建核（kernel-fusion 注入 → 融合 agent → 校验门落库）→ 分身派生 → 单事务六表落库。

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
