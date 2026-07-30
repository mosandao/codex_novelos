# 07.3：Review Profile 路由

## 状态

`DONE`

## 前置

`02_contract_resource.md` 必须为 `DONE`。

## 目标

解除 Review Agent 对 `prose-quality-review` 的固定绑定，由 MCP 根据精确 `review_profile` 返回允许使用的 Catalog 包。未知 Profile 必须失败关闭。

## 允许修改

- `config/agents.yaml`
- `mcp/novelos/src/novelos_mcp/agent_contracts.py`
- `mcp/novelos/src/novelos_mcp/service.py`
- `mcp/novelos/src/novelos_mcp/server.py`
- `catalog/skills/review/planning-quality-review/**`
- `catalog/skills/review/planning-cross-consistency-review/**`
- `catalog/skills/review/entity-authority-review/**`
- `catalog/skills/review/continuity-quality-review/**`
- `mcp/novelos/tests/test_agent_contracts.py`
- `mcp/novelos/tests/test_protocol.py`
- `mcp/novelos/tests/test_production_catalog.py`
- `mcp/novelos/tests/test_pure_codex_workflow.py`
- `mcp/novelos/tests/test_service.py`
- 本文件的状态和实施记录

## 禁止修改

- 规划资产类型、Agent 数量、Review Receipt 表结构、SQLite Schema 和来源仓库。
- 复用生产者 Prompt 作为审查 Prompt。
- 前缀模糊匹配；路由必须使用精确 Profile 名称。

## 精确配置

在 `config/agents.yaml` 增加顶层 `review_profile_routes`，值固定为非空包名数组：

```yaml
review_profile_routes:
  planning-direction: [planning-quality-review]
  planning-architecture: [planning-quality-review]
  planning-strategy: [planning-quality-review]
  planning-character-contract: [planning-quality-review]
  planning-world-contract: [planning-quality-review]
  planning-story-arc: [planning-quality-review]
  planning-volume-outline: [planning-quality-review]
  planning-chapter-plan: [planning-quality-review]
  planning-character-world-cross-consistency: [planning-cross-consistency-review]
  entity-character: [entity-authority-review]
  entity-world: [entity-authority-review]
  entity-faction: [entity-authority-review]
  entity-rule: [entity-authority-review]
  entity-timeline: [entity-authority-review]
  prose-v1: [prose-quality-review]
  continuity-v1: [continuity-quality-review]
```

同时：

- `review_agent.catalog_package` 改为 `null`。
- `read_only_tools` 与 `review_tools` 增加 `skill_catalog.review_route`。

Review Agent 使用已有 `review_profile` 调用 Route 工具，不改变 `minimum_inputs`。延期的 `agent-quality-blind-comparison` 评测继续使用自身固定 rubric，不纳入生产权威 Profile 路由。

## 新增 Catalog 包

四个包均为 `target-native`、`typed_result`，复制现有 `prose-quality-review` 的输入/输出 Schema 结构，但 Prompt 职责分别限定为规划上游忠实度与内部一致性、人物世界交叉一致性、实体权威来源一致性、连续性候选证据一致性。不得复制来源仓库未授权 Prompt。

## 实施步骤

1. `AgentContractStore` 严格校验 `review_profile_routes`：键和值非空、包名不重复、所有生产权威 Profile 完整覆盖。
2. 增加 `review_packages(profile)`；未知 Profile 抛出 `invalid_review_profile`，返回配置顺序稳定的包名列表。
3. `NovelOSService` 增加 `get_review_catalog_route(profile)`，逐包调用 Catalog `get()`，确认包存在且为 `active`，返回 Profile、包名、package Hash 和 Resource refs。
4. MCP 注册只读工具 `skill_catalog.review_route`。
5. 创建四个目标原生 Review 包；每个具有 metadata、prompt、provenance、input_schema 和 schema。
6. `accept_chapter()` 只接受 `prose-v1`，`promote_reviewed_continuity()` 只接受 `continuity-v1`；现有规划、交叉审查和实体提交继续使用各自已有的精确 Profile 门禁。
7. 测试八类规划、交叉审查、五类实体、正文和连续性的精确映射；测试未知 Profile、缺包、非 active 包、重复包和固定 `catalog_package` 被拒绝。
8. 更新临时工具白名单测试以显式允许只读后缀 `review_route`；生产 Catalog 测试由“全部包等于固定集合”改为“核心包是 active 集合的子集且所有 active 包合法”。
9. 更新纯 Codex 工作流测试：Review Agent 启动后按精确 Profile 解析 Route，再加载返回的 Prompt refs；不改变 Agent 的最小输入字段。

## 停止条件

- 任一路由包不存在或不是 `active`。
- 需要通过猜测 subject 文本选择 Profile。
- 为实现路由新增 Review Agent 或数据库表。

## 验证

```bash
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_agent_contracts.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_protocol.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_production_catalog.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_pure_codex_workflow.py' -v
PYTHONPATH=mcp/novelos/src .venv/bin/python -m unittest discover -s mcp/novelos/tests -p 'test_service.py' -v
git diff --check
```

## 完成证据

- 实际 Profile Route 对应：
  - 8 类规划 (`planning-direction` ... `planning-chapter-plan`) -> `[planning-quality-review]`
  - 交叉审查 (`planning-character-world-cross-consistency`) -> `[planning-cross-consistency-review]`
  - 5 类实体 (`entity-character` ... `entity-timeline`) -> `[entity-authority-review]`
  - 正文 (`prose-v1`) -> `[prose-quality-review]`
  - 连续性 (`continuity-v1`) -> `[continuity-quality-review]`
- 未知 Profile 错误：`NovelOSError: 未知 Review Profile` (代码 `invalid_review_profile`)
- 四个新包 package Hash：
  - `planning-quality-review`: `sha256:f2412056b5418e3eab4aff8d3d42aaefbbd04d4fcec2b816b6654f5b7d379292`
  - `planning-cross-consistency-review`: `sha256:121a847d79aea033fce69c5515b932a7e1383026499df440a321ef7f709e407c`
  - `entity-authority-review`: `sha256:26185fa7a981aedd51afd2a56fd9007a6f1464b8c99d9c5d23c2d2c2179bf73b`
  - `continuity-quality-review`: `sha256:2c5af33dda44b821a1aac6aeb48c6ad87ed8319186d9ed6e20037aca0d302ad3`
- 命令验证全通过。

