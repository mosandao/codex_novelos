# 外部小说 Skill 生态调研 · 13 仓对比交叉分析

> 调研日期：2026-08-29。方法：13 个仓库 shallow clone 至 `/tmp/novel-skills-survey/`（约 116MB，可随时删除重 clone），结构勘察后按三条线（中文网文知识包 / 工程化长篇流程 / 英文·多 harness·平台）由三个 sub agent 深读，主控交叉综合。分仓详读原文见附录三节，引用证据均带文件路径。
> 基准对照物 = 本仓 NovelOS：SQLite 权威库+事务直写、`candidate→locked→stale` 状态机+依赖边传播、Review Receipt 引文机器验证（FATAL 打回）、六账本连续性、persona cannot_write 盲区、composer 组装器（manifest v2 配方矩阵+渐进式披露）、prose fingerprint 预筛（screen/measure+人类语料金丝雀基线）、多 harness 零变体适配。
> 本报告仅为调研记录，未提交；任何借鉴项落地前按本仓纪律呈报用户裁决。

## 1. 总览

| 仓库 | ★ | LICENSE | 形态 | skill 数 | 工程化 | 一句话定位 |
|---|---|---|---|---|---|---|
| [dama-cyber/Distilled-Novel-Toolbox](https://github.com/dama-cyber/Distilled-Novel-Toolbox) | 180 | README 声明 MIT，**无 LICENSE 文件** | 知识包 | 13 | 无 | 平台×爽点×合规×去AI腔的行业知识密度天花板 |
| [tance-mang/chinese-webnovel-skills](https://github.com/tance-mang/chinese-webnovel-skills) | 45 | **MIT** | Claude Code 插件+CLI+导出 | 33 | 中 | 全流程商业网文工具包，档案体系最全 |
| [penglonghuang/chinese-novelist-skill](https://github.com/penglonghuang/chinese-novelist-skill) | — | **无 LICENSE**（README 挂 MIT badge） | 单 skill | 1 | 中 | 全自动写书流水线：JSON 章节状态机+3 轮重写上限 |
| [yangsonhung/awesome-agent-skills](https://github.com/yangsonhung/awesome-agent-skills)（仅 novel-writer-cn） | — | MIT | 大杂烩仓库之一 | 1 | 无 | 通用写作常识双语镜像，无行业无工程 |
| [zy-zmc/tianming-skill](https://github.com/zy-zmc/tianming-skill) | 137 | **CC BY-NC-SA 4.0（禁商用）** | 主干+协议群 | 1+30 文件 | 高（协议级） | prompt 当软件做：路由表/常数表/lint/熔断矩阵 |
| [xiaofeng-928/chinese-longnovel-skill](https://github.com/xiaofeng-928/chinese-longnovel-skill) | 67 | **MIT** | skill+脚本链 | 1 | **最高（文件系统级）** | 提交链 CAS+状态回证 sha256+50 章双窗口 |
| [lingfengqaq/webnovel-writer](https://github.com/lingfengqaq/webnovel-writer) | — | **GPLv3** | 插件+CLI+hooks | 8 | **最高（DB 级）** | 五投影 read-model+写入门禁+断点续跑 |
| [skyfiredao/dreampowers](https://github.com/skyfiredao/dreampowers) | 68 | **GPLv3** | opencode 技能包 | 14 | 低（纯 prompt） | 防写崩方法论密度最高：六铁律+概念预算+TBD 兜底 |
| [wgwtest/novel-writing](https://github.com/wgwtest/novel-writing) | 30 | **MIT** | 单 skill | 1 | 中（文本卫生脚本+契约测试） | 纯叙事工艺库：认知分层/决策所有权五分离 |
| [haowjy/creative-writing-skills](https://github.com/haowjy/creative-writing-skills) | 433 | **Apache 2.0** | 多 agent+skill 包 | 35 | 中 | 知识分层理论最体系化（qi-layer/kb-management） |
| [forsonny/Claude-Code-Novel-Writer](https://github.com/forsonny/Claude-Code-Novel-Writer) | 128 | **无 LICENSE（默认版权保留）** | 文件工作区模板 | 5+7 role | 中 | 手稿唯一真源+派生 JSON 可再生+薄适配三 harness |
| [zenstory-ai/oh-story-dsh](https://github.com/zenstory-ai/oh-story-dsh) | 218 | **MIT** | DSH 插件（TS monorepo） | 30 | 高（供应链级） | 与本仓退役 plugin/ 同血统的最新演化：manifest 哈希钉版 |
| [alfredxw/denova](https://github.com/alfredxw/denova) | 670 | **Apache 2.0** | Go 平台 | 6 | 高（平台级） | skillassembly 三面同源投影+写作双档 lite/standard |

注：★ 为 2026-08-29 快照；skills.sh 安装量参考——chinese-novelist 5.5K、novel-writer-cn 2.2K、webnovel-writer 系列 400-760。

## 2. 交叉分析

### 2.1 装配机制：四种流派

1. **单文件知识卡**（Distilled 13 平级模块、dreampowers 14 个巨型 SKILL.md、awesome-agent-skills）：dreampowers 证明单文件路线的极限——`dp-set-outline` 928 行，其 `tested_model.md` 自测显示弱模型（Claude Sonnet 4.6「多约束并行」仅 15 分）直接崩，**巨型单文件对模型能力敏感**是硬伤。
2. **主干+references 渐进披露**（chinese-novelist、chinese-webnovel-skills、wgwtest）：主流做法，与本仓 composer 主干+条件模块同型。
3. **协议工程**（tianming：指令路由表+`core/` 冷启动+`protocols/` 按需加载+`constants/global-constants.md` 集中常数表+`scripts/reference-linter.ps1` 引用完整性 lint；chinese-longnovel-skill：SKILL 路由+references「权威关系唯一说明层」+prompts「执行模板」+scripts「只输出确定性事实」三权分立）：把 prompt 当软件做配置管理，与 composer 组装器目标一致但靠约定执行。
4. **平台化装配**（denova `internal/agents/skillassembly/assembly.go` 把有效目录同源投影到 SystemPrompt 目录/工具/`skill://` 引用三面；oh-story-dsh manifest v2 逐文件 sha256+parity CI+host 侧 allowlist 引用器；webnovel-writer 统一 CLI+PreToolUse hooks 写保护）：**运行时强制**取代 prompt 自觉。

对 NovelOS 的印证：composer 的「配方矩阵+渐进披露」在第 2/3 流派的收敛方向上；oh-story-dsh 的 manifest 哈希钉版是本仓退役插件若重启分发最该抄的供应链形态。

### 2.2 上下文工程：四条路线

| 路线 | 代表 | 机制 |
|---|---|---|
| 固定预算分层 | chinese-longnovel-skill | 读取窗口写死：近 3 章正文/近 20 章总结/50 章阶段摘要/200 章长期摘要（`references/长篇上下文与一致性.md`），防上下文随章节数线性膨胀 |
| 物理围栏 | dreampowers | 章节文件夹符号链接白名单，未链接设定**物理不可见**；Stage C 写作只读 spec.md；oh-story Reference Gate「落笔前必须读到 EOF，旧会话『读过』不作数」 |
| 动态排序 | webnovel-writer | `context_ranker.py` 新近度+钩子信号加权，`context_weights.py` 按题材×阶段动态分配 |
| 配方渐进披露 | **NovelOS composer**、denova SkillCatalog、creative-writing-skills qi-layer 理论 | 冷启动轻载+按任务路由+槽位预算 |

chinese-novelist-skill 另有一个独有细技巧：**「动笔前最后读的必须是正文语态」**（上一章结尾 500-800 字+文风基准段落，不让大纲表格成为最后上下文），防文风被大纲表格污染——低成本高收益。

### 2.3 状态与连续性光谱（弱→强）

1. 无状态：awesome-agent-skills、wgwtest（外包给姊妹仓库）、Distilled（仅「设定文档单独管理」一句）。
2. **markdown 档案+自觉维护**（最大阵营）：chinese-webnovel-skills 8 档案+伏笔编号 F001+知情人名单+情绪轨迹值+语言指纹+git 快照；dreampowers 一伏笔一文件 `tracking/thread-NNN-*.md`+`[章末状态]` 快照+摘要重生成时向下游插 **STALE-DEP 陈旧标记**；tianming《世界基石.md》六区+「存档」输出结构化补丁由用户应用；Claude-Code-Novel-Writer 手稿唯一真源+tracking JSON **可再生派生物**（`sync-state.sh` 按字数重算）；oh-story `_tracking-state.json`+post-write hook 提醒。
3. **JSON 状态机**：chinese-novelist `02-写作计划.json`（pending/in_progress/completed/failed+retryCount，支持并行协调与中断续写）。
4. **提交链+哈希 CAS**：chinese-longnovel-skill（head CAS+不可变事务资产+单写者锁+maintenance rebase shadow 代际+「从 committed 正文重建投影，不用投影覆盖正文」裁决序）。
5. **DB+投影**：webnovel-writer（SQLite index.db+五投影+`projection_log.jsonl` 失步日志+retry/replay+doctor）。
6. **NovelOS**：SQLite 权威库+`candidate→locked→stale` 沿依赖边传播——本仓处于光谱最右端，且唯一具备「上游变更自动传播」语义（dreampowers 的 STALE-DEP 是场景级手工近似）。

### 2.4 审查与质量门光谱

- 自评一句（awesome-agent-skills）→ **诊断/修改分离**（chinese-webnovel-skills：aidetect 只诊断不改稿 ↔ deslop 只改不诊断——与本仓 screen/measure 与 review/writing 分离同构）→ **多视角对抗**（oh-story story-review 并行 spawn 三视角 agent+统一 Findings Schema+S1/S2/S3 分级+「路径不可读时必用内置 rubric 并报 `Rubric Source: embedded fallback`」防降级条款；creative-writing critic/editor/reader-sim/character-sim 分离；webnovel-writer 六维 reviewer 只回严格 JSON）→ **循环+上限+人工升级**（chinese-novelist 3 轮重写上限+超限留痕不阻塞；dreampowers 三阶段审查+外审各 ≤3 轮+`chapter-NNN-TBD.md` 人工兜底；tianming AI 指纹净化 3 次上限+FATAL_ERROR 报请执笔者三选一裁决+下级协议可向上游驳回）。
- **机器验证端点**：chinese-longnovel-skill 的 `validate_chapter_candidate.py` 对 state delta 的 `source_anchor` 做 sha256 比对（最接近 NovelOS Receipt）；wgwtest `check_manuscript_text.py` 的 prompt 泄漏/编码损伤确定性检查+「文档即契约」测试（`tests/test_story_outline_contract.py` 把 SKILL 文档当契约断言）；oh-story 的 manifest 哈希（供应链而非内容）；denova 工具结果检查门。
- **NovelOS Receipt 引文验证（excerpt 无命中即 FATAL）在全部 13 仓中没有等价物**——各仓审查产物最严格的也只要求「附原文证据位置」，不做机器回验。这是本仓最大差异化资产。

### 2.5 去AI味路线对比

| 路线 | 代表 | 内容 |
|---|---|---|
| 规则清单 | chinese-webnovel-skills `deslop` 症状表 21 条；tianming AI 指纹黑名单 7 类一票否决 | 定性 |
| 量化指标 | chinese-webnovel-skills `aidetect` 12 项指标+阈值+权重+0-10 指数（比喻密度≤3/千字、连续同句式≤2、句长波动≥3 倍、四类配比 40/30/20/10）；Distilled 39 条改写规则+五维评分 35/50 门槛 | 半量化 |
| 模型自测 | dreampowers `tested_model.md` 八维依从性矩阵 | 工程诚实度高 |
| 基线对照 | **NovelOS 金丝雀（22 篇人类语料叙述层误报基线+`--compare` 回归）** | 本仓独有 |

校准参考价值高，但注意本仓口径纪律：aidetect/Distilled 的阈值是**全文/自报口径**，与金丝雀「对话抑制后的叙述层」口径不同不可直比（同 `docs/knowledge/canary-baseline.md` 对 lieflat 母本的打折声明逻辑）。

### 2.6 NovelOS 的盲区（13 仓共同揭示）

1. **行业/商业知识维度为零**：平台参数（番茄第 1000 字首爽点、起点金手指第 3 章、飞卢 500 字/起点 1500 字一个爽点）、数据漏斗诊断（曝光→点击→收藏→完读→追读+止损规则）、投稿拒因复盘、合规敏感词分级改写——13 仓中 Distilled 与 chinese-webnovel-skills 最厚，本仓完全没有。
2. **读者模拟缺位**：creative-writing reader-sim（persona 沿 5 条 reader reward channel 报告体验）、dreampowers dp-review-reader（翻页欲/认知负荷/共情/节奏四维冷读）、chinese-webnovel-skills 继续率预测——本仓 review 无读者视角通道。
3. **可量化叙事阈值**：dreampowers 概念预算（首章 ≤3 新概念/每章 ≤2/每 3000 字 ≥1 未解问题）、Claremont 系数（active−resolved>2 预警）、揭示时间表（悬念出现点→解释发生点间隔 1-2 场景）——本仓六账本有伏笔登记但无**收支预算**门禁。
4. **模型依从性基准**：dreampowers `tested_model.md` 公开各模型对技能的依从性评分——本仓多模型分工有映射但无依从性度量。

### 2.7 三个独立收敛（对 NovelOS 方向选择的印证）

- **诊断/修改分离**：chinese-webnovel-skills（aidetect↔deslop）、wgwtest（review 输出 only findings）、denova（SubAgent 只审不改）全部收敛到与本仓 screen 只报事实不判级、review 与 writing 分离相同的判断。
- **单源多 harness**：Claude-Code-Novel-Writer canonical+thin adapter（`.claude/skills/` 只剩一行指回 `.agents/skills/` 正本）、creative-writing-skills `skills/`→`cw/` 构建期双分发+CI 漂移检查、denova 三面同源投影——三种实现都收敛到本仓 adapters 单源零变体的结论。
- **投影可再生**：Claude-Code-Novel-Writer（tracking 是派生物，手稿唯一真源）、webnovel-writer（state.json「仅兼容投影」）、chinese-longnovel-skill（「从 committed 正文重建投影」）——与本仓 novels/ md 投影「只读派生、可删除重建」同一原则。

## 3. 可借鉴机制清单（按优先级）

> 许可证约束见表 1；GPLv3/NC-SA/无 LICENSE 仓库只借思想、不搬文字。落地均按本仓纪律：先呈报、过金丝雀 `--compare`、不过度工程。

**P1（低成本低风险，直接可用）**
1. 「动笔前最后注入语态文本」——chinese-novelist-skill（无 LICENSE，仅借思想）。落地：composer 章节草稿场景在注入尾部追加上一章定稿结尾 500-800 字语态段。
2. prompt 泄漏/文本卫生 screen 规则——wgwtest（MIT）。落地：`novelos-prose-fingerprint.mjs` screen 层新增指令残留/编码损伤检测；新规则须过金丝雀基线 `--compare`。
3. 重试上限+失败留痕不阻塞——chinese-novelist-skill。落地：章节接受流程记录 retryCount 语义，3 轮未收敛走既有 G6 升级纪律（本仓已有升级条款，此处仅补「留痕不阻塞」的失败隔离语义）。
4. 审查 finding 末项「是否沉淀为项目规则？」——wgwtest（MIT）。落地：Review Receipt 增加可选字段，把复查问题转 planning 资产修订线索。

**P2（需要设计，收益明确）**
5. 三本新账候选：知情人名单（马甲/秘密暴露状态）、情绪轨迹值、语言指纹 speech_profile——chinese-webnovel-skills（MIT）。落地：连续性六账本扩展评估，走 U 呈报。
6. 概念预算+揭示时间表+Claremont 伏笔收支计数——dreampowers（GPLv3，只借思想）。落地：六账本伏笔账加收支计数门禁；审查 checklist 加「新概念数/解释密度」。
7. `[章末状态]` 快照+下游 STALE-DEP——dreampowers（思想）。落地：与既有 stale 传播互补的场景级近似，评估是否值得（防重复建设）。
8. 蓝图不可偏移字段级验收（标题/核心事件/钩子/冲突值六字段不得改写）——tianming（NC-SA，重写文字）。落地：chapter_plan 锁定验收字段清单。
9. 写作双档 lite/standard——denova（Apache 2.0）。落地：章节任务配方分档（快续直出 vs 带审查全流程）。

**P3（方向性储备）**
10. manifest 哈希钉版+parity CI+allowlist 引用器——oh-story-dsh（MIT）。适用：未来任何 skill 包分发/上游同步场景。
11. 平台参数/合规知识卡——Distilled（授权弱）+chinese-webnovel-skills（MIT，优先取材）。落地：`config/knowledge/distilled.{platform,compliance}.json`，走既有 knowledge 槽预算（单条 ≤512B，槽 ≤4096B）。
12. 缺失降级矩阵+「待决议/新发现实体」报告通道——tianming（思想）。落地：candidate→locked 之外的能力降级表；连续性提取遇新实体不静默入库。
13. 读者模拟审查位——creative-writing（Apache 2.0）/dreampowers（思想）。落地：review 增加读者冷读视角的可选审查 agent。
14. 文风校准段落自回填（第 1 章定稿回填作后续锚点）——chinese-novelist-skill（思想）。落地：style_seed 维护流程。

**不可倒退红线**（全部 13 仓均未达到本仓强度的部分，借鉴任何机制时不得回退）：
- SQLite 权威库+`BEGIN IMMEDIATE` 事务（最强对手 webnovel-writer 的 commits 仍是 JSON 文件，index.db 只存实体大数据）；
- Review Receipt 引文机器验证（各仓最严格的 chinese-longnovel 也只校验状态增量锚点、不验全量引文）；
- 上游变更沿依赖边自动 stale 传播（dreampowers STALE-DEP 是手工场景级）；
- 金丝雀人类语料基线（各仓去AI味阈值均无人类语料对照，属「拍脑袋阈值」）。
- 反面教材同样明确：webnovel-writer 概念名目繁多（Strand/CBN/CPNs/CEN/追读力/三层记忆）造成认知负担、docs/archive 大量历史 phase 文档——**概念爆炸是过度工程的真实样本**，借鉴时克制命名。

## 4. 许可证红绿灯

| 通行 | 限用 | 禁文本搬运 |
|---|---|---|
| MIT：chinese-webnovel-skills、chinese-longnovel-skill、wgwtest、oh-story-dsh、awesome-agent-skills；Apache 2.0：creative-writing-skills、denova | GPLv3（传染，思想可参考、文本不可进本仓）：webnovel-writer、dreampowers；CC BY-NC-SA（禁商用+同源传染）：tianming | 无 LICENSE=默认版权保留：Distilled-Novel-Toolbox（仅 README/frontmatter 口头 MIT，依据弱）、chinese-novelist-skill、Claude-Code-Novel-Writer |

## 附录 A：中文网文知识包 5 仓详读（sub agent 原始报告）

（精简保留方法论清单要点，完整骨架含定位/结构/审查/状态/许可证八节，证据路径以 `…` 缩略。）

### A1. Distilled-Novel-Toolbox

13 个平级目录 `novel-*`，每个 SKILL.md（Purpose/When to Use/Instructions/Execution Protocol/Failure Handling/CHECKPOINT/Anti-Patterns/Checklist 固定骨架）+ references/ 子文档（4-13 篇）+ index.md + test-prompts.json；无脚本无状态。核心资产：
- **200+ 检测指标/8 核心**、五大 AI 特征模式、特征群判定（单点不算堆叠才算）、混合创作模式（AI 40-60%+人工，双盲识别率 29% vs 纯 AI 83%）、平台 AI 政策与 2026-09-01《生成式AI服务管理办法》标注要求（`novel-anti-detection/`）。
- **39 条改写规则**（内容/语法/排版/废话/对冲五类：「不仅是X更是Y」直接删、破折号全禁、三项式排比拆解）+**五维评分 35/50 门槛**+禁用词表（`novel-polishing/`）。
- **60+ 爽点模式 30 类**（各配心理机制）、三段式结构（铺垫30/爆发50/余韵20）、**平台爽点密度表**（飞卢 500 字/番茄 800/起点 1500/晋江 2000 一个小爽点）、疲劳管理 5 策（`novel-pleasure-points/`）。
- 黄金开篇公式、30+ 断章钩子六类、高潮密度（小 2-3 章/中 8-10/大每卷）、章节节奏诊断表（`novel-pacing/`）。
- 60+ 主角标签、30+ 配角功能、20+ 反派模板、角色验收 5 项（`novel-character-design/`）；情绪色彩轮盘、20+ 共情触发器、情绪桥模板（`novel-emotion/`）；题材融合矩阵主 70% 副 30%、选题 6 维评分 <18 不开书（`novel-genres`/`novel-innovation`）；文风光谱 7 型带量化参数（`novel-language-style/`）；平台全景对比+**数据漏斗诊断+止损规则**（`novel-commercialization/`）；敏感词 4 法+**合规改写矩阵**（`novel-compliance/`）；**新设定 Schema 7 字段**+力量体系 4 模板（`novel-worldbuilding/`）；日更 4000 字流程（`novel-tools/`）。
- 评价：行业知识密度全组最高，39 条规则可直接作预筛器规则层参考；但零工程、无审查循环、政策数据有时效性。LICENSE 依据弱。

### A2. chinese-webnovel-skills（MIT）

`.claude-plugin/plugin.json` v0.29.1（`/webnovel:*` 命令）+ `exports/` 跨模型导出 + `cli/webnovel.py` 独立 CLI 三形态；`skills/` 33 短名技能 + `references/` 31 知识库 + `templates/` 3（book-bible/progress/submission-log）；`skills/start` 四门路由入口。核心资产：
- **打脸四拍**（嘲讽→沉默→碾压→围观）、三段式爽感闭环+爽点升级链、金手指 10 流派+防烂尾。
- **世界观先行 World Engine**（六模块+唯一标签+世界状态随章变+写章前「世界四问」）；**七条逻辑链**（行为/因果/资源/身份/伤势/战力/情绪）+时间线绝对锚点+**长篇失忆三临界点（50/100/300 章）**。
- **创作档案 8 文件**+伏笔追踪表（F001 编号/埋点/计划回收章/重要度）+**情绪轨迹值**+**语言指纹 speech_profile**+知情人名单+战力对照表+git 快照。
- **AI 味量化 12 项指标+阈值+权重+指数 0-10**（`aidetect`/`ai-detector.md`）；**人味三手法**（非理性行为/情绪不完整表达/逻辑不完全闭环，`human/`）；deslop 症状表 21 条。
- 平台调性库（番茄第 1000 字首爽点、起点金手指第 3 章、晋江同人引用 ≤1/10、知乎盐选第一句悬念+段落 ≤3 行）+篇幅字数标准+投稿拒因复盘标签。
- 评价：档案体系最接近本仓账本思路、MIT 最友好；但档案回写是软约束、审查无机器验证、技能无自动编排。

### A3. chinese-novelist-skill（无 LICENSE）

SKILL.md 65 行主干+`references/flows/` 7 篇（phase0-4+shared-infrastructure）+`references/guides/` 9 篇；脚本仅 `check_chapter_wordcount.py`。核心资产：
- **`02-写作计划.json` 章节状态机**（pending/in_progress/completed/failed+wordCount+retryCount+writingMode）+三种写作模式（serial/**subagent-parallel** 每批 5-8 章不重叠 JSON 协调/agent-teams）。
- **「动笔前最后读的必须是正文语态」**（上一章结尾 500-800 字+文风基准段，不让大纲表格成为最后上下文）；**03-文风基准.md** 校准段落由第 1 章定稿回填。
- **设定词典**（首现章/读者已知/完整真相/计划揭示章）；章首引子七式/悬念十三式/强度 5 级/短中长三弧并行；AI 痕迹清除（「不是xxx」句式禁用、「的」字密度 ≤2/句）；8 维质量评分（>60 交付、单维 <6 必改）。
- **Phase 4 自动校验：字数硬校验不合格自动重写、最多 3 轮（retryCount），超限保留记录不阻塞并在完成报告标注**——全部候选仓唯一明确迭代上限+失败不阻塞设计。
- 评价：工程化超预期但连贯性仅靠章节摘要、除字数外全靠自评、README 广告噪声。

### A4. awesome-agent-skills·novel-writer-cn（MIT）

zh-cn/en 逐段镜像+references 5 篇+templates 4 个。三幕 25/50/25、角色卡四件、世界观四层三原则、类型要点表、负面清单。审查仅一句自检、无状态。**结论：知识密度极低，无独有内容，最不值得花时间**；仅「模板与 references 分离」目录习惯与负面清单表述风格可参考。

### A5. tianming-skill（CC BY-NC-SA 4.0，禁商用）

SKILL.md 243 行指令路由表（7 条指令→协议文件→KERNEL_REF）+`core/` 3 篇冷启动必载+`protocols/` 6 篇（toc.md 694 行）+`aesthetic/` 4 篇+`constants/global-constants.md`+`scripts/reference-linter.ps1`（[ID]/[REF]/[KERNEL_REF] 引用 lint）+`scripts/conflict-score.py`（冲突值量化）+`examples/mini-volume/`。核心资产：
- **双层真理仲裁**（法则塑造事实、事实更新法则）；**知识库五件套+缺失降级矩阵**（缺哪件禁哪些任务）+「事实不足不补设定」→「待决议/新发现实体」报告。
- Ω 级法典：**因果律闭环**（断链 FATAL_ERROR: Causality_Chain_Broken）、代价守恒、角色灵魂烙印、实体时序（[C-XXX] ID+时间锚）、**关系向量**（信任 70/宿怨 10，目录期演算正文期锁定）、冲突值 ★1-5 量化、时空协议（±0.5 三级净化）、**载体 DNA**（钩子语义指纹+意图仲裁，「意图保真≠字面保真」）。
- **缓冲池体系**（总缓冲比 37%+叙事熵增熔断：10 章窗口新实体>5 且缓冲<2 → 强制注入缓冲章）；伏笔 Tier 分级+暗埋率 98%+核心回收率 ≥80%+**沉睡伏笔扫描** 50 章阈值；熔断 L1-L6+向上游驳回；**蓝图不可偏移清单**（六字段不得改写）；AI 指纹黑名单 7 类一票否决+净化 3 次上限。
- 状态：用户侧《世界基石.md》六区，「天命：存档」输出**结构化更新补丁由用户应用**（skill 只读工具 `allowed-tools: Read, Glob, Grep`）。
- 评价：审查协议群全组最强、引用规范+lint 是唯一「prompt 当软件做配置管理」的；但全部约束靠模型自觉、300 章后《世界基石.md》膨胀失准、NC-SA 阻碍文本复用（只借思想+重写文字）。

## 附录 B：工程化长篇流程 4 仓详读（sub agent 原始报告）

### B1. chinese-longnovel-skill / MyNovel（MIT）

SKILL.md 102 行只做路由+全局不变量；references/ 12 篇「流程与权威关系唯一说明层」、prompts/ 12 篇「执行模板」、scripts/ 8 个「只输出确定性事实与证据」（三方契约见 `references/自动化脚本契约.md`）。核心资产：
- **分层上下文组装 7 层证据层级**（config+commit head+计划节点边界 → 主角/系统状态仓库 → 50 章计划（只认计划不当事实）→ 近 3 章正文 → 近 20 章总结跨 50 章块拼接 → 50 章阶段总结+200 章长期摘要 → 角色档案/世界观/伏笔/文风）。
- **状态回证**：state delta 含 `delta_id/field/old/new/source_anchor/source_excerpt_sha256/fact_lock_ids`；`--require-state-validation` 不通过不能 prepare 事务（`scripts/validate_chapter_candidate.py` 425 行）。
- **章节事务链**：候选验证→总结/状态增量→状态回证→prepare 冻结→**CAS 推进 commit head**→物化投影；`review_pending` 是 committed 节点、**审查不阻断续写**；`scripts/项目事务.py` 835 行（manifest 校验、单写者锁、genesis→commit-head 链、rebase 三控制事务、50 章双窗口）。
- **50 章分阶段规划+双窗口切换**；每 50 章阶段总结、每 200 章长期摘要（只留阶段结算/时间锚/活跃角色/未偿因果债）。
- **事实锁**（硬事实/时间锚/角色认知/能力资源/系统权限余额库存/关系承诺/信息流/因果债/伏笔/后文禁止误写，逐条绑定来源+锚点+SHA-256）；**「（草稿）」文件名状态机**（三重门禁过→原子改名）；**maintenance rebase**（shadow 链逐节点重放原子切回）；双独立审查绑定同一 reviewed_sha256；`原文重合检查.py`（连续重合 16-23 字复核、≥24 阻断）；evals/ 7 用例硬断言（含「破坏样本零容忍阻断」）。
- 评价：**提交链工程全组最深**，把「正文改了摘要没改」变成可机械验证闭环；弱点是规则全靠 prompt 自觉（无 hooks 兜底）、题材锁死经营流系统文、两份「独立审查」仍是同模型两次调用。

### B2. webnovel-writer（GPLv3）

v6.2.1 Marketplace 插件，主 agent+3 subagent（context-agent/reviewer/data-agent）+只读 Dashboard。8 skill 是流程编排器（每步给 bash 命令+Agent 调用+产物路径），**真正保证层在 scripts/**：`scripts/webnovel.py` 统一 CLI（preflight/write-gate/chapter-commit/projections/memory/rag/run-ledger/user-report…）+`data_modules/` 约 60 模块配 100+ 测试文件。核心资产：
- **Story System 合同驱动**：`.story-system/` 唯一事实源（MASTER_SETTING.json+卷合同+审查合同）；**CHAPTER_COMMIT 提交链**（blocking_count>0 或 missed_nodes 非空自动 rejected）。
- **五投影 read-model**（state.json/index.db(SQLite)/summaries/memory_scratchpad/vectors.db 全是投影）+`projection_log.jsonl` 失步日志+retry/replay+doctor。
- **三段写入门禁**（`write_gates/{prewrite,precommit,postcommit}.py`）+**PreToolUse hooks 写保护**（拦截对 `.story-system/commits/`、index.db 等的直接写）。
- **写作任务书五段固定排序**（chapter_directive 硬约束→CBN/CPNs/CEN 与 must_cover_nodes→forbidden_zones→风格指引→dynamic_context 仅风格参考）；防幻觉三定律（大纲即法律/设定即物理/发明需识别）。
- **六维审查**（High-point/Consistency/Pacing/OOC/Continuity/Reader-pull；无总分、severity=critical 自动 blocking）；reviewer 只回严格 JSON，落库由 review-pipeline 统一。
- **上下文契约 v2**（`context_ranker.py` 新近度+钩子信号加权；`context_weights.py` 题材×阶段动态权重）；长期记忆 v2 三层（Working/Episodic/Semantic，status 含 contradicted/outdated）；RAG 无 Key 自动退 BM25；**run-ledger 断点续跑+作者友好四态报告**（已完成/部分完成/需要你处理/未完成）；CSV 技法检索表 9 张+37 题材模板。
- 评价：**脚本/prompt 职责划分最彻底**（状态变更全过 CLI 门禁+hooks 写保护）、投影可观测性最好；弱点：章节事实真源仍是 JSON、SQLite 无事务边界、无上游 stale 传播、概念名目繁多（Strand/CBN/CPNs/CEN/追读力/三层记忆）认知负担重——**过度工程的真实样本**。

### B3. dreampowers（GPLv3）

opencode 生态（`install.sh` 软链到 `~/.config/opencode/skills/`），14 个 dp-* 单文件巨型 SKILL.md（合计 6135 行），零脚本零 references——全部方法论内联。`dp-using-dreampowers` 入口含「危险信号」反合理化对照表。核心资产：
- **六铁律**（防设定倾泻：先好奇后解释/先感知后体系/扩展已有少添新增/概念预算/禁止旁白讲解/按需揭示）+**概念预算量化**（首章 ≤3 新概念、后续每章 ≤2、每场景 ≤1 解释、每 3000 字 ≥1 未解问题）+**揭示时间表**（大纲服从「悬念出现点→解释发生点」间隔而非反之）。
- **伏笔场记**（一伏笔一文件 `tracking/thread-NNN-*.md`，foreshadow/progress/twist/climax/resolution 事件流，明线/暗线/草蛇灰线三层）+**Claremont 系数**（active−resolved>2 预警）+deferred-threads 延期账。
- **章节文件夹围栏**（一概念一文件未链接即物理不可见；Stage C 写作只读 spec.md；豁免不传递给子代理）+**草稿预审 A/B/C**（A 评估 18 步读取清单→B 用户确认可删减模型可见信息→C 只读 spec 写作）。
- **三阶段审查**（情节→揭示→文笔，各自独立子 agent 各 ≤3 次）+**外部审阅闭环**（dp-review-reader 四维冷读+dp-review-consistency 合并修改 ≤3 轮，仍有问题落 `release/chapter-NNN-TBD.md` 人工兜底）+**九维连续性检查**+AI 味六层面检测。
- **场景类型导演**（动作/情感/对话子模式+主模式判定「去掉哪层场景失效」+张弛法则 ≤2 连续高张力+张力追踪表+赌注阶梯）；**章节摘要契约**（≤150 字+[章末状态]快照，重生成时向下游 spec 插 STALE-DEP 陈旧标记）；七维风格问卷+54 参考作者+遮名测试；`tested_model.md` 八维模型依从性矩阵（Claude Opus 4.6 基准，MiniMax M2.7 可用、Sonnet 4.6「多约束并行」仅 15 分）。
- 评价：**防写崩方法论密度全组最高**+物理围栏是最激进上下文收敛+TBD/STALE-DEP/tested_model 工程诚实度高；但零确定性校验（字数/Claremont/AI 味全靠模型自己数）、巨型单文件对弱模型不友好、流程极重。

### B4. wgwtest/novel-writing（MIT）

单 SKILL.md 216 行+10 篇 references+`scripts/check_manuscript_text.py`（编码损伤/**prompt 泄漏**正则捕获/可疑拉丁片段白名单/引号失衡/段落重复）。项目状态外包给姊妹仓库 novel-project-strategy。核心资产：
- **Context LOD L0-L4**（任务→硬约束→近场全文→远场结构卡→冷区默认排除）；**读者知识≠作者知识**；**重要角色不能裸进**（首场必须身份+关系+第一印象）；**观察权 vs 知识权双查**；**认知分层与语言**（信息分布 shared/specialized/private × 认知地位观察/转述/判断/意图/误认）；**决策所有权五分离**（experiential center/problem owner/decision owner/domain actor/execution owner——POV 决定压力先后不自动授予权威）；对话经由行为三分；**因果桥链条**（new pressure→interpret→goal→method→options 变化→visible consequence）；**风格承载材料保护**（对话/内心/节奏性重复不得静默压缩成摘要）；入场/退场状态契约；结构化审查输出含**「Should this become a project rule?」**问题→规则沉淀位。
- **「文档即契约」测试**（`tests/test_story_outline_contract.py` 把 references 术语当契约断言，文档漂移 CI 抓住）。
- 评价：全组最纯叙事工艺库+prompt 泄漏检查独有+维护纪律最好（文档测试化）；但零状态零审查循环零网文特化——是可拼装的上游素材而非竞品。

## 附录 C：英文/多 harness/平台 4 仓详读（sub agent 原始报告）

### C1. creative-writing-skills（Apache 2.0，433★）

Mars/Meridian 生态「agent+skill 组合包」，分发到 Claude Code/Cowork/Claude.ai/Meridian。35 个 SKILL.md：`skills/` 11 个为 Mars 源、`cw/skills/` 24 个为构建产物（`scripts/sync_cw_skills.py` 区分 GENERATED/MANUAL，**CI 对漂移直接失败**——「单源多 harness」的构建期解法）。11 个独立 agent（muse/writer/critic/editor/reader-sim/character-sim/brainstormer/outliner/style-creator/continuity-checker/kb-lead 依赖上游）。核心资产：
- **kb-management 五分区**（Canon 已定事实/Wiki 综合/Styles 文风/Vocab 术语表（canonical/aliases/来源）/Issues 持续问题）+**knowledge-layers 五层**（AGENTS.md 意图/.context/ 契约/KB 跨域/docs/ 用户/work 临时+「Current Truth Over History」删除优先）+**qi-layer 四原则**（Fractal Compression/Hierarchical Summarization/LCA Deduplication/Progressive Disclosure）——**知识分层理论全组最体系**。
- reader-sim（persona 沿 5 条 reader reward channel 逐刻报告体验）、character-sim（以角色知识边界对话）、style file 文风蒸馏（从散文样本提取 voice 入 `kb/styles/`）。
- 评价：理论最完整；但状态全靠 LLM 自觉写 markdown、依赖私有 Meridian 生态、无硬约束门。

### C2. Claude-Code-Novel-Writer（无 LICENSE，128★）

文件工作区模板（非 skill 库）：5 skill+7 role，`.agents/` 正本+`.claude/` 一行指回的 thin adapter+`.codex/agents/*.toml`+Pi 直读——**canonical+thin adapter 与本仓 adapters 最同思路**。核心资产：
- **ground-truth order**（用户指令>手稿正文>大纲>人物世界状态>派生指标五级权威序）；**手稿唯一真源+派生 JSON 可再生**（`sync-state.sh` 按字数阈值从手稿重算 planning/characters/worldbuilding 的 JSON）；**intentional ambiguity 分类**（continuity-pass 把「真矛盾」与「不可靠叙述/延迟揭示」四级分级分开）；**mechanical signals only**（quality-check.sh 只出字数/对话占比信号，明令「不得宣称启发式指标能证明文学质量」）；`verify-system.sh` 仓库结构自检门。
- 评价：derived-state 可再生设计与本仓投影原则同源；无 LICENSE、无书/卷/章层级、continuity finding 不可机器验证。

### C3. oh-story-dsh（MIT，218★）——与本仓退役 plugin/ 同血统的最新演化

DSH 社区插件，vendored 三知识包（oh-story 13 skill+7 role、drama 10 skill、novel-to-game 7 skill）。**核心演化 = 供应链工程**：
- `packages/knowledge/oh-story/manifest.json` schemaVersion 2：逐项钉住 upstream repo、commit、releaseVersion 0.7.8、`agentsVersion: 28`，**每个文件 sha256+bytes 清单**；`sync-oh-story-assets.ts` 上游同步（剔除爬榜脚本/字节码）+`check-upstream-parity.ts`/`check-dsh-boundary.ts` 奇偶校验。
- 运行时 `skill-provider.ts` cordos provider：frontmatter 解析+目录名校验+每 skill 前置 DSH bridge；**`oh_story_bundled_reference` 只读 allowlist 引用器（拒绝路径逃逸，防 skill 篡改 role 参考资料）**；发布 npm `@oh-story/dsh`。
- 方法论：story 主路由（意图路由+作者记忆+多书切换+`.story-deployed` agents_version 部署标记）；**Reference Gate 强制先读后写**（落笔前分块读到 EOF，旧会话「读过」不作数）；**Constraint Lock**（用户字数带/必发生/禁止发生/时间锚原样锁定）；作者记忆回执（无 `Author Memory Receipt` ok:true 不得声称已记住）；deslop 四原则（改味优先/最小改动/保留意图/自然文本基准）；story-review 三视角并行对抗+统一 Findings Schema+S1/S2/S3+「路径不可读时必用内置 rubric 并报 `Rubric Source: embedded fallback`」防降级。
- 评价：manifest 哈希钉版+parity CI 是**全部 13 仓最强的供应链完整性方案**；但连续性仍是提示词纪律（post-write 补救而非写前校验）、六 harness 靠运行时目录探测比单源配置噪音大。

### C4. denova（Apache 2.0，670★）

Go 单二进制创作平台（写作 IDE+互动文字冒险+图像），skill 是平台可插拔能力。核心资产：
- **skillassembly 三面同源**（`internal/agents/skillassembly/assembly.go`：一个有效目录同时投影到 SystemPrompt SkillCatalog（仅 name+description）/可调用工具/`skill://` 引用适配器，三面可见性一致）；zip/目录安装（准 marketplace）+按 10 种 agent kind 的 per-agent 可用性覆盖+写作 skill 动态解析。
- **novel-standard / novel-lite 双档**：standard = 主 agent 起草→内建 SubAgent 只审不改→主 agent 修订并同轮更新状态；**lite = 主 agent 直出、禁止起任何子流程**（快续/探索稿）；scope 由用户消息唯一决定（明令无 `writing_scope` 字段）；review 只出带证据位置的结构化 issue、不含表扬。
- **四种稳定性上下文契约**（immutable/stable leading/mutable state/turn ephemeral，`docs/agent-prompt-context-architecture-benchmark.md`，含对 Codex/Claude Code/oh-my-pi 对标审计）+Context State 快照+append-only diff；游戏线四真源分工（历史=已提交 Turn、当前可算事实=Actor State、稳定设定=资料库、未来意图=`director.md`）。
- 评价：平台承载 skill 的成熟答案（三面同源/双档/稳定性契约可直接对标）；但写作方法论厚度全组最薄（仅 2 skill）、进度/人物状态靠模型自觉、无权威库。

## 附录 D：clone 清单

`/tmp/novel-skills-survey/`：Distilled-Novel-Toolbox、chinese-webnovel-skills、chinese-novelist-skill、awesome-agent-skills、tianming-skill、chinese-longnovel-skill、webnovel-writer、dreampowers、novel-writing、creative-writing-skills、Claude-Code-Novel-Writer、oh-story-dsh、denova（均 `--depth 1`，共约 116MB，可删除重 clone）。
