# Task 37: 人物阶段深度整改——执行端投递、席位闭环硬门与二级造人约束

**状态**: DONE（2026-08-22）
**前置**: Task 36（world→character 串行化、席位机制、roster 档位机器门）；Task 32（卷级班底）；Task 31（status-update 对账）。

## 背景：三轮反向审计（说明盘点 → persona/上游反向 → 席位填充追问 → 深度反向）

T36 落地后用户对 character 阶段做同节奏审计，共盘出 **11 条缺陷**：

**A 执行端投递断裂（🔴）**
- **A1 契约设计不进写作端**：chapter-draft 槽位无人物通道；canon 最小集人物状态只查注册表四字段（name/role_class/status/exit_type），不含 arc_role、不含契约档案；执行卡必给字段无「出场人物要点」。执念/失稳/心理简表/行为残迹经两次衰减归零——与 world 修复前同构（world_lexicon 槽就是为此而建），character 无对等物。
- **A2 arc_role/预期退场只有承诺无验收**：落 state_json 后无任何机器或审查节点核对兑现；--pending-status 只对账 status 六态。

**B 二级造人端缺约束（🟡）**
- **B1 persona 盲区门只守契约层**：volume-outline/chapter-plan 槽位无 persona——班底（含微档案）与章级微档案实际造人但「不得整档落 cannot_write」无门，最早 prose-review 才暴露。
- **B2（深度轮新增）执行卡查重无数据**：微档案要求「不与在库人物重名」，但执行卡注入无注册表镜像（character_roster 槽只在卷纲端）——查重指令是空头支票。

**C 席位闭环四洞（上轮追问挖出）**
- **C1 roster 落库丢 seat_ref**（实 bug）：register 白名单只写 arc_role/预期退场/登场卷，SKILL 声称 seat_ref 随 state_json——文档与代码不符；注册表答不了「席位谁坐」，席位重坐无对账基础。
- **C2 「待契约认领」承诺无人验收**：validate 判据「未认领**且**无处置才 WARN」——标了待契约认领却忘了认领静默通过，处置标注沦为免检标签。
- **C3 卷级班底席位无机器门**：待卷级班底席位有没有人填只有 LLM 审查管。
- **C4 席位对账靠人传参**：--world 不传则静默跳过，无机器强制。

**D 轻项**：平台轴「声明知晓」零落实（D1）；近重名只查契约层（D2，T36 已知遗留）。

**用户授权**：「在进行一次深度反向思考看看是否还有漏洞问题，允许联网补充知识、允许破坏性改动」——一轮全量落地。

## 研究锚点（联网）

