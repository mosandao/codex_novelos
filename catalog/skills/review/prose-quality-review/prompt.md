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

## 可选方法素材

以下 craft skill 提供细化的诊断方法，**均为可选输入，不能替代本主干审查产出，不能改变 Receipt 结构或 verdict 定级规则**。审查智能体可按需调用 `skill_catalog.get("<name>")` 拉取其完整 prompt 作为诊断灵感，仅用于辅助 finding 的定位与证据描述：

- **scene-pacing**：当正文出现**节奏停滞、跳跃或无效重复**嫌疑时，参考其场景节奏诊断（目标建立→阻力→应对失败→选择升级→状态改变），定位需压缩/展开/前移/后移的具体片段。其使用条件见 metadata 的 `use_when` / `avoid_when`。
- **dash-ellipsis-guide**：当正文存在**破折号/省略号过密或语义错误**时，参考其标点语义诊断（强制中断/补充/转折 vs 主动收声/未尽之意）。其使用条件见 metadata 的 `use_when` / `avoid_when`。
- **mobile-formatting**：当正文需评估**移动端阅读密度**时，参考其段落组织方法（角色切换/独立大动作/直接对话/关键反转另起段落），不改写故事事实。其使用条件见 metadata 的 `use_when` / `avoid_when`。
