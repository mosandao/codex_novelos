# Task 34: 架构阶段深度反向审计与双层引擎重构（architecture 生成/审查/管线/机器门）

状态：`DONE`（2026-08-22）

## 背景

继 Task 33（direction 反向审查批次）后对 architecture 阶段做四轮反向审计：①人格与 setup 维度消费核验；②硬格式/质检门的发散度削平通道推演；③柯南式单元剧模型对「并列双引擎」模型的证伪；④联网补充叙事学/连载工业知识的深度挖掘。确认问题分三层：**管线级**（上游 metadata 与审查回执在阶段边界蒸发）、**模型级**（并列双引擎硬编码网文形态，误伤柯南/X 档案式低密度主线）、**审查级**（槽位贫血——声称查 persona 却不注入 persona；审查模块为生成侧自检的镜像复述）。本批全量落地，含破坏性改动（双引擎模型重构、compose-manifest 槽位 pattern 放宽）。

## 审计发现（新漏洞，超出 T33 轮）

1. **审查槽位贫血**（blocking 级）：direction-review 注入 `[project_setup, kernel_full, persona_full, subject]`，architecture-review 仅 `[subject, upstream:direction]`——审查第 7 项要求核 POV 契约（persona 消费）却看不到 persona 全文。
2. **上游 metadata 蒸发**：T33 的 lineage/cadence_plan 落 direction metadata，而 `upstream:` 槽只注正文——数字门产物到 architecture 边界消失，无人核验「兑现结构节拍与 cadence_plan 数字一致」。
3. **strength 跨阶段蒸发**：direction 锁定回执的 strength 指认/豁免记录不流入下游，修复保护令只在同资产内有效。
4. **genre-null 回退文案指向不存在的模块**（architecture 无 genre-null 模块）。
5. **测试证据无要求**：压力/油耗测试是声称，输出不含记录，审查无从核验。
6. **终局闭合双重孤儿**：骨架第 6 节在生成自检与审查清单均无对应门。
7. **题材死槽**：genre_pack 注入但主干零消费指令、审查零 check-genre 模块（direction 两侧成对）。
8. **direction 非 book_soul 产出静默丢弃**：美学基因/情感登记/读者画像无翻译位也无豁免声明。
9. **发散度削平四通道**：无 strength 保护（修复削平异类）/咬合声明式合规（「A 喂 B」空话可过）/赏金阶梯例证锚定无复用禁令/expansive 档位无操作化纪律。
10. **规模盲**：油耗 ≥3 级不分档（短篇过度工程、超长篇门槛过松）、主干硬编码超长篇意象（300 万字 ≈ 上千章）。

联网知识补充（可信来源）：story engine = 可再生情节生产机制（Orchard Project / Scriptnotes）；X 档案经典配比为 MOTW 主体 + 神话线每季 handful 集聚于季首季尾，**后期神话线过度错综是公认崩坏点**（主线膨胀与主线缺失同罪）；中文网文工业经验值——每章 1 小爽点、3-5 章 1 大爽点、连续 3 章无爽点即弃书风险（单元弧粒度与免费平台密度锚）。

## 改动清单

### 模型重构（生成侧 `planning/story-architecture/prompt.md`，破坏性）

- **并列双引擎 → 双层嵌套引擎**：
  - 生产层 = 单元机器，粒度改**单元弧（1-N 章）**（原「章级」混淆章与单元弧）；免费平台常规 2-5 章/单元；
  - 统合层 = 卷级统合器，产出三件调度规格：**主线节拍表**（beats/卷可为 0——空窗卷合法、空窗有上限、爆发点有位置）/ **单元配额与筛选器** / **注入配额**（每 k 单元 1 个主线承载单元 + 载荷类型：线索/人物揭示/压力前置）；
  - **主线密度声明**（必填）：tier 高/中/低 + beats_per_volume + gap_limit_volumes + burst_positions；**柯南/X 档案低密度形态显式合法**，但须与 scale/平台/promise_cadence（cadence_plan 数字）对表论证；**主线膨胀同罪**（X 档案后期教训，释放阶梯层数与 beats 须有上限意识）。
- **耦合双形态**：I/O 耦合（写明实体字段，非「A 喂 B」空话）‖ 配额注入耦合（k 值+载荷类型），可组合；metadata 每机制 coupling 条目必填，孤岛 schema 层不合法。
- **题材翻译位**（genre_pack 双态）：非空 = 三条实体翻译（母题库→输入源 / 常规桥段→变奏对象 / 题材禁忌→防火墙补充）；缺位 = 显式声明从 direction 与 persona 库存推导。
- **direction 非 book_soul 产出处置**：美学基因/情感登记/读者画像/题材逐样消费或显式豁免，静默丢弃 = warning。
- **persona 四用法**（三→四，各有验收门）：目光→信息时序（可指认规则）/ 盲区→机制不支撑清单（逐条覆盖 cannot_write）/ 有限视角→POV 契约 / **差异化库存→单元输入源库存**（career_track 等至少一项进输入源）。
- **四段式引用双源**：direction 字段 + persona 部件，metadata sources 结构化，单源血缘过不了 validate。
- **引擎验证记录落正文**：压力测试 ≥5 输入×产出摘要、油耗分级表不再是声称。
- **油耗×scale 档位化**：短篇 ≥2 / 中长篇 ≥3 / 超长篇 ≥5。
- **发散纪律**（expansive 操作化）：主线密度与引擎形态至少各探索两档再收敛；例证复用禁令；上游 strength 不削平。
- **终局闭合入自检**（无收束设计不完整）；好坏对照新增低密度节拍表正例与「每卷对撞」硬编码反例。

