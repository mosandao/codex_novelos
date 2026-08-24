# 章节执行卡审查 Rubric (Chapter Plan Review Rubric)

审查 `chapter_plan` 资产候选。

## 输入边界
- 目标资产：`chapter_plan`
- 精确上游：已锁定的 `volume_outline` 与近期 Canon 上下文

## 检查清单
0. **三拍完整**：每场声明分级/执行/结算位置——只有执行无结算或只有结算无分级 = blocking；跨章半循环无衔接点 = warning。
0b. **钩子强度合规**：metadata `hook_strength` 已标注且判级与 `catalog/skills/craft/prose-webnovel-accessibility` §3 一致（唯一权威源）——开篇/卷末章非强钩子 = blocking；弱钩子 = blocking。
1. **场景目标**：本章核心场景的矛盾对抗与推进目标是否明确。
2. **冲突阶梯**：场景内部的张力与冲突是否呈阶梯递进。
3. **信息揭示**：本章揭示的关键信息与知识边界是否合规。
4. **进出状态**：场景进入与退出时角色的物理、心理或情绪状态变化是否准确。
5. **可执行性**：场景指令是否具体清晰，可直接指导正文起草。
6. **思想压力**：是否明确 `soul_pressure` 的前景强度、触发选择和 Direction 来源；纯过渡场景是否允许低强度而不强塞主题。
7. **道德残留**：`moral_residue` 是否留下可观察后果或明确承接既有残留，而不是叙述者标准答案。
7b. **出场人物要点**（T37）：出场人物清单齐全（POV 与在场者每人一行，含执念/失稳/语域要点索引，源自人物卡 essence）——清单缺失 = warning；POV 人物未声明本场知识边界 = warning；在场人物无因超出卷纲冲突线载体范围 = blocking。
7c. **微档案查重与盲区**（名册镜像注入可查）：微档案新名字与在库人物（含音近形近）撞名 = warning 并列出对；微档案整档落在 persona_gate 槽分身「写不了」场景且无绕开方式 = blocking。
7d. **弧线挂接**（T38）：冲突推进标注所属弧（arc_id 引用卷纲弧挂接）——无弧引用且无说明 = warning；兑现声明引用 promise_ledger 中已 closed 的承诺 = blocking（重复收账）；实际账本 open 承诺被无声跳过连续多章 = warning。
7e. **POV 与字数对账**（T39）：本章 POV 偏离卷纲 `lines[].pov` 声明且同线连续超 1/3 卷长无理由 = warning；本批执行卡章数 × target 字数与卷纲 `word_range` 明显悬殊 = warning（卷纲节奏失效，上报重排而非硬凑）。

## Blocking 条件
- 场景缺乏张力矛盾、进出状态无变化或缺乏可执行细节。
- 缺失 `soul_pressure` 或 `moral_residue`，发明新的作者思想，或为了表达观点改变卷纲状态。

## 不得检查的下游
- 不得在章纲阶段审查尚未生成的正文草稿。

## 证据要求
- 引用章纲内容与卷纲对应章节要求对照。
