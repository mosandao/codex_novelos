# Task 35: 战略阶段深度反向审计与全量落地（strategy 双侧重构）

状态：`DONE`（2026-08-22）

## 背景

继 T33（direction）、T34（architecture）后对 strategy 阶段做同口径反向审计。四轮审计共确认十四项缺口（F1-F14）：

**第一轮（persona/setup 消费）**
- F1 题材盲区：卷节奏骨架对题材完全无感（仙侠境界弧/悬疑案件弧/竞技赛季弧形状差异消失），比 T34 后的 architecture 还退一步。
- F5 无 schema 无校验器：strategy 是唯一有结构化上游（book_soul v2 + architecture-metadata）却无自身 metadata schema、无 validate --scale 的规划阶段；decision_points 只有松散 array。
- persona 三层缺席：无槽位、无方法论条款、审查无输入无条目——层×卷映射（信息时序=目光领域）、阶段终局事件形态（场景类型=盲区领域）、收益主形态（频道通用化）三处 persona 敏感决策全部裸奔。

**第二轮（用户三条硬约束质疑）**
- F6 阶段量化自相矛盾：短篇=30 万字以下，但「每阶段平均 ≥20 万字」与「30 万字短篇 ≤2 阶段」互斥（2 阶段即 15 万均值），30-40 万字带宽无解。
- F7 代价落点未限定：现行「人物或世界留下不可逆代价」未限定落点，字面执行可产出主角永久损伤（拆生产引擎）；且缺压制代价桶（金手指封印一卷这类经典弧装置无处安放）。
- F8 book_soul 半数字段静默缺位：protected_dignity（谁能死）/narrative_cruelty/mercy（代价落点）/recurring_tests（防阶段重复测试）/deliberate_silences（合法挖坑不埋通道）全部无消费。

**第三轮（管线/一致性）**
- F2 T33/T34 新字段语义断链：cadence_plan、mainline_density、engines 经 T34 管线修复数据已可达，但翻译表五行没它们、自检没有、审查不查。
- F3 跨阶段数字无对账：配对表行数 vs escalation_levels、总兑现次数 vs fulfillment_count、卷节奏骨架 vs beats_per_volume×卷数。
- F4 豁免/亮点通道断链：defer→strategy 的 warning 无处落地（strategy-review 无 upstream-reviews 槽），上游 strength 不可见（修复可能削平）。

**第四轮（联网锚点深挖）**
- F9 中盘续命缺位：中期疲软是长篇头部弃书原因，主流解法 = 换地图（丝滑不清空人际）+ 矛盾递进链 + 大纲先行——strategy 是防线所在层，原文只字未提。
- F10 终局纪律残缺：只防了 forbidden_resolutions；无收束预算（100 条 claim 塞一个终局 = 鞭尸式赶工烂尾）、无终局字数下限（压缩赶工）、无开放引擎显式通道（12 年无尾化必须是设计不是事故）、无首尾呼应要求（结尾要兑付 promise+progress 两笔）。
- F11 progress 与 payoff 不分：Sanderson promise-progress-payoff 分形结构——中段健康靠 progress（推进感）而非每段 payoff；「逐阶段抛谜即兑」产出节拍器节奏。
- F12 下游交接清单缺失：character/world 契约以 strategy 为输入，但 strategy 不产出每阶段人物弧需求/世界状态变更，下游只能自创（与 architecture 的移交清单对偶缺失）。
- F13 发散纪律缺位：direction/architecture 都有发散纪律节，strategy 无。
- F14 层×卷粒度错位：claim 揭层落到「卷」但卷数此刻未知（volume_outline 未做），应以阶段为主锚。

## 用户裁决（三条硬约束的划界）

1. **不可逆代价**：不可逆/压制分桶；主角永久损伤（情感永久创伤/残废/灵魂）不在默认菜单，仅 book_soul 显式声明可入；死亡名单过 protected_dignity；关系不可逆改变（决裂/信任崩塌）是合法载体不受误伤。
2. **承诺-收益配对**：逐阶段配对改跨阶段债务周期；即兴铺垫允许烂尾（不进账本不算债），登记承诺不许遗忘；deliberate_silences 是合法挖坑不埋通道。
3. **阶段量化**：事件判据为主（≥1 不可逆变更+螺旋轮换），字数为申报项；档位区间替代全局下限。

## 改动清单

### 生成侧（catalog/skills/planning/story-strategy/prompt.md，破坏性重写 110→128 行）

- **上游消费表 v3**：五行→七行（+双层引擎配置→阶段配比演化、+上游审查回执→strength 落点/defer 处置）；三处数字对账入列（fulfillment_count/escalation_levels/beats_per_volume×卷数）；book_soul 十三字段逐样处置表（F8）。
- **题材阶段形态位**（F1）：题材决定阶段阶梯形状，缺位显式声明禁默认模糊升级。
- **persona 四用法 strategy 版**：目光→揭层节奏；盲区→终局场面形态门（cannot_write 绕开：大战写奏报/庭审写门外）；有限视角→阶段 POV 契约；差异化库存→阶段燃料。
- **代价类型学**（F7）：不可逆/压制分桶 + 主角永久损伤门。
- **承诺-债务周期**（F11+约束二）：progress 八类/payoff 三档/存债连续 ≤2/登记承诺三分类/收束预算。
- **阶段量化 v2**（F6+约束三）：档位区间表（短篇 1-2/中篇 2-4/长篇 3-8/超长篇 5-12）。
- **中盘续命与终局纪律**（F9/F10）：换挡事件（丝滑不清空）；closed（收束预算+字数下限+首尾呼应）/open（喂料声明）双模式。
- **下游交接清单**（F12）；**发散纪律**（F13）；层×阶段映射（F14）。

