# R7 · 机器强制层复活与对抗审查修正（任务书 v1）

> 状态：**DONE（2026-08-29 执行收口；021 生产库应用 2026-08-30 用户裁决「确认」后执行完毕——R7 全部关闭）**——执行记账见 `tasks/README.md` R7 条目，指标见 `docs/knowledge/metrics.md` 追加行。
> 来源：`docs/novelos-adversarial-cross-exam.md`（对抗审查裁决：成立 12 项）修正案 A1/A2/A3/A4/A7；2026-08-29 用户已裁决：R6 关闭、三待定项关闭（lite 快档/FTS5/运行时拉取均不做，本任务书不再含）。
> 缓行项 A5（TBD 物化）/A6（多视角审查）/A8（M7 依从性记账）/A9（蒸馏扩域）/A10（漏报试点）**不在本任务范围**，另行呈报。
> 纪律前提：零 Python（一切 node:sqlite/node:crypto，Node 22+）；生产库任何写入前先复制 `data/novelos-v2.db` 备份；金丝雀 rule_table 不动（A1-A4/A7 均不触碰 fingerprint 规则表，canary `--compare` 必须零回归）；单渲染器红线不动。

## 0. 目标与验收总则

把对抗审查证实的四处「强制层缺口」以 harness 中立方式补回：**G2 空回执默认放行（P4-1）→ 默认 FATAL；写库机器门缺位（P1-5/P3-7）→ CLI 门；账本无流水（P3-3）→ promise_events；语态槽缺位（P2-4）→ composer 槽**；并清偿三处防漂移行为证据（P2-5）。

**总 DONE 判据**（全部满足才可记账 DONE，缺一即 BLOCKED）：
1. 七套测试全绿：guardrails / compose / fingerprint(49) / verify-review-evidence / render(48) / canary `--compare` PASS / **新增 test-gate**。
2. 生产路径实测：门 CLI 对生产库只读冒烟 PASS；migration 021 仅在副本库验证，生产库应用=单独裁决门（见 T4）。
3. AGENTS.md / sql-reference.md / 相关 SKILL.md 写库口径全部改指门通道，无残留「裸 SQL 直写」表述（grep 验证）。
4. `tasks/README.md` 记账 + `docs/knowledge/metrics.md` 追加行。

## T0 · 预检（半小时，无写入）

- [ ] 复制备份：`cp data/novelos-v2.db data/novelos-v2.db.bak-r7-$(date +%Y%m%d%H%M%S)`。
- [ ] 基线测试快照：依次跑 guardrails/compose/fingerprint/verify/render/canary 六套，记录通过数作为回归基线（当前应为 296/28/49/15/48/PASS）。
- [ ] git 基线：工作区干净（两份调研报告先按用户对 ① 的处置入库或 stash）。
- **验证**：六套基线数字与 tasks 账本 R3-R4 记录一致；不一致先停下呈报。

## T1 · A1+A7a+A7b 快修（半天，纯文件改动，零库接触）

**A1 — G2 空回执升默认 FATAL**（堵 P4-1，最优先）：
- [ ] `scripts/novelos-verify-review-evidence.mjs`：`empty_findings_approved` 从 `--strict`-only 升为**默认 FATAL**；新增 `--allow-empty` 显式豁免（豁免必须在回执 note 或 CLI 输出留痕字样）。
- [ ] `scripts/test-verify-review-evidence.mjs`：改 1-2 个受影响用例（原 advisory 语义），新增两例：默认空回执 exit 1；`--allow-empty` exit 0 且输出含豁免留痕。
- [ ] 接线三处增句不删句（沿用 R2 惯例）：`.agents/skills/novel-review/SKILL.md` 标准命令行、`AGENTS.md` 工作流第 3 步、`.agents/skills/novel-writing/SKILL.md` 预筛注记。
- **验证**：`node scripts/test-verify-review-evidence.mjs` 全绿（预计 17±2 例）；合成空回执实例 exit 1 冒烟。R2 账本「--strict 升级」口径在 tasks/README.md R7 记账行注明被本条取代。

