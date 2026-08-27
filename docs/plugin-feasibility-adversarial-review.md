# NovelOS × DSH 插件化提案 · 对抗审查报告
> ⚠️ **历史档案（插件时代，仅考古参考，不再更新）**：本文描述的对象（DSH 插件 / defineTool 写门 / viewer 面板）已随 `plugin/` 移除退役（2026-08-27）。当前写库口径见 `README.md` 与 `AGENTS.md`。

> 审查对象：《NovelOS 改造为 dsh-oil-creator 形式 hybrid 插件》可行性初评。
> 方法：三路独立只读红队子代理（技术可行性 / 架构价值 / 安全治理）+ 主控本地实证交叉印证。
> 结论先行：**初评「可行」降级为「有条件可行，按原文不批」**。三路独立收敛于同一裁决，且各自挖出初评未覆盖的硬伤。

---

## 一、三路裁决汇总

| # | 初评论点 | 技术路 | 架构路 | 安全路 | 终裁 |
|---|---|---|---|---|---|
| 1 | Node 工具薄封装 Python 子进程 | **"薄"不成立**（编码/退出码/契约全要建） | — | F3 路径参数 argv 工具化 | 有条件成立，前置工程量被低估 |
| 2 | 向导迁入面板"反而变好"、"改造量最小" | **改造量最小不成立**（roster 磁盘工件循环断链） | YAGNI 成立：tasks 全账本零 UI 痛点记录 | F5 postMessage 桥 targetOrigin "*" | 有条件成立 |
| 3 | 阶段从 DB 推导比扫文件夹更可靠 | schema 支持但**库不在场**（data/ 不存在、无迁移应用脚本） | 违反「生产路径接通才 DONE」纪律 | — | 有条件成立 |
| 4 | dev 注入器可支撑 overlay/settings 卡/侧栏替换 | **不成立**（scaffold 只产底座+占位 div；侧栏主区替换根本不在 KNOWN_SLOTS，仅 sidebar.footer.action） | 参照物检索不到公开索引 | — | 不成立（需 spike 验证） |
| 5 | 数据面双通道分裂风险 | 当前实为**单通道**（mcp-novelos-sqlite 注册实际不存在=文档漂移）；真洞是 MCP 无校验门/hash/审计 | 双指令源成立：AGENTS.md 与 systemPrompt 无仲裁机制，仓内已有文档漂移现行犯（architecture.md:33 v2 vs AGENTS.md:73 v3） | F1 execute_sql 无过滤任意 SQL 实锤 | 有条件成立 |

## 二、关键证据（文件路径+行号）

### 技术
- `scripts/run_sqlite_mcp.cmd:8` 优先 `.venv`（Python 3.10.10）；实测该解释器管道输出编码=**cp936**（chcp 65001 有欺骗性），Node 按 UTF-8 解码→中文全乱码。全部 `scripts/*.py` **零处** PYTHONIOENCODING/reconfigure。
- FAIL/WARN 走 stdout 非 stderr（`scripts/novelos_create_project.py:746-751`）；退出码 1 歧义：校验门拒绝(:751/:764/:809/:820)与未捕获 traceback(:854)同码，无法区分业务拒绝与崩溃；PATH python 为 **3.15.0a7 alpha**——pythonPath 设置卡必须白名单。
- 无 WAL/busy_timeout pragma（db/+scripts/ 零命中），BEGIN IMMEDIATE(:457,:597)+默认 5s busy 超时；`--payload` 是文件路径参数(:712,:737)，host 须先写无 BOM 临时文件。
- `ui/kernel-roster.js` 是磁盘工件循环（由 `novelos_export_kernel_roster.py:82-89` 覆写），入 bundle 即构建期常量→每次建核即陈旧；Python 靠字符串切片读同一 `project-wizard-data.js` 作词表权威(`novelos_create_project.py:63,:95-97`)，改 TS 即断源。
- 注入器：`@dsh-external/dsh-super-injector/lib/index.js:2102` KNOWN_SLOTS 含 settings.plugin.item/shell.overlay 但 **scaffold 四形态只产出底座+conversation.view 占位**（SCAFFOLD_UI_CLIENT :348-380），无设置卡模板无 overlay 示例。

