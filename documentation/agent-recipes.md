# 阶段配方矩阵（Agent Recipes）

每个创作阶段的 agent 配方在这里定死：**消费槽位（加载什么）× 发散档位（怎么想）× 决策权限（能定什么）× 输出契约 × 失败行为**。机器权威是 `config/agent-recipes.json`；本文的表格由其渲染（`tests/test_recipe_matrix.py` 校验两处同步，改 JSON 后须同步重新生成表格段落）。

## 为什么需要配方矩阵

1. **加载是质量杠杆**：加载多了注意力稀释，加载少了失准——每阶段的输入应当是最小充分集，配方把这个选择从「执行时凭感觉拼」变成「设计时定死、机器校验」。
2. **发散度分层**：方向层要真候选（expansive），正文层要逐字执行（constrained）——同维度同时驱动生成端指令与审查端 rubric，不会拿发散标准卡正文。
3. **决策权限显式化**：sub agent 出候选（propose_only）、审查给 verdict 但豁免归主控（judge）、写作照合同执行（execute）、融合发现错配必须上报（flag）——「哪个 agent 在哪个阶段能决定什么」是契约不是惯例。

## 档位与权限定义

- 发散档位：`expansive`（多候选/禁早收敛/张力菜单）→ `balanced`（单方案/结构内自由/decision_points 显式）→ `constrained`（逐字锚定/防指纹禁令/清单逐项过）。审查资产 divergence 为空 = 跟随被审对象档位。
- 决策权限：`propose_only` / `judge` / `execute` / `flag`（定义见 JSON `decision_scopes`）。

## 全资产矩阵

