# Task 29: 动态 Prompt 组装流水线 + 三 harness 适配

**状态**: `TODO`（P0-1 基线已固化，见下）

**范围**: 本任务交付一套「确定性组装、可追溯、可核验」的创作流水线：全链路 skill 模块化动态组装、题材×材料数据槽、阶段化发散度控制、harness 适配层（**仅 codex / zcode / deepseek harness 三个**）。四根柱子（权威 SQLite、依赖有序规划资产、方法论即 skill、审查门）不动。

## 目标（验收对照）

| # | 目标 | 对应阶段 |
|---|---|---|
| G1 | prompt 动态组装，结合题材/材料，产出更好更准 | P1 + P2 + P3 |
| G2 | 项目架构更清晰（分层明确，AGENTS.md 瘦身） | P4-3 |
| G3 | codex / zcode / deepseek harness 三家可用，catalog 与 scripts 零改动 | P4 |
| G4 | main/sub agent 产出更好更稳、阶段化发散度 | P1-1 + P2 + P3-4 |

## 现状基线（P0-1，已固化）

- 基线 commit：`2c9c6f0 feat(prompt): 方法论 prompt 模块化动态组装——direction 与融合链路双改造`
- 验证基线（2026-08-15 本会话实测）：51 tests OK；`compileall` OK；`check_repository_hygiene.py --check` exit 0；`build_catalog_manifest.py --check` exit 0；工作树干净。
- 已有能力：`scripts/novelos_compose_prompt.py`（when 路由 + U 型组装 + 自检尾部聚合）；3 个 skill 已模块化（story-direction / planning-direction-review / creator-signature-fusion）；路由维度覆盖 channel×platform×genre×aesthetic×人格库规模×原型数；`tests/test_compose_prompt.py` 含互斥断言与 SIZE_BUDGET 回归闸。
- 待补齐：仅覆盖 3/30+ skill；数据区硬编码（无声明式槽位）；无组装日志；无发散度档位；无 harness 适配层。

## 与 Task 28 的关系（P0-2）

Task 28（Agent Prompt 增强队列）剩余范围由本任务吸收执行，映射如下。28 状态保持 `IN PROGRESS` 直到本任务 P2 完成后一并关 `DONE`（范围经 29 交付）。

| Task 28 剩余项 | 进入本任务 |
|---|---|
| 阶段 1 补丁尾项（力量货币 / 代价形态学 / 道德债权 / 平台耐心结构；频道语法已进 modules） | P0-2 盘点 → P2-1 前作为 direction 增补模块补入 |
| 阶段 2 小补丁（architecture） | P2-1 |
| 阶段 3-10（strategy / character‖world / story-arc / volume-outline / chapter-plan / writing / review / continuity） | P2-2 ~ P2-8 |
| 横切收尾 | P2-9 |

## 追溯体系

1. **任务状态**：只用 `TODO` / `IN PROGRESS` / `DONE` / `BLOCKED`；生产路径接通且验证通过才可 `DONE`（AGENTS.md 约定）。
2. **Commit 规约**：每个任务项独立提交，**代码 + 测试 + 文档同 commit 入账**，message 末尾带任务项 ID，如 `feat(compose): manifest schema v2 [T29-P1-1]`。文档改动不单独游离提交。
3. **组装日志**（P1-3 起）：每次组装落盘 `data/compositions/`，记录 content_hash、命中模块、注入槽位与上游版本——每次生成「看到了什么」可回查。运行数据不进 git（.gitignore 增加 `data/compositions/`）。
4. **验收记录与文档变更登记**：每任务项完成后在本文件「验收记录」节登记两条——① 验证摘要（测试数、exit code、关键 diff 规模）；② **文档变更清单**：本项实际改动/新增/删除的文档文件（AGENTS.md、catalog 各 prompt.md 与 modules、tasks/README.md、各目录 README、schema 说明等），每个文件一句话说明改了什么、为什么。
5. **端到端链**：P2 总验收用同一合成项目贯穿全资产，组装日志按序可查。

## 核验体系

