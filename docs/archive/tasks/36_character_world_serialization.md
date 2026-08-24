# Task 36: 人物‖世界串行化与世界/人物阶段深度重构

**状态**: DONE（2026-08-22）
**前置**: Task 35（strategy 交接产物 handoffs/claim_ledger/档位区间）；Task 32（卷级班底）；Task 30（六角色/三层造人/死亡退场设计）。

## 背景：四轮反向审计（说明盘点 → 三问 → persona/setup 反向 → 深度反向）

用户按既有节奏对 character‖world 做阶段审计，四轮共盘出 **19 条接缝 + 深挖新增 4 条**：

**A 结构层（🔴×5）**：sibling 无依赖边（world 增量修订不标 character stale，静默漂移）；交叉审查假设清单无载体；席位机制不存在（势力不留岗位、人物不认领、无对账）；卷纲盲区（槽位只有 story_arc——看不到世界消费时序表/契约 roster/注册表，班底「指认来源+查重」无从校验）；语域表执行端双断（Writer 与 prose 审查都被要求遵守看不见的表）。

**B 签收层（🟡×4）**：无结构化上游消费表；T35 handoffs 数据随 metadata 注入但零教学；claim_ledger/progress_types 无人挂接；双 review 无 upstream-reviews 槽。

**C 人格层**：character persona_full 注入零教学（分身盲区/目光/库存全闲置，童年线素材失联）；world 零 persona 零 kernel（盲区门缺失——分身写不了大战争而军阵体系成核心消费场景无人拦）。

**D setup 四轴（一好三残）**：频道 world 只盖男频（女频/全向零模块、审查零频道检查）；规模双侧零接线 + character 缺 project_setup 槽；题材 character 零模块 + world genre_pack 内容未注入（非空态静默退化）；平台唯一合法通道（分身）恰好盲。

**E 投递层**：world 零 metadata 结构化出口（全链唯一）；worlds DB 死表。

**F 代价机制**：world 维度代价缺可逆性轴（无不可逆阈值、压制无解除）与承担者轴（不查 strategy 红线，可绕过 book_soul 门扣主角永久代价）；strategy 调度层与 world 物理层语言不通。

**深度新增（联网锚点后）**：中盘换挡的世界演化预留（midpoint_renewal 的换地图/势力重组/规则改写需要世界预置接口，无人设计）；open 终局的喂料储备声明；六角色与岗位表同源（六角色的「人」本该席位化）；自造词节制（每个自造词损耗读者——研究锚点）+ 近重复词条合并。

**用户裁决**：链形从 character‖world 并行改为 **world → character 串行**（世界设岗位不造人，人物认领席位）——并行协调的弱机制（互列假设）退役为单向消费 + 依赖边自动化。

## 研究锚点（联网）

- 次序之争三派（world-first/character-first/story-first）：奇幻侧「世界塑造一切」+「只建故事需要的」支持 故事层先行→世界实现→人物入世；scribe-forge 的 need-based 展开即本系统反百科+增量扩展。
- 人物表规模基准（Goodreads 大样本）：单册 4-6 主要 + ~10 次要 + 15-20 提及；系列金字塔逐卷扩员——锚定 roster 档位 短篇 2-5/中篇 3-8/长篇 5-12/超长篇 8-16（班底/微档案在契约之外接盘）。
- 连载词汇一致性（series bible/concordance/词汇表实践）：词汇表抓近重名、从手稿反查定义——支撑语域表机器可读化 + 执行端注入 + 近重复词条检查。

## 变更清单（按层）

**L0 schema**：`config/schemas/world-metadata.schema.json` 新建（v1：seats 1-40 六要素+disposition 枚举 / lexicon 四件套四类各≥1 示例禁词 / dimension_costs 1-12 压制→release、protagonist_permanent→book_soul_ref 条件门[修 JSON Schema if 空真陷阱：条件加 required] / decision_points 0-4）；planning-candidate.schema.json 两处 + 可选 `seat_ref`（roster + volume_characters）。

**L1 脚本**：`novelos_compose_prompt.py` 新增 `world_lexicon`（locked world metadata.lexicon → 执行端紧凑注入；未锁定/未结构化 → 警示占位不阻断）与 `character_roster`（契约 roster + 注册表镜像 → 卷纲班底指认/查重权威）两 resolver 入 SLOT_REGISTRY；`novelos_validate_world.py` 新建（schema + 岗位重名 + 代价两轴机器门：压制缺解除/不可逆缺阈值/主角永久缺 ref）；`novelos_validate_character.py` 新建（roster schema + 规模×scale 机器门 + 重名 + main 在场 + `--world` 席位对账[引用不存在=错、未认领无处置=WARN]）。

