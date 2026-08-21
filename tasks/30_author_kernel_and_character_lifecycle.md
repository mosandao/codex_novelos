# Task 30: 作者内核双层架构 + 创作链深度参与 + 人物全量设计与生命周期

**状态**: `IN PROGRESS`

**范围**: 本任务把《作者内核、心理运作与作品设计指导规范》（外部规范，研究对照报告见会话记录）中仓库缺失的四层方法论制度化：①作者内核层（跨书持久内核 + 成长记录 + 修正归因）②心理与知识层（心理运作八维 + 知识生态）③作品世界层（规则六角色 / 三类规则分层 / 力量-规则循环 / 开局无敌冲突转移）④叙事对象层（角色死亡 / 退场七型 / 人物状态账本 / 全量主要人物设计）。四根柱子（权威 SQLite、依赖有序规划资产、方法论即 skill、审查门）不动。

## 决策登记（用户已裁决，2026-08-21）

1. **内核跨题材一致**：每本书从内核派生分身，按题材适配不同文风/手法。
2. **内核完全取代原型**：向导不再选原型，纯 hints 建内核；`config/system_archetypes.json` 降为参考资料库（保留文件，退出创建链路）。已有项目与旧分身不受影响。
3. **内核深度参与创作链**：方向 → 人物 → 写作 → 审查全链注入消费。
4. **主要人物全量设计**（不只主角），次要角色通过动态创建（规划端预登记 + 接受后落账）。
5. **道德债以女频为主**；男频/全向仅作功能性出现（反派/圣母驱动、谈资、吐槽点）。
6. wound→fear→refuses 链保持不动（不采纳文档 4.1 的放宽主张）。
7. **用户要求最高优先**，创作中可实时打断修改（打断协议入文档）。

## 核心架构决策

- **内核载体 = `creator_profiles` 加 ownership 枚举 `author_kernel`**（不建新表）：复用版本链/双资源链/subject_hash/指纹去重/绑定表全套机制。每书分身 `parent_version_id` 指向内核版本（自引用 FK 天然成立）；「一书一分身」不变式保留在分身层，内核成为共享根。
- **请求契约升 v3**：`novelos.project.create.v3`，`creator` 段替换为 `author_kernel{mode: select|create, kernel_version_id?, kernel_hints}`；hints 保留原四字段 + 新增 `core_questions`、`knowledge_domains`。
- **人物注册表 = 复活 `characters` 表**（migration 018 重建：role_class / status / 退场字段），作为主要人物 roster、次要角色动态登记、entity-authority-review 新宿主的三合一锚点。

## 前置缺陷（探索发现，P0 修复）

- `scripts/novelos_compose_prompt.py` `_slot_canon_minimal` 五条账本 SQL 列名全部漂移（`fact_json`/`promise_type`/`expectations`/`character_a`/`arc_id` 均非活库列名），被 `except OperationalError` 静默吞掉——连续性账本实际零注入；近期章节 SQL 还缺 project 过滤（跨项目混章）。`.agents/skills/novel-continuity/SKILL.md`、`novel-memory/SKILL.md` 存在同源漂移。
- prose-quality-review 要求判 persona 盲区（blocking）但 manifest 未注入 `persona_full`。
- entity-authority-review 依赖的表已被 migration 016 删除（孤儿审查，P3-4 重锚定）。
- `.agents/skills/novel-planning/SKILL.md` 称 character_contract 未注册（过时文本）。

## 目标（验收对照）

| # | 目标 | 对应阶段 |
|---|---|---|
| G1 | canon 账本真正注入创作链（SQL 漂移修复 + 测试夹具对齐活库） | P0 |
| G2 | 作者内核跨书持久 + 每书派生 + 向导 v3 + 创建管线 | P1 |
| G3 | 内核深度参与方向/人物/写作/审查（kernel_full 槽 + 消费规则） | P2 |
| G4 | 主要人物全量设计 + 死亡/退场设计 + 人物状态账本 + 次要角色动态创建 | P3 |
| G5 | 规则六角色/三类规则/力量-规则循环/开局无敌 + 道德债功能化 | P4 |
| G6 | 文档协议收尾（AGENTS/flows/打断协议）+ 四命令全绿 | P5 |

## 追溯体系

