# NovelOS 任务账本 · 零 Python 演进路线

> 2026-08-24 仓库重组后重置。历史任务账本（Task 06–39，py 时代）归档于 `docs/archive/tasks/`，仅作考古参考，不再更新。
> 状态只用 `TODO` / `IN PROGRESS` / `DONE` / `BLOCKED`；生产路径接通且验证通过才 `DONE`。

## R1 · 插件实体化（读路径，先行）

- [x] `DONE` dsh-novelos-viewer 脚手架：ui-panel 形态，host 双只读路由 `GET /db-bytes` + `GET /manifest`（另有 `/sql-wasm.wasm` 托管）。**验证（2026-08-24）：注入 active(da88a057)，三路由实测 200——manifest ok=True 解析到真实库 / db-bytes 2,326,528 字节 / wasm 659,806 字节；`novelos_viewer_status` 工具注册**
- [x] `DONE` client 集成 sql.js(WASM)：内存直读 db 字节，六视图渲染（总览/卷纲/章节/人物/世界/连续性）。**验证：sql.js 1.13.0 打入 bundle（client.js 83KB）；六视图全部 SQL 对真实库冒烟 21/21 通过（scripts/smoke-sql.mjs）**
- [ ] `BLOCKED(环境)` 浏览器端面板视觉确认——浏览器自动化 token 服务未启动（127.0.0.1:53699 拒连）无法截图；机器层已全绿：client bundle 经 `/plugins/@dsh-external/dsh-novelos-viewer/client.js` 与 `/api/client.js` 均 200、SQL 冒烟 21/21、wizard 四路由 GET 200 + POST 405。待用户在 GUI 打开面板一眼终验即可关闭
- [x] `DONE` wizard 三件套从 `plugin/client/` 接入面板（替代 file:// 打开），kernel-roster 数据源改为 host 直查。**验证（2026-08-24）：host 新增三路由——`/wizard`（html，相对 script src 改写为绝对 API 路径）、`/project-wizard-data.js`（静态 36KB）、`/kernel-roster.js`（node:sqlite 只读实时直查，SQL 与 legacy-python/scripts/novelos_export_kernel_roster.py 的 build_roster 同源：author_kernel+active 每 profile 取最高 revision）；client 面板新增「项目向导」入口（iframe + 最小 JSON-RPC 桥接应答器 ui/initialize/ui/update-model-context，提交请求捕获到面板文本框+复制按钮）。实测：四路由 GET 全 200、POST /wizard 405、src 重写生效、roster 直查返回 []（库中 author_kernel active=0，与静态镜像一致）**

## R2 · JS 写门（写路径收口，三件套捆绑交付）

