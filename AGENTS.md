# NovelOS Agent 规则（零 Python）

本仓库已完成**零 Python 演进路线**（路线与验证记录见 `tasks/README.md`）：方法论组装器已 JS 化（见「方法论获取」节），`legacy-python/` 与 `.venv` 已删除，全仓无任何 .py。**插件时代已结束**：`plugin/`（DSH 插件与 defineTool 写门）已移除退役，数据库读写改为 node:sqlite 直连（见「数据库访问」节）。

## 分层架构

```
L0 权威存储   data/novelos-v2.db + config/（schemas ×18 · genre-packs（唯一词表源，scripts/test-guardrails.mjs 守卫）· system_archetypes）
              —— schemas 与 SQL migrations 与语言无关，是落库前自查复用的资产
L1 运行时     主控 agent + node:sqlite（读=一次性只读查询；写=机器门 novelos-gate.mjs 优先，门未覆盖的幂等读改受控事务直写）
L2 方法论     catalog/skills/**（prompt.md 主干 + modules/ + manifest v2）——语言无关，原样有效
L3 组装产物   data/compositions/
L4 harness 适配 adapters/（单源 adapters/source/harness.yaml）
L5 会话编排   .agents/skills/novel-*（六个操作层技能）+ 本文件路由协议
UI            md 投影（scripts/novelos-render-projection.mjs，node:sqlite 只读单向渲染到 novels/，可重建；viewer 面板已退役，不重建 HTML 视图层）
```

## 数据库访问

**写路径**：写库由主控 agent 经 node:sqlite 事务直写（`BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON`，任一步失败整体回滚零写入）。SQL 模板唯一来源 = `.agents/skills/novel-project/sql-reference.md`；落库前对照 `config/schemas/*.json` 自查。sub agent 不持有数据库访问手段，只返回候选文本，所有持久化由主控完成。

原插件 defineTool 门工具（`novelos_gate_entry` / `novelos_kernel_commit` / `novelos_project_commit` / `novelos_register_characters` / `novelos_propagate_stale` / `novelos_delete_project` / `novelos_review_commit` / `novelos_lock_asset` / `novelos_accept_chapter` / `novelos_validate_asset`）已随 `plugin/` 移除退役——机器校验不再存在，其语义约束转为下列纪律（主控自查执行）：

状态机约束：`candidate → locked` 与章节接受必须留下 review 关联（`db/migrations/019_state_machine_links.sql` 的 chapters.review_id）——锁定资产须绑定 `verdict='approved'` 且 `subject_ref` 匹配的回执；章节接受须写 `review_id` 留痕；已接受章节不得免审直改（降级 draft → 改 → 重审 → 重接受）。项目创建遇 mismatch 必须用户裁决后才落库（红队 F2「纸面化裁决门」教训）。

写库三约定：① ID 格式 `类型:uuid`；② resources.content 经 BLOB 写入并同步 content_hash（`'sha256:'+hex`，node:crypto 计算）；③ 多表写入单事务，任一步失败整体回滚。**第四约定（R7 起）**：关键状态写入优先走机器门 `scripts/novelos-gate.mjs`（commit-review/lock-asset/accept-chapter/propagate-stale/register-characters/validate-asset；dry-run 默认，写库须 `--commit`+生产库 `--allow-production`；GateFail=阻断零写入），门未覆盖的幂等读改才走受控 SQL 直写。

**读路径**：agent 查库用一次性 node:sqlite 只读查询；人类浏览用任意 SQLite 工具只读打开 `data/novelos-v2.db`，或打开 `node scripts/novelos-render-projection.mjs --project <id> --verify` 渲染出的 `novels/` 投影目录阅读。Python MCP 通道、legacy-python 校验门与 DSH 插件均已删除，不要再寻找或重建它们。

## 路由顺序

1. 简单读写/搜索/Git/浏览器/API 直接执行。
2. 有业务流程不需隔离上下文的任务，加载项目 Skill（`.agents/skills/novel-*`）。
3. 需要隔离上下文或大范围推理时创建 sub agent。

## 规划资产依赖顺序

direction → architecture → strategy → world → character → story_arc → volume_outline → chapter_plan。
世界先行：world 设岗位不造人，character 认领席位；上游修订沿依赖边标 stale 并传播。资产存 `planning_assets`，状态 `candidate` → `locked` → （上游变更时）`stale`。

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

角色→模型分工由主控在编排时显式指定（格式 `provider:model` 或裸 model 名）：写作=强创意模型；审查=异构厂商模型（防共谋，reviewer_profile 留机器身份前缀）；记忆提取=廉价快速模型。在 workflow/subagent 按 per-agent provider/model 覆盖。方法论与校验基准均模型无关——映射只影响编排，不改代码。