### 架构
- `documentation/architecture.md:7` 与 `tasks/06_user_project_projection.md:97` 明文将 Web 前端列为非目标/设计原则——插件化是推翻自家成文决策且未举证。
- 本工作区从未跑通生产创建链：data/ 目录不存在 + kernel-roster 空 → 开发 DB 驱动 UI 直接触发 AGENTS.md DONE 纪律红线。
- 初评漏掉的欠账：DEFERRED 的 70-case 质量实验（`tasks/experiments/agent_quality/deferral.json`）是有记录的真实优先级更高项。

### 安全
- F1 高危：`mcp/sqlite-mcp/server.py:47` conn.execute(sql) 无过滤（VACUUM INTO 整库拷贝、PRAGMA 关外键均可）；`.codex/config.toml:8-12` 已在 Codex 注册。
- F2 高危：**裁决门是纸面的**——`novelos_create_project.py:823-834` parent_rationale mismatch 只 print 警告即 fall-through 到 persist()(:584-684)；面板自动化后无人执行。
- F3 高危：--emit-payload 任意路径写(:703-707)、--db 任意挂载(:718)、render --output root 不受限(:727)。
- F6 高危：`docs/dsh-compatibility.md:19-39` 正在指导把 MCP 注册进用户 profile=重演 oil 侧栏残留教训；且实测该注册当前不存在（文档超前于现实）。
- F7 高危：DSH web 50876 无鉴权，整库/persona 全文(render_projection :440-514)对本机进程+DNS-rebinding 裸奔。
- F5 中危：wizard.html:356-361 postMessage targetOrigin "*"、无 origin 校验、payload 直注模型上下文(:497-501)。
- F8 中危：锁定/接受无专用脚本，现状靠 agent 手工 SQL——按钮化即新直写路径。

## 三、P0（立项前置，缺一不批）

1. **Phase 0 地基验收**：恢复生产 data/novelos-v2.db + 四命令全绿 + v3 创建链端到端冒烟。库不在场一切免谈。
2. **子进程契约硬化**：解释器白名单（封杀 PATH alpha python）+ PYTHONIOENCODING=utf-8 全链 + 结构化 JSON 结果契约 + 退出码语义表（业务拒绝≠崩溃≠环境错）+ 同库互斥 + 树杀超时。
3. **治理动作落代码**：裁决门 mismatch 从警告改阻断退出（pending_adjudication）；锁定/接受出专用脚本（receipt+blocking=0 前置）。面板自动化前必须先补执行者缺口。
4. **写路径唯一化**：execute_sql 收窄（只读或语句白名单）或加审计触发器；插件工具黑名单成文——永不暴露通用 novelos_sql 工具。
5. **patch 卫生 + 修文档**：修 `docs/dsh-compatibility.md` 用户层注册指引（残留温床）；mcp-novelos-sqlite 条目要么补回要么删声明。
6. **面板安全基线**：Host 校验/CSRF token/postMessage origin 白名单/最小投影（非整库）；路径类参数 client-facing schema 零暴露，host 配置拼装。
7. **Spike 先行**：验证注入器 settings.plugin.item/shell.overlay 实际渲染面 + 侧栏降级方案，再谈克隆 oil 形态。

## 四、P1

- payload schema 补漏：platform_traits maxLength、控制字符/surrogate 拒收（content_hash :91-92 裸崩）。
- kernel-roster 活取机制（host 工具取名册替代构建期常量）；project-wizard-data.js 保唯一词表源（raw 导入）。
- 迁移夹具+空库首跑态设计；测试内存 schema 与 migrations 防漂移。
- AGENTS.md 与插件 systemPrompt 单源生成（消灭双指令源）。
- 新鲜度契约成文（快照制，复用 export_kernel_roster 镜像先例）。
- DEFERRED 70-case 质量实验优先偿还（有记录的真实欠账）。

## 五、总裁决

**按原文不批准立项。** 三路红队独立收敛：这不是一个"改造量最小"的包装活，而是①地基缺失（无生产库）、②执行者缺口（纸面治理门）、③能力未证（注入器 slot 渲染面）、④编码边界未破（cp936 管道默认乱码）四座山。若用户坚持推进，须先过 P0 七项中的第 1、2、3、7 项再重新送审；同样的精力应优先偿还 DEFERRED 70-case 实验这笔已记账的欠账。

> 最大单点风险（技术路原话）：子进程 stdio 编码边界——"终端手工验证正常（控制台 UTF-8）、宿主管道内全乱码（cp936）"是该方案的默认失败模式，不前置解决则插件 demo 完美、实战报废。