- **One-line essence / character bible**（[PlotLens 模板](https://plotlens.ai/downloads/character-bible-template/)、[Scriptation 指南](https://scriptation.com/blog/tv-show-bible-and-character-bibles-guide/)）：编剧室标准实践——每个人物一条 essence/logline 一句话字段 + 详细档案；主要人物约 3 段、次要 1 短段；新加入的编剧靠 bible 写出一致的人物。锚定 roster `essence` 字段设计。
- **series bible 应含全部主要+次要人物**（[Nathan Bransford](https://nathanbransford.com/blog/2010/05/series-bible)、[Killzoneblog](https://killzoneblog.com/2020/12/tips-to-create-a-series-bible.html)）：concordance 功能 + 逐书记录情感弧——锚定执行卡查重必须看到全量在库人物（B2）与微档案升级通道。
- **命名混淆防护**（[Helping Writers Become Authors](https://www.helpingwritersbecomeauthors.com/dont-confuse-readers-with-similar/)、[Killzoneblog 命名贴](https://killzoneblog.com/2021/05/tips-for-dealing-with-character-names.html)）：同书避免首字母/读音相近的名字对——锚定 register 的归一化近重名 WARN（语义判级仍属 LLM 审查）。

## 变更清单（按层）

**L0 schema**：planning-candidate.schema.json 的 `character_roster` 与 `volume_characters` 条目各 + 可选 `essence`（1-160 字，人物卡一句话要点）。

**L1 脚本**
- `novelos_register_characters.py`：roster 白名单补 `seat_ref`/`essence`（C1）；新增 `--world`（席位对账：roster/entry 的 seat_ref 引用不存在 = FAIL；写库后报告「待契约认领/待卷级班底」仍无认领人的席位 WARN 终核——C3）；新增归一化近重名 WARN（NFKC + 去空白 + casefold，原始名不同才报；完全同名走幂等合并不报）。
- `novelos_validate_character.py`：席位处置分级（C2）——待契约认领无人认领 = **error**（标注是承诺不是免检标签）；待卷级班底无人认领 = WARN（卷级义务，register --world 终核）；显式虚位 = 静默。新增 `--project <id>`（C4）自动解析 setup.scale（归一化 `超长篇（300万字以上）`→`超长篇`，冒烟实测发现并修复）与 locked world_contract metadata——漏传参不再静默降级；显式 `--scale/--world` 优先。
- `novelos_compose_prompt.py`：新增 `character_essence` 槽（出场人物卡：注册表 main/secondary 逐行——arc_role/席位/essence 要点 + 死活状态与退场型；无 essence 逐行标注旧数据降级；空注册表警示占位）与 `persona_gate` 槽（persona 硬边界门：`persona.anchors.blindspots` 的 cannot_write/refuses（自带绕开方式）+ 表达偏好 + 负向约束紧凑渲染；旧版分身/未绑定降级占位不阻断）；`character_roster` 槽注册表行补 state_json 席位显示。

**L2 方法论（8 个 prompt + 槽位矩阵 6 资产）**
- `character-contract/prompt.md`：roster 出口 + `essence`（main 必填——「写他时必须抓住什么」，好坏对照示例：它不是 arc_role 复述）；平台行改口（经分身间接生效，无直接消费点不设检查项——D1）；自检 +14 人物卡、+14 席位认领。
- `volume-outline/prompt.md`：班底节 + persona 盲区门（不整档落「写不了」场景，涉盲区带绕开方式）；锁定指令改 `--entry --world`。
- `chapter-plan-execution-card/prompt.md`：必给字段 + **出场人物要点**（POV 与在场者每人一行契约要点索引 + POV 知识边界声明；无因超出卷纲载体范围 = blocking）；微档案查重改「对照名册镜像（character_roster 槽）」+ 盲区门一句。
- `chapter-draft-generation/prompt.md`：persona 纪律 +第 5 条「出场人物卡对表」（essence 逐人对表、失稳点显形、已退场人物不得无因出场）。
- `prose-quality-review/prompt.md`：+人物卡一致性（语域/行为与 essence 矛盾 = warning；退场人物无连续性依据出场 = blocking）。
- 三个 review：volume-outline-review +8b 班底盲区门（blocking）；chapter-plan-review +7b 出场人物要点（缺 = warning/超载体 = blocking）+7c 微档案查重与盲区；character-contract-review +16 essence 核验（main 缺 = warning；与档案矛盾 = blocking）。
- 槽位矩阵（agent-recipes.json + 文档表 + 各 manifest）：volume-outline(±review) +`persona_gate`；chapter-plan(±review) +`character_roster`+`persona_gate`；chapter-draft +`character_essence`（canon 前）；prose-review +`character_essence`。slot_vocabulary +两词条。

**L5 编排**：novel-planning SKILL.md——step 5 Character 输入 + essence 与 `--project` 校验；step 8 双锁定指令带 `--world`；速查表区新增「character essence 速查表」。

## 设计取舍记录

1. **essence 放 roster 而非新表**：人物卡的机器源与 arc_role 同行——注册表 state_json 单点落库，character_essence 槽从注册表读（不查 planning_assets），执行端与规划端同源。
2. **persona_gate 轻量而非 persona_full 全量注入二级造人端**：卷纲/执行卡需要的是硬边界（盲区+约束），全量人格是写作端的燃料——省 token 且语义正确；旧版分身无结构化盲区时降级为可取字段（表达偏好/负向约束），再无则占位不阻断。
3. **待契约认领提级 error 而非 WARN**：语义上该标注就是对契约层的承诺；确需改道走 change proposal 改 world 处置（待卷级班底/虚位），而不是留一个永远不兑现的「待认领」。
4. **register 的近重名只做归一化近似**（NFKC/空白/大小写），音近形近语义判级仍属审查——机器候选生成 + 人判的完整方案维持 T36 遗留。
5. **arc_role 兑现（A2）未做机器对账**：弧职责是自由文本，机器无法验证「兑现」；本轮把「预期退场偏离」留给 --pending-status 既有对账、弧兑现留给卷/章审查项（7b 在场人物超出载体范围 = blocking 即其执行端形态）。
6. **执行卡出场人物要点是 LLM 字段非机器槽**：场景级人物集合只有执行卡知道；机器槽（character_essence）负责 Writer 端兜底，执行卡字段负责场景级精度——双层互补，与 world_lexicon（机器）+ 消费时序表（LLM 对账）同构。

## 验收

- `tests/test_character_world_validate.py` +5（处置三态分级/essence 边界/_resolve_from_db 自动解析），20 项全绿。
- `tests/test_register_characters.py` +4（seat_ref+essence 落库/--world 引用不存在 FAIL/未认领承诺席位 WARN/归一化近重名 WARN 与完全同名不误报），22 项全绿。
- `tests/test_slot_resolution.py` +`EssenceGateSlots` 5 项（essence 双态/persona_gate 三态/执行卡见名册+门/卷纲与正文端新槽）。
- **223 tests 四命令全绿**（209→223：+5 validate +4 register +5 slots +既有断言更新）；SIZE_BUDGET character-contract 175→180（实测 175 顶格）。
- CLI 冒烟：validate_character `--project` 自动解析（实测发现 setup.scale 全标签格式并归一化修复）；显式 `--world --scale` 三路径——待契约认领未认领 FAIL（处置 error）、认领后 PASS（待卷级班底 WARN、显式虚位静默）。
- 修复实现期两处自伤：_near_dup_warns 空值误报（norm 不在库时 get 返回 None 也触发）；测试种子连接错用（conn vs conn2）。

## 遗留说明

1. **arc_role 兑现机器对账**（A2 全量）：需要弧职责结构化（带 id 的承诺挂接）才有机器判据——T36 取舍 4 已记录同因；当前由审查项 7b + 卷级班底核验兜底。
2. **近重名语义判级**：维持 T36 遗留（机器候选生成 + 人判）；本轮已补归一化近似（全半角/空白/大小写）。
3. **旧契约无 essence**：character_essence 槽逐行标注降级不阻断；契约经 change proposal 出新 revision 补 essence 后自动生效（与 world_lexicon 旧项目策略一致）。
4. **微档案升级检测**（minor 连续出场 N 章提示升班底）：需要章-人物关联统计，留待连续性账本增强。