- [x] `DONE` ajv(Ajv2020/Draft 2020-12) 消费 `config/schemas/*.json` 复刻 jsonschema 校验门（含词表级联、内核库内反查）。**验证（2026-08-24）：`plugin/dsh-novelos-viewer/src/gate/create-project.ts` 全量移植 validate_request / validate_kernel_candidate / validate_candidate（E0 结构短路、其余累加）；快照比对用键序无关 deepEqual；真实词表 project-wizard-data.js + 真实 schema 冒烟全过**
- [x] `DONE` node:sqlite BEGIN IMMEDIATE 单事务落库 + crypto content_hash。**验证：persistKernel/persistProject 两事务逐条 INSERT 与 py 同序；UNIQUE(content_hash,media_type) 撞车译成业务 GateFail 且整体回滚（测试断言资源计数不变）；金样哈希等价 4/4——py json.dumps(indent=2,ensure_ascii=False) vs JS pyJson 对 CJK/转义/emoji/浮点向量 sha256 字节级一致**
- [x] `DONE` 写旁路封死：唯一写入口 = 插件 defineTool；agent 无裸 SQL 写通道。**验证（2026-08-24）：`src/gate/write-tools.ts` 注册五工具——`novelos_gate_entry`（只读校验）/ `novelos_kernel_commit`（内核事务，dryRun 支持，mode=create 自动缝合返回 boundPayload）/ `novelos_project_commit`（六表事务 + 裁决门 userAdjudicated 参数）/ `novelos_propagate_stale` / `novelos_delete_project`；任何 FAIL 返回 ok:false 且不产生写入。dev_inject_plugin host ✓（注册零异常）；scripts/smoke-gate.mjs + smoke-r6.mjs 用编译产物对真实词表+真实 schemas+生产库只读冒烟 SMOKE PASS。注意：宿主 Node ESM 下子路径必须 `ajv/dist/2020.js`（平铺 dist 布局），裸 `ajv/dist/2020` 会 ENOENT**
- [x] `DONE` 门测试 vitest 迁移并全绿。**验证：test/create-project.test.ts 12 用例 + test/propagate-delete.test.ts 10 用例 + 原语 9 + 夹具 2 = 33/33 通过；tsc --noEmit 干净**
- [x] `DONE` R2 补齐 · stale 传播 JS 化（commit 本轮）。**验证：`src/gate/propagate-stale.ts` 移植 novelos_propagate_stale.py——coarse BFS 直接+间接全量标 / fine 模式依赖边 upstream_version+content_hash 双重比对（neutral 不误伤，间接下游列 indirectPending 不自动标）；事务失败回滚抛 GateFail。test/propagate-delete.test.ts 覆盖 dryRun/全量标/candidate 不动/fine 判定/GateFail。生产库 smoke-r6.mjs 只读冒烟 PASS**
- [x] `DONE` R2 补齐 · 项目删除 JS 化（commit 本轮）。**验证：`src/gate/delete-project.ts` 移植 novelos_delete_project.py——foreign_keys=OFF 显式事务依赖逆序逐表删（planning_asset_dependencies 双向边→reviews→连续性六账本→chapters/volumes/planning_assets/characters/worlds/bindings/books/projects/resources），不动 creator_profile_versions 共享系统原型资源；cleanOrphans/verify/backupDatabase（.bak-YYYYMMDD-HHMMSS 同格式）；投影目录删除随视图链退役省略（单渲染器红线）。测试覆盖删净断言、共享资源完好、孤儿清理、触发器注入失败后回滚+FK 复原 ON**
- [x] `DONE` R2 补齐 · 人物登记 JS 化（novelos_register_characters.py 25KB）。**验证（2026-08-24，子代理移植+主线程接线）：`src/gate/register-characters.ts` 全量移植三入口——`registerCharactersRun`（预检→BEGIN IMMEDIATE 单事务 roster→entries→statusUpdate 落库）/ `checkPendingStatus` / `checkAuditEntries`（只读对账）；FAIL 一律 throw GateFail（py print+exit 语义收口为阻断），席位对账 seat_ref 不存在=FAIL、未认领承诺席位=WARN。`write-tools.ts` 第六工具 `novelos_register_characters`（project + roster/entries/statusUpdate/world JSON 文本参数 + pendingStatus/auditEntries 只读开关；**无 dryRun**——校验与落库同一事务，假干跑会误导 agent）。test/register-characters.test.ts 22 用例；全仓 vitest 5 文件 55/55、tsc 干净；dev_build_plugin→uninject/inject host ✓ client ✓；scripts/smoke-r7.mjs 编译产物对生产库只读冒烟 SMOKE PASS**
- [x] `DONE` 删除 `legacy-python/` 与 `.venv`，仓库达成零 Python（2026-08-25 收口）。**验证：组装器 JS 移植完成——`scripts/novelos-compose-prompt.mjs`（74,432B，Node22+ 纯标准库零 npm 依赖）经 `scripts/test-compose-prompt.mjs` 19/19 PASS + py↔JS 金样对比 4/4 MATCH（\r 归一后逐字节一致；direction/fusion/kernel-fusion revise/direction+proposal 四样，行为差异 10 条声明见 scripts/COMPOSE-PORT-NOTES.md），主控独立复验通过后执行 `Remove-Item -Recurse -Force legacy-python,.venv` 双 False 确认；全仓 .py 审计（排除 node_modules/docs/archive）= 0 残留；JS 组装器对生产库只读冒烟 exit 0。引用切换：AGENTS.md/README.md/adapters/docs/schemas/catalog prompt/.agents skills 全量改口径（详见重组裁决记录补记）。AGENTS.md 头部已声明「零 Python 达成」**
- [x] `DONE` R4 · validate_* 七件资产校验器机器门语义 JS 化（2026-08-25，git 考古移植）。**验证：从 8af69a8^ 恢复 legacy-python/scripts/novelos_validate_{architecture,book_soul,character,strategy,story_arc,volume_outline,world}.py 七件全文通读（无 direction 校验器——实际命名以此为准），`plugin/dsh-novelos-viewer/src/gate/validate-assets.ts` 全量移植：常量/阈值/错误文案逐字（_SCALE_CADENCE/_STAGE/_ENGINE/_TIER_BEATS/_ROSTER/_ARC 规则表、_CLIMAX_GAP_WORDS=300000、_CLIMAX_UNIT_WORDS=250000、_ACTIVE_DUTIES={推进,兑现,收束}、debt_streak_limit 默认 2 等）；iter_errors 三件（book_soul/strategy/architecture）收集全部错误且不短路继续语义检查，短路四件保持 `${prefix}[path]: msg` 格式（prefix=schema/roster/metadata）；统一入口 `runAssetValidations(conn,{assetType,projectId,scopeRef,schemasDir,metadata?,scale?,upstream?})` 全只读 SELECT，未知类型 GateFail 明确报错；库内模式自动解析 setup.scale（split('（')[0] 归一）/locked 上游/前置卷链（排除当前 scope 防自参照）/注册表名册。`write-tools.ts` 注册第七类工具 `novelos_validate_asset`（assetType/projectId/scopeRef/metadata/scale/upstream，只读连接）供 agent 锁定前自查。test/validate-assets.test.ts 85 用例；插件全量 vitest 7 文件 159/159 通过、tsc --noEmit 干净。已知偏离（声明）：ajv 措辞与 py jsonschema 不同（R2 先例）、JSON.parse 不区分 int/float 字面量、volume_outline 前置卷链排除当前 scopeRef（py CLI 直读文件无库内取行场景的防自参照适配）**
- [ ] `TODO` R4 · 连续性账本直写通道缺口：chapter_facts 等六账本的候选晋升/落库目前无门工具覆盖（AGENTS.md 声称 agent 无裸 SQL 写通道，但该写面实际只能靠主控受控 SQL），需评估新增第七类 defineTool 门或显式声明豁免口径