默认映射（主控编排首选，随 API key 可用性调整；完整方案与备选见 `docs/model-roles.md`）：
- 写作：`deepseek-v4-pro`（备选 `minimax-m3`）
- 审查：`zai-coding-cn:glm-5.3`（备选 `kimi-k3` 仅关键章双审；与写作端必须不同厂商）
- 记忆提取：`glm-5.3-flash`（备选 `deepseek-v4-flash`）
- 视觉：`glm-4v-flash`（已配置）

## 小说工作流

1. `$novel-memory` 组织上下文（canon 最小集经组装器注入）。
2. `$novel-writing` 起草 → sub agent → 主控按 sql-reference.md 模板落库（draft）。落库前跑 `node scripts/novelos-prose-fingerprint.mjs --text-file <draft>` 预筛（screen 命中即候选，只报事实不判级），候选清单由主控手工附审查注入尾部并标注「仅供证伪，须逐条 confirm（`fpr:<ID>`）或 deny（`fpr-deny:<ID>`）+理由」；修订轮 UPDATE 分支重跑预筛并更新 `metadata_json.prescreen`。
3. `$novel-review` 审查：blocking+warning 必修，修复 = 新 revision 受控重组装；3 轮未收敛或同因复发 → 升级用户裁决，禁止无限打转。回执落库前跑 `node scripts/novelos-verify-review-evidence.mjs --receipt <回执> --draft <该版草稿>` 引文验证，FATAL（excerpt 无命中/缺失/subject_hash 错配/空 findings+approved 空查回执——R7-A1 起默认拦截，确需放行加 `--allow-empty` 并留痕）即打回、不得落库。
4. `$novel-continuity` 提取连续性：账本候选落库后与人物注册表对账（SQL 见 sql-reference.md），有漂移即处理完才开下一章。
5. **用户实时打断与修改（最高优先级）**：任何阶段用户提出修改——①暂停生成与提交；②按影响面分流（setup 级→UPDATE+全量 stale 重审；资产级→change proposal 走上游修订；章内级→审查回执受控重组装）；③呈报影响面清单获确认后执行。禁止以「生成进行中」为由推迟用户指令。

## 项目创建向导

收到「创建小说项目」请求，主控按以下流程编排（向导 UI 已随插件退役）：

1. 与用户确认项目约束（频道/平台/题材/表里基调/作者内核 select 或 create 双模式），产出 `novelos.project.create.v3` 形态的 JSON 载荷。
2. 载荷落库前对照 `config/schemas/project-create-request.schema.json`（v3）自查：结构 + 词表级联 + 表里互斥 + select 模式内核库内反查（版本存在 + ownership='author_kernel' + status='active' + subject_hash 相符）。自查 FAIL 拒绝继续。
3. mode=create 先建核：`node scripts/novelos-compose-prompt.mjs --asset kernel-fusion --payload <json>` 产出内核融合注入文本，交给融合 agent 产出 `novelos.kernel.candidate.v1`；对照 `config/schemas/author-kernel.schema.json` 自查后按 sql-reference.md「作者内核链」落库。
4. 分身派生：`node scripts/novelos-compose-prompt.mjs --asset fusion --payload <json>` 注入引导融合智能体（onboarding_agent），产出 `creator_derivation_candidate`；对照 `config/schemas/creator-signature.schema.json` 自查（persona 必填、cannot_write 非空、七字段无逐字复制内核 identity）。
5. 主控以 node:sqlite 单事务六表落库（模板见 sql-reference.md「作者签名链」）：resources×2（签名 + 派生记录含完整用户输入快照）→ creator_profiles/versions → projects（metadata_json 写 setup v3 快照）→ project_creator_bindings。parent_rationale 含错配标记时先呈报用户裁决再落库。

## 重要约束

- **零 Python 纪律**：新增工具/脚本一律 JS（Node 22+，node:sqlite/crypto）；不得在 scripts/ 新建 .py。
- **单渲染器 = md 投影**：人类视图只有 `novels/` 项目投影一条通道（`node scripts/novelos-render-projection.mjs --project project:xxx --verify`），只读派生、可删除重建、直接改文件不回写数据库；viewer 面板与独立 HTML/Web 渲染器已退役，不要重建。
- **数据库备份**：任何 schema 变更前先复制 `data/novelos-v2.db`。
- **裁决纪律**：mismatch 仅警告即放行 = 纸面化（红队 F2 教训）；项目创建 mismatch 必须用户裁决，审查有 blocking 不得锁定/接受。
- `/Users/yiyi/github/novelos` 只读（生产环境）。

## 任务连续性

多阶段工作前读 `tasks/README.md`（路线图 + 裁决记录）；历史账本在 `docs/archive/tasks/`。状态只用 `TODO`/`IN PROGRESS`/`DONE`/`BLOCKED`；生产路径接通且验证通过才 `DONE`。

## 书写语言

文档默认中文；代码标识符、命令、路径、SQL 关键字与状态字面量保持英文。
