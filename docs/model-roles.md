# 多模型分工方案

> 本文为 AGENTS.md「多模型分工」节的展开说明。原则：写作=强创意模型；审查=异构厂商模型（防共谋）；记忆提取=廉价快速模型。方法论与校验基准均模型无关——映射只影响编排，不改代码。
> 初版日期：2026-08-28（按当时 DSH 通道定案）。
> 更新日期：2026-09-01（合并 23 模型中文文学创作联网评测；通道按当日 `~/.dsh/settings.yaml` 重新核对）。

## 全量模型清单与文学适配评级（2026-09-01）

评级依据：foreverse 中文小说续写榜（双盲真人评审、连续续写 20 轮协议）、各厂商官方基准、中文社区实测。`通道` 列标注本机可得性：**DSH**=`opencode-go` 通道已注册；**ZCode**=ZCode 客户端模型清单可得；两者皆无=暂不可用。

| 模型 | 厂商 | 评级 | 通道 | 一句话依据 |
|---|---|---|---|---|
| DeepSeek V4 Pro | DeepSeek | **A** | DSH | 女频在位冠军；创意写作胜率 77.5%、同人文 83.25%（对 Gemini 3.1 Pro）；1M/384K。⚠️ 0813 正式版细腻文体卫冕战 1:11 输自家 0716 快照 |
| DeepSeek V4 Flash | DeepSeek | **A-** | DSH | 玄幻在位冠军，价格极低；⚠️ 幻觉率上升、后期「铺陈注水、流水账」 |
| MiniMax M3 | MiniMax | **A-** | DSH | 中文社区「网文写作提升巨大」，海螺创意写作基因，1M 上下文 |
| GLM-5.3 | 智谱 | **B+** | ZCode | 官方主打编程/Agent，写作是评测「意外之喜」；文学专项第三方数据少 |
| Grok 4.6 | xAI | **B+** | ZCode | foreverse 复审判词「快节奏玄幻第一梯队；婉转古言差一档密度」；女频「大纲体」；单轮延迟 39-44s |
| MiMo-V2.5-Pro | 小米 | **B** | DSH | 文学创作「稳健均衡」，创意写作 81.5 分；⚠️ 幻觉率约 8.5% |
| MiMo-V2.5 | 小米 | **B-** | ZCode | 同系小杯，创意写作部分场景反超 Pro（81.5），长文稳定性未知 |
| Kimi K3 | Moonshot | **B-** | ZCode | 2.8T 参数定位编程与知识工作，2x 成本；文学专项评测未见 |
| Kimi K2.6 | Moonshot | **B-** | ZCode | 无直接写作专项；K 系长文本中文传统较好 |
| Qwen3.7 Max | 阿里 | **B** | ZCode | 创意写作口碑好于 3.8 代（阿里云对比文） |
| Qwen3.7 Plus | 阿里 | **B** | ZCode | 同上，创意写作与多轮对话表现卓越 |
| Qwen3.8 Max | 阿里 | **C+** | ZCode | 编程/推理/视觉顶尖，但写作「平淡、逻辑漏洞多」（社区反馈） |
| Qwen3.8 Flash | 阿里 | **C+** | ZCode | 同 3.8 代通病，写作非卖点 |
| Hy4 preview | 腾讯混元 | **C+** | ZCode | 工程定位，修复前代输出稳定性；文学无专项数据 |
| Hy3 | 腾讯混元 | **C** | ZCode | 输出稳定性困扰到 Hy3 才修复，写作链不推荐 |
| LongCat-2.0 | 美团 | **C** | ZCode | 编程国产第一（SWE-bench Pro 59.5），创意写作第三方评测「表现一般」 |
| Muse Spark 1.2 | Meta | **C** | ZCode | 多模态推理/代码定位，整体落后第一梯队 |
| GLM-5.2 / GLM-5.1 | 智谱 | **C** | ZCode | 被 5.3 全面覆盖（体感 +50%），仅作降级备选 |
| Kimi K2.7 Code | Moonshot | **C** | ZCode | 代码特化，不入写作链 |
| MiniMax M2.7 | MiniMax | **C** | DSH | 旧代且仅 200K 上下文，被 M3 覆盖 |
| DeepSeek V4 Flash Vision Exp | DeepSeek | 视觉实验 | DSH | 不入写作链；DSH 通道内唯一视觉可用模型 |
| GLM-5.3-Flash | 智谱 | 记忆档 | ZCode | 廉价快速，忠实转录不需创意 |
| Grok 4.5 | xAI | 不推荐 | — | foreverse 九模型垫底（逐字循环/剧情停摆/人称失守） |

## 角色分配（分环节）