### ⚠️ 有意行为变更（F2 整改，与 py 版差异显式声明）

py `main()` 在 parent_rationale 含错配标记时仅 print 提示仍继续落库（红队判定的「纸面化裁决门」）。JS 版 `checkMismatchAdjudication()` 默认抛 `GateFail` 阻断落库，仅当调用方显式传入 `userAdjudicated: true`（用户已裁决）才放行。这是红线「任何 FAIL 必须阻断」的直接落实，非等价移植。

### R2 准备记录（2026-08-24）

- **发现并修复：db/migrations/schema.sql 是链中快照且过期**——独立执行缺 planning_assets/creator_profiles/planning_asset_dependencies/project_creator_bindings/creator_profile_versions 五表（002.. 迁移链需不存在的基底，无法自洽重建）。已从生产库 sqlite_master DDL 只读导出重生成 v18 终态基线，回验与生产 **25 表全列零差异**；git 历史可溯（6544290）。
- 插件新增 ajv@8.20.0 依赖；JS 门测试夹具来源 = 重生成后的 schema.sql（node:sqlite `:memory:` 直接 exec 即得生产结构空库）。
- vitest@4.1.11 就位（`pnpm test` = `vitest run`）；R2 首批测试落地：夹具 25 表断言 + 门原语（contentHash/newId/parseCandidateText 容错解析/形状检查器/MISMATCH_MARKERS）**11/11 通过**。原语移植自 create_project.py L91-193，语义逐点对齐——注意 py 裸合法 JSON 不在解析层查形状（形状归上层 validate），修复路径才查。
- 门规格提取子代理运行中 → 产出 `docs/r2-js-gate-spec.md`（create_project.py 全语义规格 + 其余写库脚本清单 + JS 漂移风险点），落地后开始门实现。

