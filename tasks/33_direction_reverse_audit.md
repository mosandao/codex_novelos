# Task 33: 方向阶段反向审查批次（direction 生成/审查双侧强化）

状态：`DONE`（2026-08-22）

## 背景

对 direction 阶段做三轮反向审查（人格与频道/平台/规模/题材消费 → 审查侧三问 → 生成侧三问），确认体系定位是「方法论合规门 + 反泛化门」，但缺质量上限门与市场验证门：反平庸武器全是禁令形态无激励形态、修复循环对大胆候选有系统性收敛税、黑暗内容只有修饰位无主菜位、假多样性防线只查两维且自产自判。本批全量落地修复。

## 改动清单

### 审查侧（review）

- **新增 `check-aesthetic-present.md`** + manifest 注册——补齐美学基因审查对偶（此前生成侧有模块、审查侧 manifest 缺项的显式不对称）。
- **`planning-direction-review/prompt.md` 重写强化**（36→68 行）：
  - 第 3 项辨识度对照（题材撞车 warning）+ 例证警示（长得像频道例证≠好）；
  - 第 5 项**规模数字门**：四档兑现次数×间隔复述进 rubric，失配 = blocking，含糊 = warning + 移交 volume_outline 回查；
  - 第 6 项血缘**逐字段核验**（抽查映射真实性，非核对声明）；
  - 第 7 项 cruelty **具体落点**检查（谁/形态/结局哪侧，存在性敷衍 = warning）;
  - 第 10 项**库存反向对账**（persona 差异化库存集体闲置 = warning）；
  - 第 11 项**证伪与读者模拟**（2-3 个断裂点：两难瓦解/重复疲劳/弃书空窗，目标读者视角）；
  - 新增 **check 执行纪律**（所附 check 模块逐条回答并列清单）、**strength 通道**（独有赌注亮点，不阻断不修复，修复不得削平）、**横向回执**（多候选并列时主控汇总最强候选/差异维/推荐序呈报用户）。

### 生成侧（planning/story-direction）

- **prompt.md**：比较表五维→**七维**（+情感登记+承诺类型），情感登记两两不得相同，题材换皮不算差异；**发散纪律**（至少一候选最大表里反差档或激进承诺结构）；**负向承诺**语法（见证代价/追讨真相/守护将失之物为合法主承诺，兑现单位可感）；**逐字段血缘映射表**入骨架；cruelty 具体落点入字段标准；画像过薄显式声明「消费受限」；自检 3/4/5/6/7 同步强化。
- **channel-male/female/omni**：各加**负向暗轨合法**条款（暗色主轨为合法发散方向，不强制全部正向翻盘）+ 例证禁复用声明。
- **platform-free/paid**：附加自检加画像薄声明（不在贫信息上空转消费语法）。

### 编排层（.agents/skills）

- **novel-review SKILL**：severity 四档（+strength）；**修复不得削平 strength 特质**；**生成侧异议（辩护回合）**——复核一次、争议升级用户；**横向回执**节；豁免通道扩为两种——defer_to_downstream（原有）+ **accepted_risk**（艺术风险经用户确认豁免，硬约束不得豁免）；未解决项查询 SQL 同步。
- **novel-planning SKILL**：第 7 步命令补 `--subject <候选资产ID>`（原文档遗漏）+ 横向回执联动。

### schema / 测试

- **review-receipt-candidate.schema.json**：severity enum 加 `strength`；findings item 补 `defer_to_downstream`（此前 SKILL 语义已用但 schema 缺字段）/ `accepted_risk` / `accepted_by`。
- **test_compose_prompt.py**：SIZE_BUDGET direction 190→210（direction-review 120 保持，实测 95），注释注明本批次缘由。

## 验收

- `.venv/bin/python -m unittest discover -s tests`：**151 tests OK**（含新增 `test_book_soul_validate.py` 13 项）
- `.venv/bin/python -m compileall -q scripts tests catalog config`：通过
- `check_repository_hygiene.py --check`：通过
- `build_catalog_manifest.py --check`：通过
- 组装冒烟：check-aesthetic 随 `aesthetic_styles` 非空命中、空值互斥不命中；生成侧负向暗轨/七维比较表/逐字段血缘映射/消费受限条款全部随条件路由命中。
- validate CLI 冒烟：`cadence_plan.fulfillment_count=3 --scale 超长篇` → FAIL 非零退出（数字门生效）。

## 追加批次：三条"轻量替代"彻底化（同日，用户裁决后全量落地）

初版将三条列为"轻量替代/不动"，经复核判定为保守划线，全部彻底化：

1. **血缘结构化追溯**：book_soul v2 可选扩展 `lineage`（2-24 条 {field, source_type: signature/persona/kernel/setup/reference_material, source_ref, derivation, variation?}，不进 required 向后兼容旧资产）；validate 加覆盖检查（organizing_principle 与 central_contradiction 必须有条目）；生成侧骨架第 1 节映射表落 metadata；审查侧第 6 项以 lineage 为结构化抓手抽查 derivation 真实性。
2. **规模数字机器门**：可选扩展 `cadence_plan`（fulfillment_count × interval_volumes）；`validate --scale <档位>` 机器校验兑现次数（短篇 1-2 / 中篇 ≥3 / 长篇 ≥3 / 超长篇 ≥5，短篇超限报错）；审查第 5 项优先核 cadence_plan 并查与 promise_cadence 文本一致。
3. **血缘变奏通道**（不推翻血缘哲学的解法）：发散纪律允许至多一个候选为变奏候选——lineage 条目标 `variation: true` 显式越界（derivation 写明理由与代价）；审查对变奏条目不判断裂，未标 variation 的越界照判 warning；横向回执向用户显式标注变奏候选供知情裁决。

涉及文件：`config/schemas/book-soul.schema.json`、`scripts/novelos_validate_book_soul.py`（语义校验层 + --scale）、story-direction / direction-review 双侧 prompt、novel-planning SKILL 速查表、`tests/test_book_soul_validate.py`（新增 13 项）。

## 遗留说明

- 「例证即泛化中心」风险以双向警示（生成侧禁复用 + 审查侧长得像例证须警示）缓解，未移除例证（教学价值大于风险）。
- cadence_plan 间隔的绝对字数核对仍属 volume_outline 层（方向层只有卷数估计），已由审查第 5 项显式移交回查。