| 环节 | 主选 | 备选 | 理由 |
|---|---|---|---|
| 内核融合 / 分身融合 | `deepseek-v4-pro` | `minimax-m3` | 旗舰创意 + 1M/384K 长输出 |
| 方向 / 架构 / 策略 | `deepseek-v4-pro` | `glm-5.3`；发散脑暴副手 `grok-4.6` | 创意+推理兼得；Grok 只作碰撞不定稿 |
| 世界契约 / 人物契约 | `deepseek-v4-pro` | `mimo-v2.5-pro`（异构第二意见） | 契约层忌幻觉，8.5% 幻觉率模型只作对照不作主笔 |
| 卷纲 / 章纲 | `deepseek-v4-pro` | `glm-5.3` | 结构能力优先，1M 上下文装得下全书账本 |
| 正文·细腻 / 女频 / 古言 | `deepseek-v4-pro`（锁 0716 代快照，见下） | `minimax-m3` | 女频在位冠军；0813 正式版细腻文体有退步信号 |
| 正文·快节奏玄幻 / 爽文 | `deepseek-v4-flash` | `grok-4.6`；压轴章升 `deepseek-v4-pro` | 玄幻在位冠军且极廉价；Flash 流水账倾向用压轴章对冲 |
| 审查（全部 review 资产） | `glm-5.3` | `kimi-k3`（仅关键卷/结局章双审） | 与写作端异构厂商防共谋；⚠️ 通道缺口见下节 |
| 记忆提取（六账本 + 人物状态） | `glm-5.3-flash` | `deepseek-v4-flash` | 廉价快速，忠实转录不需创意 |
| 视觉 | `glm-4v-flash` | `deepseek-v4-flash-vision-exp`（DSH 内唯一） | ⚠️ zhipu-vision 通道已从 DSH 配置移除，恢复前用 V4 Flash Vision Exp |

## 文体分流与快照锁定

1. **正文按文体系列分流**：细腻向（女频/古言/正剧）走 V4 Pro 链；快节奏向（玄幻/爽文）走 V4 Flash 链。一个项目一个文体，中途不换链。
2. **快照锁定**：foreverse 实测同模型换快照可 1:11 翻车（V4 Pro 0813 输 0716）。通道若提供快照/版本选择，细腻文体锁 0716 代快照并在项目 metadata_json 记录快照 ID；仅有最新版通道时，细腻文体改用 M3 双写对比择优。
3. **换链即复审**：任一环节切换主选模型后，复查防共谋矩阵并重跑 `novelos-prose-fingerprint.mjs` 预筛基线。

## 防共谋矩阵

写作端与审查端必须不同厂商（审查端当前默认智谱 GLM）：

- 写作 DeepSeek / MiniMax / 小米 / xAI / Moonshot / 阿里 / 腾讯 / Meta → 审查 GLM ✓（均为异构厂商）
- 禁止：写作 `glm-5.3` / `glm-5.2` / `glm-5.1` 时仍用 GLM 审查 → 审查端须切 `kimi-k3` 或 `deepseek-v4-pro`
- 禁止：任何同厂商自写自审（盲区重合，互相放水）

审查回执落库时 `reviewer_profile` 必须带机器身份前缀（schema 落库门强制）：`model:<provider:model>`（如 `model:zai-coding-cn:glm-5.3`）或 `agent:<name>@<model>`；匿名裸字符串拒绝落库。

## 通道现状核对（2026-09-01）

`~/.dsh/settings.yaml` 的 llm-pi-ai 现仅注册 `opencode-go` 一个通道，6 个模型：`minimax-m3` / `deepseek-v4-flash` / `deepseek-v4-flash-vision-exp` / `deepseek-v4-pro` / `mimo-v2.5-pro` / `minimax-m2.7`。

⚠️ **审查端通道缺口**：08-28 版依赖的 `zai-coding-cn`（glm-5.3/glm-5.3-flash）、`deepseek-official`、`zhipu-vision` 通道已不在 DSH 配置中。审查与记忆提取主选（GLM 系）当前只能走 ZCode 客户端通道。若以 DSH 为唯一编排面，需先补注册 GLM 通道，或将审查端临时切换为 DSH 内可得的最异构选项（写作 DeepSeek 时审查 MiniMax M3，写作 MiniMax 时审查 DeepSeek——仍满足异构，但两家均非审查特化，仅作过渡）。

`agent-default-model` 当前为 `grok-4.5`（未注册于 providers 清单），与 NovelOS 编排无关，主控编排时必须显式 per-agent 指定 provider/model，不依赖默认值。

## 调整规则

- 映射由主控在编排时显式指定（workflow/subagent 按 per-agent provider/model 覆盖），本表只是默认首选。
- 任一通道 key 失效或配额耗尽时，按「备选」列切换；写作/审查切换后必须复查防共谋矩阵与快照锁定。
- 方法论注入与校验基准与模型无关，换模型不改代码。
- 通道或模型清单变化时，先重新核对 `~/.dsh/settings.yaml` 与客户端模型清单，再更新本文的清单表与通道核对节。

## 主要证据来源（2026-09-01 检索）

- foreverse《Grok 4.6 小说续写复审》（九模型榜、V4 Pro 卫冕战、玄幻/女频分文体裁决）：foreverse.cn/zh/blog/grok-4-6-fiction-retrial
- 端传媒/InfoQ：DeepSeek V4 Pro 创意写作 77.5%、同人文 83.25% 胜率
- 知乎《用了一周后，来深入聊聊 GLM-5.3》：写作「意外之喜」
- B站《Minimax M3 网文写作提升巨大》：M3 网文实测口碑
- HuggingFace Qwen3.8-27B 讨论 #107 + 阿里云《Qwen3.8-Max 与 Qwen3.7-Plus 对比》：3.8 写作退步、3.7 创意写作口碑
- 美团技术博客 LongCat-2.0 发布 + UniFuncs 评测：编程强、创意写作一般
- 小米 MiMo 人文社科测评博客：文学创作「稳健均衡」
- 腾讯混元 Hy4 preview 发布页 + 知乎测评：稳定性修复、工程定位
- 马良写作《Grok 4.6 发布：写小说的人需要关心吗》：Grok 定位脑暴副手