1. **任务状态**：只用 `TODO` / `IN PROGRESS` / `DONE` / `BLOCKED`；生产路径接通且验证通过才 `DONE`。
2. **Commit 规约**：每任务项独立提交，代码 + 测试 + 文档同 commit，message 末尾带任务项 ID（如 `feat(compose): canon 账本 SQL 对齐活库 [T30-P0-1]`）。
3. **验收记录**：每任务项完成后在「验收记录」节登记验证摘要 + 文档变更清单。

## 核验体系

全局四命令（每任务项 DONE 前必跑，全绿为准）：

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

数据库变更前 `cp data/novelos-v2.db data/novelos-v2.db.bak`；migration 018 走 `backup_novelos_database.py` 备份 + 恢复演练仪式。

---

## 阶段任务

### P0 基线修复

- [x] **P0-1 canon 账本 SQL 对齐活库**：`_slot_canon_minimal` 五条 SQL 按活库列名重写（`description_resource_id`/`state_resource_id` JOIN resources 取描述；`expectation_ledgers` 表名；`subject_ref`/`object_ref`/`arc_ref`；事实按 `chapter_facts.status='accepted'` + project 过滤；近期章节经 volumes→books 加 project 过滤）；`OperationalError` 改显式 stderr 降级日志不再静默；同步修 `.agents/skills/novel-continuity/SKILL.md`（删除漂移 SQL 块，单一来源指向 sql-reference.md）与 `novel-memory/SKILL.md` 的事实检索模板；测试夹具补五账本 + books/volumes 表并用真实列名 seed 断言注入。
- [x] **P0-2 prose-review 补 persona_full 槽**：agent-recipes.json 矩阵先行 + manifest data_slots——修复「判盲区却无 persona 注入」缺口。
- [x] **P0-3 novel-planning SKILL 过时文本修正**：character_contract 已注册组装器，删除「未注册资产 Read prompt.md」残留；顺带修一处「十二字段」→「十三字段」漏改。

### P1 作者内核层（L0 + 向导 + 创建管线）

- [x] **P1-1 migration 018**：备份仪式 → creator_profiles 重建（ownership CHECK + `author_kernel`）→ project_creator_bindings 重建（+ `kernel_version_id` FK、binding_mode + `kernel_derive`）→ characters 重建（+ role_class main/secondary/minor、+ status active/peripheral/dormant/departed/transformed/dead、+ first_chapter_id/exit_chapter_id/exit_type）→ schema.sql 基线同步 → schema_migrations 登记。
- [x] **P1-2 `config/schemas/author-kernel.schema.json`**：identity（核心问题/价值公理/情感立场/审美承诺/知识观/创作公理/内核盲点）+ psychology 八维五段式（注意偏向/情绪加工/核心需求/依恋/防御补偿/不确定性耐受/道德直觉/认知更新，每维 tendency/triggers/reactions/blindspots/revision）+ knowledge_ecology（domain/depth/use/verification/common_errors）+ growth_log（trigger/attribution 四归因 express|slot|setting|kernel/change）+ stability_rules。
- [x] **P1-3 新 skill `catalog/skills/onboarding/author-kernel-fusion/`**（七件套；create 从 hints 融合 / revise 必须带四归因 growth_log；原型签名仅作参考资料）+ ASSET_DIRS 注册 `kernel-fusion` + 矩阵行 + marker/SIZE_BUDGET 测试。
- [x] **P1-4 v3 请求 schema + `novelos_create_project.py`**：kernel 候选校验门（author-kernel schema + 库内反查 select 模式）+ 落库事务扩展（新建内核 profile/version → 每书分身 version parent=内核版本 → binding kernel_derive）+ 删除原型三方比对（保留 config 完整性校验）。
- [x] **P1-5 creator-signature-fusion 换派生源**：`kernel_full` 槽 + kernel-present 条件模块（内核层继承不变可追溯，表达层 voice_samples/trait_profile/七字段按 setup 适配）；creator-signature schema 加可选 `kernel_origin`；creator-derivation-candidate parent 反查改内核版本。
- [ ] **P1-6 向导 v3**：`novelos_export_kernel_roster.py` 生成 `ui/kernel-roster.js` 镜像；project-wizard.html 07 步重做（选已有内核 / 新建内核 hints 表单含两个新字段）；移除原型选择 UI；request_type v3。
- [ ] **P1-7 sql-reference.md 内核两步查询 + AGENTS.md 向导条款改写**。