### 审查侧（`review/planning-architecture-review/`）

- **manifest 槽位补齐**：`[subject, upstream:direction, upstream-reviews:direction, project_setup, persona_full]`（修贫血）；配方矩阵 `config/agent-recipes.json` 先行扩 + `documentation/agent-recipes.md` 表再生。
- **prompt.md 重写**（36→57 行内）：检查清单 8→11 项——双层引擎与统合三件套、**主线密度一致性**（对表 + 主线膨胀 warning）、耦合双形态核验（空话 = warning）、四段式**血缘双源抽查**、测试证据核验（无记录 = warning）、**终局闭合**、**库存反向对账**、**证伪与读者模拟**（空窗卷弃书点/单元重复疲劳/主线膨胀瓦解）；Blocking 补密度失配/油耗低于档位/终局无收束/strength 削平；**strength 通道**节；证据要求补 persona 全文引用（不得凭候选转述）。

### 管线（`scripts/novelos_compose_prompt.py`）

- **`_slot_upstream` 补注 metadata**：每 scope 正文后附 `--- 上游 metadata ---` 节——lineage/cadence_plan/机制清单跨阶段流动（影响全部下游资产组装，破坏性）。
- **新增 `upstream-reviews:<asset>` 前缀族槽**：locked 上游的最新审查回执（verdict + findings 逐条，strength/accepted_risk/defer 标注；无回执显式占位节）——strength 与豁免的跨阶段传递。
- **`_slot_genre_pack` 回退文案资产无关化**：不再指向 architecture 不存在的 genre-null 模块。
- `compose-manifest.schema.json` 槽位 pattern 放宽（允许连字符前缀族 `upstream-reviews:`）。

### 机器门（schema + validate）

- **`config/schemas/architecture-metadata.schema.json`**（新）：`mechanisms[]`（2-16，sources{source_type: direction_field/persona_part/genre_pack/setup/reference_material}、downstream、coupling{form: io/quota/both, spec} 必填——孤岛 schema 层不合法）、`mainline_density`（tier/beats_per_volume/gap_limit_volumes/burst_positions）、`unit_arc`（min/max chapters，上限 12）、`engines`（production/integrator 各 escalation_levels）。
- **`scripts/novelos_validate_architecture.py`**（新，`--scale` 数字门）：血缘双源覆盖（direction_field + persona_part 各至少一条）；油耗×档位下限（短篇 2/中篇 3/长篇 3/超长篇 5，与 book_soul cadence 规则同源）；tier×beats 一致性（高 ≥1/中 [0.5,1)/低 <0.5）；**空窗上限×档位**（短篇 1/中篇 2/长篇 3/超长篇 4）；单元弧粒度倒置检查。

### 编排层

- **novel-planning SKILL**：architecture 步骤改双层引擎表述 + validate 命令；新增 **architecture metadata 速查表**节。
- **AGENTS.md**：确定性脚本清单登记 `novelos_validate_architecture.py`。

### 测试

- `tests/test_architecture_validate.py`（新，15 项）：schema 兼容/孤岛不合法/双源缺失/油耗门（超长篇 5 级）/**柯南式低密度合法用例**/空窗超档/粒度倒置。
- `tests/test_slot_resolution.py`：内存库加 reviews 表；direction seed 带 cadence_plan metadata；新增 upstream metadata 注入断言 + upstream-reviews strength/defer 渲染断言 + 无回执占位断言。
- `tests/test_compose_prompt.py`：SIZE_BUDGET architecture 130→170（实测 150，注释注明 T34 缘由；architecture-review 60 保持，实测 57）。

## 验收

- `.venv/bin/python -m unittest discover -s tests`：**168 tests OK**（151 + 17 新增）
- `.venv/bin/python -m compileall -q scripts tests catalog config`：通过
- `check_repository_hygiene.py --check`：通过
- `build_catalog_manifest.py --check`：通过
- validate CLI 冒烟：超长篇档 `escalation_levels=3` + 无 persona_part + 单机制 → FAIL 非零退出（四条门全中）；柯南式低密度（beats 0.3/空窗 3/油耗 5/爆发点卷首卷尾）+ 超长篇 → PASS。
- composer 冒烟：architecture 主干新节（双层引擎/密度声明/耦合规格/验证记录/发散纪律/终局闭合）随组装命中；genre-null 回退不再引用不存在模块。

## 设计取舍记录

- **不注入 kernel_full**（与 direction 不同）：persona 为本层第一因（分身自带完整人格）；内核二阶保真经 upstream metadata 的 lineage（source_type: kernel 条目）可追溯，避免重复注入噪音。
- **downstream 枚举保持三值**（strategy/character_contract/world_contract）：统合层节拍表经 strategy（卷节奏骨架所有者）传递至 volume_outline，不跨层直连。
- **空窗上限数字**（短篇 1/中篇 2/长篇 3/超长篇 4）：以 X 档案「神话线集聚季首季末」≈ 每 1 卷一 burst 为锚随规模放宽，validate 可随经验调参。

## 遗留说明

- 主线 beats 与 cadence_plan.fulfillment_count 的精确换算（beat 是否等于大兑现）未做机器门——语义判读留给 architecture-review 第 3 项，数字门只管各自边界。
- 旧 architecture 资产（无新 metadata 结构）属历史锁定数据，不追溯校验；新候选必须过 validate。
