# Task 09：叙事原型与项目化作者派生

## 状态

`DONE`

系统叙事原型、仅派生向导、确定性 Top 3 推荐、Schema 12 数据生命周期和严格约束校验均已完成并通过全量自动化测试。


## 目标

将项目创建时的作者选择改为“系统预设叙事原型 + 本书最小派生差异”。用户不再从空白表单创建作者、也不直接把已有作者版本绑定到新项目；每个新项目必须选择一个系统原型，确认系统根据项目定位给出的差异草稿后，原子创建项目专属的派生 Creator Profile 并绑定该项目。

本任务解决初次创建项目时作者签名难以填写的问题，同时避免把单本书的题材、平台和素材错误沉淀为可跨项目复用的作者身份。

## 核心决策

### 1. 叙事原型不是具体作者

- 预设资产命名为“叙事原型”，不得使用真实、已故或在世作者姓名、作品名、可识别笔法或规避检测指令。
- 原型只表达抽象的价值取向、叙事机制、关系观、表达偏好和负面约束；不得从年龄、性别、职业、地域等人口属性推导风格或思想。
- 现有 `kb_author_personas` 含具体作者资料，只能继续作为冻结知识库历史内容，不得作为本任务的原型来源、训练来源或转换来源。

### 2. 原型是系统资产，派生 Profile 是用户资产

```text
系统叙事原型（只读、不可直接绑定）
  -> 项目资料驱动的最小差异草稿（可编辑、未持久化）
    -> 项目专属 Creator Profile 版本（用户确认、不可变）
      -> Story Direction / book_soul
```

- 系统原型必须有稳定 ID、revision、`subject_hash`、标签和完整 `creator_signature`。
- 系统原型不可被 `revise`、`archive` 或直接 `reuse` 绑定；仅可作为 `derive` 的父版本。
- 项目提交在同一事务中校验原型 exact ref、合并显式差异、创建用户拥有的派生 Profile、创建项目、写入绑定和刷新投影。
- 派生版本必须记录父原型 exact ref/hash 和显式差异，不能只记录展开后的完整签名。
- 已创建项目后修改作者约束，继续使用 `project.creator.rebind`、Trace 和下游 `stale` 规则；不得原地修改已绑定版本。

### 3. 向导只保留派生

项目资料区应先于原型选择区。向导流程为：

1. 填写项目名称、频道、平台、规模、题材、情绪、美学和可选创作资料。
2. 按题材、情绪、美学和叙事诉求推荐三个原型，用户仍可浏览全部原型。
3. 用户选择一个原型，查看其继承项。
4. 系统只为本书生成“最小派生差异”草稿；用户逐项确认或修改。
5. 用户提交后，创建项目和派生 Profile；不保留空白 `create`，不允许 `reuse`。

频道、平台和规模只用于原型推荐和后续 Direction 的受众/篇幅约束，不得被伪装成作者长期价值取向。

### 4. 最小差异边界

默认继承且在向导中只读展示：

- `sympathies`；
- `distrusts`；
- `negative_constraints`；
- 原型的核心关系观和道德温度。

默认允许项目化草拟并由用户编辑：

- `recurring_attention`；
- `narrative_principles`；
- `expression_preferences`；
- 必要时局部 `forbidden_conveniences`。

差异界面必须同时显示“继承自原型”和“本书新增/替换”，并保证空字段确实继承父版本。自动草稿不得盲目覆盖全部字段，也不得宣称具备模型生成能力；若 V1 使用确定性模板，界面文字必须称为“生成基础差异草稿”。

### 5. 覆盖光谱与底层基因（含暗黑风、人性博弈与极端盲区原生支持）

- 18 个系统原型必须做到对**正统升级、硬核推演、阳光治愈、暗黑博弈（邪道/恶人主角/人性黑洞）、强情感拉扯（宿敌救赎/双向博弈）与荒诞解构（无厘头/乐子人）**等全光谱叙事需求的原生覆盖。
- **暗黑风与人性阴暗面**（如《暗夜博弈》、《智斗死局》、《黑化复仇》）在 `system-shadowed-choice` 与 `system-psychological-maze` 中必须作为**原生一等基因**写入其底色（`sympathies`, `distrusts`, `negative_constraints`），不得强制套用传统正派道德约束，防止派生时产生底色与面貌的基因冲突。
- **情感拉扯**（女频言情/强关系博弈）与**荒诞解构**（沙雕无厘头/吐槽流）分别由 `system-youthful-bonds` 与 `system-contrast-adventure` 在底色层原生包含，确保 18 个原型结构不膨胀的前提下实现 100% 叙事光谱覆盖。

