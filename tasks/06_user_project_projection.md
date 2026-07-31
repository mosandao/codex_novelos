# Task 06：用户项目文件夹投影

## 状态

`DONE`

## 目标

为每个小说项目生成用户可直接浏览、搜索和交付的 Markdown 文件夹。SQLite 继续作为唯一权威数据源；展示目录是可删除、可重建、只读语义的派生投影，不引入独立 HTML/Web 应用或第二套业务状态。项目创建可另由受 MCP Apps 宿主约束的嵌入式 `project-wizard.html` 收集约束，但该页面不替代投影。

## 决策

- 当前展示入口采用项目文件夹，不开发独立 HTML/Web 应用、账号体系或本地 Web 服务；项目创建向导是统一 MCP 提供的嵌入式 MCP Apps 资源，不是第二个前端系统。
- 所有展示内容通过统一 `novelos` MCP 读取和生成；主控智能体、Skill 与临时 Agent 不直接读取 SQLite，也不自行拼装权威快照。
- 用户可以在编辑器中打开和复制投影文件，但直接修改 Markdown 不会回写 SQLite。
- 未来若支持导入，必须作为独立的候选、差异审查和权威提交流程设计，不复用本任务的单向投影接口。
- 现有 `scripts/export_novelos_data.py` 是灾备 JSONL 导出，不作为用户阅读功能复用。

## 目标目录

默认输出根目录为仓库忽略的 `novels/`，每个项目使用稳定、经过清理的目录名，并在清单中保存真实 `project_id`：

```text
novels/<项目目录>/
├── README.md
├── manifest.json
├── 规划/
│   ├── 01-故事方向.md
│   ├── 02-故事架构.md
│   ├── 03-全书战略.md
│   ├── 04-人物契约.md
│   ├── 05-世界契约.md
│   └── 06-故事弧.md
├── 大纲/
│   ├── 第01卷-卷纲.md
│   └── 第01卷-章纲.md
├── 正文/
│   └── 第01卷/
│       └── 第001章-章节标题.md
├── 候选/
├── 产出/
│   ├── 规划/
│   ├── 正文/
│   └── 智能体/
├── 档案/
├── 人物/
├── 世界/
└── 连续性/
    ├── 伏笔与叙事承诺.md
    ├── 读者期待.md
    ├── 人物关系.md
    ├── 故事弧状态.md
    ├── 时间线.md
    └── 正文事实.md
```

空分类可以保留索引说明，但不得生成虚构业务内容。`规划/` 只展示 `locked` 规划资产，`正文/` 只展示 `accepted` 正文；`候选/` 保留兼容的候选诊断视图；默认投影额外在 `产出/` 展示候选、草稿、失效、被替代内容以及完成的 Agent 原始输出，并以目录状态隔离，避免误认作当前权威版本。`档案/` 为已锁定规划展示生产、独立审查和锁定凭据的可读溯源。

## 实施范围

### 1. MCP 查询与投影模型

- 增加项目级只读快照查询，返回精确项目版本、资产 ID/版本/Hash、章节 Hash、连续性版本和 Resource refs。
- 长文本继续通过 Resource 读取，不复制到控制信封 JSON。
- 对输出排序、文件命名、缺失资产和 Unicode 名称制定确定性规则。
- 快照生成期间检测版本漂移；混合了两个权威版本时必须失败，不输出部分目录。

### 2. 文件夹生成

- 增加一个 MCP 文件工具，将快照渲染到目标根目录下的临时同级目录。
- 完成全部文件、Hash 清单和校验后，再原子替换该项目的旧投影。
- 目标目录已存在但不属于同一 `project_id` 时拒绝覆盖。
- 拒绝绝对路径逃逸、`..`、符号链接逃逸、控制字符和清理后为空的名称。
- 不把 SQLite 路径、可写控制信封或可用于绕过门禁的内部数据写入展示文件；`档案/` 可展示已锁定规划所需的 Trace、Review findings 与 authority commit 溯源。

### 3. 清单与可验证性

`manifest.json` 至少记录：

- 投影格式版本；
- `project_id`、项目版本和生成时间；
- Authority Snapshot Hash；
- 每个文件的相对路径、SHA-256、来源类型、来源 ID、来源版本和来源 Hash；
- 生成器版本。

同一权威快照的业务文件内容和路径必须完全一致；允许生成时间只存在于清单，不进入 Markdown 正文。

### 4. 用户工作流

- 增加“生成项目文件夹”和“刷新项目文件夹”操作。
- 返回实际输出目录、快照 Hash、文件数和跳过的非权威内容统计。
- README 明确提示：该目录由 NovelOS 生成，直接修改不会更新数据库。
- 删除投影目录不影响 SQLite；重新生成可恢复全部用户视图。