**A7a — 修幽灵指针**：
- [ ] `catalog/skills/writing/chapter-draft-generation/prompt.md:37`：`catalog/skills/craft/` 路径修正——`scene-dialogue`/`scene-fight-craft` 实际在 `catalog/skills/writing/`，`compliance-place-guard` 在 `catalog/skills/craft/`，逐一改为正确前缀。
- **验证**：对三个目标目录逐个 `ls` 存在性断言；`node scripts/novelos-compose-prompt.mjs --asset chapter-draft`（fixture 库）产物 diff 仅指针行变化。

**A7b — 清陈旧引用**：
- [ ] `config/agent-recipes.json:3` description：删除「由 tests/test_recipe_matrix.py 校验」句，改为「由 scripts/test-guardrails.mjs G-recipe 校验（T2 落地）」。
- [ ] 顺手清 `tests/__pycache__/` 35 个 .pyc 尸体（零 Python 纪律的物理残留）。
- **验证**：`grep -rn "test_recipe_matrix" --include="*.json" --include="*.md" .` 零命中；`git status` 确认 pyc 删除。

## T2 · A7c 防漂移守护 JS 化（一天，零库接触）

- [ ] **G-recipe 检查**（复活被删守护的仓内形态）：`scripts/test-guardrails.mjs` 新增检查——对 composer_key 非空的配方行断言 `divergence`/`decision_scope` 与对应 manifest 全等、`data_slots` 只许增长（manifest ⊆ matrix）；契约照旧 .py 的描述语义（`8da464c^` 历史 + 现行 G2b 实现）。
- [ ] **catalog manifest lint**：新脚本 `scripts/novelos-catalog-manifest.mjs`——生成/复核 `catalog/skills/**`（prompt.md/modules/*/manifest.json/metadata.yaml）逐文件 sha256 清单（参照 oh-story manifest v2 形态，本仓自研零依赖），`--check` 模式 exit 1 报漂移；清单落 `config/catalog-manifest.json`。
- **验证**：guardrails 全绿（296+新增）；故意篡改一个 prompt.md 字节 → `--check` exit 1 → 还原后 exit 0（红绿双向实测）；compose 28 无回归。

## T3 · A2 写门 CLI 复活（核心阶段，2-3 天，副本库开发）

**形态**：`scripts/novelos-gate.mjs`，单文件 CLI，node:sqlite 直连，`GateFail` 语义=校验失败即 throw 且零写入（对齐旧 `primitives.ts`）。**dry-run 默认**；写库必须 `--commit` 且生产库路径额外要求 `--allow-production`（先例：`novelos-import-personas.mjs` 硬编码拒绝生产路径）。所有写操作单事务 `BEGIN IMMEDIATE` + `PRAGMA foreign_keys=ON`，任一步失败整体回滚。

**子命令与语义来源**（规格=`docs/r2-js-gate-spec.md` + git 历史 `9e80bb7`/`27d34a4`/`da9ee5c` + tasks/README.md R2-R4/WP5 记账）：

| 子命令 | 语义要点 | 移植源 |
|---|---|---|
| `lock-asset` | 封跳审：须绑定 `verdict='approved'` 且 `subject_ref` 匹配的 review；旧 locked 翻 superseded | WP5 记账 L65 + 019 迁移注释 |
| `accept-chapter` | 须写 `review_id`（019 FK）；已接受章节禁免审直改（降级 draft→重审链）；T4 起追加 Claremont 收口 | 同上 |
| `commit-review` | 回执落库前自动跑 A1 后的 verify（空回执/引文 no_hit 即 GateFail）；reviewer_profile 强制 `^(model\|agent):` pattern（关 P4-2） | verify 脚本 + schema L87-91 教训 |
| `propagate-stale` | coarse 直接+间接全量标 / fine 模式 upstream_version+content_hash 双比对，neutral 不误伤 | `propagate-delete.test.ts` 10 用例语义 |
| `validate-asset` | 七件资产校验器（`_CLIMAX_GAP_WORDS=300000` 等常量逐字）只读自查 | `validate-assets` 85 用例语义 |
| `register-characters` | 名册三入口；非法迁移 GateFail 零写入；幂等重入不覆盖状态史 | `register-characters.test.ts` 22 用例语义 |

**测试**：新 `scripts/test-gate.mjs`（/tmp 夹具库），验收=移植旧用例关键断言 **≥40 例**（状态机 19 全量 + propagate 10 全量 + register 22 中挑 12 关键 + create-project 12 中挑 5 事务/裁决门），文件头部注明每例对应的旧 `.ts` 用例名作溯源。
**口径更新**：`.agents/skills/novel-project/sql-reference.md` 写模板段标注「执行通道=novelos-gate.mjs 对应子命令」；AGENTS.md「写库三约定」追加第四约定「关键状态写入（锁定/接受/回执/stale 传播）过门，直写仅限门未覆盖的幂等读改」。
**明确不做**：不重建 defineTool/插件形态；不封死裸 SQL 通道（纪律层，非本任务范围——hooks 属 harness 专属已裁决排除）。
- **验证**：test-gate ≥40 例全绿；生产库只读冒烟（六子命令 dry-run 全走一遍）PASS 且 `PRAGMA data_version` 前后一致（零污染证明）；六套基线测试无回归。

## T4 · A3 账本流水（1-2 天；**含独立用户裁决门**）

- [ ] 新迁移 `db/migrations/021_promise_events.sql`：追加表 `promise_events(id, project_id, promise_key, chapter_id, event_type CHECK IN ('plant','progress','twist','resolve','break'), source_content_hash, created_at)` + `narrative_promises` 增 `resolved_chapter_id` 列；存量行不回填（照 019 先例）。备份纪律：应用前再复制一次库。
- [ ] Claremont 收口：`novelos-gate.mjs accept-chapter` 内计算 `active−resolved`（open promises 计数），>2 时输出 WARN 进回执 metadata（不阻断——先观察一个项目周期再议是否升 blocking，避免过度工程）。
- [ ] `db/migrations/schema.sql` 照 020 先例再导出；独立空库建表验证 26 表。
- [ ] 连续性对账 SQL 模板补「流水查询」一节进 sql-reference.md。
- **验证**：/tmp 副本库应用 021 → 插入/查询/Claremont 计算全流程实测；旧数据零损失（行数对账）；test-gate 增 5 例（事件追加/非法 event_type/Claremont 阈值）全绿。
- **裁决门**：021 落**生产库**前单独呈报（备份名+影响面+回滚 SQL），用户点头才执行；未点头则 T4 记 BLOCKED(用户裁决) 不阻塞 T5。

## T5 · A4 语态槽（一天，composer 改动）

- [ ] `scripts/novelos-compose-prompt.mjs` SLOT_REGISTRY 新增 `prev_chapter_tail`：取最近 accepted 章节正文结尾 **500-800 字**（超长按 800 截断、不足 500 整段注入并注明），**置于自检节之前**（生成点前最近端）；manifest/recipes 同步（chapter_draft 配方加槽）。
- [ ] 无 accepted 章节时（首章）槽渲染为空并在组装日志留痕，不 fail。
- **验证**：guardrails G2b 全等（manifest⊆matrix 语义同步更新）；fixture 库 compose 产物 diff 仅新增语态节；字节增量记入 metrics M5 追加行；canary `--compare` PASS（不涉规则表）。

## T6 · 收口（半天）

- [ ] 全量七套测试重跑（含 test-gate）记录终值。
- [ ] `tasks/README.md` R7 记账（DONE 判据四条逐一勾验）；`docs/knowledge/metrics.md` 追加 M5 语态槽行 + M2 口径更新行（A1 生效后 M2 含空回执拦截语义）。
- [ ] `docs/novelos-adversarial-cross-exam.md` §5 修正案表标注 A1/A2/A3/A4/A7 执行状态与 commit hash。

## 回滚预案

| 阶段 | 回滚方式 |
|---|---|
| T1/T2/T5 | git revert 单提交；无库接触 |
| T3 | 删 `novelos-gate.mjs`+test-gate；口径文档 revert；门未接入生产流程前零影响 |
| T4 | `data/novelos-v2.db.bak-r7-*` 整库还原（021 仅副本验证时无生产影响）；schema.sql revert |

## 工作量与顺序

总计约 5-7 个工作日；顺序刚性 T0→T1→T2→T3→T4→T5→T6（T4 生产应用可后置不阻塞 T5/T6）。T1 完成即可独立交付价值（最大洞已堵）；T3 是本任务重心，建议 T3 开工时先出 `novelos-gate.mjs` 接口签名（子命令+参数+退出码）供过目再填实现。