## V1 原型清单

| ID | 原型 | 核心读者承诺 | 题材标签 | 气质标签 |
|---|---|---|---|---|
| `system-epic-framework` | 体系史诗 | 规则、文明与人物命运彼此咬合 | 玄幻、奇幻、仙侠、科幻 | 宏阔、克制、结构化 |
| `system-upward-striver` | 逆境攀登 | 低起点人物用选择和代价向上 | 玄幻、仙侠、都市、游戏、体育 | 坚韧、热血、递进 |
| `system-honor-in-action` | 侠义行动 | 行动中辨明责任、尊严与代价 | 武侠、军事、历史、玄幻 | 果决、悲壮、正直 |
| `system-community-builder` | 群像共建 | 分歧中的人走向协作与共同体 | 现实、都市、历史、军事、游戏 | 温厚、务实、群像 |
| `system-rational-inference` | 理性推演 | 清晰约束下的意外且必然 | 科幻、历史、游戏、现实 | 冷静、严谨、逻辑 |
| `system-disaster-survivor` | 灾厄求生 | 极端压力下守住人性与判断 | 科幻、奇幻、悬疑、诸天无限 | 高压、坚忍、危机 |
| `system-fair-truth` | 公平求真 | 真相来自可回溯线索与动机 | 悬疑、都市、历史、现实 | 克制、精确、悬念 |
| `system-folklore-echo` | 民俗幽微 | 异常与日常交织，恐惧背后有人情 | 悬疑、奇幻、仙侠、武侠 | 诗性、诡谲、悲悯 |
| `system-institutional-lens` | 制度观察 | 个体命运在资源与时代中变化 | 历史、现实、都市、军事 | 厚重、清醒、多视角 |
| `system-everyday-repair` | 市井治愈 | 平凡关系里的修复、成长与互助 | 都市、现实、轻小说 | 温暖、细腻、生活流 |
| `system-youthful-bonds` | 青春与情感羁绊 | 年轻人在关系、情感拉扯、梦想与自我中长成 | 轻小说、都市、现实、体育 | 明亮/强张力、真诚、宿命 |
| `system-contrast-adventure` | 反差与荒诞解构 | 严肃目标与轻快日常/荒诞吐槽彼此提振 | 游戏、轻小说、都市、诸天无限 | 幽默、解构、对话驱动 |
| `system-shadowed-choice` | 暗影与暗黑博弈 | 没有完美选项，主角以利己/灰色选择承担后果与黑洞 | 奇幻、玄幻、悬疑、诸天无限 | 冷峻、暗黑、复杂、反英雄/恶人 |
| `system-restoration-craft` | 经营复兴 | 用资源、技艺和关系重建衰败之地 | 历史、都市、仙侠、游戏 | 耐心、建设、成就 |
| `system-tactical-teamwork` | 战术协作 | 胜利来自信息、配合和临场判断 | 军事、体育、游戏、科幻 | 紧张、专业、团队 |
| `system-civilization-voyage` | 文明远航 | 探索未知并追问文明如何延续 | 科幻、奇幻、诸天无限 | 好奇、壮阔、探索 |
| `system-psychological-maze` | 心理迷宫与人性博弈 | 外部谜题与智斗映照创伤、欲望、算计与人性黑洞 | 悬疑、现实、都市、轻小说 | 内省、压抑、智斗、细密 |
| `system-fate-cultivation` | 宿命修行 | 以修行、承诺和选择改变既定秩序 | 仙侠、玄幻、武侠、奇幻 | 古典、沉潜、执着 |

每个原型的完整 `creator_signature`、标签、适用范围、不可兼容组合和 `subject_hash` 必须由本任务产出、独立审校并版本化；本表仅是 V1 资产清单，不是可直接提交的签名正文。

## 数据与 MCP 范围

