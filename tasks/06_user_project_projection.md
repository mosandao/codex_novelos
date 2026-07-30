# Task 06：用户项目文件夹投影

## 状态

`DONE`

## 目标

为每个小说项目生成用户可直接浏览、搜索和交付的 Markdown 文件夹。SQLite 继续作为唯一权威数据源；展示目录是可删除、可重建、只读语义的派生投影，不引入 HTML UI，也不建立第二套业务状态。

## 决策

- 当前展示入口采用项目文件夹，不开发 HTML UI、账号体系或本地 Web 服务。
- 所有展示内容通过统一 `novelos` MCP 读取和生成；Main Agent、Skill 与临时 Agent 不直接读取 SQLite，也不自行拼装权威快照。
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

空分类可以保留索引说明，但不得生成虚构业务内容。只有 `locked` 规划资产和 `accepted` 正文进入默认用户视图；候选、失效、被替代内容只能在显式诊断模式下展示。

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
- 不把 SQLite 路径、内部 Trace、Review 详情或非用户内容写入展示文件。

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

- HTML、前端框架、HTTP Server 和实时预览。
- Markdown 与 SQLite 双向同步。
- 从展示目录接受正文、锁定规划或晋升连续性。
- 在展示目录保存 Agent Prompt、Review Receipt、Trace 或内部 JSON 控制信封。
- 替代 SQLite 备份与灾备 JSONL 导出。

## 验收标准

- [x] 一个包含完整规划链、两卷正文、人物/世界实体和连续性账本的项目可生成目标目录。
- [x] 默认投影不包含 `candidate`、`stale`、`superseded` 规划或非 `accepted` 正文。
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

- 实现了 `mcp/novelos/src/novelos_mcp/projection.py` (`ProjectionEngine` 与相关清洗、渲染、原子替换和安全检查逻辑)。
- 在 `service.py` 中实现了 `get_projection_snapshot` (只读事务并带版本漂移防御) 与 `render_project_projection`。
- 在 `server.py` 中注册了 `projection.get_snapshot` 和 `projection.render_project_folder` 两个 MCP 工具。
- 创建了 `mcp/novelos/tests/test_projection.py` 包含 6 个单元测试，覆盖安全防护、过滤规则、确定性渲染与原子重构。
- 更新了 `test_protocol.py` 与 `test_runner_protocol.py` 工具清单与数量断言 (67 个工具)。
- 验证根 unittest (48/48) 与 MCP unittest (108/108) 全部 100% 通过。
