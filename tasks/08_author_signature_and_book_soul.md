# Task 08：作者签名与书级创作灵魂

## 状态

`DONE`

生产路径和确定性验收已完成。受控语义质量实验仍为 `BLOCKED`：尚无真实模型输出与独立评审，
因此不得据此宣称消除 AI 感或扩大 Writer、上下文构建智能体的触发范围。

## 目标

为 NovelOS 增加可跨项目复用、按精确版本绑定的 `creator_signature`，并在每个新小说项目的 Story Direction 中形成该书独有的 `book_soul`。同一创作者可以在多部作品中保持稳定的观察偏向、叙事原则和表达习惯，同时每部作品必须拥有不同的核心追问、有代价的创作承诺和不可轻易化解的思想冲突。

本任务解决的是作品缺少稳定创作主体、不同章节思想和声音漂移，以及每次创建项目都要从零描述作者约束的问题。它不以伪装真人或模仿具体作者为目标，也不新增常驻作者 Agent。

## 核心决策

### 1. 作者不是 Agent

- `creator_signature` 是用户拥有的跨项目创作配置，不是常驻 Agent，也不拥有生成、审查或提交权限。
- Writer Agent 继续保持临时生命周期；每个完整章节或长场景 Writer run 读取精确的作者签名版本、锁定 Chapter Plan、Canon 上下文和 Catalog 快照。
- 不为作者签名新增第九个规划资产 Agent。需要模型推理的 `book_soul` 由现有 方向智能体 作为 Story Direction 的组成部分生成，并沿用原有 Review 与 authority commit 门禁。

### 2. 两层约束

```text
creator_signature（跨项目复用）
  -> book_soul（当前项目的 Story Direction）
    -> Architecture / Strategy / Character / World / Story Arc
      -> Volume Outline / Chapter Plan
        -> Writer / Review
```

- `creator_signature` 回答“这个创作者通常同情什么、警惕什么、反复注意什么、拒绝哪些廉价处理”。
- `book_soul` 回答“这本书无法放下什么问题、存在哪个内部矛盾、愿意为哪些判断牺牲更方便的写法”。
- `pov_voice` 仍属于人物和具体场景的感知、措辞与知识边界，不得与作者签名合并。
- `scene_mode` 只允许调节局部节奏和表现方式，不得覆盖锁定规划、Canon 或 `book_soul`。

### 3. 项目与书的 V1 边界

- V1 将一个 NovelOS 项目视为一个小说创作单元，`book_soul` 随项目级 Story Direction 锁定。
- 项目内 `books`、`volumes` 和 `chapters` 继续作为内容容器；本任务不改变现有规划资产依赖顺序和 scope 规则。
- 多部独立小说应创建多个项目并复用同一 `creator_signature` 精确版本。
- 系列级 `series_soul`、选集内每篇独立 `story_soul` 和同项目多本书各自 Direction 留待独立任务，不在 V1 中隐式实现。

## `creator_signature` 契约

### 必需语义

`creator_signature` 至少表达以下维度：

- `sympathies`：叙事天然愿意维护其尊严的人或处境；
- `distrusts`：持续警惕的权力、话术或行为模式；
- `recurring_attention`：反复观察的生活细节、关系变化或制度后果；
- `narrative_principles`：作品表达判断时遵守的叙事原则；
- `forbidden_conveniences`：即使能让情节更爽、更快或更圆满也不得采用的廉价解决；
- `expression_preferences`：跨作品相对稳定的叙述距离、留白、议论和意象偏好；
- `negative_constraints`：明确禁止的模仿、标签化和不适用表达。

配置只保存用户明确提供或逐项确认的约束。不得根据年龄、性别、学历、职业、地域或其他人口属性自动推导能力、思想和文风；不得把具体在世或近现代作者姓名保存为“模仿目标”。

### 版本与 Hash

- 增加 `creator_profiles`、`creator_profile_versions` 和 `project_creator_bindings`（最终命名可保持同义，但职责不得合并）。
- Profile 保存稳定身份和显示名；每次内容修改创建不可变版本，不原地覆盖旧内容。
- 每个版本保存结构化 Resource、递增 revision、`subject_hash`、创建时间和可选父版本。
- 项目绑定必须记录 profile ID、精确 revision、`subject_hash` 和绑定模式；只保存“当前 Profile”引用不合格。
- Profile 归档只禁止新项目选择，不得破坏既有项目对历史版本的读取。
- 项目删除只级联删除项目绑定，不删除仍可被其他项目复用或审计的 Profile 版本。

## `book_soul` 契约