### P2 内核深度参与创作链

- [ ] **P2-1 SLOT_REGISTRY 增 `kernel_full`**（三表 JOIN 照抄 _slot_persona_full 模式，缺失即停）+ slot_vocabulary 登记。
- [ ] **P2-2 注入与消费**：direction（核心问题→organizing_principle 种子、价值公理→矛盾价值侧）、character-contract（八维=作者观察方式，非角色模板）、chapter-draft（kernel-psychology 条件模块：心理呈现纪律）+ review 消费检查（direction-review / character-contract-review / prose-review 增「心理解释压过节奏」「立场突变无触发」）；矩阵/manifest/SIZE_BUDGET/文档同步。
- [ ] **P2-3 内核陈旧检查**：绑定旧版内核的项目查询模板 + SKILL 升级裁决指引（跟随新内核重派生 vs 锁定当前分身）。

### P3 人物全量设计与生命周期

- [ ] **P3-1 character-contract prompt 重写**：全量主要人物（主角+核心对手+主锚点+卷级关键载体，对照架构移交清单逐人认领）+ 每人心理运作简表（八维选 3-4 维）+ 知识边界 + 计划内死亡设计卡 + 退场设计（七型+回归条件）。
- [ ] **P3-2 planning-candidate.schema.json metadata 增可选 `character_roster`**（name/role_class/arc_role/登场卷/预期退场）。
- [ ] **P3-3 动态配角机制**：`scripts/novelos_register_characters.py`（幂等 upsert 注册表）；chapter-plan-execution-card 增「本章新登场人物微档案」节；continuity schema 增第六类候选 `character_status`（owners + character）。
- [ ] **P3-4 entity-authority-review 重锚定 characters 注册表**（新人物/状态变化须指认授权来源：执行卡预登记或已接受正文）。
- [ ] **P3-5 人物链 review 检查项**：主要人物覆盖度、死亡必要性（只为刺激主角=blocking）、退场债务清算、还债不降智。
- [ ] **P3-6 canon_minimal 增人物状态节 + 投影渲染人物状态文件**。

### P4 作品世界层补全 + 道德债功能化

- [ ] **P4-1 新 expansion skill `catalog/skills/expansions/power-ecology/`**：八力量类型+七属性、三类规则分层、规则六角色、男频力量-规则循环、开局无敌冲突转移。
- [ ] **P4-2 world-contract 主干深化**：规则条目必答六角色 + 三类规则分层 + 可选素材挂 power-ecology；channel-male 模块增力量-规则循环与开局无敌条目。
- [ ] **P4-3 world-contract-review 检查项**：规则六角色缺失=warning、规则分层核对增强。
- [ ] **P4-4 道德债功能化**：character-contract/modules/channel-male.md、channel-omni.md 增「功能性道德债」节 + check-channel-male/omni 对应检查项。

### P5 文档与协议收尾

- [ ] **P5-1 AGENTS.md**：分层图 L0 注内核、创建向导 v3 流程、Agent 角色表增 kernel-fusion、「一书一分身」条款改写为「内核跨书共享+每书派生独一分身」。
- [ ] **P5-2 documentation/flows.md + agent-recipes.md 表格再生成 + adapters 校验**。
- [ ] **P5-3 用户实时打断协议**：AGENTS.md 小说工作流增条款（setup 级→UPDATE+propagate_stale；资产级→change proposal；章内→受控重组装；用户打断优先于进行中生成，主控先停手上报影响面）+ novel-writing/novel-planning SKILL 呼应。
- [ ] **P5-4 验收记录收尾，四命令全绿**。

## 依赖与并行

- P0 独立先行；P1 内部按编号串行（schema→脚本→skill→向导）；P2 依赖 P1-1/P1-2；P3 与 P4 理论可并行，按序执行；P5 收尾依赖全部。
- P3-3/P3-6 依赖 P1-1 的 characters 表重建。

## 风险与回退