## 非目标

- 独立 HTML/Web 应用、前端框架、HTTP Server 和实时预览；受 MCP Apps 宿主约束的项目创建向导不属于本项非目标。
- Markdown 与 SQLite 双向同步。
- 从展示目录接受正文、锁定规划或晋升连续性。
- 把展示目录作为可写的 Agent Prompt、Review Receipt、Trace 或内部 JSON 控制信封；`产出/` 和 `档案/` 仅为单向可读投影。
- 替代 SQLite 备份与灾备 JSONL 导出。

## 验收标准

- [x] 一个包含完整规划链、两卷正文、人物/世界实体和连续性账本的项目可生成目标目录。
- [x] 默认投影在 `产出/` 完整保留 `candidate`、`stale`、`superseded` 规划、非 `accepted` 正文和完成的 Agent 原始输出；当前权威视图不混入这些内容。
- [x] 连续两次从同一 Authority Snapshot 生成的 Markdown 路径和 Hash 完全一致。
- [x] 生成中发生版本漂移时失败且保留上一份完整投影。
- [x] 路径穿越、符号链接逃逸、项目 ID 冲突和非授权覆盖均被拒绝。
- [x] 删除投影后可从 SQLite 完整重建，且不会修改任何权威表。
- [x] `manifest.json` 能逐文件验证内容 Hash 和来源 Hash。
- [x] 根测试、MCP 测试和 `compileall` 全部通过。

## 验证命令

```bash
PYTHONWARNINGS='error::ResourceWarning' .venv/bin/python -m unittest discover -s tests -v
PYTHONWARNINGS='error::ResourceWarning' PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -v
.venv/bin/python -m compileall -q tests mcp/novelos/src mcp/novelos/tests scripts catalog config
```

## 实施记录

初版（commit `5d9beb5`）交付了 `projection.py`（`ProjectionEngine`）、`service.py` 的 `get_projection_snapshot`/`render_project_projection`、`server.py` 的 `projection.get_snapshot` 与 `projection.render_project_folder` 两个工具，以及 6 个初始单元测试。

经审查发现初版存在验收清单过度勾选与 2 处规格偏离，已在本轮补齐：

- **版本漂移防御（验收标准 4）**：`get_projection_snapshot` 改为在只读连接上显式开启事务，获得快照隔离——并发写无法穿插进读取过程，从结构上保证「混合两个权威版本」不可能发生；新增测试在读取期间注入并发写，断言快照一致且旧投影完整保留。
- **manifest 逐文件校验（验收标准 7）**：新增 `ProjectionEngine.verify_manifest`（及 `projection.verify_manifest` 工具）逐文件重算 SHA-256 并校验来源 Hash；派生/合成文件（README、连续性账本）的 `source_hash` 回退为内容 Hash，保证全部条目可校验；新增篡改检测测试。
- **连续性账本缺口（偏离）**：快照与渲染接入 `timelines`（新增 `时间线.md`）与 `chapter_facts`（`正文事实.md` 不再恒空），连续性目录恢复为规格要求的 6 个文件。
- **跳过统计（偏离）**：`skipped_non_authoritative_stats` 改由 service 层在 SQL 过滤时统计被跳过的 candidate/stale/superseded 规划与 draft/superseded 正文，不再返回占位零值；该统计不参与 `authority_snapshot_hash` 计算，确保非权威内容的增删不破坏确定性。
- **测试覆盖补齐（验收标准 1/2/5/6）**：`test_projection.py` 扩展至 11 个用例，新增两卷正文、stale/superseded/非 accepted 过滤、路径穿越与符号链接逃逸拒绝、删除重建不改权威表（逐表内容指纹对比）等用例。
- `test_protocol.py` 增加 `projection.verify_manifest` 注册断言，`test_runner_protocol.py` 工具总数随后更新为 71。

工具集现为：`projection.get_snapshot`、`projection.render_project_folder`、`projection.verify_manifest`。

后续项目创建与删除扩展（commit `25eb225`）补充了 `project.wizard.render`、
`project.wizard.submit` 和 `project.delete`：

- 向导以 MCP Apps resource `ui://novelos/project-wizard.html` 提供 V2 固定表单；二级方向按一级题材展示 18 个静态 LLM 预生成候选，提交只记录 `metadata.project_setup` 并刷新默认投影。
- 本地 `file://` 直开只能检查页面，不具备 MCP Apps 提交桥；向导不会生成或提交任何规划资产。
- 默认投影扩展为保留所有非权威规划/正文、完成 Agent 输出和已锁定规划的过程档案。
- `project.delete` 需要当前项目版本，拒绝活动 Trace 和 authority commit，只删除 manifest 归属匹配的投影；完成的 Trace/Agent 审计保留并解除项目关联。