方向智能体 必须把以下内容作为 Story Direction 的固定组成部分，而不是附加写作备注：

```yaml
book_soul:
  unresolved_claims: []
  central_contradiction: ""
  costly_commitments: []
  protected_dignity: []
  forbidden_resolutions: []
  recurring_tests: []
  narrative_mercy: ""
  narrative_cruelty: ""
  deliberate_silences: []
```

约束如下：

- `central_contradiction` 必须包含两个都能成立、但不能同时被完整满足的判断，不得只是正确价值口号。
- 每个 `costly_commitment` 必须指出作品愿意牺牲的便利，例如爽点、圆满、推进速度、主角正确性或读者即时认同。
- `forbidden_resolutions` 必须约束因果和结局，不能只约束用词。
- `protected_dignity` 约束叙事如何对待失败者、弱者和作者不认同的人，不等于免除行为后果。
- `narrative_mercy` 与 `narrative_cruelty` 必须同时存在，防止作品只有温和理解或只有惩罚宣判。
- `deliberate_silences` 指定哪些价值问题只能通过选择与后果呈现，不由叙述者宣布答案。

## 项目创建工作流

### 向导模式

项目创建向导增加作者选择步骤，只允许以下三种模式：

1. `reuse`：绑定已有 Profile 的精确版本，默认推荐。
2. `derive`：从已有精确版本创建新 Profile 版本分支，并只保存用户明确提交的差异。
3. `create`：创建新的 Profile 和首个版本。

向导必须展示绑定的显示名、revision 和摘要，不得只展示可漂移的 Profile 名称。提交后在同一事务中创建或确认 Profile 版本、创建项目并建立绑定；任一步失败时不得留下孤立项目或半完成绑定。

`project.wizard.submit` 仍只创建项目容器和记录用户约束，不直接调用 LLM，不生成或锁定 Story Direction。创建完成后，Main Agent 读取绑定的 `creator_signature`，启动 Trace，并将其精确 ref/hash 传给 方向智能体。

### 兼容性

- 现有无作者绑定的项目必须继续可读、可投影和可导出。
- 旧项目首次进入新的规划流程时，由用户显式选择“绑定已有 Profile”或“创建 Profile”；不得自动猜测作者思想。
- 未绑定 Profile 的旧项目不得伪造默认作者签名。允许沿用既有 Story Direction，但 Writer run 若声明使用本功能，必须失败关闭并报告缺少 `style_refs`。

## Agent 与 Catalog 改动

### 方向智能体

- 在 `minimum_inputs` 增加精确 `creator_signature_ref`；引用必须包含 profile ID、revision 和 Hash。
- 更新 `story-direction` Catalog 包，使其根据 Project Profile、用户约束和作者签名生成少量可比较 Direction 候选。
- 候选必须说明继承了哪些 `creator_signature` 约束、为本书形成了什么 `book_soul`，以及两者是否存在冲突。
- 作者签名与用户的新项目约束无法兼容时，返回明确冲突，不得在 Direction 中静默改写 Profile。

### 下游规划 Agent

- Architecture 将 `book_soul` 转换为可重复施压的叙事机制、立场呈现方式和信息留白规则。
- Strategy 规定核心矛盾如何阶段性奏效、反噬和产生不可逆代价。
- Character 为主要人物分配相互冲突且各自有尊严的答案；不得让所有角色替作者发言。
- World 只实现能承载这些冲突的制度、资源和规则，不把价值立场伪装成世界客观真理。
- Chapter Plan 增加 `soul_pressure` 和 `moral_residue`：前者说明本章如何触碰核心矛盾，后者说明结尾留下什么不能被标准答案完全消解的后果。

### Writer Agent

- 将现有 `style_refs` 明确为一组精确引用，至少包含绑定的 `creator_signature` 版本、锁定 Direction 和适用的 POV/风格引用。
- Writer 只能表现已确认约束，不得自行创建新的作者思想、重写 `book_soul` 或为了强化观点改变 Chapter Plan。
- 纯动作、过渡和信息场景可以降低思想前景强度；不得要求每个场景机械复述全部作者约束。
- 完整章节仍由临时 Writer Agent 生成；本任务不得扩大 Writer 的保守触发范围。

### Review Agent

扩展现有规划与正文 Review Profile，至少检查：

- `creator_signature` 继承是否准确，是否出现未确认的人口属性推导或具体作者模仿；
- `book_soul` 是否具有真实内部矛盾和有代价的承诺；
- 对立立场是否由有能力、有合理动机的人物承担；
- 章节是否通过选择和后果表达思想，而不是叙述者总结；
- Writer 是否为了爽点、圆满或推进方便违反 `forbidden_resolutions`；
- 多章节之间是否出现作者立场漂移、所有人物同声或相同母题机械重复。