- 向导 v3 是 breaking 变更：已有项目与旧分身不受影响（binding 数据不动）；回退 = git revert ui/ 两文件 + schema v2 分支保留。
- creator_profiles 表重建迁移：先备份后执行，失败从 `.bak` 恢复（backup 脚本自带恢复演练）。
- SIZE_BUDGET：新增模块后逐资产实测调预算，防方法论膨胀失控。
- 内核取代原型后 26 原型退出创建链：config 保留为参考资料库，test_wizard_data 相应调整。

## 验收记录

- **[T30-P0-0] 任务文档建立** — 2026-08-21
  - 验证：本文档 + tasks/README.md Task 表加行。
  - 文档变更：新建 `tasks/30_author_kernel_and_character_lifecycle.md`（决策登记七条 + 架构决策 + 前置缺陷 + P0-P5 任务项）；`tasks/README.md` 加 Task 30 行。
- **[T30-P0-1] canon 账本 SQL 对齐活库** — 2026-08-21
  - 验证：100 tests OK（新增 `CanonLedgerInjection` 两用例：真实列名注入 + 项目隔离 + 缺表降级可见性）；四命令全绿。`test_genre_packs.py` 旧用例补 books/volumes 层级（project 过滤生效的连带修正）。
  - 文档变更：`scripts/novelos_compose_prompt.py`（五条 SQL 重写 + stderr 降级日志）；`.agents/skills/novel-continuity/SKILL.md`（删漂移 SQL 块改单一来源指向 + 写入纪律三条款）；`.agents/skills/novel-memory/SKILL.md`（事实检索模板改 JOIN resources）；`tests/test_slot_resolution.py`（夹具补六表 + 新测试类）；`tests/test_genre_packs.py`（旧用例补层级）。
  - 备注：narrative_promises 语义收窄为 `status='open'`（与槽位标题「未决」及 novel-memory 模板对齐，原 `!= 'broken'` 会混入已兑现承诺）；近期章节查询补 project 过滤修复跨项目混章。
- **[T30-P0-2] prose-review 补 persona_full 槽** — 2026-08-21
  - 验证：100 tests OK（test_recipe_matrix 同步断言通过）。
  - 文档变更：`config/agent-recipes.json`（prose-quality-review slots + persona_full，矩阵先行）；`catalog/skills/review/prose-quality-review/modules/manifest.json`（data_slots）；`documentation/agent-recipes.md`（表格行再生成）。
- **[T30-P0-3] novel-planning SKILL 过时文本修正** — 2026-08-21
  - 验证：100 tests OK（test_project_skills frontmatter 一致性通过）。
  - 文档变更：`.agents/skills/novel-planning/SKILL.md`（步骤 3 改为「全部八类规划资产已注册」；「十二字段」→「十三字段」漏改修正）。
- **[T30-P1-1] migration 018** — 2026-08-21
  - 验证：备份 + 恢复演练通过（`backup_novelos_database.py`，pre 回滚件 `novelos-v2-schema18-pre-backup.db` 保留）；迁移后 `PRAGMA foreign_key_check` 零违例；ownership/status CHECK 注入实测拒绝；100 tests OK；四命令全绿。现网 30 profiles / 1 binding / 0 characters 数据零损失。
  - 文档变更：`db/migrations/018_author_kernel_and_characters.sql`（新）；`db/migrations/schema.sql`（characters 基线同步；creator 系表历史上就不在基线中，维持现状）；`scripts/export_novelos_data.py` + `tests/test_data_export.py`（drill 证据对升至 schema18：export + restore 双 manifest）；`tasks/migration/schema18_{export,restore}_drill.json`（新证据）。
  - 备注：schema12_restore_drill.json 曾被无参备份调用误刷新，已 `git checkout` 还原为历史证据；后续备份必须显式传 `--backup/--manifest`。
- **[T30-P1-2] author-kernel schema** — 2026-08-21
  - 验证：107 tests OK（P1-3 一并验证）；compileall 全绿。
  - 文档变更：`config/schemas/author-kernel.schema.json`（新：identity 八字段 + 八维五段式 $defs/dimension + 知识生态深度四档枚举 + growth_log 四归因枚举）。stability_rules 未入 schema——修正纪律属方法论约束，由 author-kernel-fusion prompt 执行，growth_log 携带归因数据。