**L2 方法论**：
- `world-contract/prompt.md` 破坏性重写（150→165 行）：上游消费表六行（world_changes↔时序表逐条对账 / midpoint 演化预留 / open 喂料储备 / costs 两轴对齐 / claim 兑付世界条件 / power_currency 同源）；六角色人侧席位化；**岗位表**（设位不设人 + 主要席位处置枚举 + 退场继承）；**代价两轴**（可逆性三档+阈值、承担者默认配角/世界/物品、不得新增主角永久）；语域表 + 自造词节制/近重复合并 + metadata 机器可读；规模接线四档；persona 盲区门；world-metadata 出口；增量扩展保留 + 设定同质化自检。
- 新模块：world `channel-female.md`（规则-声誉循环/空间政治/力量服务关系/开局优势转移）、`channel-omni.md`（双轨规则层/主结算轴声明/交叉点）；审查对偶 check-channel-male/female/omni（male 从 rubric 内联迁出条件模块）。
- `character-contract/prompt.md` 破坏性重写（130→170 行）：上游消费表九行（character_arcs 载体/claim 认领/progress_types 承载/power_currency 三方同源/narrative_cruelty 边界/setup 四轴处置）；**世界移交清单消费**六项（席位认领+seat_ref/能力边界对 world 细则/语域分化/六角色对应/代价承担者认领/功能转移席位重坐）；**persona 四用法 character 版**（盲区→角色类型门/目光→失稳频段/库存→细节原料含童年线/有限视角→误判呈现方式）；roster 扩展 seat_ref + 规模档位；新模块 `genre-present.md`（题材人物光谱：原型在场预期/烂大街预警/执念母题取材）；缺口走 change proposal 回 world，禁止隐式发明世界设定。
- 双 review 重写：world-review 0-9 项（语域双版一致/人侧岗位化/代价两轴三级 blocking/岗位表越权造人 blocking/strategy 对账/open 无储备 blocking/persona 盲区门/规模失配）+ 上游回执边界；character-review 0b/0c/14/15 新项（世界移交对账/strategy 认领/persona 用法核验/近重名）+ 席位与规模 blocking。
- 执行端微调：chapter-draft 与 prose-review 的术语语域行改为消费 `world_lexicon` 槽注入的本书语域表（craft 卡只管判定分档）；卷纲新增「世界消费与本卷欠账」节（时序表对账/席位消费/变迁行兑现/禁止就地发明）+ 班底 seat_ref；卷纲审查新增第 9 项世界对账（就地发明 = blocking）。

**槽位/配方（matrix-first，双侧同步）**：world +persona_full+genre_pack；world-review +setup+persona+genre+双 upstream-reviews；character +project_setup+genre_pack+upstream:world_contract；character-review +同款 11 槽（含三上游回执）；volume_outline/volume-outline-review +upstream:world_contract+character_roster；chapter_draft/prose-quality-review +world_lexicon。`agent-recipes.json` 八条目更新，documentation/agent-recipes.md 表重生成。

**L5 编排**：novel-planning SKILL 路由表改串行依赖（world 先行）、step 5 增 World/Character sub agent 输入描述、step 8 增契约锁定 --roster、新增 world-metadata 速查表；AGENTS.md 依赖顺序 + 角色表拆两行 + 双 validate 脚本登记。

## 设计取舍记录

1. **串行方向 world→character 而非反向**：六角色的人侧、能力边界细则锚点、语域分化、代价物理先于调度——数据依赖方向本就是世界喂人物；反向循环（人物需要 world 没建的机构）走 change proposal 回流，比卷纲/正文期发现便宜。
2. **岗位表用岗位名做键而非 UUID**：seats.name 即 seat_ref——席位是少量人工产物，重名由 validate 拦，ID 仪式感不值。
3. **roster 规模是机器门、world 设定深度只是方法论指导**：人物数可数可拦；设定深度题材差异极大（world prompt 自己警告强制统一字段有害），机器门会误伤。
4. **claim 挂接留在正文语义层**：claim_ledger 无稳定 id，roster 加 claims 字段是无 id 的伪结构化——弧与承诺的挂接由 prompt 要求 + 审查核验，不进 schema。
5. **worlds DB 死表维持现状**：投影从 planning_assets 渲染已闭环；规范化落库需迁移且收益低于成本，记录为预留（未来需要世界库检索再启用）。
6. **旧项目兼容**：world_lexicon 槽对无 world/无 metadata 的项目降级为警示占位（craft 卡保底纪律），不阻断章节生产；character 修订时 world 缺失会停（链形完整性，与其它上游同规则）——旧项目修订 character 前需先补世界契约。
7. **male 频道检查从 world-review rubric 内联迁出为条件模块**：三频道对偶后主干频道中立，男频条款不再常驻（原 1b 内联句删除，模块化对齐 character 侧模式）。

## 验收

- `tests/test_character_world_validate.py` 新建 15 项（schema 兼容/规模档位边界×4 档/未知档位/跳过门/重名/无 main/席位引用错/未认领 WARN）。
- `tests/test_slot_resolution.py` 新增 `WorldCharacterSlots` 6 项（character 消费 world 上游含 metadata/缺 world 即停/world 生成槽/persona 盲区注入/world_lexicon 双态/卷纲见 world+名册镜像）+ 空名册占位。
- **209 tests 全绿**（188→209：+15 validate +6 slots），compileall / hygiene / manifest 四命令全过。
- CLI 冒烟：validate_world PASS（席位 2/维度 2）与 FAIL 双路径（缺阈值+缺解除 exit 1）；validate_character PASS（规模档位+席位对账）与 FAIL（seat_ref 引用不存在席）。
- schema 条件门陷阱修复实测：`if.properties` 对缺省属性空真匹配 → 条件加 `required` 后 PASS/FAIL 边界正确。

## 遗留说明

1. **语域禁词机器扫描**：banned_categories 已有示例禁词，可再建正则扫描器做正文预检（prose-review 目前 LLM 判级 + craft 卡阈值）——留待需要时做。
2. **禁用词条近重复**（灵石/灵晶）审查为语义判级（warning），无机器判据。
3. 旧 world 契约（无 metadata）不回溯；修订时经 change proposal 补齐即可被 world_lexicon 消费。
4. story-arc 未动（本轮范围 character‖world；其槽位本就含双上游全文）。