Review 只审查绑定 Hash 的不可变资产，不重写作者签名、规划或正文。

## 变更与失效规则

- Profile 新建版本不影响任何已绑定旧版本的项目。
- 项目切换到另一 Profile 版本必须显式执行 rebind，提供 `expected_version`；不得因 Profile 更新自动漂移。
- 已存在 locked Direction 时，rebind 必须在运行中的项目 Trace 内完成，并将当前 Direction 及全部后代标记为 `stale`；不得自动重生成。
- rebind 的 Trace step 必须记录旧/new profile revision、Hash、用户原因和受影响资产列表。
- 只调整单章 `scene_mode` 或人物措辞、不改变 `book_soul` 和章节状态时，不得触发全链失效。
- 修改 `book_soul` 必须产生新的 Direction 候选，走方向智能体、独立 Review 和锁定流程，不允许直接编辑锁定 Direction。

## MCP 与投影范围

### MCP

至少提供以下能力，精确工具名可在实现时统一，但不得绕过统一 `novelos` Server：

- 创建、列出、读取、修订和归档 Creator Profile；
- 读取精确 Profile 版本及其 Resource；
- 查询项目当前作者绑定；
- 原子创建项目并建立作者绑定；
- 在 Trace 内显式 rebind，并返回失效影响；
- 为 Agent 构建包含精确版本和 Hash 的只读作者约束引用。

所有权威数据访问继续经过 MCP；Skill、临时 Agent 和向导页面不得直接访问 SQLite。

### 用户投影

刷新项目投影时增加：

```text
novels/<项目目录>/
└── 创作约束/
    ├── 作者签名.md
    └── 本书创作灵魂.md
```

- `作者签名.md` 展示绑定的 Profile、revision、Hash 和结构化约束。
- `本书创作灵魂.md` 只展示 locked Direction 中的当前 `book_soul`；尚未锁定时明确显示缺失，不展示候选冒充权威。
- `manifest.json` 记录两个文件的来源 ref、版本与 Hash，同一权威快照必须确定性生成。
- 创建 Profile、项目绑定、Direction 候选、Agent 输出、Review 或 rebind 后，Main Agent 必须刷新项目投影。

## 数据迁移、备份与导出

- 新增单向 Schema migration，不改写历史 migration 文件。
- 更新迁移 manifest、数据库备份/恢复、JSONL 导出和仓库卫生检查，使 Creator Profile、版本与项目绑定可完整恢复。
- 迁移后旧项目保持“未绑定”状态，不创建合成 Profile。
- 导出数据必须能证明项目绑定到哪个精确 Profile revision/hash；恢复后引用关系和 Hash 必须一致。

## 非目标

- 新增常驻作者 Agent、作者人格 Agent 或第九个规划资产 Agent。
- 根据年龄、性别、学历、职业等属性自动生成文风或思想。
- 模仿、复刻或规避检测地模拟具体作者的可识别风格。
- 让 Writer 自行决定项目主题、价值答案或改写锁定规划。
- 用固定句长、成语密度、对话比例或“每 N 章一个爽点”替代语义判断。
- 在本任务中实现系列级 `series_soul`、选集模型或同项目多套独立 Direction。
- 宣称消除 AI 痕迹或在未完成质量实验时扩大 Writer Agent 触发范围。

## 实施顺序

只有前一项达到验收条件后才能开始后一项：

1. 冻结 `creator_signature`、Profile 版本、项目绑定和 `book_soul` 契约，补充 JSON Schema 与失败关闭夹具。
2. 增加数据库 migration、Profile/版本/绑定 Service API，以及备份、恢复和导出覆盖。
3. 扩展项目向导的 `reuse`、`derive`、`create` 模式，完成原子提交和旧项目兼容。
4. 更新 方向智能体 输入、Direction Catalog 与 Review Profile，将 `book_soul` 接入现有锁定链。
5. 更新下游 Catalog、Chapter Plan、Writer `style_refs` 和正文 Review，使约束真正进入规划与正文。
6. 实现显式 rebind、Direction 全链失效、Trace 证据和并发版本检查。
7. 扩展项目投影、manifest、文档和端到端协议测试。
8. 运行确定性验收和受控质量实验；根据证据收口状态。

## 验收标准