- **[T30-P1-3] author-kernel-fusion skill + 组装器接入** — 2026-08-21
  - 验证：107 tests OK（新增 test_kernel_fusion.py 6 用例：载荷双模式校验/拒识、create 槽序与 marker、revise 基底直读、未知 base 停机；SIZE_BUDGET kernel-fusion=200 实测通过）；四命令全绿。
  - 文档变更：`catalog/skills/onboarding/author-kernel-fusion/`（prompt.md/metadata.yaml/provenance.yaml/modules 四件 + mode-create/mode-revise 双模块）；`config/schemas/kernel-candidate.schema.json`（新信封，revise 必带 base_version 的 if-then）；`scripts/novelos_compose_prompt.py`（ASSET_DIRS + kernel_hints/kernel_subject 槽 + build_context_kernel_fusion + validate_kernel_fusion_payload + main 路由 + fingerprints/project_setup 容错内核载荷）；`config/agent-recipes.json` + `documentation/agent-recipes.md`（kernel_fusion 行 + 槽位词表 kernel_hints/kernel_subject/kernel_full）；`tests/test_kernel_fusion.py` + `tests/test_compose_prompt.py`。
- **[T30-P1-4] v3 请求 schema + 创建管线内核化** — 2026-08-21
  - 验证：111 tests OK（新增 test_create_v3.py 6 用例：v3 全链端到端[建核→缝合 payload→分身→落库 kernel_derive+parent=内核]、select 未知内核拒绝、select 非内核 profile 拒绝、revise 改名/growth_log 缺失拒绝、分身逐字复制内核条目拒绝）；四命令全绿。
  - 文档变更：`config/schemas/project-create-request.schema.json`（v2/v3 双分支：request_type enum + 根层 allOf 条件；author_kernel{mode select|create, kernel_version_id, kernel_hints 六字段}）；`scripts/novelos_create_project.py`（重写：内核阶段 --kernel-candidate + 独立修订 --kernel-revise + --emit-payload 缝合 select 形态、validate_kernel_candidate 两步校验、persist_kernel create/revise 双路径、validate_candidate v3 分支 parent=内核库内反查 + KERNEL_IDENTITY_LIST_FIELDS 逐字复制、persist v3 binding kernel_derive+kernel_version_id、删除 cross_archetype_similarity——撞库改由 fusion 生成端指纹机制承担）；`tests/test_create_v3.py`（新）；`tests/test_wizard_data.py`（request_type 断言跟随 enum）；`tests/test_compose_prompt.py`（删除 CrossArchetypeSimilarity 类）。
  - 备注：① v2 分支为向导切换过渡兼容，P1-6 向导 v3 上线时移除；② 版本 id 模式放宽为可选 `:<revision>` 后缀——生产生成 `creator-profile-version:<uuid>` 无后缀，config 原型带后缀，两种形态均合法；③ create 模式建核后 `--emit-payload` 机械缝合 id/hash（非内容改写，协议允许）。
- **[T30-P1-5] fusion 换内核派生源** — 2026-08-21
  - 验证：112 tests OK（FusionSlots 槽序更新 + 新增 v3 内核派生用例：kernel_full 注入内核全文、原型/素材槽占位、kernel-derive 模块 marker、kernel_origin 输出契约）；四命令全绿。
  - 文档变更：`scripts/novelos_compose_prompt.py`（`_slot_kernel_full` 双域解析[绑定/payload] + selected_archetypes/persona_hints/build_context_fusion v3 容错 + SLOT_REGISTRY 注册 kernel_full）；`catalog/skills/onboarding/creator-signature-fusion/modules/kernel-derive.md`（新模块：内核层继承不变/表达层适配/wound→fear 留分身层/盲区双重来源/kernel_origin 必填）；同目录 `manifest.json`（kernel_full 槽位前置 + kernel-derive 挂接条件 setup.author_kernel not_null）与 `prompt.md`（输入节 kernel_full 首位 + 输出格式 kernel_origin）；`config/schemas/creator-signature.schema.json`（可选 kernel_origin{kernel_version_id/kernel_subject_hash/adaptation_notes}）；`scripts/novelos_create_project.py`（校验门 kernel_origin 一致性核对）；`config/agent-recipes.json` + `documentation/agent-recipes.md`（fusion slots + kernel_full）；`tests/test_slot_resolution.py`。