1. 扩展 Creator Profile 存储，区分 `system_archetype` 与 `user_profile`，或建立等价的只读原型表；两种实现都必须保留 exact ref、revision、Hash、父子关系和原子事务。
2. 系统原型必须由仓库中版本化、可审计的结构化资产初始化；禁止从运行时模型、外部服务或 `seed.db` 中自动抽取。
3. `creator_profile.list` 与 `project.wizard.render` 必须能按所有权、安全绑定能力和标签返回原型；不得把系统原型混同为可直接复用的用户 Profile。
4. `project.wizard.submit` 仅接受原型派生请求。兼容旧项目的读取、投影、备份和导出；历史 `reuse` / `create` 绑定继续可读，不得篡改。
5. 建立对原型 revision/hash 不匹配、归档/不可用原型、空差异、越权直接绑定、以及系统原型被修订或归档的失败关闭校验。

## 实施顺序

1. 冻结原型 Schema、所有权/可绑定能力、exact-ref 与项目化差异契约；完成 18 个原型的完整签名与独立审校。
2. 新增单向 migration、初始化和 Service/MCP API；保证升级既有数据库时幂等、不改变历史绑定。
3. 修改项目向导为“项目资料 -> 推荐原型 -> 继承/差异确认 -> 仅派生提交”，删除新项目入口中的 `reuse` 与 `create`。
4. 为确定性推荐与基础差异草稿实现可测试的纯函数；不得在浏览器内隐藏不可审计的业务规则。
5. 更新项目投影、备份、恢复、导出、协议测试和维护文档。
6. 运行全量验证，记录 production path 证据后才能将任务置为 `DONE`。

## 验收标准

- [x] 空数据库初始化后可读到 18 个系统叙事原型；每个都有稳定 ID、revision、Hash、标签和符合 `creator-signature.schema.json` 的完整内容。
- [x] 18 个原型的完整签名在底色层原生覆盖暗黑流、人性阴暗面博弈、强情感拉扯与荒诞解构，防范只读底色与派生面貌之间的基因冲突。
- [x] 系统原型无法被直接绑定、修订、归档或作为普通用户 Profile 删除；任何项目只能以 `derive` 创建项目专属绑定。
- [x] 向导只显示派生流程，能根据项目定位推荐三个原型并允许用户切换查看全部原型。
- [x] 选择原型后，向导明确展示继承项与项目差异；自动草稿只影响允许派生字段，用户可编辑、重置和确认。
- [x] 提交在一个事务中校验原型 exact ref/hash、创建派生 Profile、创建项目、建立绑定并刷新投影；任一步失败不留下孤立资产。
- [x] 历史 `reuse` 和 `create` 项目仍可读取、投影、备份、恢复和导出；新向导不能再创建这两种绑定。
- [x] 系统原型内容、提示文案、测试夹具和 Review 规则均不含具体作者模仿、人口属性推导或从 `kb_author_personas` 复制的内容。
- [x] 根测试、MCP 测试、migration/catalog/seed/backup/export 检查、仓库卫生和 `compileall` 全部通过。

## 完成证据

2026-08-02 验证结果：

- 根测试：53 项通过。
- MCP 测试：137 项通过，启用 `ResourceWarning` 失败关闭。
- migration、catalog、Agent quality dataset、seed、production seed、Schema 12 backup/restore、Schema 12 export/restore、migration summary、repository hygiene、cutover readiness、cutover plan 和 `compileall` 检查全部通过。
- 向导定向测试 4 项、系统原型测试 6 项、stdio 协议测试 3 项通过；本地页面确认 18 个原型选项、JSON handoff 区域、表单语义标签和响应式单列规则。

## 非目标

- 新增作者 Agent、叙事原型 Agent 或任何常驻生成角色。
- 根据项目自动锁定 Story Direction、生成 `book_soul` 或跳过 Review/Trace 门禁。
- 声称确定性草稿是模型理解、模型生成或已通过语义质量实验。
- 删除或改写历史项目绑定、历史 Creator Profile 或 Task 08 的既有审计证据。
- 用预设原型模仿、复刻或规避检测地模拟具体作者。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_seed_inventory.py --check
.venv/bin/python scripts/build_seed_inventory.py --production --check
.venv/bin/python scripts/backup_novelos_database.py --check
.venv/bin/python scripts/export_novelos_data.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有系统原型、仅派生向导、原子项目创建、历史兼容、投影和数据生命周期均已接通，并且全部验收项与验证命令通过，才可将本任务从 `TODO` 标记为 `DONE`。仅有原型文案、界面草图或测试桩时不得标记完成。
