---
name: novel-writing
description: 根据已锁定 Chapter Plan 和已确认 Canon 上下文起草或修改小说正文。续写完整章节、撰写长场景、扩展对话、调整文风，或将章节执行卡转化为正文时使用。
---

# 小说写作

只生成正文候选；不要查询 Storage、扩大上下文、保存草稿或修改规划资产。

## 工作流

1. 接收有效且非 `stale` 的 Chapter Plan、精选上下文、视角、语气、长度和选中的 Catalog refs。`style_refs` 至少包含项目绑定的精确 Creator Profile revision/hash 与锁定 Direction，POV/局部风格引用只能叠加。全章起草查询 `stage=write, asset=chapter, capability=generate`；局部修订润色查询 `stage=write, asset=chapter, capability=revise`。
2. 将已确认上游与 Canon 视为约束。缺少关键材料时返回 context gap，不要自行检索或编造替代事实。
3. 完整章节或长场景由 Main Agent 创建隔离的 Writer Agent 执行；局部改句且不改变章节状态时可由 Main Agent 直接处理。
4. 写作时保持人物动机、知识边界、地点规则、时间顺序、伏笔和场景状态变化一致。通过选择和后果表现已确认的 `book_soul`、`soul_pressure` 与 `moral_residue`；不要自行创造作者思想、改写书级创作灵魂、让所有人物同声或用叙述者宣布标准答案。纯过渡场景按 Chapter Plan 降低思想前景强度。
5. 返回标题、正文和简短的新增 Canon 候选摘要，不返回自报 Hash。
6. Main Agent 使用 `chapter.create_draft` 登记正文，由 MCP 计算 `subject_hash`，然后交给 `$novel-review`。

Writer Agent 不接受、锁定或晋升任何结果。
