# Task 32: 卷级配角班底（volume_characters）——动态配角第二造人口

**状态**: `DONE`

**范围**: Task 30 给了动态配角一个章级入口（执行卡微档案），卷级冲突线的配角载体只能逐章预登记或挤进人物契约。本任务在卷纲开第二个规划端造人口：卷级配角班底。链路：volume_outline 候选 metadata.`volume_characters` → 审查（无源载体 blocking）→ 卷纲锁定后主控经 `novelos_register_characters.py --entry` 落人物注册表（source:"volume_outline"）→ 本卷章纲执行卡直接消费（标注「卷纲已登记」，免逐章微档案）。schema/脚本/三处 prompt/两处审查/SKILL/flows 六端同步。

## 设计要点

- **载体溯源强制**：本卷各冲突线的人物载体必须逐一指认来源——契约 roster / 在库配角（人物注册表）/ 本卷新生成；无源载体 = blocking（planning-volume-outline-review 第 8 项）。
- **硬边界**：班底不得生成 main（主角/核心对手/主锚点/卷级关键载体仍归人物契约，缺人走 change proposal）；不得承载跨卷职责（需要回归/常驻时候选内标注「待 change proposal 升级进人物契约」）；不与在库人物重名。
- **字段契约**：每人 `name`（≤60）/ `role_class`（secondary 卷内复用 | minor 一次性）/ `arc_role` 一句话职责 / `预期退场`（七种退场型 + 持续活跃共八值，与 character_roster 同源；卷级配角默认卷内退场）/ `微档案`（一句话职责 + 可写细节）/ `登记备注`。schema 见 `config/schemas/planning-candidate.schema.json` 的 `$defs/volume_characters`（maxItems 40，additionalProperties false）。
- **注册表落点**：`--entry` 扩展——条目可带 `arc_role` / `预期退场` / `来源卷`（1-99 整数）/ `微档案` / `登记备注` / `source:"volume_outline"`，随 state_json 落库；非法 `预期退场` / `来源卷` 非零退出。
- **审查四源授权**：entity-authority-review 人物权威来源由三源扩为四源（契约 roster + 卷级班底 + 执行卡微档案 + character_status 状态迁移）；班底人物承载跨卷职责而无 change proposal = warning。

## 任务项

- **32-1** schema：`$defs/volume_characters` + metadata properties 挂载
- **32-2** 脚本：`novelos_register_characters.py --entry` 班底字段校验与落库说明
- **32-3** 方法论同步：volume-outline（生成节+自检+metadata 出口）、chapter-plan-execution-card（先查班底再微档案）、character-contract（次要角色分流改两级）、planning-volume-outline-review（第 8 项）、entity-authority-review（四源）、planning-character-contract-review（措辞）；novel-planning SKILL 第 8 步锁定后落库、flows.md 动态创建步两级化
- **32-4** 测试补齐 + 四命令验证 + 验收记录

## 验收记录

- **32-4（验证）**：四命令全绿——`unittest discover` **138 tests OK**（+3）、`compileall` OK、`check_repository_hygiene --check` 0、`build_catalog_manifest --check` 0。
- 新增测试：`test_entry_volume_characters_fields`（班底条目经 `--entry` 落库——arc_role/预期退场/来源卷/source 均入 state_json）、`test_entry_volume_characters_validation`（非法 `预期退场`、非整数 `来源卷` 非零退出）、`test_entry_volume_characters_schema`（`$defs/volume_characters` 独立校验：合法班底通过、role_class=main 被拒）。
- 全部改动一次提交落地：`71cd6be`（commit 未带 `[T32-x]` 子项标号——工作先于本记录实施，追溯以 commit hash 为准）。

## 文档变更清单

- `config/schemas/planning-candidate.schema.json`：`$defs/volume_characters`（required name/role_class/arc_role/预期退场；role_class 仅 secondary/minor）+ metadata 挂载。
- `scripts/novelos_register_characters.py`：`_validate_entries` 增 `预期退场`（EXIT_TYPES + 持续活跃）与 `来源卷`（1-99 整数）校验；docstring 补班底入口说明。
- `catalog/skills/planning/volume-outline/prompt.md`：新增「卷级配角班底」节（溯源+硬边界+锁定后落库）、自检第 6 项（原「形式」顺延为第 7 项）、「metadata 要求」节。
- `catalog/skills/planning/chapter-plan-execution-card/prompt.md`：微档案条款改为先查本卷班底，班底内标注「卷纲已登记」直接消费。
- `catalog/skills/planning/character-contract/prompt.md`：次要角色分流两级（卷级班底 / 章级微档案），roster 出口说明同步。
- `catalog/skills/review/planning-volume-outline-review/prompt.md`：rubric 第 8 项（无源载体 blocking / main blocking / 跨卷未标注 warning / 重名 warning / 叙述与数组不一致 warning）。
- `catalog/skills/review/entity-authority-review/prompt.md`：三源 → 四源；班底跨卷无 proposal = warning。
- `catalog/skills/review/planning-character-contract-review/prompt.md`：全量覆盖条款分流措辞。
- `.agents/skills/novel-planning/SKILL.md`：第 8 步 volume_outline 锁定后班底落注册表。
- `documentation/flows.md`：人物生命周期「动态创建」步两级化。
- `tests/test_register_characters.py`：+3 用例。