## R3 · 编排层适配

- [x] `DONE` AGENTS.md 路由随 R1/R2/R3 落地同步收敛。**验证（2026-08-24）：「数据库访问」节重写为 R2 后规则——写路径唯一入口=插件六门工具（表格列明六工具用途与裁决门红线），读路径=viewer 面板/node:sqlite 只读；头部与 L1 分层改为「业务写面已 JS 化，legacy-python 仅剩只读/非库写工具待处置」；多模型分工节保留**
- [x] `DONE` 多模型分工设置卡：Config 新增 roleWriter/roleReviewer/roleMemory（`provider:model` 或裸 model 名，留空=沿用主会话），`GET /model-roles` 只读路由 + `novelos_model_roles` 工具；AGENTS.md 已加「多模型分工」节。**注入验证：dev_uninject_plugin→dev_inject_plugin 全链路 host ✓ client ✓（2026-08-24）。client 面板可视化展示为可选项暂缓——设置值经 dsh 标准设置界面即可配置**

## R1 实施记录（2026-08-24）

- 插件源码 `plugin/dsh-novelos-viewer/`（pnpm，勿用 npm——本机 npm arborist 报 `Cannot read properties of null (reading 'children')`）；依赖 sql.js@1.13.0。
- 构建链适配安装版 DSH：`dev_build_plugin` 的 detectCheckout 要求 `<root>/packages` 存在 → 建 `~/.dsh/dsh-harness` 垫片（packages=空目录 + node_modules→junction 到桌面版 node_modules）；`scripts/build.sh` 兼容两种布局（源码 checkout / 安装版 node_modules），peer 依赖 junction 保证插件与宿主共享同一 cordis/tools 实例；client 由流水线 `npm run build:client`（tsdown）完成，build.sh 只管 host tsc。
- **注入器修复**：`dsh-super-injector/lib/index.js` findBash 原逻辑 PATH 探测命中 system32 bash.exe（WSL 垫片，未装 WSL 时 spawnSync 不报错但执行失败）→ 已补丁为优先 Git Bash 常见路径 + PATH 探测加 status/wsl 输出校验（备份 index.js.bak-findbash）。
- db 路径解析：模块经 profile junction 加载时 import.meta.url 保留 junction 路径 → realpath 规范化后回推仓库根需上**三级**（lib → dsh-novelos-viewer → plugin → repo）。

## 重组裁决记录（2026-08-24）