### 审查侧（review/planning-strategy-review/prompt.md 重写，7→13 项）

新增：数字对账、代价类型学（主角永久损伤/protected_dignity=blocking）、承诺-债务周期、中盘续命、终局纪律（open 无喂料=blocking）、persona 四用法核验（盲区未绕开=blocking）、题材阶段形态、下游交接、证伪与读者模拟（中盘弃书点/赶工感/承诺遗忘投诉）；strength 通道；横向回执；证据要求（persona 引用原文部件）。

### 槽位与矩阵（矩阵先行）

- 生成侧 data_slots：3→5（+persona_full +genre_pack）。
- 审查侧 data_slots：3→8（+upstream-reviews:direction +upstream-reviews:architecture +project_setup +persona_full +genre_pack）——F4 修复，defer→strategy 移交项落地、strength 跨阶段可见。
- config/agent-recipes.json 两行 slots 同步；documentation/agent-recipes.md 表重生成。

### schema / 校验器 / 测试

- **config/schemas/strategy-metadata.schema.json（新）**：consumption 恰 7 行枚举全覆盖；stages[]（payoff/progress_types/costs 分桶 if-then：suppression 必带 release、protagonist_permanent 必带 declared_in_book_soul+ref）；claim_ledger 三分类；midpoint_renewal；terminal_mode closed/open 条件门；handoffs；decision_points 强类型。
- **scripts/novelos_validate_strategy.py（新）**：七行消费覆盖、阶段数×档位区间、存债连续上限、全书至少一兑付、中盘续命必备（≥3 阶段）、收束预算、终局字数下限、换挡位置合法。
- tests/test_strategy_validate.py（新，18 项：含 open 模式跳过收束检查、主角永久损伤声明门、三连存债拦截、档位边界）。
- tests/test_slot_resolution.py：+2 项（strategy 生成侧五槽 / strategy-review 双上游回执含 defer→strength）。
- tests/test_compose_prompt.py：SIZE_BUDGET strategy 110→150、strategy-review 60→75；两处旧断言更新（≥20 万字→档位区间；上游机制消费完整→七行翻译）。

### 编排层

- novel-planning SKILL：strategy sub agent 输入描述重写；「strategy metadata 速查表」新节；「节奏密度约束」修正（≥20 万下限废除 → 档位区间 + 事件判据）。
- AGENTS.md：登记 novelos_validate_strategy.py。

## 设计取舍记录

- **档位区间数字**：区间中位 25-40 万字/阶段与旧 ≥20 万启发式同源；区间内自由（前重后轻/中点爆发不受罚——F6 的教训是硬下限惩罚合法疏密分布），区间外 validate 拦截 + 审查豁免通道（accepted_risk）。
- **主角永久损伤不是全局铁律**：默认菜单排除 + book_soul 声明豁免——与 T33「黑暗内容要有主菜位、按书校准」哲学一致，悲剧向作品可在 direction 声明后合法使用。
- **登记承诺 vs 即兴铺垫二分**：用户「允许遗忘」限定在未登记铺垫——登记承诺遗忘与六账本连续性体系正面冲突（narrative_promises 账本存在的唯一目的）；deliberate_silences 是体系内合法的永不填通道。
- **层×阶段映射**（F14）：claim 揭层以阶段为主锚，卷数为估计值——卷的权威划分在 volume_outline。
- **open 模式跳过收束检查但保留主线密度对账**：柯南式开放引擎是合法商业形态，但单元机器供压能力仍须对表（无尾化必须是设计不是事故）。

## 验收

- `.venv/bin/python -m unittest discover -s tests`：**188 tests OK**（168→188，+18 validate +2 slots）
- `.venv/bin/python -m compileall -q scripts tests catalog config`：通过
- `check_repository_hygiene.py --check`：通过
- `build_catalog_manifest.py --check`：通过
- CLI 冒烟：PASS（长篇 4 阶段）/ FAIL（短篇 4 阶段→exit 1 档位门）/ open 模式（超长篇 6 阶段，跳过收束检查）三向验证。

## 遗留说明

- 三处数字对账（fulfillment_count/escalation_levels/beats_per_volume×卷数）中，fulfillment_count 与 escalation_levels 的精确对账在 validate 层不可机器判定（需要上游 metadata 同传），留在审查语义层（第 2 项）+ metadata.ref 引用抓手。
- 旧 strategy 资产（如有锁定）不回溯校验，新候选强制走 validate --scale。
- platform-free 模块的「蓄势卷最多连续一卷」与 debt_streak_limit=1（免费收紧）语义相近但层级不同（卷级 vs 阶段级），未合并。
