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
- [ ] `TODO` R4 · validate_* 七件资产校验器机器门语义 JS 化（world/book_soul/volume_outline/architecture 等）。当前过渡口径：catalog prompt 与 schemas description 已改为「对照规则自查（机器门待 R4 JS 化）」；在 R4 落地前这些门仅靠 agent 自查，无机器强制
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