<!-- BEGIN RECIPES TABLE -->
| 资产 | 槽位配方 | 发散档位 | 决策权限 | 输出契约 | 失败行为 |
|---|---|---|---|---|---|
| fusion（onboarding/creator-signature-fusion） | kernel_full, archetype_roster, project_setup, persona_fingerprints | expansive | flag | creator_derivation_candidate（jsonschema 信封 + 签名 v2 深层校验；v3 带 kernel_origin） | 错配警告 → 呈报用户裁决，未获裁决不落库；候选解析失败要求融合智能体重出，主控禁手工改写 |
| kernel_fusion（onboarding/author-kernel-fusion） | kernel_hints, project_setup, kernel_subject, persona_fingerprints, archetype_roster | expansive | flag | novelos.kernel.candidate.v1（信封 schema + author-kernel 深层两步校验；revise 带 base_version） | 内核撞车/单线创伤链/题目语域渗入 → 退回重做；表达层反馈误归因 kernel → 上报主控裁决 |
| direction（planning/story-direction） | project_setup, kernel_full, persona_full, genre_pack | expansive | propose_only | 候选正文（七节骨架）+ book_soul v2 十三字段（jsonschema） | 审查-修复循环；表里失联/假多样性自检不过即重做 |
| direction-review（review/planning-direction-review） | project_setup, kernel_full, persona_full, subject | 跟随被审对象 | judge | Review Receipt（findings: blocking/warning/note + evidence_refs） | blocking → 修复循环；对称可预算代价 → warning；同因复发/3 轮未收敛 → 升级用户 |
| architecture（planning/story-architecture） | project_setup, persona_full, upstream:direction, genre_pack | expansive | propose_only | planning-candidate 正文 + metadata（双引擎/四段式/防火墙） | 审查-修复循环；翻译完整度缺陷（字段无机制形态无豁免）blocking |
| architecture-review（review/planning-architecture-review） | subject, upstream:direction, upstream-reviews:direction, project_setup, persona_full | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| strategy（planning/story-strategy） | project_setup, persona_full, upstream:direction, upstream:architecture, genre_pack | balanced | propose_only | planning-candidate（阶段骨架/承诺-债务周期/代价账本） | 修复循环；阶段不得消解 unresolved_claims |
| strategy-review（review/planning-strategy-review） | subject, upstream:direction, upstream-reviews:direction, upstream:architecture, upstream-reviews:architecture, project_setup, persona_full, genre_pack | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| character_contract（planning/character-contract） | kernel_full, persona_full, project_setup, genre_pack, upstream:architecture, upstream:strategy, upstream:world_contract | balanced | propose_only | 人物契约候选（席位认领/strategy 弧职责挂接/persona 四用法；roster 档位机器门） | 修复循环；与上游矛盾 → change proposal 不隐式改上游 |
| character-contract-review（review/planning-character-contract-review） | subject, kernel_full, persona_full, project_setup, genre_pack, upstream:architecture, upstream:strategy, upstream:world_contract, upstream-reviews:architecture, upstream-reviews:strategy, upstream-reviews:world_contract | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| world_contract（planning/world-contract） | project_setup, persona_full, genre_pack, upstream:architecture, upstream:strategy | balanced | propose_only | 世界契约候选（岗位表/代价两轴/语域机器可读/strategy 对账） | 修复循环；规则自洽缺陷 blocking |
| world-contract-review（review/planning-world-contract-review） | subject, project_setup, persona_full, genre_pack, upstream:architecture, upstream:strategy, upstream-reviews:architecture, upstream-reviews:strategy | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| story_arc（planning/story-arc） | project_setup, persona_gate, genre_pack, book_soul, mechanisms, upstream:strategy, upstream:character_contract, upstream:world_contract | balanced | propose_only | 跨卷弧线候选（arcs/映射表/台账/卷计划 metadata——validate 机器门） | 修复循环 |
| story-arc-review（review/planning-story-arc-review） | subject, upstream:strategy, upstream:character_contract, upstream:world_contract, upstream-reviews:strategy, upstream-reviews:character_contract, upstream-reviews:world_contract, project_setup, persona_gate, genre_pack, book_soul, mechanisms | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| volume_outline（planning/volume-outline） | upstream:story_arc, upstream:world_contract, book_soul, mechanisms, character_roster, persona_gate, project_setup, genre_pack, prev_volume_outline, promise_ledger | balanced | propose_only | 卷纲候选（卷型 + 高潮门 + 线弧双向 + 双台账对账 + 班底/设定双通道） | 修复循环 |
| volume-outline-review（review/planning-volume-outline-review） | subject, upstream:story_arc, upstream:world_contract, book_soul, mechanisms, character_roster, persona_gate, upstream-reviews:story_arc, upstream-reviews:world_contract, project_setup, genre_pack, prev_volume_outline, promise_ledger | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| chapter_plan（planning/chapter-plan-execution-card） | upstream:volume_outline, upstream:character_contract, upstream:world_contract, character_roster, persona_gate, project_setup, promise_ledger | balanced | propose_only | 章纲候选（含 soul_pressure 与 moral_residue + 弧线挂接） | 修复循环 |
| chapter-plan-review（review/planning-chapter-plan-review） | subject, upstream:volume_outline, upstream:character_contract, upstream:world_contract, character_roster, persona_gate, upstream-reviews:volume_outline, project_setup, promise_ledger | 跟随被审对象 | judge | Review Receipt | 修复循环 |
| chapter_draft（writing/chapter-draft-generation） | kernel_full, persona_full, upstream:chapter_plan, canon_minimal, review_feedback, world_lexicon, character_essence | constrained | execute | 章节正文（style_refs 逐字锚定 + 防指纹禁令） | prose-quality-review 循环；persona 盲区场景按绕开方式处理 |
| prose-quality-review（review/prose-quality-review） | subject, kernel_full, persona_full, upstream:chapter_plan, world_lexicon, character_essence | 跟随被审对象 | judge | Review Receipt（盲区场景未绕开 = blocking） | 修复循环；3 轮未收敛/同因复发 → 升级用户 |
| continuity-extraction（continuity/continuity-candidate-extraction） | subject, canon_minimal | constrained | execute | 连续性候选条目（六类账本） | continuity-quality-review 后晋升；不实条目拒绝 |
| continuity-quality-review（review/continuity-quality-review） | subject, canon_minimal | 跟随被审对象 | judge | Review Receipt | 条目拒绝/修订循环 |
| cross-consistency-review（review/planning-cross-consistency-review） | subject, upstream:direction, upstream:architecture, upstream:strategy | 跟随被审对象 | judge | Review Receipt（跨资产一致性） | 修复循环 |
| entity-authority-review（review/entity-authority-review） | subject | 跟随被审对象 | judge | Review Receipt（实体权威边界） | 修复循环 |
| planning-quality-review（review/planning-quality-review） | subject | 跟随被审对象 | judge | Review Receipt（兜底通用质量） | 修复循环；专属 review skill 存在时优先专属 |
<!-- END RECIPES TABLE -->

## 演进规约

- P2 各资产模块化时，其 manifest 的 `divergence` / `decision_scope` 必须与本矩阵全等；`data_slots` 只许在矩阵先行增长后跟进（测试强校验：manifest ⊆ matrix）。
- 新增槽位先登记 `slot_vocabulary` 与受影响资产行，再实现 resolver（`scripts/novelos_compose_prompt.py` 的 `SLOT_REGISTRY`）。
- 未注册 composer 的资产行（composer_key=null）是 P2/P3 的落地目标配方，模块化完成时补 composer_key。