- [x] 同一 Creator Profile 可被两个新项目绑定，两个项目均保存精确 revision/hash，不随 Profile 后续修订漂移。
- [x] `reuse`、`derive`、`create` 三种向导模式均能原子创建项目和绑定；失败不会留下半完成数据。
- [x] 旧项目无需绑定即可读取、投影、备份和恢复，系统不会自动合成作者思想。
- [x] 方向智能体 的候选包含契约完整的 `book_soul`，并绑定精确 Creator Profile 版本和当前 Trace。
- [x] 同一 `creator_signature` 可生成不同项目的不同 `book_soul`，且 Review 能识别机械复制与无代价口号。
- [x] Chapter Plan 明确包含适用的 `soul_pressure` 与 `moral_residue`，不要求纯过渡场景机械前景化母题。
- [x] Writer run 的 `style_refs` 能追溯到 Creator Profile revision/hash、锁定 Direction 和 POV/风格引用。
- [x] rebind 使用错误 `expected_version`、错误 Hash、已结束 Trace 或跨项目引用时失败关闭。
- [x] 成功 rebind 会把当前 Direction 与全部规划后代标记为 `stale`，保留旧 Profile 版本和审计证据，且不自动重生成。
- [x] 投影只把 locked Direction 的 `book_soul` 展示为当前权威内容，manifest 可逐文件校验来源 Hash。
- [x] 备份、恢复和导出完整保留 Profile 历史版本、项目绑定与 Hash。
- [x] Review 能拒绝人口属性推导、具体作者模仿、所有人物同声、廉价结局和叙述者代替剧情讲道理。
- [x] 不增加常驻 Agent、规划资产类型或独立 MCP Server，不改变 Writer 和上下文构建智能体 的保守触发条件。
- [x] 根测试、MCP 测试、manifest、备份/导出、仓库卫生和 `compileall` 全部通过。

## 验收证据

- 精确版本、三种创建模式、失败原子性、绑定 Direction/Writer/Chapter Plan、rebind 及其 Trace
  证据：`mcp/novelos/tests/test_creator_profiles.py`、`test_project_wizard.py`、`test_protocol.py`。
- 旧项目兼容、仅 locked Direction 投影、manifest 来源 ref，以及备份恢复和 JSONL 导出：
  `test_projection.py`、`tests/test_data_export.py`、Schema 11 的 restore/export drill。
- 人口属性字段与正向具体作者模仿均失败关闭；Review Catalog 明确把人口属性推导、具体作者模仿、
  所有人物同声、廉价结局与叙述者代替剧情设为阻断项：`creative_contracts.py`、
  `test_creator_profiles.py`、`tests/test_author_signature_quality_protocol.py`。
- 2026-08-01 已通过根测试 53 项、MCP 测试 132 项，以及迁移、Catalog、种子、备份、导出、
  迁移摘要、仓库卫生、切换、编译和补丁格式全部门禁。

## 质量验证

在完整 70-case Agent 质量实验仍处于 `DEFERRED` 期间，本任务只执行边界明确的小规模 A/B，不据此宣称通用质量结论或扩大 Agent 触发范围。

固定同一 Chapter Plan、Canon 和长度，至少比较：

- 无作者约束基线；
- 绑定 Profile 但没有有效 `book_soul` 的失败关闭路径；
- 同一 Profile 下两个不同 `book_soul`；
- 两个不同 Profile 下的同一场景；
- 多章节输出中的思想与声音漂移。

评估维度至少包括 `plan_fidelity`、`canon_accuracy`、`scene_causality`、`character_voice`、`prose_quality`、`authorial_stance_fidelity`、`voice_distinguishability`、`character_independence` 和 `long_form_drift`。必须保存原始输入、原始输出、模型与 Prompt 标识、独立 Review、评分和可重算汇总；缺少真实模型输出或独立评审时结果保持 `BLOCKED`，不得伪造通过证据。

## 验证命令

```bash
.venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python scripts/build_migration_manifest.py --output-dir tasks/migration --check
.venv/bin/python scripts/build_catalog_manifest.py --check
.venv/bin/python scripts/build_agent_quality_dataset.py --check
.venv/bin/python scripts/backup_novelos_database.py --check
.venv/bin/python scripts/export_novelos_data.py --check
.venv/bin/python scripts/check_repository_hygiene.py --check
.venv/bin/python scripts/check_cutover_readiness.py --check
.venv/bin/python scripts/check_cutover_plan.py --check
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 完成条件

只有生产路径已接通、全部验收项有可审计证据、完整验证通过，并且没有用文档或测试桩冒充实现时，才允许将本任务标记为 `DONE`。质量实验若因缺少真实模型或独立评审保持 `BLOCKED`，必须明确区分“功能实现完成”和“语义质量未证实”，不得据此扩大生产路由。
