# 多模型分工方案

> 本文为 AGENTS.md「多模型分工」节的展开说明。原则：写作=强创意模型；审查=异构厂商模型（防共谋）；记忆提取=廉价快速模型。方法论与校验基准均模型无关——映射只影响编排，不改代码。
> 记录日期：2026-08-28。模型清单按本机 DSH 配置（`~/.dsh/settings.yaml` 的 llm-pi-ai providers）核对，联网确认能力后定案。

## 本机可用通道与模型

| 通道（provider） | 模型 | 关键参数 | 备注 |
|---|---|---|---|
| `deepseek-official` | `deepseek-v4-pro` | 1M 上下文 / 384K 输出 | 主会话默认（reasoningEffort: max） |
| `opencode-go` | `deepseek-v4-pro` / `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` | 1M / 384K | opencode 聚合通道 |
| `opencode-go` | `kimi-k3` | 1M / 131K | **2x usage 成本**；2.8T 参数 KDA 注意力，官方定位编程与知识工作 |
| `opencode-go` | `minimax-m3` | 1M / 131K | MiniMax 有海螺创意写作基因 |
| `opencode-go` | `mimo-v2.5` / `mimo-v2.5-pro` | 1M / 128K | 小米系 |
| `zai-coding-cn` | `glm-5.3` | 1M / 131K | 智谱旗舰，后训练强化 Agent/长文本推理 |
| `zai-coding-cn` | `glm-5.3-flash` | 1M | 快速廉价档 |
| `zhipu-vision` | `glm-4v-flash` | 16K 上下文 | 视觉助手（识图） |

## 角色分配

| 角色 | 主选 | 备选 | 理由 |
|---|---|---|---|
| ✍️ 写作（正文 + 内核融合 + 规划 expansive 档） | `deepseek-v4-pro` | `minimax-m3` | 旗舰创意模型；1M 上下文 + 384K 输出适配长章生成；与主会话同生态 |
| 🔍 审查（全部 review 资产） | `zai-coding-cn:glm-5.3` | `kimi-k3`（仅关键卷/结局章双审） | 与写作端异构厂商防共谋；1M 上下文装得下整章 + canon；`kimi-k3` 2x 成本、定位偏编程，不作常规审查 |
| 🧠 记忆提取（六账本 + 人物状态） | `glm-5.3-flash` | `deepseek-v4-flash` | 廉价快速，忠实转录不需创意 |
| 👁 视觉 | `glm-4v-flash` | — | 已配置 |

## 防共谋矩阵

写作端与审查端必须不同厂商：

- 写作 DeepSeek → 审查 GLM ✓
- 写作 MiniMax → 审查 GLM ✓
- 禁止：同厂商自写自审（盲区重合，互相放水）

审查回执落库时 `reviewer_profile` 必须带机器身份前缀（schema 落库门强制）：`model:<provider:model>`（如 `model:zai-coding-cn:glm-5.3`）或 `agent:<name>@<model>`；匿名裸字符串拒绝落库。

## 调整规则

- 映射由主控在编排时显式指定（workflow/subagent 按 per-agent provider/model 覆盖），本表只是默认首选。
- 任一通道 key 失效或配额耗尽时，按「备选」列切换；写作/审查切换后必须复查防共谋矩阵。
- 方法论注入与校验基准与模型无关，换模型不改代码。
