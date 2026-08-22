# 卷纲审查 Rubric (Volume Outline Review Rubric)

审查 `volume_outline` 资产候选。

## 输入边界
- 目标资产：`volume_outline`
- 精确上游：已锁定的 `story_arc`、`world_contract`（含人物名册镜像——契约 roster + 注册表在库人物）

## 检查清单
0. **卷内节奏量化**：≥ 3 条并行冲突线（缺 = blocking）；副高潮间隔 20-30 万字（超限空窗 = warning）；POV 分布已声明（未声明 = warning）。
0b. **四段结构**：加压/排序/对撞/结算齐且各引用架构机制——缺段或无引用 = blocking。
1. **单卷目标**：本卷的独立叙事目标与高潮定位是否明确。
2. **卷内转折**：本卷的中点转折与卷末危机是否强劲。
3. **进出状态**：本卷进入状态与退出状态是否符合跨卷故事弧分配。
4. **章节序列**：章节划分与节奏铺排是否合理。
5. **卷尾承诺**：本卷结尾是否提供了强有力的悬念或下一卷承诺。
6. **卷级灵魂职责**：是否落实指定 `recurring_test`、有代价承诺和卷末未解决压力，并与前后卷形成变化。
7. **悬念种收平衡**：本卷是否兑现至少一条前序悬念；是否只堆积新谜题而不兑现旧悬念——后者为 `warning`。
8. **卷级配角班底**：本卷各冲突线的人物载体逐一指认来源（契约 roster / 在库配角 / 本卷新生成，名册镜像注入可查）——**无源载体 = blocking**；metadata `volume_characters` 无 main 人物（main 出现 = blocking，归人物契约）；无跨卷职责（跨卷需要未标注「待 change proposal 升级」= warning）；命名与人物注册表在库人物重名 = warning；正文班底叙述与 `volume_characters` 数组不一致 = warning；`seat_ref` 引用 world 岗位表不存在的席位 = blocking。
8b. **班底 persona 盲区门**（persona_gate 槽注入时）：班底人物整档落在分身「写不了」场景且微档案无绕开方式标注 = blocking；无注入跳过本项。
9. **世界对账**（world_contract 注入时）：消费时序表标注本卷首次消费的设定逐项认领——漏消费的设定项 = warning 并逐条列出；strategy `handoffs.world_changes` 落本卷的变迁在卷内结构有兑现位置（缺 = warning）；**卷纲就地发明世界设定（时序表没有的新势力/新规则且未走 change proposal）= blocking**（隐式重写上游）。

## Blocking 条件
- 单卷目标模糊、卷末无危机或偏离跨卷故事弧分配。
- 单卷胜利廉价解除全书 `forbidden_resolutions`，或只重复主题措辞而没有选择和后果。
- 无源人物载体、seat_ref 引用不存在的席位、就地发明世界设定。

## 不得检查的下游
- 不得检查具体场景行文句子结构；不得检查世界设定本身的自洽性（归 world-contract-review）。

## 证据要求
- 引用卷纲章节序列与跨卷故事弧要求对比；世界对账引用消费时序表/岗位表的对应行。