- 删除：`.pip_tmp/.tmp_pip/__pycache__/requirements-mcp.txt`（垃圾）；`novelos_render_projection.py` + 投影测试（视图链退役）；`mcp/sqlite-mcp/` + `.codex/config.toml` + `run_sqlite_mcp.*` + `docs/dsh-compatibility.md`（Python MCP 通道退役）
- 暂存：19 个 py 校验门脚本 + 22 个 py 测试 → `legacy-python/`（用户拍板，退出条件见其 README）
- 合并：`documentation/` 并入 `docs/`；`ui/` 三件套迁入 `plugin/client/`；tasks 历史归档 `docs/archive/tasks/`
- 收尾修复（同日）：legacy-python 全部 REPO_ROOT 计算 `parent.parent/parents[1]` → `parents[2]`；测试注入 `sys.path`（parents[1]=legacy-python）保住 `from scripts.x import` 顶层导入；`tasks/cutover/hygiene.json` 迁回活动区并重生成；`tasks/migration|07_prompt_catalog` 证据文件改指 `docs/archive/tasks/`；catalog prompt/adapters/schemas/.agents skills 全量路径前缀更新；`.venv` 以 `py -3.10` 重建（全局 3.15.0a7 的 rpds DLL 不兼容）。**验证：`python -m unittest discover -s legacy-python/tests` = 269 例全绿（用 `.venv\Scripts\python.exe`）**
- 零 Python 收口补记（2026-08-25）：legacy-python/ 与 .venv 整体删除；组装器以 JS 版为唯一实现（金样 4/4 MATCH）；validate_* 七件校验器机器门语义未随迁——catalog planning/review prompt 与 config/schemas description 中相关引用已改为「对照规则自查（机器门待 R4 JS 化）」口径，语义规格以 py 删除前 git 历史（aeafdb9 及之前）为考古依据；gate/*.ts 头注释与 COMPOSE-PORT-NOTES.md 的 legacy 路径引用保留作移植溯源。

## 对抗审查修复轮（2026-08-25）

三路子代理对抗审查（题材信息流/流程间上下文/组织与产出质量）产出 23 条 P0/P1/P2，按 ROI 序修复，全部过终验链：tsc exit=0 · vitest **159/159**（7 文件）· compose **19/19** · guardrails **241/241**：

- **WP1 组装器静默降级硬失败**：`scripts/novelos-compose-prompt.mjs` slotUpstreamReviews/slotCanonMinimal/slotPromiseLedger 三处 catch 改 fail()（py 版零注入事故根因根治）；persona_gate 降级分支标题加「⚠ 降级运行」+补救指引。
- **WP2 配方补槽**：`config/agent-recipes.json` direction-review+genre_pack、chapter_plan+book_soul、chapter_draft+persona_gate/project_setup/book_soul、prose-quality-review+persona_gate/project_setup/canon_minimal；六个 manifest 同步（含护栏揪出的三处 recipe-only 漂移：planning-direction-review/chapter-plan-execution-card/continuity-quality-review）。题材信息在交付层不再结构性退场。
- **WP3 护栏 JS 后继**：新建 `scripts/test-guardrails.mjs`——G1 词表双源 deepEqual（plugin/client/project-wizard-data.js ≡ config/genre-packs.json 30 包）+ G2 25 资产 manifest≡matrix 槽集合 + SLOT_REGISTRY 注册校验；修正 AGENTS.md/README.md/docs/variables.md「向导与组装器消费 genre-packs」失实表述。
- **WP4 模型身份守卫与留痕**：`plugin/dsh-novelos-viewer/src/index.ts` modelRoleWarnings()（roleReviewer 留空=防共谋失效强 WARN）；19 个回执 schema reviewer_profile 补模型身份格式 description。
- **WP5 状态机写门**（子代理 57dbb38c）：`db/migrations/019_state_machine_links.sql`（chapters.review_id FK）+ `src/gate/state-machine.ts` commitReview/lockAsset（封跳审/错绑，旧 locked 翻 superseded）/acceptChapter（review_id 机器痕迹；force 仅 hash 未变幂等重放）+ write-tools.ts 注册三工具 + SKILL 裸 SQL 段退役改写；test/state-machine.test.ts 19 例。
- **WP6 R4 数字门**（子代理 1f74f63e）：见 :23 DONE 条目。
- **WP7 回执 schema 同步**：catalog prose-quality-review schema severity 补 strength + code/defer_to_downstream/accepted_risk/accepted_by 四字段，对齐 config 权威版。
- **WP8 口径修正**：power_currency 调和规则、continuity 提取审查口径对齐配方矩阵、craft 卡付费平台适配 §0、sql-reference upsert 模板、create-project E11a WARN→FAIL（genre_profile=null 漏带将静默丢 taboos 防火墙）。
- 遗留 TODO：:24 连续性账本直写通道缺口（候选晋升无门工具覆盖）；生产库 019 迁移待用户择机执行（仓库不手工动生产库）。

## R5 · 知识吸收与对抗审查体系(整合版 v2 已立,待批准执行)

- 指导计划:`tasks/R5-knowledge-absorption.md`(**v2 整合版**——五方向规划 `tasks/r5-plans/d{1-5}-*.plan.md` + 五红方对抗审查 `*.redteam.md`(P0×14/P1×31)经主控整合仲裁:12 条跨方向裁决、统一契约注册表(fpr: 编号/code 前缀/留痕位置/版权通道/注入通道矩阵)、U1-U13 裁决点、修订轮次 R0-R6)。执行条目开跑后在此记账。

### R5 执行记账(R0 轮)

- [x] `DONE` 计划基线固定:`b753a44`(v2 整合版+5 方向计划+5 红方报告入库);`.gitignore` 补 `data/knowledge|canary|stylecorp/`(裁-5 版权隔离)。**验证:git status 干净,14 文件入库**
- [x] `DONE` R0 知识导入:`scripts/novelos-import-knowledge.mjs`(23 张 kb 表逐一处置:16 导+7 不导记理由;biz_* 42 张显式排除)+ `data/knowledge/*.json` ×16 + `data/canary/tags.json`。**验证:`--all` 成功;`--verify` 运行时对账全绿;幂等 diff 空;techniques 1310 实数(裁-6 原始 BETWEEN 口径);dup_key 聚簇抽查 3 组 ✓;83 条源库坏 JSON 保真+_parse_error 标记**;执行偏差已回写 d3 计划顶部
- [x] `DONE` R0 金丝雀选样:22 篇全文级落 `data/canary/g{1,2,3}/`(S18+甜虐 B 级补 2+奇幻补 2;tiebreaker 可复现;正文自 source_url 压缩块程序化解压,329,300 字 vs 库 347,436 ratio 0.948)+ `_meta/selection.json` + **U1 包** `tasks/r5-plans/u1-canary-package.md`(覆盖 8/13 轴、缺口 5 轴如实声明、甜虐 B 级偏离声明、U13 男频缺失登记)。**验证:JSON.parse 通过;头尾抽查无截断;MySQL 全程只读**
- [x] `DONE` R0 机器校验:`scripts/novelos-prose-fingerprint.mjs`(43 规则注册表 fpr: 主键,screen 12/measure 31,L07b=measure/B02 增设,对话过滤栈式引号配对+叙述层分母,advisory 三指标)+ `scripts/novelos-canary.mjs`(--save 基线/--compare tier 分层 exit 1 仅拦 screen/语料指纹校验)+ `scripts/test-prose-fingerprint.mjs`。**验证:49 用例全绿;save→compare PASS→篡改语料 exit 1→漂移 exit 2 全链验证;AI 味文本冒烟 10 条 screen 命中坐标可回指**
- [x] `DONE` R0 基线测量(主控收口):`docs/knowledge/canary-baseline.json|.md`。**核心发现:screen 零容忍语义仅对 L06/L11/P02 成立;L03 破折号 0.92/千字、L02 0.14/千字等 7 条规则在人类小说叙述层有命中;L07b 直发 screen 将 8 误报(红方 F4 预判命中);spread>5 共 9 条标「仅 direction 佐证」**;层级重校方案 A/B/C 已入 U1 包呈报
- [x] `DONE` R1 语言层(`ceec226` + G5 收口 `8badbba`):prose-revision 注册前置包(composer +1 键/manifest 新建/recipes 条目,guardrails G2b 全等校验过)+ fingerprint 卡全文重写(FP↔fpr 映射 21 行/零容忍 3·阈值 7·观察期 2 与 U1 方案 A 一致/不作为表 12 行/逐特征豁免/RT-1..6)+ prose-revision 双模式(编号白名单+T×Canon 用例组 U1-U4)+ rubric 增补(message 头部 `[fpr:x]` 编号,组装实测闭环)+ 盲测夹具编备。**G5 异构红方盲测(`r1-g5-redteam.md`):A 组 screen 39→18(−54%),语义项主类全清;B 组人类段 3/3 零改动 diff 全空;P0×0,P1×2 已修(口径差注记),P2 随批 3 项已修;四命令全绿(guardrails 245/compose 19/fingerprint 49/canary PASS)**。登记待办:F-5 词表扩充/F-6 L01b·L10 正则扩项(→校准批次,动 rule_table 须重跑基线)/F-8 code 透传(→schema 合并轮)/F-9 注入体积入 M5
- [x] `DONE` R2 机器校验(`7508d65`):`scripts/novelos-verify-review-evidence.mjs`(G2 三路 FATAL:no_hit/missing/hash_mismatch;ADVISORY:空 findings+approved/weak<8 字/多处命中,--strict 升级;contentHash 复用 composer;F8 相关性边界声明)+测试 15 例全绿+接线三处增句不删句(AGENTS.md:70-71/novel-writing:28-29/novel-review:24)+deny 率首测 **43.5%**(screen 候选 23,confirm 13/deny 10,L11 7/9 为主;合成回执 verify PASS 自证+no_hit 实例 exit 1;标非真实折扣未落库)+`docs/knowledge/metrics.md` M1-M6 建档。**验证:guardrails 245/compose 19/fingerprint 49/canary PASS,rule_table_hash 未动零回归**。发现:R1-G5 报告 P 层行与其留存 JSON 不符(以机器可复现产物为准,记 R2 登记)
- [x] `DONE` R3 写作层知识(`bdc3f01`):蒸馏首批 262 条→**112 entries**(对话 65→39/开篇 46→30/节奏 151→43;dup_key 聚簇合并、orig_ids 并集对账零遗漏、零书名入正文、零例文引用)+`config/knowledge/distilled.{dialogue,opening,pacing}.json`(placement=slot+card_module_md ≤2560B)+composer `knowledge:` 槽(场景词检索 top-5×2/单条 512B/槽 4096B/白名单渲染含溯源标记/惰性读取缺文件静默跳过/`--without-slot` 入日志)+`config/knowledge/scene-maps.json`(15 行转换,映射率 20.1% 符合首批范围预期,不接线)+prose-blindtest 卡/manifest/ASSET_DIRS/recipes(裁-3:slots=[subject],指纹卡走 craft_refs)+卡面落盘(scene-pacing/accessibility 追加知识模块节+新卡 dialogue-techniques 含 metadata;chapter-draft manifest/recipes 增 knowledge:techniques+craft_refs,G2b 全等过)+guardrails DYNAMIC_PREFIXES+KG1(域文件 schema 校验,不读 data/)。**验证:compose 25(19+6 新)/guardrails 271/render 48/fingerprint 49/verify 15/canary PASS;冒烟(/tmp 副本库,生产库零写入):槽 3719B≤4096、8 条 kg 条目、--without-slot 后槽 0 次、blindtest exit 0**。待 R6:盲测「技巧名词不渗入正文」实证;U4 预算数值已入 metrics
- [x] `DONE` R4 规划层参照(`a22e086` 首批 + `7f7aa5b` 第二批):**八级规划参照全覆盖**——direction(reference-book-appeal 2256B)/world(reference-world-settings 2464B)/architecture(2208B)/strategy(2438B)/character(2375B)/story_arc(2129B)/volume_outline(2226B)/chapter_plan(2318B),modules when 路由(`setup.genre_profile non_empty`)零 composer 代码,非 Canon 信封+词表红线句+KG2 三重机检(296 测试,含词表键位形态检查),审查侧物理隔离实查(review 目录无 reference 文件)。**验证:guardrails 296/compose 28/canary PASS;路由双向实测(命中/不命中)+index.jsonl modules 留痕**。待办:R4 后续批次(其余表源:book_summaries 深挖/plot 扩展)视 R6 演练反馈再定
- [ ] `IN PROGRESS` R5 签名链(**prepare-only**——schema v3 草案/020 SQL/personas 试点选样与转换脚本/融合 prompt 增补全部就位,**生产库写与迁移执行等 U5/U6/U7 用户裁决**)
- [ ] `TODO` R5 签名链(migration 020/schema v3/personas 试点,前置 U5/U6/U7);R6 全链路演练(前置 U11/U-dirs,裁-10 隔离流程);校准批次(F-5/F-6 规则表扩项+F-8 code 透传)

## 插件退役裁决记录（2026-08-27 之后）

- `plugin/` 整体移除（用户裁决：不再使用 DSH 插件）——`dsh-novelos-viewer` / `dsh-novelos` 插件、defineTool 写门、viewer 面板、wizard 三件套全部退役删除。
- 写库口径改为：主控 agent 经 node:sqlite 事务直写，SQL 模板唯一来源 = `.agents/skills/novel-project/sql-reference.md`（原「已退役」写模板重新启用为执行模板）；机器校验改为落库前对照 `config/schemas/*.json` 自查。
- 文档同步：README.md / AGENTS.md / `.agents/skills/` / `docs/` 全量去插件口径；`scripts/test-guardrails.mjs` G1 改为 genre-packs.json 单源自洽校验（原 wizard-data.js 双源镜像已随插件删除）。
- 遗留 TODO 更新：:24 连续性账本直写通道缺口随插件退役自然闭合（直写 SQL 即通道）；生产库 019 迁移仍待用户择机执行（仓库不手工动生产库）。

## 投影恢复裁决记录（2026-08-27 之后 · 用户指令：「将项目之前投影功能在加回来」）

- 恢复 Markdown 投影渲染器（此前随「视图链退役」删除的 `novelos_render_projection.py` + 投影测试，见 2026-08-24 重组裁决记录）——零 Python 纪律下 JS 移植为 `scripts/novelos-render-projection.mjs`（node:sqlite 只读直连 + node:crypto SHA-256，零依赖；py 版原文取自已删除提交 `aeafdb9^` 的 git 历史）。
- 语义对齐 py 版（`90e172f` 裸 sqlite3 重写版）：README / 创作约束（作者签名 + 本书创作灵魂）/ 规划（locked 资产；人物契约按「## 人物档案」拆 `人物契约/` 目录）/ 大纲（卷纲 + 章纲）/ 正文（accepted）/ 人物 / 世界 / 连续性（六账本 + 人物状态注册表）/ manifest.json；「渲染—校验—原子替换」流程原样恢复（临时目录写入 → 原子 rename；manifest 逐文件 SHA-256 可 `--verify` 复核；目标目录归属校验防覆盖其他项目）。
- 移植修复 py 版真实 bug：章纲卷号解析带 `volume:` 前缀查裸 id 永远落第一卷（≥2 卷必现错卷），JS 版剥前缀按真实卷号渲染。
- 新增 `scripts/test-render-projection.mjs`：py 版 5 个拆分用例移植 + 端到端集成（临时库最小 schema → 渲染 25 文件 → manifest 校验 → 确定性 / 篡改检出 / 归属保护 / 残缺契约单文件兜底）**48/48 PASS**；生产库真实项目渲染 + `--verify` 实测通过（10 文件）。
- 口径联动：README.md（渲染器行 / 路线图 / 退役清单撤销「md 投影渲染器」条目 / 目录结构加 novels/ 行 /「用户展示（项目投影）」节 / 验证口径 +③）、AGENTS.md（分层 UI 行 / 读路径 /「单渲染器 = md 投影」约束）、docs/architecture.md 与 docs/flows.md（「投影已退役不要重建」表述全部回改为单渲染器 = md 投影；viewer 面板与 HTML 渲染器仍退役，不要重建）。
- 退役清单现状：`plugin/`（DSH 插件、defineTool 写门、viewer 面板、wizard 三件套）仍退役；md 投影渲染器已恢复为 JS 实现（README「已退役清单」尾部已注明）。`novels/` 输出目录本地忽略（.gitignore 已含）。
