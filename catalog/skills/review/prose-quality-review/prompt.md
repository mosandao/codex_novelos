# 正文质量审查

只审查给定的不可变正文和精确上下文，不重写正文。

检查章节执行卡兑现、Canon 连续性、人物知识和动机、世界规则、时间位置、场景升级、信息重复、语言清晰度与结尾状态。同时检查：

- `style_refs` 是否能追溯到精确 Creator Profile revision/hash、锁定 Direction 和适用 POV/风格引用；
- 正文是否忠实表现 `book_soul` 与本章 `soul_pressure` / `moral_residue`，而未自行发明作者思想；
- 对立立场是否由有能力、有合理动机的人物承担，是否出现所有人物同声；
- 思想是否通过选择和后果呈现，是否出现叙述者代替剧情讲道理；
- 是否为了爽点、圆满或推进便利违反 `forbidden_conveniences` / `forbidden_resolutions`；
- 与提供的近期章节相比，是否发生作者立场漂移、人物声音趋同或母题机械重复。

人口属性推导、具体作者模仿、错误/缺失作者或 Direction 精确引用、廉价结局、叙述者替代剧情宣判，以及实质性的长篇立场漂移均为 `blocking`。每个问题使用 `blocking`、`warning` 或 `note`，引用最小正文片段和来源 ref。存在 `blocking` 时 verdict 必须为 `rejected`。

返回同一 `subject_hash`、verdict、findings、evidence refs 和 reviewer profile。
