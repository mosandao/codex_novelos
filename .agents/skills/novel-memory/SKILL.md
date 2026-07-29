---
name: novel-memory
description: 为小说规划、续写或审查构建最小且连贯的 Canon 上下文。需要检索近期章节、人物与世界状态、相关事实、伏笔、关系、故事弧或时间线，并控制上下文体积时使用。
---

# 小说记忆

构建上下文；不要生成规划资产、撰写章节、晋升事实或直接访问 Storage。

## 工作流

1. 明确目标资产或章节、人物、地点、剧情线和时间窗口。
2. 使用 `memory.recent_chapters`、`memory.search_facts`、`memory.get_entity_states` 和 `memory.get_authority_snapshot` 获取轻量结果与精确版本。
3. 只在任务确实需要时读取相关 `resource_ref`；不要预载全部正文、知识或 Catalog Prompt。
4. 以较新的 Canon 和已接受章节为准。发现矛盾时列出双方来源，不要静默裁决。
5. 返回紧凑上下文包：任务目标、近期事件、活跃实体状态、世界约束、未解决线索、连续性风险和来源 refs。

只有跨卷、多线、冲突事实或直接检索结果明显超出单次上下文时，才让 Main Agent 创建临时 Context Builder。Context Builder 仍只返回精选 refs 和遗漏风险。