全局四命令（每任务项 DONE 前必跑，全绿为准）：

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall -q scripts tests catalog config
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/build_catalog_manifest.py --check
```

单项验收另加专属命令（见各项）。合成素材实测 = 用测试项目/payload 实际组装一次，产物按核验清单人工抽检：① U 型结构完整（主干→数据区→条件模块→自检汇总）② 声明槽位全部命中 ③ 自检汇总含所命中模块的附加项 ④ 无越权内容（模块外文本未混入）。

---

## 阶段任务

### P0 收尾与交接

- [x] **P0-2 Task 28 交接盘点**：`2c9c6f0` 已覆盖——频道语法（三频道模块）、平台耐心结构（platform-free/paid 三字段消费）、力量货币生成端主体（候选池+兑现语义）、道德债权的债权来源条款（channel-female）。**未覆盖项已补齐（本次一并实现）**：① 代价形态菜单（五形非对称 + 禁等价记账 + 三件套其二 + 四检验）→ direction 主干新节；② 力量货币对价与锚定（对价定义、锚进 central_contradiction）→ 十三字段表 power_currency 行；③ 道德债务显性化 + 双莲花禁令 + 选择性道德 → channel-female 模块；④ `book-soul.schema.json` 加 `power_currency`（required）+ 投影 `_SOUL_LABELS`；⑤ 审查端加检查项 9（力量货币锚定 + 代价质量 warning）与 blocking 条款；⑥ 全库「十二字段」→「十三字段」（7 处）。
  - 产出：本节清单 + 上述文件改动；novel-planning SKILL.md 的 Direction 输入清单补 channel/platform 并入 P0-3。
  - 验收：51 tests OK（含 book_soul 十三字段断言）；四命令全绿。
- [x] **P0-3 消除现存文档矛盾 + 接通已交付路由**：① `novel-project/SKILL.md` 第 2 步改为 composer 流（消除与 AGENTS.md 第 4 步的互相矛盾，删去「注入原型全库」旧指令）；② `novel-planning` 第 3 步 / `novel-review` 第 2 步改为「已模块化资产走组装器、未模块化暂 Read prompt.md」的分流规则（direction / direction-review 路由接通；novel-writing 的 chapter-draft-generation 留待 P2-7）；③ AGENTS.md「Agent 角色」段通用注入规则同步为分流规则。
  - 验收：`.agents/skills` 中不再有指向已模块化资产的旧式注入指令；`system_archetypes.json 全文` 注入指令零残留；51 tests OK。
- [ ] **P0-4 目录结构清理（低风险删减）**：① 删除 `config/agents.yaml`——全库零引用（scripts/tests/catalog/.agents 均不读它），AGENTS.md 已声明其为历史留档，git 历史可查；同步删除 AGENTS.md「config/agents.yaml（历史留档）」段；② 根目录 `readme.md` 改名 `README.md`（大小写一致性）。
  - 验收：`grep -rn 'agents.yaml' scripts/ tests/ catalog/ .agents/ AGENTS.md` 零命中；四命令全绿。
  - 说明：`db/migrations/`（留档承诺）、`tasks/` 各证据子目录（`07_prompt_catalog/fixtures` 是 `test_prompt_catalog_boundaries` 的活依赖，migration/cutover/experiments 是追溯证据）**明确不动**。

### P1 组装器通用化（schema + 槽位 + 日志）

- [ ] **P1-1 manifest schema v2**：`config/schemas/compose-manifest.schema.json`——在现有 `when` 上增加 `data_slots`（声明式注入槽：`genre_pack` / `reference_material` / `persona_full` / `canon_minimal` / `upstream:<asset_type>` / `review_feedback` / **`subject`（被审对象全文——审查与改稿组装的必需槽，对应 novel-review 的 subject + 上游原文输入契约）** / **`craft_refs`（审查/写作引用的 craft 方法卡，清单来源 = novel-review SKILL.md 的 craft 引用表）**）、`divergence`（`expansive` / `balanced` / `constrained` 三档）与 **`decision_scope`（决策权限四档，收编现在散落各 prompt 的隐含惯例为显式契约：`propose_only` 只出候选不选择（direction/fusion 现状） / `judge` 出 verdict + 证据但豁免与带病接受归主控（review 现状） / `execute` 照合同执行无重订权（writer 现状） / `flag` 发现冲突必须上报禁止静默调和（fusion 上报裁决协议现状））**。组装器加载 manifest 时先过 jsonschema。模块清单的 `file` 字段允许**跨包引用共享库**——`expansions/`、`craft/` 原位保留为共享模块/方法卡库，不搬家。
  - 发散度档位定义（生成端指令与审查端 rubric 同源）：
    | 档位 | 适用资产 | 生成端要点 | 审查端对应 |
    |---|---|---|---|
    | expansive | fusion, direction, architecture | 2-3 真候选、张力形态菜单、禁早收敛 | 候选可比性与差异度 rubric |
    | balanced | strategy, character, world, story-arc, volume-outline, chapter-plan | 单方案、结构内自由、decision_points 显式 | 结构完整性 + 上游一致性 |
    | constrained | chapter-draft, expansions, continuity 提取 | 逐字锚定 style_refs / persona anchors、防指纹禁令 | 逐项清单 + blocking 判据 |

    横切审查（cross-consistency / quality / entity-authority）不单独立档，**跟随被审对象的档位**。
  - 验收：新增 `test_manifest_schema` 校验现有 3 个 manifest 通过；四命令全绿。
- [ ] **P1-2 槽位解析框架**：`_direction_data_sections` / `_fusion_data_sections` 硬编码改为按 manifest `data_slots` 声明解析；实现槽位注册表（slot id → resolver）。**迁移不改行为**。另：fusion 载荷解析与 `novelos_create_project.py` 共用同一 jsonschema 校验（复用 `project-create-request.schema.json` 加载器），防止向导契约漂移时两处解析各自为政。
  - 验收：快照测试证明改造前后组装输出 byte 级一致（同输入）；四命令全绿。
- [ ] **P1-3 组装日志**：每次组装写 `data/compositions/<scope>/<asset>/<timestamp>.md` + 追加 `index.jsonl`（content_hash、命中模块 id、槽位清单、输入 key 版本）。CLI 加 `--log-dir` / `--no-log`。`.gitignore` 增加 `data/compositions/`。
  - 验收：同输入组装两次 hash 一致；输入变更后 hash 变化；日志文件含注入清单可读。
- [ ] **P1-4 测试扩充**：路由确定性（同 context 两次组装 byte-identical）、互斥模块、SIZE_BUDGET 维持、日志一致性。
  - 验收：四命令全绿，新增测试计入总数。
- [ ] **P1-5 模型提议路由通道（语义条件的第二路由通道）**：结构化枚举维度（channel/platform/genre/aesthetic）保持规则路由——枚举相等判断交给模型是浪费且徒增失败面；语义条件（reference_material / 材料 / canon 内容暗示的相关模块）规则表达不了，开**提议通道**：composer 加 `--proposal <json>`，主控或模型输出结构化提议（追加哪些模块 + 各自理由），composer 校验提议（模块必须在 manifest 注册、与规则命中不冲突）后**仍由代码确定性组装**，提议原文与理由进组装日志。**边界（写死）**：模块正文、数据槽内容、自检清单、U 型布局永远逐字拼接，不经模型改写——合规关键文本（防指纹禁令、persona anchors）一旦允许转述，审查即失去「当时注入了什么」的依据。路由大脑可插拔（规则 → 规则+提议 → 未来更强模型），manifest / 模块库 / 日志 / 测试零改动。
  - 验收：提议引用未注册模块 → 拒绝并报错；合法提议 → 组装含该模块且日志记录提议与理由；无提议时输出与现状 byte 级一致。

### P2 全链路 skill 模块化（吸收 Task 28 阶段 3-10）

统一模式（每项相同）：骨架 `prompt.md` 收敛为普适主干 + `modules/` 条件模块 + manifest v2（含 divergence 档位与 data_slots）；对偶 review skill 同维度路由；composer `ASSET_DIRS` 注册；SIZE_BUDGET 与 marker 断言入测试；**AGENTS.md 与对应 `.agents/skills/novel-*/SKILL.md` 条目同步**从「Read prompt.md」改为「调 composer」（两处一起改，防止再现 P0-3 那类文档矛盾）；合成素材实测一次（核验清单见核验体系）。

- [ ] **P2-0 阶段配方矩阵（设计基线）**：在 `documentation/agent-recipes.md` 落一张全资产矩阵——每个资产/审查场景一行，列 = **消费槽位配方（加载什么）× 发散档位（怎么想）× 决策权限（能定什么）× 输出契约（JSON schema 或文本形态）× 失败行为（进修复循环 / 上报裁决 / 组装重试）**。P2-1..P2-9 照矩阵实现；manifest 与矩阵不一致即测试失败。
  - 验收：矩阵覆盖 P2 全部资产 + 已模块化三个资产；新增 `test_recipe_matrix` 校验各 manifest 的 data_slots/divergence/decision_scope 与矩阵一致；四命令全绿。
- [ ] **P2-1 story-architecture + planning-architecture-review**（含 28 阶段 2 小补丁；前置：P0-2 的 direction 增补模块）— divergence: expansive
- [ ] **P2-2 story-strategy + planning-strategy-review**（28 阶段 3）— balanced
- [ ] **P2-3 world-contract + planning-world-contract-review ‖ character-contract + planning-character-contract-review**（28 阶段 4，两项可并行）— balanced
- [ ] **P2-4 story-arc + planning-story-arc-review**（28 阶段 5）— balanced
- [ ] **P2-5 volume-outline + planning-volume-outline-review**（28 阶段 6）— balanced
- [ ] **P2-6 chapter-plan-execution-card + planning-chapter-plan-review**（28 阶段 7）— balanced
- [ ] **P2-7 writing/chapter-draft-generation + prose-quality-review**（28 阶段 8 + 9 的正文部分；style_refs / persona anchors / craft 引用经槽位注入；composer CLI 扩展 `--chapter` / `--subject` 选择器——写作/审查的对象是章节与资源，不是 planning_assets）— constrained
- [ ] **P2-8 continuity/continuity-candidate-extraction + continuity-quality-review**（28 阶段 10）— constrained
- [ ] **P2-9 横切审查模块化 + expansions/craft 定位收口 + 28 横切收尾**：① planning-cross-consistency-review / planning-quality-review / entity-authority-review 三者补方法论并模块化（档位跟随被审对象）；② **expansion 方法卡改造为资产 manifest 可声明的可选模块**（替代 novel-planning SKILL.md 里「按需 Read expansion/prompt.md」的散装注入——expansion 天然就是条件模块）；③ craft 卡保持原位，统一经 `craft_refs` 槽注入（引用表以 novel-review SKILL.md 的表为准收编进 manifest）；④ 完成 28 横切收尾清单。
- **P2 总验收**：全部资产类型经 composer 出厂；同一合成项目贯穿 fusion → direction → … → draft 全链组装，组装日志按序可查；四命令全绿；Task 28 关 `DONE`。

### P3 数据槽扩展（题材 × 材料）

- [ ] **P3-1 题材信息包权威化**：从 `ui/project-wizard-data.js` 提取题材信息包 → `config/genre-packs/`（JSON）；向导数据与 config 建立单一来源关系（生成或同步校验，二选一并在实现时定案）。
  - 验收：新增 `test_genre_packs` 校验两处一致；四命令全绿。
- [ ] **P3-2 genre_pack 槽位**：direction / architecture 等按一级题材注入题材包。
  - 验收：合成项目组装 direction，产物含题材包节且命中正确题材。
- [ ] **P3-3 canon_minimal 槽位**：novel-memory 的检索规则按资产声明化（manifest 声明所需 canon 类别）。**单一来源原则**：检索 SQL 模板以 `sql-reference.md` 为唯一权威，composer 的 canon resolver 与 novel-memory SKILL.md 同源引用（novel-memory 改为「优先消费 composer 组装产物，必要时按同套模板自查」）——禁止两边各写一套检索逻辑导致结果漂移。
  - 验收：chapter-draft 组装产物含 canon 上下文节（可空但结构存在）与来源 key 清单；`grep` 确认 novel-memory 与 composer 引用同一模板节。
- [ ] **P3-4 review_feedback 槽位 + 审查-修复循环边界**：审查 FAIL 回执注入重试组装，受控重试替代自由重试。novel-review SKILL.md 已有「审查-修复-重审-退出」循环（退出条件 = 只剩 note；warning 必须修复；`defer_to_downstream` 豁免带跟踪责任），本项补齐其缺失的**循环边界**：
  ① 回执进槽规则：`blocking` + `warning` 全量注入（`note` 不注入）；
  ② 轮次上限：同一 subject 默认 **3 轮**未收敛 → 停止循环升级用户裁决（附各轮 blocking 摘要），禁止无限打转；
  ③ 同因复发检测：与上一轮同因的 blocking 再现 → 直接升级不再重试（修复手段无效的信号）；
  ④ 轮次追溯：修复用的组装日志标记 round 序号，回执与组装日志互相可回查。
  - 改动落点：novel-review SKILL.md 循环节补 ②③；composer 加 `--round` 参数并入组装日志；AGENTS.md 工作流段一句话引用。
  - 验收：模拟回执 → 重组装产物含回执节且标 round；无回执时结构不出现；单测覆盖「3 轮未收敛升级」「同因复发直接升级」两条判定。

### P4 三 harness 适配层（codex / zcode / deepseek）

- [ ] **P4-1 adapters 单源生成器**：`scripts/novelos_build_adapters.py` 从 `adapters/source/` 单源生成：① AGENTS.md（codex 与 zcode 共读，支持 per-harness 入口变体——同一事实源，允许 codex/zcode/deepseek 各自措辞与结构不同）；③ deepseek harness 入口件（约定见 P4-2）；④ 收编 `.codex/config.toml`（codex 的 SQLite MCP 注册件，本质是 harness 入口件，目前游离在版本库根目录）纳入单源生成/校验范围。**`.agents/skills/novel-*/SKILL.md` 保持手写**（它们是含 SQL 细节的操作层，不是入口件），但纳入生成器的一致性校验（检测与 AGENTS.md 说法冲突，防 P0-3 类矛盾复发）。核心原则：harness 只做三件事——跑脚本、读文件、把组装产物交给 sub agent；**组装产物文件 = 主控↔sub agent 的 ABI，三家 harness 共用同一份 sub agent prompt，不做 per-harness 变体**（差异化只发生在主控入口层）。
  - 验收：生成物与手写版 diff 为空或差异经逐条审定；一致性校验器对现存六技能跑通；`build_catalog_manifest.py --check` 与 hygiene 全绿（生成物目录不违反目录边界）。
- [ ] **P4-2 deepseek harness 入口约定确认**：调查/索取 deepseek harness 的入口文件、命令注册与 sub agent 机制 → `adapters/deepseek/README.md` 记录约定与生成映射。
  - 验收：README 存在且含入口文件名、注册方式、sub agent 调用方式三要素；P4-1 生成器覆盖该约定。
  - 风险：约定不明则本项 `BLOCKED`，不阻塞 P4-1/P4-3 的 codex/zcode 部分。
- [ ] **P4-3 AGENTS.md 瘦身**（依赖 P2 全部完成）：方法论细节归 catalog、操作细节归 scripts docstring、SQL 细节归 sql-reference；AGENTS.md 保留路由协议 + 五层架构图 + adapters 指向。记录瘦身前后行数。
  - 验收：瘦身前后 `test_project_skills` / hygiene 全绿；AGENTS.md 行数较基线下降 ≥ 40%；新增「换 harness 指引」节。
- [ ] **P4-4 三 harness 冒烟**：① zcode（本会话可测）：创建项目→fusion→direction 组装链跑通；② codex（需用户开 codex 环境）：同链跑通；③ deepseek harness（依赖 P4-2）：至少组装命令可用。每家记录：环境、命令、结果摘要。
  - 验收：三家冒烟记录写入本文件「验收记录」；任何一家失败记 `BLOCKED` 并列修复项。

### P5（可选）组装日志驱动的精细 stale

- [ ] **P5-1 变更分类器**：上游资产修订 → 对照下游组装日志的注入清单分类 `stale` / `neutral`（不做 LLM 语义判定，仅按注入 key 与版本号机械分类；语义等价留待后续）。
  - 验收：单测覆盖「改 A 字段不误伤仅消费 B 的下游」用例。
- [ ] **P5-2 propagate_stale 加 `--fine` 模式**：默认保留现行为，`--fine` 走分类器；`--check` 可对比两模式差异。
  - 验收：dry-run 对比输出合理（细模式标记数 ≤ 粗模式）。

## 依赖与并行

```
P0-2 / P0-3（可并行）→ P1-1 → P1-2 → P1-3/P1-4
P2-0 → P2-1..P2-9 顺序执行（P2-3 两项可并行）；每项依赖 P1-1（schema）与 P2-0（配方矩阵）
P3-1 独立可提前；P3-2..P3-4 依赖 P1-2/P1-3
P4-1/P4-2 可与 P2 并行；P4-3 依赖 P2 完成；P4-4 依赖 P4-1（+P4-2 for deepseek）
P5 依赖 P1-3 且为可选
```

## 风险与回退

| 风险 | 缓解 |
|---|---|
| AGENTS.md 与 `.agents/skills` 说法矛盾复发 | P0-3 先消除现存矛盾；P2 起两处同步改；P4-1 一致性校验器持续兜底 |
| canon 检索双实现漂移（composer vs novel-memory） | P3-3 单一来源：检索模板以 sql-reference.md 为权威，两处同源引用 |
| AGENTS.md 瘦身破坏既有会话行为 | 瘦身前 P2 已让全链路走 composer，AGENTS.md 只剩路由；hygiene + skills 测试兜底；单 commit 可回退 |
| deepseek harness 约定不明 | P4-2 允许 `BLOCKED`，不阻塞 codex/zcode 交付 |
| 组装日志膨胀 | 按项目/资产分目录；`--no-log` 可关；不进 git |
| 模块化把方法论改坏 | 每项迁移带快照/标记断言；SIZE_BUDGET 防主干回填；合成素材实测人工核验 |
| 数据库误写 | 全流程只用组装与校验命令；P2 实测用合成项目，落库仍走既有固化脚本 |

## 验收记录

（执行时按任务项追加，每项格式如下）

- **[T29-P0-2] Task 28 交接盘点 + 阶段 1 补丁尾项补齐** — 2026-08-15 / commit 待填
  - 验证：51 tests OK；hygiene exit 0；manifest exit 0
  - 文档变更：`catalog/skills/planning/story-direction/prompt.md`（主干加代价形态菜单节 + power_currency 字段行 + 骨架/自检措辞）；`modules/channel-female.md`（道德债务/双莲花/选择性道德）；`config/schemas/book-soul.schema.json`（power_currency required，十三字段）；`scripts/novelos_render_projection.py`（_SOUL_LABELS）；`catalog/skills/review/planning-direction-review/prompt.md`（检查项 9 + blocking）；`planning-architecture-review/prompt.md`、`story-architecture/prompt.md`、`.agents/skills/novel-planning/SKILL.md`、`tests/test_compose_prompt.py`（十二→十三字段同步）
  - 备注：阶段 1 补丁至此全部落地；Task 28 剩余 = 阶段 2 小补丁（P2-1）+ 阶段 3-10（P2-2..P2-9）+ 横切

- **[T29-P0-3] 消除文档矛盾 + 接通已交付路由** — 2026-08-15 / commit 待填
  - 验证：51 tests OK；hygiene exit 0；manifest exit 0
  - 文档变更：`.agents/skills/novel-project/SKILL.md`（第 2 步改 composer 流，消除与 AGENTS.md 的矛盾）；`.agents/skills/novel-planning/SKILL.md`（第 3 步分流规则）；`.agents/skills/novel-review/SKILL.md`（第 2 步分流规则）；`AGENTS.md`（Agent 角色段通用注入规则分流）
  - 备注：残留 prompt.md 引用均为未模块化资产（P2-7/P2-9 切换）
